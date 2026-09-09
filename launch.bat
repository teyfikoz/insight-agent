@echo off
:: InsightAgent v2.0 — Windows USB Launcher
:: Double-click or run from USB drive

title InsightAgent v2.0 - AI Website Intelligence
echo ============================================
echo   InsightAgent v2.0 - AI Web Intelligence
echo ============================================
echo.

cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install from https://python.org
    pause
    exit /b 1
)

:: Setup venv on first run
if not exist ".venv" (
    echo Setting up environment (first run)...
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

.venv\Scripts\python -c "import fastapi, uvicorn, click, rich, requests, bs4, lxml, openai, groq, fpdf, yaml, whois, dns, certifi, multipart, httpx, feedparser" >nul 2>&1
if errorlevel 1 (

    if exist "wheels" (
        echo Installing from compatible local wheels...
        .venv\Scripts\pip install --quiet --no-index --find-links="wheels" -r requirements.txt
    ) else if exist "..\wheels" (
        echo Installing from USB wheels (offline mode)...
        .venv\Scripts\pip install --quiet --no-index --find-links="..\wheels" -r requirements.txt
    ) else (
        echo Installing from internet...
        .venv\Scripts\pip install --quiet -r requirements.txt
    )
    if errorlevel 1 (
        echo Installation failed. Check network access or compatible offline wheels.
        pause
        exit /b 1
    )
    echo Setup complete.
)

echo.
echo Starting dashboard at http://localhost:7890
echo Press Ctrl+C to stop.
echo.

.venv\Scripts\python dashboard\server.py
pause
