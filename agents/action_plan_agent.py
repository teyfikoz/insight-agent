"""Action Plan Agent — synthesizes all agent outputs into prioritized action plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base_agent import BaseLLMAgent
from .skill_loader import load_skill

_PLAN_SKILL_FALLBACK = (
    "You are a senior business consultant and growth strategist. "
    "Create a concrete, prioritized action plan based on website audit data. "
    "Be specific with timelines and expected outcomes. "
    "Format as a structured report with clear sections."
)


@dataclass
class ActionItem:
    priority: int       # 1=critical, 2=high, 3=medium, 4=low
    timeframe: str      # "7 days", "30 days", "90 days"
    action: str
    expected_impact: str
    effort: str         # "low", "medium", "high"
    roi_estimate: str


@dataclass
class ActionPlan:
    domain: str
    executive_summary: str = ""
    week_1_actions: list[ActionItem] = field(default_factory=list)
    month_1_actions: list[ActionItem] = field(default_factory=list)
    quarter_actions: list[ActionItem] = field(default_factory=list)
    overall_health_score: int = 0
    top_priority: str = ""
    provider: str = "rule-based"


class ActionPlanAgent(BaseLLMAgent):
    """Synthesizes findings from all agents into an executive action plan."""

    def generate_plan(
        self,
        domain: str,
        seo_score: int,
        seo_summary: str,
        seo_quick_wins: list[str],
        technical_issues: list[str],
        warnings: list[str],
        tech_stack: list[str],
        load_time_ms: float,
        word_count: int,
    ) -> ActionPlan:
        plan = ActionPlan(domain=domain)
        plan.overall_health_score = seo_score

        system = load_skill("action_planner", fallback=_PLAN_SKILL_FALLBACK)

        user = f"""Create an executive action plan for {domain}:

SEO Score: {seo_score}/100
SEO Summary: {seo_summary}
Quick Wins Identified: {seo_quick_wins}
Critical Issues: {technical_issues}
Warnings: {warnings}
Technology Stack: {tech_stack}
Page Load Time: {load_time_ms}ms
Content Word Count: {word_count}

Generate:
1. EXECUTIVE SUMMARY (3-4 sentences — current state and biggest opportunity)
2. TOP PRIORITY (single most impactful action)
3. WEEK 1 ACTIONS (3-5 quick wins, each with: action | impact | effort)
4. 30 DAY ACTIONS (3-5 medium-term improvements)
5. 90 DAY ACTIONS (3 strategic initiatives)

Format each action as:
• [ACTION] → Impact: [IMPACT] | Effort: [low/medium/high]
"""

        def _fallback() -> str:
            issues_count = len(technical_issues)
            warns_count = len(warnings)
            lines = [
                "EXECUTIVE SUMMARY",
                f"Website audit of {domain} reveals an SEO score of {seo_score}/100 with "
                f"{issues_count} critical issues and {warns_count} warnings requiring attention. "
                f"Immediate focus on technical SEO fundamentals will yield the fastest improvements.",
                "",
                "TOP PRIORITY",
                technical_issues[0] if technical_issues else "Improve page load speed",
                "",
                "WEEK 1 ACTIONS",
            ]
            for win in (seo_quick_wins or technical_issues)[:5]:
                lines.append(f"• {win} → Impact: High | Effort: low")
            lines += [
                "",
                "30 DAY ACTIONS",
                "• Add JSON-LD schema markup → Impact: Rich snippets in SERPs | Effort: medium",
                "• Create sitemap.xml and submit to Google Search Console → Impact: Indexing | Effort: low",
                "• Optimize images with descriptive alt text → Impact: Accessibility + SEO | Effort: medium",
                "",
                "90 DAY ACTIONS",
                "• Build a content marketing strategy with 2 blog posts/week → Impact: Organic traffic | Effort: high",
                "• Implement Core Web Vitals improvements → Impact: Google rankings | Effort: high",
                "• Build 5-10 backlinks from industry directories → Impact: Domain authority | Effort: high",
            ]
            return "\n".join(lines)

        ai_text = self.generate(system, user, max_tokens=1500, fallback_fn=_fallback)
        plan.provider = self.provider

        # Parse
        plan.executive_summary = self._extract_paragraph(ai_text, "EXECUTIVE SUMMARY")
        plan.top_priority = self._extract_paragraph(ai_text, "TOP PRIORITY", lines=1)
        plan.week_1_actions = self._parse_actions(ai_text, "WEEK 1", "7 days")
        plan.month_1_actions = self._parse_actions(ai_text, "30 DAY", "30 days")
        plan.quarter_actions = self._parse_actions(ai_text, "90 DAY", "90 days")

        return plan

    def _extract_paragraph(self, text: str, section: str, lines: int = 4) -> str:
        result_lines = []
        in_section = False
        for line in text.split("\n"):
            if section.upper() in line.upper() and not in_section:
                in_section = True
                continue
            if in_section:
                if line.strip() and any(
                    kw in line.upper() for kw in
                    ["EXECUTIVE", "TOP PRIORITY", "WEEK 1", "30 DAY", "90 DAY"]
                ):
                    break
                if line.strip():
                    result_lines.append(line.strip())
                if len(result_lines) >= lines:
                    break
        return " ".join(result_lines)

    def _parse_actions(self, text: str, section: str, timeframe: str) -> list[ActionItem]:
        actions = []
        in_section = False
        for line in text.split("\n"):
            if section.upper() in line.upper():
                in_section = True
                continue
            if in_section:
                stripped = line.strip()
                if stripped and any(
                    kw in stripped.upper() for kw in
                    ["EXECUTIVE", "TOP PRIORITY", "WEEK 1", "30 DAY", "90 DAY"]
                ):
                    break
                if stripped.startswith(("•", "-", "*")):
                    clean = stripped.lstrip("•-* ").strip()
                    if not clean:
                        continue

                    # Parse "action → Impact: X | Effort: Y"
                    action_text = clean
                    impact = "Improves site performance"
                    effort = "medium"
                    roi = "Medium-term improvement"

                    if "→" in clean:
                        parts = clean.split("→", 1)
                        action_text = parts[0].strip()
                        meta = parts[1] if len(parts) > 1 else ""
                        if "Impact:" in meta:
                            impact = meta.split("Impact:")[1].split("|")[0].strip()
                        if "Effort:" in meta:
                            effort_raw = meta.split("Effort:")[1].strip().split()[0].lower()
                            effort = effort_raw if effort_raw in ("low", "medium", "high") else "medium"

                    actions.append(ActionItem(
                        priority=len(actions) + 1,
                        timeframe=timeframe,
                        action=action_text,
                        expected_impact=impact,
                        effort=effort,
                        roi_estimate=roi,
                    ))
                    if len(actions) >= 5:
                        break
        return actions
