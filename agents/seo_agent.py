"""SEO Agent — analyzes scan results and generates SEO action plan."""

from __future__ import annotations

from dataclasses import dataclass, field

from .base_agent import BaseLLMAgent
from .skill_loader import load_skill
from scanner.web_scanner import ScanResult

_SEO_SKILL_FALLBACK = (
    "You are an expert SEO consultant. Analyze the website data and provide "
    "actionable, specific recommendations. Be concise and practical. "
    "Format output as plain text with sections."
)


@dataclass
class SEOAnalysis:
    score: int = 0                   # 0-100
    grade: str = "F"
    summary: str = ""
    quick_wins: list[str] = field(default_factory=list)
    keyword_opportunities: list[str] = field(default_factory=list)
    content_recommendations: list[str] = field(default_factory=list)
    technical_fixes: list[str] = field(default_factory=list)
    provider: str = "rule-based"


class SEOAgent(BaseLLMAgent):
    """Analyzes a ScanResult and produces SEO recommendations."""

    def analyze(self, scan: ScanResult, target_keywords: list[str] | None = None) -> SEOAnalysis:
        analysis = SEOAnalysis()
        analysis.score = self._compute_score(scan)
        analysis.grade = self._grade(analysis.score)
        analysis.technical_fixes = list(scan.issues + scan.warnings)

        system = load_skill("seo_auditor", fallback=_SEO_SKILL_FALLBACK)

        keywords_str = ", ".join(target_keywords) if target_keywords else "not specified"
        user = f"""Website SEO Audit Data for {scan.domain}:

URL: {scan.url}
Title: {scan.title or 'MISSING'}
Meta Description: {scan.meta_description or 'MISSING'}
H1 Tags: {scan.h1_tags or 'NONE'}
H2 Tags (first 5): {scan.h2_tags}
Canonical: {scan.canonical or 'MISSING'}
Word Count: {scan.word_count}
SSL Valid: {scan.ssl_valid} ({scan.ssl_expiry_days} days)
Has Sitemap: {scan.has_sitemap}
Has Robots.txt: {scan.has_robots_txt}
Schema Markup: {scan.has_schema_markup} — types: {scan.schema_types}
Open Graph Title: {scan.og_title or 'MISSING'}
Internal Links: {scan.internal_links}
External Links: {scan.external_links}
Images Missing Alt: {scan.images_without_alt}
Load Time: {scan.load_time_ms}ms
Tech Stack: {scan.tech_stack}
SEO Score: {analysis.score}/100
Target Keywords: {keywords_str}

Issues Found: {scan.issues}
Warnings: {scan.warnings}

Provide:
1. SUMMARY (2-3 sentences)
2. TOP 5 QUICK WINS (specific actions, fastest impact)
3. KEYWORD OPPORTUNITIES (3-5 keyword ideas based on the site)
4. CONTENT RECOMMENDATIONS (3 specific content improvements)
"""

        def _rule_based_fallback() -> str:
            lines = [f"SEO Score: {analysis.score}/100 — Grade: {analysis.grade}"]
            lines.append("\nSUMMARY")
            lines.append(f"Found {len(scan.issues)} critical issues and {len(scan.warnings)} warnings.")

            lines.append("\nTOP QUICK WINS")
            for issue in (scan.issues + scan.warnings)[:5]:
                lines.append(f"• Fix: {issue}")

            lines.append("\nKEYWORD OPPORTUNITIES")
            lines.append("• Expand page content with long-tail keywords")
            lines.append("• Add FAQ section targeting question-based searches")
            lines.append("• Create blog posts targeting niche topics")

            lines.append("\nCONTENT RECOMMENDATIONS")
            lines.append("• Increase word count to 500+ words per page")
            lines.append("• Add structured data markup for rich snippets")
            lines.append("• Optimize images with descriptive alt text")

            return "\n".join(lines)

        ai_text = self.generate(system, user, max_tokens=1200, fallback_fn=_rule_based_fallback)
        analysis.provider = self.provider

        # Parse AI response into structured fields
        analysis.summary = self._extract_section(ai_text, "SUMMARY", 3)
        analysis.quick_wins = self._extract_bullets(ai_text, "QUICK WINS", 5)
        analysis.keyword_opportunities = self._extract_bullets(ai_text, "KEYWORD", 5)
        analysis.content_recommendations = self._extract_bullets(ai_text, "CONTENT", 4)

        if not analysis.summary:
            analysis.summary = ai_text[:300]

        return analysis

    def _compute_score(self, scan: ScanResult) -> int:
        score = 100
        deductions = {
            "Missing <title> tag": 15,
            "Missing meta description": 12,
            "No H1 tag found": 10,
            "SSL certificate invalid or expired": 20,
        }
        for issue in scan.issues:
            for key, val in deductions.items():
                if key in issue:
                    score -= val

        warnings_deduct = {
            "Title too short": 3, "Title too long": 3,
            "Meta description too short": 3, "Meta description too long": 3,
            "No canonical URL tag": 5,
            "No sitemap.xml found": 4, "No robots.txt found": 3,
            "images missing alt text": 4,
            "Slow page load": 8, "Page load could be faster": 3,
            "No JSON-LD schema markup": 4,
            "Low word count": 5,
            "No Open Graph title": 3,
        }
        for warning in scan.warnings:
            for key, val in warnings_deduct.items():
                if key.lower() in warning.lower():
                    score -= val

        return max(0, min(100, score))

    def _grade(self, score: int) -> str:
        if score >= 90: return "A+"
        if score >= 80: return "A"
        if score >= 70: return "B"
        if score >= 60: return "C"
        if score >= 50: return "D"
        return "F"

    def _extract_section(self, text: str, section: str, max_sentences: int) -> str:
        lines = text.split("\n")
        in_section = False
        result = []
        for line in lines:
            if section.upper() in line.upper():
                in_section = True
                continue
            if in_section:
                if line.strip() and any(
                    s.upper() in line.upper()
                    for s in ["QUICK WIN", "KEYWORD", "CONTENT", "TECHNICAL", "TOP "]
                ):
                    break
                if line.strip():
                    result.append(line.strip())
                if len(result) >= max_sentences:
                    break
        return " ".join(result)

    def _extract_bullets(self, text: str, section: str, limit: int) -> list[str]:
        lines = text.split("\n")
        in_section = False
        results = []
        for line in lines:
            if section.upper() in line.upper():
                in_section = True
                continue
            if in_section:
                stripped = line.strip()
                if stripped.startswith(("•", "-", "*", "1", "2", "3", "4", "5")):
                    clean = stripped.lstrip("•-*0123456789. ").strip()
                    if clean:
                        results.append(clean)
                elif stripped and not any(
                    kw in stripped.upper() for kw in ["SUMMARY", "QUICK WIN", "KEYWORD", "CONTENT", "TECHNICAL"]
                ):
                    pass
                if len(results) >= limit:
                    break
        return results
