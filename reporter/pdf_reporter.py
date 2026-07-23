"""PDF report generator using fpdf2."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scanner.web_scanner import ScanResult
from agents.seo_agent import SEOAnalysis
from agents.action_plan_agent import ActionPlan


class PDFReporter:
    """Generates a professional PDF report."""

    BRAND_COLOR = (0, 82, 204)    # Blue
    DANGER_COLOR = (220, 53, 69)  # Red
    WARN_COLOR = (255, 153, 0)    # Orange
    OK_COLOR = (40, 167, 69)      # Green
    DARK = (30, 30, 30)

    def generate(
        self,
        scan: ScanResult,
        seo: SEOAnalysis,
        plan: ActionPlan,
        output_dir: str = "reports",
    ) -> Path:
        try:
            from fpdf import FPDF, XPos, YPos
        except ImportError:
            raise ImportError("fpdf2 not installed. Run: pip install fpdf2")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain_clean = scan.domain.replace(".", "_").replace(":", "_")
        filename = f"{domain_clean}_{ts}.pdf"
        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Header bar
        pdf.set_fill_color(*self.BRAND_COLOR)
        pdf.rect(0, 0, 210, 25, "F")
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(10, 7)
        pdf.cell(0, 12, "InsightAgent Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Domain + date
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(200, 220, 255)
        pdf.set_xy(10, 17)
        now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        pdf.cell(0, 6, f"{scan.domain}  |  {now}  |  AI: {plan.provider}")

        pdf.ln(15)
        pdf.set_text_color(*self.DARK)

        # Score cards
        self._score_cards(pdf, seo, scan)
        pdf.ln(5)

        # Executive Summary
        self._section_header(pdf, "Executive Summary")
        pdf.set_font("Helvetica", "", 10)
        summary = plan.executive_summary or f"Audit completed for {scan.domain}."
        pdf.multi_cell(0, 5, summary)
        pdf.ln(3)

        if plan.top_priority:
            pdf.set_fill_color(255, 243, 205)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 8, f"  Top Priority: {plan.top_priority[:100]}", fill=True,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(3)

        # Technical Audit
        self._section_header(pdf, "Technical Audit")
        checks = [
            ("SSL Certificate", scan.ssl_valid, f"{scan.ssl_expiry_days} days remaining"),
            ("HTTPS Redirect", scan.has_https_redirect, ""),
            ("Sitemap.xml", scan.has_sitemap, ""),
            ("Robots.txt", scan.has_robots_txt, ""),
            ("Schema Markup", scan.has_schema_markup,
             ", ".join(scan.schema_types[:3]) if scan.schema_types else ""),
            ("Open Graph Tags", bool(scan.og_title), ""),
            ("Canonical Tag", bool(scan.canonical), ""),
        ]
        for label, ok, note in checks:
            icon = "✓" if ok else "✗"
            color = self.OK_COLOR if ok else self.WARN_COLOR
            pdf.set_fill_color(*color)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(8, 6, icon, fill=True, align="C")
            pdf.set_text_color(*self.DARK)
            pdf.set_font("Helvetica", "", 9)
            text = f" {label}"
            if note:
                text += f"  ({note})"
            pdf.cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        # Critical Issues
        if scan.issues:
            self._section_header(pdf, "Critical Issues")
            for issue in scan.issues[:8]:
                self._bullet(pdf, issue, color=self.DANGER_COLOR)
            pdf.ln(2)

        if scan.warnings:
            self._section_header(pdf, "Warnings")
            for warn in scan.warnings[:8]:
                self._bullet(pdf, warn, color=self.WARN_COLOR)
            pdf.ln(2)

        # SEO Details
        self._section_header(pdf, "SEO Analysis")
        meta_items = [
            ("Title", scan.title or "MISSING"),
            ("Meta Description", (scan.meta_description[:100] + "...") if len(scan.meta_description) > 100 else scan.meta_description or "MISSING"),
            ("H1 Tags", ", ".join(scan.h1_tags[:3]) if scan.h1_tags else "MISSING"),
            ("Load Time", f"{scan.load_time_ms}ms"),
            ("Word Count", f"{scan.word_count} words"),
            ("Tech Stack", ", ".join(scan.tech_stack[:5]) if scan.tech_stack else "Unknown"),
        ]
        for label, value in meta_items:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(40, 5, label + ":")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, value)
        pdf.ln(3)

        if seo.keyword_opportunities:
            self._section_header(pdf, "Keyword Opportunities")
            for kw in seo.keyword_opportunities[:5]:
                self._bullet(pdf, kw)
            pdf.ln(2)

        # Action Plan
        pdf.add_page()
        self._section_header(pdf, "Action Plan")

        if plan.week_1_actions:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*self.BRAND_COLOR)
            pdf.cell(0, 7, "Week 1 — Quick Wins", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*self.DARK)
            for item in plan.week_1_actions[:5]:
                self._action_item(pdf, item)

        if plan.month_1_actions:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*self.BRAND_COLOR)
            pdf.cell(0, 7, "Month 1 — Improvements", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*self.DARK)
            for item in plan.month_1_actions[:5]:
                self._action_item(pdf, item)

        if plan.quarter_actions:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*self.BRAND_COLOR)
            pdf.cell(0, 7, "90 Days — Strategic Initiatives", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*self.DARK)
            for item in plan.quarter_actions[:3]:
                self._action_item(pdf, item)

        # Quick win checklist
        if seo.quick_wins:
            pdf.ln(5)
            self._section_header(pdf, "Quick Win Checklist")
            for win in seo.quick_wins[:7]:
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(8, 6, "[ ]")
                pdf.cell(0, 6, win[:100], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Footer
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 10, "Generated by InsightAgent — AI-powered website intelligence", align="C")

        pdf.output(str(output_path))
        return output_path

    def _section_header(self, pdf, title: str) -> None:
        from fpdf import XPos, YPos
        pdf.set_fill_color(*self.BRAND_COLOR)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, f"  {title}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*self.DARK)
        pdf.ln(2)

    def _bullet(self, pdf, text: str, color: tuple = None) -> None:
        from fpdf import XPos, YPos
        c = color or self.DARK
        pdf.set_text_color(*c)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(5, 5, "•")
        pdf.set_text_color(*self.DARK)
        pdf.multi_cell(0, 5, text[:120])

    def _action_item(self, pdf, item) -> None:
        from fpdf import XPos, YPos
        effort_colors = {"low": self.OK_COLOR, "medium": self.WARN_COLOR, "high": self.DANGER_COLOR}
        color = effort_colors.get(item.effort, self.DARK)
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(18, 5, item.effort.upper(), fill=True, align="C")
        pdf.set_text_color(*self.DARK)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(3, 5, "")
        pdf.multi_cell(0, 5, item.action[:110])
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(21, 4, "")
        pdf.cell(0, 4, f"Impact: {item.expected_impact[:80]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*self.DARK)
        pdf.ln(1)

    def _score_cards(self, pdf, seo: SEOAnalysis, scan: ScanResult) -> None:
        from fpdf import XPos, YPos
        cards = [
            ("SEO Score", f"{seo.score}/100", seo.grade),
            ("Load Time", f"{scan.load_time_ms}ms", "FAST" if scan.load_time_ms < 1500 else "SLOW"),
            ("Issues", str(len(scan.issues)), "CRITICAL" if scan.issues else "OK"),
            ("SSL", "VALID" if scan.ssl_valid else "INVALID",
             f"{scan.ssl_expiry_days}d" if scan.ssl_valid else "FIX NOW"),
        ]
        x_start = 10
        card_w = 44
        for i, (label, value, sub) in enumerate(cards):
            x = x_start + i * (card_w + 3)
            score_int = seo.score
            if "Score" in label:
                fill = self.OK_COLOR if score_int >= 70 else self.WARN_COLOR if score_int >= 50 else self.DANGER_COLOR
            elif "Issues" in label:
                fill = self.DANGER_COLOR if scan.issues else self.OK_COLOR
            elif "SSL" in label:
                fill = self.OK_COLOR if scan.ssl_valid else self.DANGER_COLOR
            else:
                fill = self.BRAND_COLOR

            pdf.set_fill_color(*fill)
            pdf.rect(x, pdf.get_y(), card_w, 22, "F")
            pdf.set_text_color(255, 255, 255)
            pdf.set_xy(x, pdf.get_y() + 2)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(card_w, 8, value, align="C")
            pdf.set_xy(x, pdf.get_y() + 1)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(card_w, 5, label, align="C", new_x=XPos.RIGHT if i < 3 else XPos.LMARGIN)
            if i == 3:
                pdf.set_text_color(*self.DARK)
                pdf.ln(10)
