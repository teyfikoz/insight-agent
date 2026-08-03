#!/bin/bash
# InsightAgent — macOS USB Launcher
# Double-click this file to start InsightAgent Dashboard
# chmod +x launch.command

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "========================================"
echo "  InsightAgent v2.0 — AI Web Intelligence"
echo "========================================"
echo ""

# Find python3
PYTHON=""
for py in python3.12 python3.11 python3.10 python3; do
  if command -v "$py" &>/dev/null; then
    PYTHON=$(command -v "$py")
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3.10+ not found."
  echo "Install from https://python.org"
  read -p "Press Enter to exit..."
  exit 1
fi

echo "Python: $PYTHON ($($PYTHON --version 2>&1))"

# Create/activate venv
if [ ! -d ".venv" ]; then
  echo "Setting up environment (first run)..."
  "$PYTHON" -m venv .venv

  # Install from wheels if available (offline), else pip
  WHEELS_DIR="$DIR/../wheels"
  if [ -d "$WHEELS_DIR" ]; then
    echo "Installing from USB wheels (offline mode)..."
    .venv/bin/pip install --quiet --no-index --find-links="$WHEELS_DIR" -r requirements.txt
    .venv/bin/pip install --quiet --no-index --find-links="$WHEELS_DIR" fastapi uvicorn python-multipart 2>/dev/null || true
  else
    echo "Installing from internet..."
    .venv/bin/pip install --quiet -r requirements.txt
    .venv/bin/pip install --quiet fastapi uvicorn python-multipart
  fi
  echo "Setup complete."
fi

echo ""
echo "Starting dashboard at http://localhost:7890"
echo "Press Ctrl+C to stop."
echo ""

exec .venv/bin/python dashboard/server.py
