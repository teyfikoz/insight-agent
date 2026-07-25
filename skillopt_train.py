"""
SkillOpt Training — InsightAgent SEO & Action Plan Skills
=========================================================

Trains two skills using SkillOpt's ReflACT loop:
  - skills/seo_auditor.md   → SEOAgent system prompt
  - skills/action_planner.md → ActionPlanAgent system prompt

Usage:
    # Quick test — 2 epochs, 3 domains
    .venv/bin/python skillopt_train.py --skill seo_auditor --epochs 2 --quick

    # Full training — 5 epochs, all benchmark domains
    .venv/bin/python skillopt_train.py --skill seo_auditor --epochs 5

    # Train action planner
    .venv/bin/python skillopt_train.py --skill action_planner --epochs 3

    # Nightly sleep mode (harvest+evolve in background)
    .venv/bin/python skillopt_train.py --sleep
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ── Env setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

def _load_env() -> None:
    secrets = Path.home() / ".claude/projects/-Users-teyfikoz/memory/secrets.env"
    for path in (_HERE / ".env", secrets):
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    if k in ("GROQ_API_KEY", "NVIDIA_NIM_API_KEY", "OPENAI_API_KEY"):
                        os.environ.setdefault(k, v.strip().strip('"\''))

_load_env()

# ── Benchmark domains — our own portfolio (we know ground truth) ──────────────
BENCHMARK_DOMAINS = [
    "robocheckin.com",
    "b2blife.com",
    "techsyncanalytica.com",
    "fundpilot.techsyncanalytica.com",
    "kredimplus.com",
]

QUICK_DOMAINS = BENCHMARK_DOMAINS[:2]  # 2 domains for fast iteration

# ── Scoring helpers ───────────────────────────────────────────────────────────

def score_seo_output(seo_text: str, scan_data: dict) -> float:
    """Score SEO analysis output 0.0–1.0.

    Checks:
    - Has SUMMARY section (+0.15)
    - Has TOP 5 QUICK WINS with bullet points (+0.25)
    - Has KEYWORD OPPORTUNITIES (+0.15)
    - Has CONTENT RECOMMENDATIONS (+0.15)
    - Each quick win is specific (contains action verb + metric) (+0.20)
    - No generic advice like "add more content" without specifics (-0.10)
    - References tech stack in recommendations (+0.10)
    """
    score = 0.0
    text_upper = seo_text.upper()

    sections = {
        "SUMMARY": 0.15,
        "QUICK WIN": 0.25,
        "KEYWORD": 0.15,
        "CONTENT": 0.15,
    }
    for section, weight in sections.items():
        if section in text_upper:
            score += weight

    # Check for specific actions (action verbs)
    action_verbs = ["add", "fix", "update", "create", "implement", "configure", "remove", "optimize"]
    bullets = [l.strip() for l in seo_text.split("\n") if l.strip().startswith("•")]
    specific_bullets = sum(
        1 for b in bullets
        if any(v in b.lower() for v in action_verbs) and len(b) > 30
    )
    score += min(0.20, specific_bullets * 0.04)

    # Penalize vague generic advice
    vague = ["add more content", "improve seo", "optimize your site"]
    for v in vague:
        if v in seo_text.lower():
            score -= 0.10

    # Bonus for tech stack awareness
    tech_stack = scan_data.get("tech_stack", [])
    for tech in tech_stack:
        if tech.lower() in seo_text.lower():
            score += 0.10
            break

    return max(0.0, min(1.0, score))


def score_plan_output(plan_text: str, scan_data: dict) -> float:
    """Score action plan output 0.0–1.0."""
    score = 0.0
    text_upper = plan_text.upper()

    sections = {
        "EXECUTIVE SUMMARY": 0.20,
        "TOP PRIORITY": 0.10,
        "WEEK 1": 0.25,
        "30 DAY": 0.20,
        "90 DAY": 0.15,
    }
    for section, weight in sections.items():
        if section in text_upper:
            score += weight

    # Check for effort labels
    effort_labels = ["low", "medium", "high"]
    effort_count = sum(1 for e in effort_labels if f"effort: {e}" in plan_text.lower())
    score += min(0.10, effort_count * 0.03)

    # Check for measurable outcomes (numbers or %)
    import re
    has_metrics = bool(re.search(r"\d+[%\+→]|\d+ (point|position|rank|hour)", plan_text))
    if has_metrics:
        score += 0.10

    return max(0.0, min(1.0, score))


# ── InsightAgent EnvAdapter ───────────────────────────────────────────────────

from skillopt.envs.base import EnvAdapter
from skillopt.model.router import chat_optimizer  # noqa: F811 (overrides local def)


class InsightAgentEnvAdapter(EnvAdapter):
    """SkillOpt EnvAdapter for InsightAgent SEO/Action plan skills."""

    def __init__(self, skill_name: str, domains: list[str]):
        self.skill_name = skill_name  # "seo_auditor" or "action_planner"
        self.domains = domains
        self._scan_cache: dict[str, dict] = {}

    # Required abstract stubs (we call rollout/reflect directly, not via trainer)
    def build_train_env(self, batch_size: int, seed: int, **kw):
        return self.domains

    def build_eval_env(self, env_num: int, split: str, seed: int, **kw):
        return self.domains[:env_num]

    def get_task_types(self) -> list[str]:
        return [self.skill_name]

    def _scan_domain(self, domain: str) -> dict:
        """Run WebScanner and cache results (expensive network call)."""
        if domain in self._scan_cache:
            return self._scan_cache[domain]
        from scanner.web_scanner import WebScanner
        scanner = WebScanner(timeout=15)
        scan = scanner.scan(domain)
        result = {
            "domain": scan.domain,
            "url": scan.url,
            "title": scan.title,
            "meta_description": scan.meta_description,
            "h1_tags": scan.h1_tags,
            "word_count": scan.word_count,
            "ssl_valid": scan.ssl_valid,
            "ssl_expiry_days": scan.ssl_expiry_days,
            "has_sitemap": scan.has_sitemap,
            "has_schema_markup": scan.has_schema_markup,
            "schema_types": scan.schema_types,
            "load_time_ms": scan.load_time_ms,
            "tech_stack": scan.tech_stack,
            "issues": scan.issues,
            "warnings": scan.warnings,
        }
        self._scan_cache[domain] = result
        return result

    def rollout(self, env_manager, skill_content: str, out_dir: str, **kw) -> list[dict]:
        """Run InsightAgent on each domain with the current skill, return scored results."""
        from agents.base_agent import BaseLLMAgent

        class _SkillAgent(BaseLLMAgent):
            pass

        agent = _SkillAgent()
        results = []

        for domain in self.domains:
            try:
                scan_data = self._scan_domain(domain)

                if self.skill_name == "seo_auditor":
                    from agents.seo_agent import SEOAgent
                    seo = SEOAgent()
                    # Override the skill with current candidate
                    seo._skill_override = skill_content
                    # Monkeypatch load_skill for this run
                    import agents.seo_agent as seo_mod
                    _orig = seo_mod.load_skill
                    seo_mod.load_skill = lambda *a, **kw2: skill_content
                    from scanner.web_scanner import ScanResult
                    # Build minimal ScanResult from cached data
                    scan = _dict_to_scanresult(scan_data)
                    analysis = seo.analyze(scan)
                    seo_mod.load_skill = _orig
                    output_text = analysis.summary + "\n" + "\n".join(analysis.quick_wins)
                    soft_score = score_seo_output(output_text, scan_data)

                elif self.skill_name == "action_planner":
                    scan_data2 = scan_data
                    from agents.action_plan_agent import ActionPlanAgent
                    import agents.action_plan_agent as plan_mod
                    _orig = plan_mod.load_skill
                    plan_mod.load_skill = lambda *a, **kw2: skill_content
                    plan_agent = ActionPlanAgent()
                    plan = plan_agent.generate_plan(
                        domain=scan_data2["domain"],
                        seo_score=70,
                        seo_summary="Audit complete.",
                        seo_quick_wins=["Fix meta description", "Add schema markup"],
                        technical_issues=scan_data2["issues"],
                        warnings=scan_data2["warnings"],
                        tech_stack=scan_data2["tech_stack"],
                        load_time_ms=scan_data2["load_time_ms"],
                        word_count=scan_data2["word_count"],
                    )
                    plan_mod.load_skill = _orig
                    output_text = plan.executive_summary
                    soft_score = score_plan_output(output_text, scan_data2)

                else:
                    soft_score = 0.5
                    output_text = ""

                hard_score = 1 if soft_score >= 0.6 else 0
                results.append({
                    "id": domain,
                    "hard": hard_score,
                    "soft": soft_score,
                    "output": output_text[:500],
                    "domain": domain,
                    "scan_data": scan_data,
                })
                print(f"  [{domain}] score={soft_score:.3f} hard={hard_score}")

            except Exception as exc:
                print(f"  [{domain}] ERROR: {exc}")
                results.append({"id": domain, "hard": 0, "soft": 0.0, "output": str(exc)})

        # Save results for reflect stage
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        with open(f"{out_dir}/rollout_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)

        return results

    def reflect(self, results: list[dict], skill_content: str, out_dir: str, **kw) -> list[dict]:
        """Generate skill improvement patches from rollout results."""
        from skillopt.model import chat_optimizer

        failures = [r for r in results if r.get("hard", 0) == 0]
        successes = [r for r in results if r.get("hard", 0) == 1]

        if not failures:
            return []

        failure_summary = "\n".join(
            f"- {r['id']}: score={r.get('soft', 0):.2f}\n  Output snippet: {r.get('output', '')[:200]}"
            for r in failures[:3]
        )
        success_summary = "\n".join(
            f"- {r['id']}: score={r.get('soft', 0):.2f}"
            for r in successes[:3]
        )

        prompt = f"""You are a skill optimizer for an AI SEO analysis agent.

Current skill document:
---
{skill_content}
---

Failed cases (score < 0.6):
{failure_summary}

Successful cases:
{success_summary if success_summary else "None yet"}

The skill is failing because the agent outputs are not specific enough, missing required sections,
or not using action verbs. Suggest 2-3 concrete edits to improve the skill document.

For each edit, output JSON like:
{{"op": "replace", "target": "exact text to replace", "new": "replacement text"}}
or
{{"op": "append", "new": "text to append to end of skill document"}}

Output only valid JSON objects, one per line."""

        try:
            from skillopt.model.router import chat_optimizer as _co
            system_msg = "You are a skill document optimizer. Output only JSON patch objects, one per line."
            response, _ = _co(system=system_msg, user=prompt, max_completion_tokens=800)
            patches = []
            for line in response.split("\n"):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        patch = json.loads(line)
                        patches.append(patch)
                    except json.JSONDecodeError:
                        pass
            return patches
        except Exception as exc:
            print(f"Reflect error: {exc}")
            return []



def _dict_to_scanresult(d: dict):
    """Reconstruct a ScanResult-like object from cached dict."""
    from scanner.web_scanner import ScanResult
    scan = ScanResult.__new__(ScanResult)
    for k, v in d.items():
        setattr(scan, k, v)
    # Ensure list fields
    for field in ("h1_tags", "h2_tags", "tech_stack", "issues", "warnings",
                  "schema_types", "internal_links", "external_links"):
        if not hasattr(scan, field):
            setattr(scan, field, [])
    for field in ("og_title", "canonical"):
        if not hasattr(scan, field):
            setattr(scan, field, "")
    if not hasattr(scan, "images_without_alt"):
        scan.images_without_alt = 0
    return scan


# ── Training loop ─────────────────────────────────────────────────────────────

def train(skill_name: str, epochs: int = 3, quick: bool = False) -> None:
    """Run SkillOpt training loop for a given skill."""
    from skillopt.model import (
        set_optimizer_backend, set_optimizer_deployment,
        set_target_backend, set_target_deployment,
    )

    domains = QUICK_DOMAINS if quick else BENCHMARK_DOMAINS

    groq_key = os.environ.get("GROQ_API_KEY")
    nim_key = os.environ.get("NVIDIA_NIM_API_KEY")

    from skillopt.model import configure_azure_openai

    if nim_key:
        print("Using NVIDIA NIM as optimizer + target")
        set_optimizer_backend("openai_chat")
        set_target_backend("openai_chat")
        configure_azure_openai(
            optimizer_endpoint="https://integrate.api.nvidia.com/v1",
            optimizer_api_key=nim_key,
            optimizer_auth_mode="openai_compatible",
            target_endpoint="https://integrate.api.nvidia.com/v1",
            target_api_key=nim_key,
            target_auth_mode="openai_compatible",
        )
        os.environ.setdefault("OPTIMIZER_MODEL", "meta/llama-3.3-70b-instruct")
        os.environ.setdefault("TARGET_MODEL", "meta/llama-3.3-70b-instruct")
    elif groq_key:
        print("Using Groq (openai_compatible) as optimizer + target")
        set_optimizer_backend("openai_chat")
        set_target_backend("openai_chat")
        configure_azure_openai(
            optimizer_endpoint="https://api.groq.com/openai/v1",
            optimizer_api_key=groq_key,
            optimizer_auth_mode="openai_compatible",
            target_endpoint="https://api.groq.com/openai/v1",
            target_api_key=groq_key,
            target_auth_mode="openai_compatible",
        )
        os.environ.setdefault("OPTIMIZER_MODEL", "llama-3.3-70b-versatile")
        os.environ.setdefault("TARGET_MODEL", "llama-3.3-70b-versatile")
    else:
        print("ERROR: Set GROQ_API_KEY or NVIDIA_NIM_API_KEY in env")
        sys.exit(1)

    # Load seed skill
    skill_path = _HERE / "skills" / f"{skill_name}.md"
    if not skill_path.exists():
        print(f"ERROR: Seed skill not found: {skill_path}")
        sys.exit(1)

    current_skill = skill_path.read_text(encoding="utf-8").strip()
    best_skill = current_skill
    best_score = 0.0

    out_base = _HERE / "skillopt_runs" / skill_name
    out_base.mkdir(parents=True, exist_ok=True)

    adapter = InsightAgentEnvAdapter(skill_name=skill_name, domains=domains)

    print(f"\n{'='*60}")
    print(f"SkillOpt Training: {skill_name}")
    print(f"Domains: {domains}")
    print(f"Epochs: {epochs}")
    print(f"{'='*60}\n")

    for epoch in range(1, epochs + 1):
        print(f"\n--- Epoch {epoch}/{epochs} ---")
        epoch_dir = str(out_base / f"epoch_{epoch:02d}")

        # Rollout
        print("Rollout...")
        results = adapter.rollout(None, current_skill, epoch_dir)
        avg_score = sum(r.get("soft", 0) for r in results) / max(len(results), 1)
        print(f"Avg score: {avg_score:.3f}")

        # Track best
        if avg_score > best_score:
            best_score = avg_score
            best_skill = current_skill
            best_dir = _HERE / "skills" / skill_name
            best_dir.mkdir(exist_ok=True)
            (best_dir / "best_skill.md").write_text(best_skill, encoding="utf-8")
            print(f"New best! Score={best_score:.3f} → saved to skills/{skill_name}/best_skill.md")

        if avg_score >= 0.90:
            print("Reached target score 0.90 — stopping early.")
            break

        # Reflect + patch
        print("Reflecting...")
        patches = adapter.reflect(results, current_skill, epoch_dir)
        print(f"Generated {len(patches)} patches")

        if patches:
            from skillopt.optimizer.skill import apply_patch
            for patch in patches:
                try:
                    current_skill = apply_patch(current_skill, patch)
                except Exception as e:
                    print(f"  Patch apply failed: {e}")

            # Save candidate skill for this epoch
            (out_base / f"epoch_{epoch:02d}_skill.md").write_text(current_skill, encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Training complete. Best score: {best_score:.3f}")
    print(f"Best skill: skills/{skill_name}/best_skill.md")
    print(f"{'='*60}")


def sleep_mode() -> None:
    """SkillOpt-Sleep: nightly offline self-evolution for both skills."""
    print("SkillOpt-Sleep: evolving all InsightAgent skills...")
    for skill in ("seo_auditor", "action_planner"):
        print(f"\n[Sleep] Training: {skill}")
        train(skill_name=skill, epochs=2, quick=True)
    print("\n[Sleep] Done. Skills updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SkillOpt training for InsightAgent")
    parser.add_argument("--skill", choices=["seo_auditor", "action_planner"],
                        default="seo_auditor", help="Which skill to train")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--quick", action="store_true", help="Quick mode: 2 domains only")
    parser.add_argument("--sleep", action="store_true", help="Sleep mode: nightly evolution")
    args = parser.parse_args()

    if args.sleep:
        sleep_mode()
    else:
        train(skill_name=args.skill, epochs=args.epochs, quick=args.quick)
