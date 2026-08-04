"""
InsightAgent Dashboard Server
FastAPI web UI — runs locally, serves the management panel.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = FastAPI(title="InsightAgent Dashboard", version="2.0.0")

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory stores
JOBS: dict[str, dict] = {}
MONITORS: dict[str, dict] = {}
_monitor_stop: dict[str, threading.Event] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_score_from_md(path: Path) -> int | None:
    try:
        txt = path.read_text(encoding="utf-8")
        m = re.search(r"SEO Score[^\d]*(\d+)/100", txt)
        if m:
            return int(m.group(1))
        m = re.search(r"\*\*(\d+)/100\*\*", txt)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


def _load_reports() -> list[dict]:
    reports_dir = ROOT / "reports"
    reports = []
    if not reports_dir.exists():
        return reports
    for f in sorted(reports_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        parts = f.stem.split("_")
        domain = "_".join(parts[:-2]) if len(parts) >= 3 else f.stem
        pdf_path = reports_dir / (f.stem + ".pdf")
        reports.append({
            "filename": f.name,
            "domain": domain,
            "size_kb": round(stat.st_size / 1024, 1),
            "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "score": _parse_score_from_md(f),
            "has_pdf": pdf_path.exists(),
        })
    return reports


def _run_scan_sync(job_id: str, target: str, report_type: str, keywords: str, no_pdf: bool):
    JOBS[job_id]["status"] = "running"
    JOBS[job_id]["progress"] = "Scanning..."
    try:
        cmd = [
            sys.executable, str(ROOT / "main.py"),
            "--target", target,
            "--report", report_type,
            "--output", str(ROOT / "reports"),
        ]
        if keywords:
            cmd += ["--keywords", keywords]
        if no_pdf:
            cmd.append("--no-pdf")

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = proc.stdout + proc.stderr

        score = None
        for line in output.splitlines():
            if "SEO Score" in line:
                try:
                    score = int(line.split()[2].split("/")[0])
                except Exception:
                    pass

        JOBS[job_id]["status"] = "done" if proc.returncode == 0 else "error"
        JOBS[job_id]["progress"] = "Completed"
        JOBS[job_id]["output"] = output
        JOBS[job_id]["score"] = score
        JOBS[job_id]["finished_at"] = datetime.now().strftime("%H:%M:%S")
    except subprocess.TimeoutExpired:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["progress"] = "Timeout"
        JOBS[job_id]["output"] = "Scan timed out after 120 seconds."
    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["output"] = str(e)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/status")
async def status():
    reports_count = len(list((ROOT / "reports").glob("*.md"))) if (ROOT / "reports").exists() else 0
    skills_dir = ROOT / "skills"
    has_best_skill = (skills_dir / "seo_auditor" / "best_skill.md").exists()
    # Check API keys
    env_file = ROOT / ".env"
    env_keys: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env_keys[k.strip()] = v.strip().strip('"\'')
    nim_ok = bool(env_keys.get("NVIDIA_NIM_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY"))
    groq_ok = bool(env_keys.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY"))
    gemini_ok = bool(env_keys.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    return JSONResponse({
        "version": "2.0.0",
        "reports_count": reports_count,
        "active_jobs": sum(1 for j in JOBS.values() if j["status"] == "running"),
        "has_optimized_skill": has_best_skill,
        "python": sys.version.split()[0],
        "root": str(ROOT),
        "monitors_active": sum(1 for m in MONITORS.values() if m["status"] == "running"),
        "api_nim": nim_ok,
        "api_groq": groq_ok,
        "api_gemini": gemini_ok,
    })


@app.post("/api/scan")
async def start_scan(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    target = data.get("target", "").strip()
    if not target:
        return JSONResponse({"error": "target is required"}, status_code=400)
    job_id = str(uuid.uuid4())[:8]
    JOBS[job_id] = {
        "id": job_id, "target": target, "status": "queued", "progress": "Queued",
        "started_at": datetime.now().strftime("%H:%M:%S"), "finished_at": None,
        "output": "", "score": None,
    }
    background_tasks.add_task(
        _run_scan_sync, job_id, target,
        data.get("report_type", "full"),
        data.get("keywords", ""),
        data.get("no_pdf", False),
    )
    return JSONResponse({"job_id": job_id})


@app.post("/api/scan/batch")
async def start_batch_scan(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    raw = data.get("targets", "")
    targets = [t.strip() for t in raw.replace(",", "\n").splitlines() if t.strip()]
    targets = targets[:10]  # max 10 at once
    if not targets:
        return JSONResponse({"error": "No targets provided"}, status_code=400)
    job_ids = []
    for target in targets:
        job_id = str(uuid.uuid4())[:8]
        JOBS[job_id] = {
            "id": job_id, "target": target, "status": "queued", "progress": "Queued",
            "started_at": datetime.now().strftime("%H:%M:%S"), "finished_at": None,
            "output": "", "score": None,
        }
        background_tasks.add_task(
            _run_scan_sync, job_id, target,
            data.get("report_type", "full"),
            data.get("keywords", ""),
            data.get("no_pdf", True),
        )
        job_ids.append(job_id)
    return JSONResponse({"job_ids": job_ids, "count": len(job_ids)})


@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(job)


@app.get("/api/jobs")
async def list_jobs():
    return JSONResponse(list(JOBS.values()))


@app.get("/api/reports")
async def list_reports():
    return JSONResponse(_load_reports())


@app.get("/api/report/{filename}")
async def get_report(filename: str):
    f = ROOT / "reports" / filename
    if not f.exists() or not filename.endswith(".md"):
        return JSONResponse({"error": "not found"}, status_code=404)
    report = {
        "content": f.read_text(encoding="utf-8"),
        "filename": filename,
        "score": _parse_score_from_md(f),
    }
    return JSONResponse(report)


@app.get("/api/report/{filename}/download")
async def download_report(filename: str):
    # Try PDF first
    if filename.endswith(".md"):
        pdf_name = filename[:-3] + ".pdf"
        pdf_path = ROOT / "reports" / pdf_name
        if pdf_path.exists():
            return FileResponse(str(pdf_path), media_type="application/pdf", filename=pdf_name)
    f = ROOT / "reports" / filename
    if f.exists():
        return FileResponse(str(f), media_type="text/plain", filename=filename)
    return JSONResponse({"error": "not found"}, status_code=404)


@app.get("/api/settings")
async def get_settings():
    env_file = ROOT / ".env"
    settings: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                settings[k.strip()] = v.strip().strip('"\'')
    return JSONResponse(settings)


@app.post("/api/settings")
async def save_settings(request: Request):
    data = await request.json()
    env_file = ROOT / ".env"
    existing: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip().strip('"\'')
    for k, v in data.items():
        if v:
            existing[k] = v
        elif k in existing and not v:
            del existing[k]
    env_file.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n")
    for k, v in existing.items():
        os.environ[k] = v
    return JSONResponse({"status": "ok", "message": f"Saved {len(existing)} settings"})


# ── Monitor ───────────────────────────────────────────────────────────────────

@app.post("/api/monitor/start")
async def monitor_start(request: Request):
    data = await request.json()
    target = data.get("target", "").strip()
    interval = max(300, int(data.get("interval", 3600)))
    if not target:
        return JSONResponse({"error": "target required"}, status_code=400)

    # Stop existing
    if target in _monitor_stop:
        _monitor_stop[target].set()

    stop_evt = threading.Event()
    _monitor_stop[target] = stop_evt
    MONITORS[target] = {
        "target": target, "interval": interval, "status": "running",
        "last_scan": None, "scan_count": 0,
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    def _loop():
        while not stop_evt.is_set():
            job_id = str(uuid.uuid4())[:8]
            JOBS[job_id] = {
                "id": job_id, "target": target, "status": "queued",
                "progress": "Monitor scan", "started_at": datetime.now().strftime("%H:%M:%S"),
                "finished_at": None, "output": "", "score": None,
            }
            _run_scan_sync(job_id, target, "full", "", True)
            MONITORS[target]["last_scan"] = datetime.now().strftime("%H:%M:%S")
            MONITORS[target]["scan_count"] += 1
            stop_evt.wait(interval)
        MONITORS[target]["status"] = "stopped"

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return JSONResponse({"status": "started", "target": target, "interval": interval})


@app.post("/api/monitor/stop")
async def monitor_stop(request: Request):
    data = await request.json()
    target = data.get("target", "").strip()
    if target in _monitor_stop:
        _monitor_stop[target].set()
        if target in MONITORS:
            MONITORS[target]["status"] = "stopped"
        return JSONResponse({"status": "stopped", "target": target})
    return JSONResponse({"error": "monitor not found"}, status_code=404)


@app.get("/api/monitor/list")
async def monitor_list():
    return JSONResponse(list(MONITORS.values()))


# ── Launcher ──────────────────────────────────────────────────────────────────

def run(host: str = "127.0.0.1", port: int = 7890, open_browser: bool = True):
    if open_browser:
        import threading as _t
        import webbrowser
        def _open():
            time.sleep(1.2)
            webbrowser.open(f"http://{host}:{port}")
        _t.Thread(target=_open, daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run()
