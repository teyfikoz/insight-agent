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

    if exist "..\wheels" (
        echo Installing from USB wheels (offline mode)...
        .venv\Scripts\pip install --quiet --no-index --find-links="..\wheels" -r requirements.txt
        .venv\Scripts\pip install --quiet --no-index --find-links="..\wheels" fastapi uvicorn python-multipart 2>nul
    ) else (
        echo Installing from internet...
        .venv\Scripts\pip install --quiet -r requirements.txt
        .venv\Scripts\pip install --quiet fastapi uvicorn python-multipart
    )
    echo Setup complete.
)

echo.
echo Starting dashboard at http://localhost:7890
echo Press Ctrl+C to stop.
echo.

.venv\Scripts\python dashboard\server.py
pause
