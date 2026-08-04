#!/bin/bash
# InsightAgent USB Packager
# Creates a fully self-contained offline bundle with Python wheels and launchers.
# Usage: ./make_usb.sh [/path/to/usb_mount]
#
# USB layout:
#   InsightAgent/
#   ├── wheels/           ← offline pip wheels (macOS + Windows)
#   ├── agents/
#   ├── scanner/
#   ├── reporter/
#   ├── dashboard/
#   ├── skills/
#   ├── main.py
#   ├── requirements.txt
#   ├── README.md
#   ├── QUICK_START.txt   ← plain-text guide for non-technical users
#   ├── launch.command    ← macOS double-click launcher
#   └── launch.bat        ← Windows double-click launcher

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
USB_PATH="${1:-/tmp/InsightAgent_USB}"
DEST="$USB_PATH/InsightAgent"

echo "=========================================="
echo " InsightAgent USB Packager v2.0"
echo " Source : $SCRIPT_DIR"
echo " Target : $DEST"
echo "=========================================="

# ── 1. Clean + create destination ─────────────────────────────────────────────
rm -rf "$DEST"
mkdir -p "$DEST/wheels"

# ── 2. Copy project files ─────────────────────────────────────────────────────
echo "[1/5] Copying project files..."
rsync -a \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='reports/' \
    --exclude='wheels/' \
    --exclude='skillopt_runs/' \
    --exclude='NOTEBOOKLM_UPDATE.md' \
    "$SCRIPT_DIR/" "$DEST/"

# ── 3. Download wheels ────────────────────────────────────────────────────────
echo "[2/5] Downloading Python wheels (this may take a minute)..."
PIP_CMD="python3 -m pip"

# macOS / Linux wheels
$PIP_CMD download \
    --dest "$DEST/wheels" \
    --prefer-binary \
    -r "$SCRIPT_DIR/requirements.txt" \
    --quiet || true

# Windows wheels (best-effort, may not work on all hosts)
$PIP_CMD download \
    --dest "$DEST/wheels" \
    --prefer-binary \
    --platform win_amd64 \
    --python-version 311 \
    --only-binary :all: \
    -r "$SCRIPT_DIR/requirements.txt" \
    --quiet 2>/dev/null || true

echo "    Wheels downloaded: $(ls "$DEST/wheels" | wc -l | tr -d ' ')"

# ── 4. Write macOS launcher ───────────────────────────────────────────────────
echo "[3/5] Writing launchers..."

cat > "$DEST/launch.command" << 'LAUNCHER_MAC'
#!/bin/bash
# InsightAgent — macOS Launcher
# Double-click this file in Finder to start InsightAgent.

cd "$(dirname "$0")"

echo ""
echo "======================================"
echo "  InsightAgent — AI Website Intelligence"
echo "======================================"
echo ""

# Check Python 3
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 not found."
  echo "Download from: https://www.python.org/downloads/"
  osascript -e 'display dialog "Python 3 not found.\n\nDownload it from python.org then try again." buttons {"Open python.org","Cancel"} default button 1 with icon stop' 2>/dev/null && \
    open "https://www.python.org/downloads/" 2>/dev/null
  exit 1
fi

PYVER=$(python3 -c "import sys; print(sys.version_info.minor)")
PYMAJ=$(python3 -c "import sys; print(sys.version_info.major)")
if [ "$PYMAJ" -lt 3 ] || [ "$PYVER" -lt 10 ]; then
  echo "ERROR: Python 3.10 or higher required (found 3.$PYVER)."
  osascript -e 'display dialog "Python 3.10+ required.\n\nDownload from python.org." buttons {"OK"} default button 1 with icon stop' 2>/dev/null
  exit 1
fi

# Create virtual environment on first run
if [ ! -d ".venv" ]; then
  echo "First run: setting up virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# Check if already installed
if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "Installing dependencies..."
  if [ -d "wheels" ] && [ "$(ls wheels | wc -l)" -gt 0 ]; then
    echo "  Using offline wheels (no internet needed)"
    python3 -m pip install --no-index --find-links=wheels -r requirements.txt -q 2>/dev/null || \
    python3 -m pip install -r requirements.txt -q
  else
    echo "  Downloading from internet..."
    python3 -m pip install -r requirements.txt -q
  fi
  echo "  Done."
fi

echo ""
echo "  Dashboard : http://localhost:7890"
echo "  Press Ctrl+C to stop InsightAgent."
echo ""

# Open browser after short delay
(sleep 2 && open http://localhost:7890) &

exec python3 main.py --dashboard
LAUNCHER_MAC
chmod +x "$DEST/launch.command"

# ── 5. Write Windows launcher ─────────────────────────────────────────────────
cat > "$DEST/launch.bat" << 'LAUNCHER_WIN'
@echo off
cd /d "%~dp0"
title InsightAgent — AI Website Intelligence

echo.
echo ======================================
echo   InsightAgent - AI Website Intelligence
echo ======================================
echo.

:: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Download from: https://www.python.org/downloads/
    echo.
    pause
    start "" https://www.python.org/downloads/
    exit /b 1
)

:: Check Python version
python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.10 or higher is required.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create virtual environment on first run
if not exist ".venv" (
    echo First run: setting up virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

:: Install dependencies if needed
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    if exist "wheels" (
        echo   Using offline wheels - no internet needed
        python -m pip install --no-index --find-links=wheels -r requirements.txt -q 2>nul
        if errorlevel 1 python -m pip install -r requirements.txt -q
    ) else (
        echo   Downloading from internet...
        python -m pip install -r requirements.txt -q
    )
    echo   Done.
)

echo.
echo   Dashboard : http://localhost:7890
echo   Close this window to stop InsightAgent.
echo.

start "" http://localhost:7890
python main.py --dashboard
pause
LAUNCHER_WIN

# ── 6. Write QUICK_START.txt ──────────────────────────────────────────────────
cat > "$DEST/QUICK_START.txt" << 'QUICKSTART'
====================================
InsightAgent — Quick Start Guide
====================================

REQUIREMENTS
  • Python 3.10 or higher
    Download from: https://www.python.org/downloads/
  • No internet required (all packages are bundled)

--------------------------------------
macOS / Linux — HOW TO START
--------------------------------------
1. Open this folder in Finder
2. Double-click "launch.command"
   (If blocked by macOS: right-click → Open → Open)
3. A browser opens at http://localhost:7890

--------------------------------------
Windows — HOW TO START
--------------------------------------
1. Open this folder in Explorer
2. Double-click "launch.bat"
3. A browser opens at http://localhost:7890

--------------------------------------
FIRST TIME SETUP (one-time, ~2 min)
--------------------------------------
The first launch installs Python packages from the bundled "wheels" folder.
No internet is needed. Subsequent launches start immediately.

--------------------------------------
RUNNING A SCAN
--------------------------------------
1. In the dashboard, click "New Scan"
2. Enter any domain (e.g. example.com)
3. Click "Launch Scan"
4. Wait ~30-60 seconds for results
5. View the report in the "Reports" tab

--------------------------------------
AI PROVIDERS (optional — improves results)
--------------------------------------
Without a key: rule-based analysis runs offline (always works)
With a free key: AI-powered insights via NIM, Groq, or Gemini

Go to Settings tab to add your API keys:
  • NVIDIA NIM:   https://integrate.api.nvidia.com  (free credits)
  • Groq:         https://console.groq.com          (14,400 free/day)
  • Google Gemini:https://aistudio.google.com       (generous free tier)

--------------------------------------
BULK SCAN
--------------------------------------
Scan multiple websites at once:
1. Click "Bulk Scan" in the sidebar
2. Paste up to 10 domains (one per line)
3. Click "Launch Bulk Scan"

--------------------------------------
TROUBLESHOOTING
--------------------------------------
Q: "Python not found" on Windows
A: Install Python from python.org — check "Add to PATH" during install

Q: macOS blocks launch.command
A: Right-click → Open → Open (only needed once)

Q: Dashboard won't load
A: Make sure nothing else is using port 7890
   Try: http://127.0.0.1:7890

Q: Scan fails / no results
A: Check your internet connection (scans need to reach the target site)
   InsightAgent needs internet to SCAN websites, but not to install itself.

--------------------------------------
GITHUB & DOCS
--------------------------------------
https://github.com/teyfikoz/insight-agent

====================================
QUICKSTART
chmod 644 "$DEST/QUICK_START.txt"

# ── 7. Create empty reports dir ───────────────────────────────────────────────
mkdir -p "$DEST/reports"

# ── 8. Summary ────────────────────────────────────────────────────────────────
echo "[5/5] Done."
echo ""
echo " USB bundle ready: $DEST"
echo " Bundle size    : $(du -sh "$DEST" | cut -f1)"
echo ""
echo " Contents:"
ls "$DEST"
echo ""
echo "============================================"
echo " NEXT STEPS:"
echo " 1. Copy the InsightAgent/ folder to a USB drive"
echo " 2. macOS: double-click launch.command"
echo " 3. Windows: double-click launch.bat"
echo " 4. Browser opens at http://localhost:7890"
echo "============================================"
