# InsightAgent — AI-Powered Website Intelligence

> **Scan any website in seconds. Get an AI-generated SEO audit, action plan, and PDF report.**
> Works 100% offline — perfect for USB deployment. No data ever leaves your machine.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Offline Ready](https://img.shields.io/badge/Offline-Ready-green.svg)](#usb-offline-mode)

---

## What It Does

InsightAgent scans a website and produces a professional intelligence report in under 60 seconds:

| Module | What it analyzes |
|--------|-----------------|
| **WebScanner** | SSL certificate, load time, title/meta tags, schema markup, sitemap, robots.txt, Open Graph |
| **SEOAgent** | AI-powered SEO score (0–100), quick wins, keyword opportunities |
| **ActionPlanAgent** | Executive summary + 7 / 30 / 90-day action plan with effort/impact ratings |
| **SkillOpt** | Self-improving prompt engine — gets smarter with every scan |
| **Reports** | Markdown + optional PDF output |

**AI Chain (automatic fallback):**
```
NVIDIA NIM → Groq → Google Gemini → Rule-Based (always works offline)
```
All providers are optional. InsightAgent works without any API key using built-in rule-based analysis.

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

### USB Offline Mode

**Prepare USB on an internet-connected machine (one time):**
```bash
git clone https://github.com/teyfikoz/insight-agent.git
cd insight-agent
./make_usb.sh /Volumes/MY_USB   # macOS
# or
./make_usb.sh /media/MY_USB     # Linux
```

**Use on any offline machine:**
```
USB:/InsightAgent/
  ├── launch.command    ← macOS: double-click to start
  ├── launch.bat        ← Windows: double-click to start
  ├── wheels/           ← all Python packages (51 files, offline install)
  └── ...
```

Double-clicking `launch.command` (Mac) or `launch.bat` (Windows):
1. Creates a Python virtual environment automatically
2. Installs all dependencies from the bundled wheels (no internet needed)
3. Opens the dashboard at `http://localhost:7890`

---

## Quick Start

### CLI
```bash
# Single scan — Markdown report
python3 main.py --target example.com

# PDF + Markdown report
python3 main.py --target example.com --output ~/Desktop/reports/

# No PDF (faster, useful offline)
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
NVIDIA_NIM_API_KEY=nvapi-...   # Best quality — free credits at signup
GROQ_API_KEY=gsk_...           # Fast & free — 14,400 req/day
GEMINI_API_KEY=AIza...         # 1M context — free at aistudio.google.com
```

Or set them through the **Settings** tab in the dashboard.

| Provider | Model | Free Tier | Quality |
|----------|-------|-----------|---------|
| NVIDIA NIM | Llama 3.3 70B | Credits on signup | ⭐⭐⭐ Best |
| Groq | Llama 3.3 70B | 14,400 req/day | ⭐⭐⭐ Fast |
| Google Gemini | Gemini 2.0 Flash | 1M tokens/day | ⭐⭐ |
| Rule-Based | Built-in | Always free | ⭐ Offline |

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

All dependencies are bundled in the USB package (`wheels/` folder).

---

## Privacy & Security

- **No telemetry.** InsightAgent never phones home.
- **Local only.** All scans, reports, and API keys stay on your machine.
- **API keys** are stored in `.env` — git-ignored by default, never logged.
- **Offline mode** — works completely without internet when using USB bundle.

---

## License

MIT — Free to use, modify, and distribute.

---

*Built with Python, FastAPI, NVIDIA NIM, Groq, and SkillOpt.*
*Part of the [TechSyncAnalytica](https://techsyncanalytica.com) AI toolkit.*
