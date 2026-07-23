"""Markdown report generator for InsightAgent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scanner.web_scanner import ScanResult
from agents.seo_agent import SEOAnalysis
from agents.action_plan_agent import ActionPlan


class MarkdownReporter:
    """Generates a comprehensive Markdown report."""

    def generate(
        self,
        scan: ScanResult,
        seo: SEOAnalysis,
        plan: ActionPlan,
        output_dir: str = "reports",
    ) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain_clean = scan.domain.replace(".", "_").replace(":", "_")
        filename = f"{domain_clean}_{ts}.md"
        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        md = self._build_md(scan, seo, plan, ts)
        output_path.write_text(md, encoding="utf-8")
        return output_path

    def _build_md(
        self, scan: ScanResult, seo: SEOAnalysis, plan: ActionPlan, ts: str
    ) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        lines: list[str] = []

        # Header
        lines += [
            f"# InsightAgent Report — {scan.domain}",
            f"**Generated:** {now}  ",
            f"**Target:** {scan.url}  ",
            f"**AI Provider:** {plan.provider}",
            "",
            "---",
            "",
        ]

        # Executive Summary
        lines += [
            "## Executive Summary",
            "",
            plan.executive_summary or f"Audit completed for {scan.domain}.",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| SEO Score | **{seo.score}/100** ({seo.grade}) |",
            f"| Health Score | **{plan.overall_health_score}/100** |",
            f"| Load Time | {scan.load_time_ms}ms |",
            f"| Word Count | {scan.word_count} words |",
            f"| Critical Issues | {len(scan.issues)} |",
            f"| Warnings | {len(scan.warnings)} |",
            "",
        ]

        # Top Priority
        if plan.top_priority:
            lines += [
                "## Top Priority Action",
                "",
                f"> ⚡ **{plan.top_priority}**",
                "",
            ]

        # Technical Audit
        lines += [
            "## Technical Audit",
            "",
            "### Overview",
            "",
            f"| Check | Status |",
            f"|-------|--------|",
            f"| SSL Certificate | {'✅ Valid' if scan.ssl_valid else '❌ Invalid'} ({scan.ssl_expiry_days} days) |",
            f"| HTTPS Redirect | {'✅ Yes' if scan.has_https_redirect else '❌ No'} |",
            f"| Sitemap.xml | {'✅ Found' if scan.has_sitemap else '⚠️ Missing'} |",
            f"| Robots.txt | {'✅ Found' if scan.has_robots_txt else '⚠️ Missing'} |",
            f"| Schema Markup | {'✅ Yes' if scan.has_schema_markup else '⚠️ None'} |",
            f"| Open Graph | {'✅ Yes' if scan.og_title else '⚠️ Missing'} |",
            f"| Canonical Tag | {'✅ Yes' if scan.canonical else '⚠️ Missing'} |",
            "",
        ]

        if scan.tech_stack:
            lines += [
                "### Technology Stack",
                "",
                ", ".join(f"`{t}`" for t in scan.tech_stack),
                "",
            ]

        if scan.issues:
            lines += ["### Critical Issues", ""]
            for issue in scan.issues:
                lines.append(f"- ❌ {issue}")
            lines.append("")

        if scan.warnings:
            lines += ["### Warnings", ""]
            for warning in scan.warnings:
                lines.append(f"- ⚠️ {warning}")
            lines.append("")

        # SEO Analysis
        lines += [
            "## SEO Analysis",
            "",
            f"**Score: {seo.score}/100 — Grade: {seo.grade}**",
            "",
            seo.summary or "",
            "",
        ]

        if scan.title:
            lines += [f"**Title:** {scan.title}  "]
        else:
            lines += ["**Title:** ❌ MISSING  "]

        if scan.meta_description:
            lines += [f"**Meta Description:** {scan.meta_description[:150]}...  "]
        else:
            lines += ["**Meta Description:** ❌ MISSING  "]

        lines += [
            f"**H1 Tags:** {', '.join(scan.h1_tags) if scan.h1_tags else '❌ MISSING'}  ",
            f"**Internal Links:** {scan.internal_links} | **External Links:** {scan.external_links}",
            "",
        ]

        if seo.keyword_opportunities:
            lines += ["### Keyword Opportunities", ""]
            for kw in seo.keyword_opportunities:
                lines.append(f"- 🎯 {kw}")
            lines.append("")

        if seo.content_recommendations:
            lines += ["### Content Recommendations", ""]
            for rec in seo.content_recommendations:
                lines.append(f"- 📝 {rec}")
            lines.append("")

        # Action Plan
        lines += [
            "## Action Plan",
            "",
        ]

        if plan.week_1_actions:
            lines += ["### Week 1 — Quick Wins", ""]
            for item in plan.week_1_actions:
                effort_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(item.effort, "⚪")
                lines.append(
                    f"- {effort_emoji} **{item.action}**  \n"
                    f"  Impact: {item.expected_impact} | Effort: {item.effort}"
                )
            lines.append("")

        if plan.month_1_actions:
            lines += ["### Month 1 — Improvements", ""]
            for item in plan.month_1_actions:
                effort_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(item.effort, "⚪")
                lines.append(
                    f"- {effort_emoji} **{item.action}**  \n"
                    f"  Impact: {item.expected_impact} | Effort: {item.effort}"
                )
            lines.append("")

        if plan.quarter_actions:
            lines += ["### 90 Days — Strategic Initiatives", ""]
            for item in plan.quarter_actions:
                effort_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(item.effort, "⚪")
                lines.append(
                    f"- {effort_emoji} **{item.action}**  \n"
                    f"  Impact: {item.expected_impact} | Effort: {item.effort}"
                )
            lines.append("")

        if seo.quick_wins:
            lines += [
                "## Quick Win Checklist",
                "",
                "Copy this to your task manager:",
                "",
            ]
            for i, win in enumerate(seo.quick_wins, 1):
                lines.append(f"- [ ] {win}")
            lines.append("")

        lines += [
            "---",
            "",
            "*Generated by [InsightAgent](https://github.com/teyfikoz/insight-agent) — "
            "AI-powered website intelligence*",
        ]

        return "\n".join(lines)
