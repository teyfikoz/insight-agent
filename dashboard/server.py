"""
InsightAgent Dashboard Server
FastAPI web UI — runs locally, serves the management panel.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
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

# In-memory job store
JOBS: dict[str, dict] = {}


def _load_reports() -> list[dict]:
    reports_dir = ROOT / "reports"
    reports = []
    if reports_dir.exists():
        for f in sorted(reports_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            stat = f.stat()
            parts = f.stem.split("_")
            domain = "_".join(parts[:-2]) if len(parts) >= 3 else f.stem
            reports.append({
                "filename": f.name,
                "domain": domain,
                "size_kb": round(stat.st_size / 1024, 1),
                "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
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


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/scan")
async def start_scan(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    target = data.get("target", "").strip()
    if not target:
        return JSONResponse({"error": "target is required"}, status_code=400)

    job_id = str(uuid.uuid4())[:8]
    JOBS[job_id] = {
        "id": job_id,
        "target": target,
        "status": "queued",
        "progress": "Queued",
        "started_at": datetime.now().strftime("%H:%M:%S"),
        "finished_at": None,
        "output": "",
        "score": None,
    }
    background_tasks.add_task(
        _run_scan_sync, job_id, target,
        data.get("report_type", "full"),
        data.get("keywords", ""),
        data.get("no_pdf", False),
    )
    return JSONResponse({"job_id": job_id})


@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(job)


@app.get("/api/reports")
async def list_reports():
    return JSONResponse(_load_reports())


@app.get("/api/report/{filename}")
async def get_report(filename: str):
    f = ROOT / "reports" / filename
    if not f.exists() or not filename.endswith(".md"):
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"content": f.read_text(encoding="utf-8"), "filename": filename})


@app.get("/api/jobs")
async def list_jobs():
    return JSONResponse(list(JOBS.values()))


@app.get("/api/status")
async def status():
    reports_count = len(list((ROOT / "reports").glob("*.md"))) if (ROOT / "reports").exists() else 0
    skills_dir = ROOT / "skills"
    has_best_skill = (skills_dir / "seo_auditor" / "best_skill.md").exists()
    return JSONResponse({
        "version": "2.0.0",
        "reports_count": reports_count,
        "active_jobs": sum(1 for j in JOBS.values() if j["status"] == "running"),
        "has_optimized_skill": has_best_skill,
        "python": sys.version.split()[0],
        "root": str(ROOT),
    })


def run(host: str = "127.0.0.1", port: int = 7890, open_browser: bool = True):
    if open_browser:
        import threading
        def _open():
            time.sleep(1.2)
            import webbrowser
            webbrowser.open(f"http://{host}:{port}")
        threading.Thread(target=_open, daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run()
