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
for py in python3.13 python3.12 python3.11 python3.10 python3; do
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

fi

# Retry a failed first installation; existence of .venv is not proof of setup.
if ! .venv/bin/python -c 'import fastapi, uvicorn, click, rich, requests, bs4, lxml, openai, groq, fpdf, yaml, whois, dns, certifi, multipart, httpx, feedparser' >/dev/null 2>&1; then
  WHEELS_DIR="$DIR/wheels"
  if [ ! -d "$WHEELS_DIR" ]; then WHEELS_DIR="$DIR/../wheels"; fi
  if [ -d "$WHEELS_DIR" ]; then
    echo "Installing from USB wheels (offline mode)..."
    .venv/bin/pip install --quiet --no-index --find-links="$WHEELS_DIR" -r requirements.txt
  else
    echo "Installing from internet..."
    .venv/bin/pip install --quiet -r requirements.txt
  fi
  echo "Setup complete."
fi

echo ""
echo "Starting dashboard at http://localhost:7890"
echo "Press Ctrl+C to stop."
echo ""

exec .venv/bin/python dashboard/server.py
