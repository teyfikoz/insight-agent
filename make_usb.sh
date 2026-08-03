#!/bin/bash
# InsightAgent USB Packager
# Prepares a self-contained USB bundle with offline Python wheels.
# Usage: ./make_usb.sh [/path/to/usb]
#
# Output layout on USB:
#   InsightAgent/
#   ├── wheels/          ← offline pip wheels (all platforms)
#   ├── agents/
#   ├── scanner/
#   ├── reporter/
#   ├── dashboard/
#   ├── skills/
#   ├── main.py
#   ├── requirements.txt
#   ├── launch.command   ← macOS double-click
#   └── launch.bat       ← Windows double-click

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
USB_PATH="${1:-/tmp/InsightAgent_USB}"
DEST="$USB_PATH/InsightAgent"

echo "=========================================="
echo " InsightAgent USB Packager"
echo " Source : $SCRIPT_DIR"
echo " Target : $DEST"
echo "=========================================="

# ── 1. Clean destination ──────────────────────────────────────────────────────
rm -rf "$DEST"
mkdir -p "$DEST/wheels"

# ── 2. Copy project files (exclude venv, cache, git) ─────────────────────────
echo "[1/4] Copying project files..."
rsync -a --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
         --exclude='*.pyc' --exclude='.env' --exclude='reports/' \
         --exclude='wheels/' \
         "$SCRIPT_DIR/" "$DEST/"

# ── 3. Download wheels for macOS + Windows (universal where possible) ─────────
echo "[2/4] Downloading Python wheels..."
pip download \
    --dest "$DEST/wheels" \
    --prefer-binary \
    -r "$SCRIPT_DIR/requirements.txt" \
    2>/dev/null || true

# Try to get Windows-compatible wheels too (only works on non-cross-compile setups)
pip download \
    --dest "$DEST/wheels" \
    --prefer-binary \
    --platform win_amd64 \
    --python-version 311 \
    --only-binary :all: \
    -r "$SCRIPT_DIR/requirements.txt" \
    2>/dev/null || true

echo "    Wheels downloaded: $(ls "$DEST/wheels" | wc -l | tr -d ' ')"

# ── 4. Write launch.command (macOS) ──────────────────────────────────────────
echo "[3/4] Writing launchers..."
cat > "$DEST/launch.command" << 'LAUNCHER_MAC'
#!/bin/bash
# InsightAgent — macOS Launcher (double-click to run)
cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &>/dev/null; then
  osascript -e 'display dialog "Python 3 not found. Download from python.org" buttons {"OK"} default button 1 with icon stop'
  exit 1
fi

PYVER=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PYVER" -lt 10 ]; then
  osascript -e 'display dialog "Python 3.10+ required. Download from python.org" buttons {"OK"} default button 1 with icon stop'
  exit 1
fi

# Create venv if needed
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Install from wheels (offline) or fallback to internet
source .venv/bin/activate
if [ -d "wheels" ] && [ "$(ls wheels | wc -l)" -gt 0 ]; then
  echo "Installing from offline wheels..."
  pip install --no-index --find-links=wheels -r requirements.txt -q 2>/dev/null || \
  pip install -r requirements.txt -q
else
  echo "Installing from internet..."
  pip install -r requirements.txt -q
fi

# Open browser then start
sleep 1 && open http://localhost:7890 &

echo ""
echo "  InsightAgent starting at http://localhost:7890"
echo "  Press Ctrl+C to stop."
echo ""
exec python3 main.py --dashboard
LAUNCHER_MAC
chmod +x "$DEST/launch.command"

# ── 5. Write launch.bat (Windows) ────────────────────────────────────────────
cat > "$DEST/launch.bat" << 'LAUNCHER_WIN'
@echo off
cd /d "%~dp0"
title InsightAgent

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found. Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

if exist "wheels" (
    echo Installing from offline wheels...
    pip install --no-index --find-links=wheels -r requirements.txt -q 2>nul
    if errorlevel 1 pip install -r requirements.txt -q
) else (
    echo Installing from internet...
    pip install -r requirements.txt -q
)

echo.
echo   InsightAgent starting at http://localhost:7890
echo   Close this window to stop.
echo.
start "" http://localhost:7890
python main.py --dashboard
pause
LAUNCHER_WIN

# ── 6. Summary ────────────────────────────────────────────────────────────────
echo "[4/4] Done."
echo ""
echo " USB bundle ready: $DEST"
echo " Size: $(du -sh "$DEST" | cut -f1)"
echo ""
echo " Contents:"
ls "$DEST"
echo ""
echo " Next: Copy the InsightAgent/ folder to a USB drive."
echo " macOS: double-click launch.command"
echo " Windows: double-click launch.bat"
