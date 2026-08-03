#!/usr/bin/env python3
"""
InsightAgent — AI-powered website intelligence tool.

Usage:
    python3 main.py --target example.com
    python3 main.py --target example.com --report full --output ~/Desktop/reports/
    python3 main.py --target example.com --keywords "saas, monitoring, uptime"
    python3 main.py --dashboard          # Start web dashboard (port 7890)
    python3 main.py --monitor example.com --interval 3600  # Continuous monitoring
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()


def _load_env() -> None:
    """Load .env from project root if present."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"\''))

    # Also try secrets.env from memory dir
    secrets_file = Path.home() / ".claude/projects/-Users-teyfikoz/memory/secrets.env"
    if secrets_file.exists():
        for line in secrets_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                k = key.strip()
                if k in ("NVIDIA_NIM_API_KEY", "GROQ_API_KEY"):
                    os.environ.setdefault(k, val.strip().strip('"\''))


@click.command(context_settings={"ignore_unknown_options": True})
@click.option("--target", "-t", default="", help="URL or domain to analyze")
@click.option("--output", "-o", default="reports", help="Output directory (default: reports/)")
@click.option("--report", "-r", default="full",
              type=click.Choice(["full", "seo", "quick"]),
              help="Report type")
@click.option("--keywords", "-k", default="", help="Comma-separated target keywords")
@click.option("--no-pdf", is_flag=True, help="Skip PDF generation")
@click.option("--no-md", is_flag=True, help="Skip Markdown generation")
@click.option("--dashboard", is_flag=True, help="Start web dashboard at http://localhost:7890")
@click.option("--monitor", default="", help="Domain to monitor continuously")
@click.option("--interval", default=3600, help="Monitor interval in seconds (default: 3600)")
def main(target: str, output: str, report: str, keywords: str,
         no_pdf: bool, no_md: bool, dashboard: bool, monitor: str, interval: int):
    """InsightAgent — AI-powered website intelligence."""

    _load_env()

    # Dashboard mode
    if dashboard:
        console.print(Panel.fit(
            "[bold]InsightAgent Dashboard[/bold]\n"
            "[dim]Starting at http://localhost:7890[/dim]",
            border_style="blue"
        ))
        from dashboard.server import run as run_dashboard
        run_dashboard()
        return

    # Monitor mode (continuous)
    if monitor:
        import time
        console.print(Panel.fit(
            f"[bold blue]InsightAgent Monitor[/bold blue]\n"
            f"[dim]Target: {monitor} · Interval: {interval}s[/dim]",
            border_style="blue"
        ))
        run_count = 0
        while True:
            run_count += 1
            console.print(f"\n[bold]Run #{run_count}[/bold] — {monitor}")
            _run_scan(monitor, output, report, keywords, no_pdf, no_md)
            console.print(f"[dim]Next scan in {interval}s (Ctrl+C to stop)[/dim]")
            time.sleep(interval)
        return

    if not target:
        console.print("[red]Error:[/red] --target is required (or use --dashboard / --monitor)")
        raise SystemExit(1)

    _run_scan(target, output, report, keywords, no_pdf, no_md)


def _run_scan(target: str, output: str, report: str, keywords: str, no_pdf: bool, no_md: bool):

    console.print(Panel.fit(
        "[bold blue]InsightAgent[/bold blue] — AI-powered website intelligence\n"
        f"[dim]Target: {target}[/dim]",
        border_style="blue"
    ))

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    _load_env()

    # Step 1: Scan
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        task = progress.add_task("Scanning website...", total=None)

        from scanner.web_scanner import WebScanner
        scanner = WebScanner(timeout=15)
        scan = scanner.scan(target)

        progress.update(task, description="Analyzing SEO...")
        from agents.seo_agent import SEOAgent
        seo_agent = SEOAgent()
        seo = seo_agent.analyze(scan, keyword_list if keyword_list else None)

        progress.update(task, description="Generating action plan...")
        from agents.action_plan_agent import ActionPlanAgent
        plan_agent = ActionPlanAgent()
        plan = plan_agent.generate_plan(
            domain=scan.domain,
            seo_score=seo.score,
            seo_summary=seo.summary,
            seo_quick_wins=seo.quick_wins,
            technical_issues=scan.issues,
            warnings=scan.warnings,
            tech_stack=scan.tech_stack,
            load_time_ms=scan.load_time_ms,
            word_count=scan.word_count,
        )

        progress.update(task, description="Writing reports...")

        output_files = []

        if not no_md:
            from reporter.markdown_reporter import MarkdownReporter
            md_path = MarkdownReporter().generate(scan, seo, plan, output)
            output_files.append(("Markdown", md_path))

        if not no_pdf:
            try:
                from reporter.pdf_reporter import PDFReporter
                pdf_path = PDFReporter().generate(scan, seo, plan, output)
                output_files.append(("PDF", pdf_path))
            except ImportError:
                console.print("[yellow]⚠ fpdf2 not installed — skipping PDF. Run: pip install fpdf2[/yellow]")

        progress.update(task, description="Done!")

    # Results summary
    console.print()

    # Score table
    table = Table(title="Audit Results", show_header=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_column("Status")

    def status_icon(ok: bool) -> str:
        return "[green]✓[/green]" if ok else "[red]✗[/red]"

    table.add_row("SEO Score", f"{seo.score}/100", f"Grade: {seo.grade}")
    table.add_row("Load Time", f"{scan.load_time_ms}ms",
                  "[green]Fast[/green]" if scan.load_time_ms < 1500 else "[yellow]Slow[/yellow]")
    table.add_row("SSL", f"{scan.ssl_expiry_days} days", status_icon(scan.ssl_valid))
    table.add_row("Sitemap", "", status_icon(scan.has_sitemap))
    table.add_row("Schema", ", ".join(scan.schema_types[:2]) or "None", status_icon(scan.has_schema_markup))
    table.add_row("Title", scan.title[:50] + "..." if len(scan.title) > 50 else scan.title,
                  status_icon(bool(scan.title)))
    table.add_row("Critical Issues", str(len(scan.issues)),
                  "[red]Found[/red]" if scan.issues else "[green]None[/green]")
    table.add_row("AI Provider", plan.provider, "[blue]AI[/blue]" if plan.provider != "rule-based" else "[dim]Fallback[/dim]")
    console.print(table)

    if scan.issues:
        console.print("\n[bold red]Critical Issues:[/bold red]")
        for issue in scan.issues:
            console.print(f"  [red]✗[/red] {issue}")

    if plan.top_priority:
        console.print(f"\n[bold yellow]Top Priority:[/bold yellow] {plan.top_priority}")

    if seo.quick_wins:
        console.print("\n[bold green]Quick Wins:[/bold green]")
        for win in seo.quick_wins[:5]:
            console.print(f"  [green]→[/green] {win}")

    console.print()
    for fmt, path in output_files:
        console.print(f"[bold]{fmt} report:[/bold] {path}")

    if plan.provider == "rule-based":
        console.print(
            "\n[dim]Tip: Set NVIDIA_NIM_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY for AI-powered insights.[/dim]"
        )


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()  # pylint: disable=no-value-for-parameter
