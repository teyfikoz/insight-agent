"""Web scanner — audits URL for SEO, SSL, performance, and tech stack."""

from __future__ import annotations

import socket
import ssl
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class ScanResult:
    url: str
    domain: str
    status_code: int = 0
    load_time_ms: float = 0.0

    # SSL
    ssl_valid: bool = False
    ssl_expiry_days: int = 0

    # SEO
    title: str = ""
    meta_description: str = ""
    h1_tags: list[str] = field(default_factory=list)
    h2_tags: list[str] = field(default_factory=list)
    canonical: str = ""
    robots_meta: str = ""
    og_title: str = ""
    og_description: str = ""

    # Technical
    has_sitemap: bool = False
    has_robots_txt: bool = False
    server: str = ""
    tech_stack: list[str] = field(default_factory=list)
    has_https_redirect: bool = False

    # Content
    word_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    images_without_alt: int = 0
    broken_links: list[str] = field(default_factory=list)

    # Schema
    has_schema_markup: bool = False
    schema_types: list[str] = field(default_factory=list)

    # Issues found
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class WebScanner:
    """Scans a URL and collects SEO, performance, and technical data."""

    def __init__(self, timeout: int = 15, user_agent: str | None = None):
        self.timeout = timeout
        self.ua = user_agent or "Mozilla/5.0 (compatible; InsightAgent/1.0)"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def scan(self, url: str) -> ScanResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        result = ScanResult(url=url, domain=domain)

        try:
            start = time.time()
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            result.load_time_ms = round((time.time() - start) * 1000, 1)
            result.status_code = resp.status_code
            result.server = resp.headers.get("Server", "")
            result.has_https_redirect = resp.url.startswith("https://")

            if resp.status_code == 200:
                self._parse_html(result, resp.text, url)
                self._check_ssl(result, domain)
                self._check_sitemap(result, url)
                self._check_robots(result, url)
                self._detect_tech(result, resp)
                self._score_issues(result)

        except requests.exceptions.SSLError:
            result.issues.append("SSL certificate error")
        except requests.exceptions.ConnectionError:
            result.issues.append("Cannot connect to server")
        except requests.exceptions.Timeout:
            result.issues.append(f"Timeout after {self.timeout}s")
        except Exception as exc:
            result.issues.append(f"Scan error: {exc}")

        return result

    def _parse_html(self, result: ScanResult, html: str, base_url: str) -> None:
        soup = BeautifulSoup(html, "lxml")

        # Title
        title_tag = soup.find("title")
        result.title = title_tag.get_text(strip=True) if title_tag else ""

        # Meta
        meta_desc = soup.find("meta", attrs={"name": "description"})
        result.meta_description = meta_desc.get("content", "") if meta_desc else ""

        robots_meta = soup.find("meta", attrs={"name": "robots"})
        result.robots_meta = robots_meta.get("content", "") if robots_meta else ""

        # Canonical
        canonical = soup.find("link", attrs={"rel": "canonical"})
        result.canonical = canonical.get("href", "") if canonical else ""

        # OG
        og_title = soup.find("meta", attrs={"property": "og:title"})
        result.og_title = og_title.get("content", "") if og_title else ""
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        result.og_description = og_desc.get("content", "") if og_desc else ""

        # Headings
        result.h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
        result.h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")][:5]

        # Word count
        body = soup.find("body")
        if body:
            text = body.get_text(separator=" ", strip=True)
            result.word_count = len(text.split())

        # Links
        parsed_base = urlparse(base_url)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#") or not href:
                continue
            full = urljoin(base_url, href)
            fp = urlparse(full)
            if fp.netloc == parsed_base.netloc:
                result.internal_links += 1
            else:
                result.external_links += 1

        # Images without alt
        result.images_without_alt = sum(
            1 for img in soup.find_all("img")
            if not img.get("alt")
        )

        # Schema markup
        schemas = soup.find_all("script", attrs={"type": "application/ld+json"})
        result.has_schema_markup = len(schemas) > 0
        import json
        for s in schemas:
            try:
                data = json.loads(s.string or "{}")
                t = data.get("@type", "")
                if t:
                    result.schema_types.append(t if isinstance(t, str) else str(t))
            except Exception:
                pass

    def _check_ssl(self, result: ScanResult, domain: str) -> None:
        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(
                socket.create_connection((domain, 443), timeout=10),
                server_hostname=domain
            ) as s:
                cert = s.getpeercert()
                import datetime
                expiry_str = cert.get("notAfter", "")
                if expiry_str:
                    expiry = datetime.datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                    result.ssl_expiry_days = (expiry - datetime.datetime.utcnow()).days
                result.ssl_valid = result.ssl_expiry_days > 0
        except Exception:
            result.ssl_valid = False

    def _check_sitemap(self, result: ScanResult, base_url: str) -> None:
        parsed = urlparse(base_url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        try:
            r = self.session.head(sitemap_url, timeout=8)
            result.has_sitemap = r.status_code == 200
        except Exception:
            result.has_sitemap = False

    def _check_robots(self, result: ScanResult, base_url: str) -> None:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            r = self.session.head(robots_url, timeout=8)
            result.has_robots_txt = r.status_code == 200
        except Exception:
            result.has_robots_txt = False

    def _detect_tech(self, result: ScanResult, resp: requests.Response) -> None:
        tech = []
        headers = {k.lower(): v for k, v in resp.headers.items()}

        if "x-powered-by" in headers:
            tech.append(headers["x-powered-by"])
        if "x-generator" in headers:
            tech.append(headers["x-generator"])

        body = resp.text[:5000].lower()
        checks = {
            "Next.js": "next.js" in body or "_next/" in body,
            "React": "react" in body,
            "WordPress": "wp-content" in body,
            "Shopify": "shopify.com" in body,
            "Wix": "wixstatic.com" in body,
            "Tailwind CSS": "tailwind" in body,
            "Bootstrap": "bootstrap" in body,
            "Vue.js": "vue.js" in body or "v-bind" in body,
            "Angular": "ng-app" in body or "angular" in body,
            "Stripe": "stripe.com" in body,
        }
        for name, detected in checks.items():
            if detected:
                tech.append(name)

        if "cf-ray" in headers:
            tech.append("Cloudflare")
        if headers.get("server", "").lower().startswith("nginx"):
            tech.append("Nginx")
        if headers.get("server", "").lower().startswith("apache"):
            tech.append("Apache")

        result.tech_stack = list(dict.fromkeys(tech))  # deduplicate

    def _score_issues(self, result: ScanResult) -> None:
        if not result.title:
            result.issues.append("Missing <title> tag")
        elif len(result.title) < 30:
            result.warnings.append(f"Title too short ({len(result.title)} chars, recommend 50-60)")
        elif len(result.title) > 65:
            result.warnings.append(f"Title too long ({len(result.title)} chars, recommend <60)")

        if not result.meta_description:
            result.issues.append("Missing meta description")
        elif len(result.meta_description) < 100:
            result.warnings.append("Meta description too short (recommend 150-160 chars)")
        elif len(result.meta_description) > 165:
            result.warnings.append("Meta description too long (may be truncated in SERPs)")

        if not result.h1_tags:
            result.issues.append("No H1 tag found")
        elif len(result.h1_tags) > 1:
            result.warnings.append(f"Multiple H1 tags found ({len(result.h1_tags)})")

        if not result.canonical:
            result.warnings.append("No canonical URL tag")

        if not result.ssl_valid:
            result.issues.append("SSL certificate invalid or expired")
        elif result.ssl_expiry_days < 30:
            result.warnings.append(f"SSL expiring in {result.ssl_expiry_days} days")

        if not result.has_sitemap:
            result.warnings.append("No sitemap.xml found")

        if not result.has_robots_txt:
            result.warnings.append("No robots.txt found")

        if result.images_without_alt > 0:
            result.warnings.append(f"{result.images_without_alt} images missing alt text")

        if result.load_time_ms > 3000:
            result.issues.append(f"Slow page load: {result.load_time_ms}ms (target <3000ms)")
        elif result.load_time_ms > 1500:
            result.warnings.append(f"Page load could be faster: {result.load_time_ms}ms")

        if not result.has_schema_markup:
            result.warnings.append("No JSON-LD schema markup found")

        if result.word_count < 300:
            result.warnings.append(f"Low word count ({result.word_count} words, recommend 500+)")

        if not result.og_title:
            result.warnings.append("No Open Graph title (affects social sharing)")
