# InsightAgent — AI-Powered Website Intelligence

> **Scan any website in seconds. Get an AI-generated SEO audit, action plan, and PDF report.**
> Runs locally. Website scans need network access; enabled AI providers receive analysis inputs.
> The source ZIP contains no API keys, personal reports or preinstalled Python environment.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What It Does

InsightAgent scans a website and produces an SEO audit and action plan. Duration depends on the target and configured providers:

| Module | What it analyzes |
|--------|-----------------|
| **WebScanner** | SSL certificate, load time, title/meta tags, schema markup, sitemap, robots.txt, Open Graph |
| **SEOAgent** | AI-powered SEO score (0–100), quick wins, keyword opportunities |
| **ActionPlanAgent** | Executive summary + 7 / 30 / 90-day action plan with effort/impact ratings |
| **SkillOpt** | Self-improving prompt engine — gets smarter with every scan |
| **Reports** | Markdown + optional PDF output |

**AI Chain (automatic fallback):**
```
NVIDIA NIM → Groq → Google Gemini → Rule-Based
```
All AI providers are optional. Rule-based analysis requires no AI key; collecting live website data still requires a network connection.

## v2.0 source distribution and OCC

Build: `python3 scripts/build_release.py --output /tmp/InsightAgent-v2.0.zip`.
The release builder includes only distribution source files, excludes private data and refuses known credential patterns.
SHA-256 accompanies the archive. Python 3.10+ and dependency installation are required.
macOS/Linux: `bash launch.command`; Windows: `launch.bat`.
The launchers retry incomplete dependency setup and stop if installation fails.
Offline dependency installation requires compatible wheels; the source ZIP alone is not a full offline bundle.
OCC embeds `/insight-agent/` behind its login and CSRF checks. Keep the standalone dashboard bound to loopback.
Credential fields are write-only; an empty field preserves the configured key.

---

## Management Dashboard

Launch the full web dashboard:
```bash
python3 main.py --dashboard
# Opens http://localhost:7890
```

**Dashboard features:**
- **Overview** — stats, quick scan, score history sparkline
- **New Scan** — configure and run a single-domain audit
- **Bulk Scan** — scan up to 10 domains simultaneously (competitor analysis)
- **Monitor Mode** — schedule recurring scans (hourly, daily, weekly)
- **Jobs** — real-time progress tracking
- **Reports** — search, filter, view inline, download PDF
- **Skills & AI** — model routing status, SkillOpt training
- **Settings** — API key management, stored only in local `.env`
- **Help** — quick reference guide

---

## Installation

### From GitHub

```bash
git clone https://github.com/teyfikoz/insight-agent.git
cd insight-agent

python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate.bat

pip install -r requirements.txt
```

### Offline dependency installation

The source ZIP does not include wheels or Python. Prepare a `wheels/` folder
for the target operating system, CPU architecture and Python version before
using the launcher without internet. Put it beside `launch.command`/`launch.bat`
or in the parent directory. A wheel set from macOS does not establish Windows
compatibility. Live website scans and cloud AI still need network access.

---

## Quick Start

### CLI
```bash
# Single scan — Markdown report
python3 main.py --target example.com

# PDF + Markdown report
python3 main.py --target example.com --output ~/Desktop/reports/

# Skip PDF generation
python3 main.py --target example.com --no-pdf

# With target keywords
python3 main.py --target example.com --keywords "saas, monitoring, uptime"

# Continuous monitoring (scan every hour)
python3 main.py --monitor example.com --interval 3600
```

### Dashboard
```bash
python3 main.py --dashboard
# → http://localhost:7890
```

### Example Output
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│ InsightAgent — example.com       │
└━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┘

 Metric           Value            Status
─────────────────────────────────────────
 SEO Score        89/100           Grade: A
 Load Time        472ms            Fast ✓
 SSL              56 days          ✓
 Sitemap          found            ✓
 Schema           SoftwareApp      ✓
 Critical Issues  0                None ✓
 AI Provider      NVIDIA NIM       AI ✓

Quick Wins:
  → Add canonical URL tag (30 min)
  → Shorten title to under 60 chars (15 min)
  → Add generateMetadata to all pages (1 hour)

Markdown report: reports/example_com_20260804_120000.md
```

---

## API Keys (All Optional)

InsightAgent works without any API key. Keys unlock AI-powered insights:

```bash
# Create .env in the project folder
NVIDIA_NIM_API_KEY=your_nim_key
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
```

Or set them through the **Settings** tab in the dashboard.

Provider availability, model support and quotas depend on your account.
Review the configured model names in `agents/base_agent.py` before use.
Rule-based analysis uses no paid AI API.

---

## Bulk Scan (Competitor Analysis)

Scan multiple domains at once from the dashboard or CLI:

**Dashboard:** Bulk Scan tab → paste domains (one per line) → Launch

**CLI:** Run separate scans in background:
```bash
for domain in example.com competitor1.com competitor2.com; do
  python3 main.py --target $domain --no-pdf &
done
wait
```

---

## Monitor Mode

Track a site's SEO over time:
```bash
# CLI: scan every 6 hours
python3 main.py --monitor example.com --interval 21600

# Dashboard: Monitor tab → set domain + interval → Start Monitoring
```

---

## SkillOpt — Self-Improving AI

InsightAgent uses SkillOpt (ReflACT loop) to improve its analysis prompts over time.
The model weights never change — only the `skills/*.md` prompt files are updated.

```
skills/
  seo_auditor.md          ← seed prompt
  seo_auditor/
    best_skill.md         ← trained version (auto-updated by SkillOpt)
```

```bash
# Run training (improves SEO analysis quality)
python3 skillopt_train.py --skill seo_auditor --epochs 3

# Nightly cron: auto-train every night at 2am
0 2 * * * cd /path/to/insight-agent && .venv/bin/python skillopt_train.py --sleep
```

---

## Project Structure

```
insight-agent/
├── main.py                    ← CLI entry point
├── requirements.txt
├── make_usb.sh                ← USB bundle creator
├── launch.command             ← macOS launcher (double-click)
├── launch.bat                 ← Windows launcher (double-click)
├── skillopt_train.py          ← SkillOpt training
├── .env                       ← API keys (git-ignored)
│
├── agents/
│   ├── base_agent.py          ← NIM → Groq → Gemini → fallback router
│   ├── seo_agent.py           ← SEO analysis
│   ├── action_plan_agent.py   ← Action plan generator
│   └── skill_loader.py        ← SkillOpt skill loader
│
├── scanner/
│   └── web_scanner.py         ← HTTP scanner (SSL, meta, schema, perf)
│
├── reporter/
│   ├── markdown_reporter.py   ← .md report
│   └── pdf_reporter.py        ← .pdf report (fpdf2)
│
├── dashboard/
│   ├── server.py              ← FastAPI dashboard server
│   └── templates/index.html  ← Single-page management panel
│
├── skills/
│   ├── seo_auditor.md
│   └── action_planner.md
│
└── reports/                   ← Generated reports (git-ignored)
```

---

## Requirements

```
Python 3.10+
requests, beautifulsoup4, lxml    — HTTP scanning
openai                            — NIM + Groq + Gemini client
fastapi, uvicorn                  — Dashboard server
click, rich                       — CLI interface
fpdf2                             — PDF generation
httpx, feedparser                 — Extended data fetching
pyyaml                            — Config
```

The source distribution installs these dependencies on first launch.
Optional training and USB preparation scripts listed above belong to the full
GitHub checkout; they are not included in the minimal source ZIP.

---

## Privacy & Security

- Reports are saved locally. Website requests contact the selected sites;
  configured AI providers receive the analysis inputs sent by their adapters.
- API keys are stored in the local `.env` with owner-only permissions when
  saved through Settings. Settings responses do not return the keys.
- Use only your own environment variables or project `.env`; credentials are
  not imported from another application's private configuration.
- The standalone dashboard has no multi-user login. Keep it on loopback;
  remote access must go through OCC authentication and CSRF protections.
- Review scan results before sharing them. No independent security audit or
  claim of complete offline website analysis is implied by this release.

---

## License

MIT — Free to use, modify, and distribute.

---

*Built with Python, FastAPI, NVIDIA NIM, Groq, and SkillOpt.*
*Part of the [TechSyncAnalytica](https://techsyncanalytica.com) AI toolkit.*
