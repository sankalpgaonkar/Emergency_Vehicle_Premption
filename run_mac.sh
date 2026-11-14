#!/bin/bash
# One-click setup + run for macOS / Linux. First run installs everything (~5-10 min), later runs start in seconds.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r demo_app/requirements.txt
else
  source .venv/bin/activate
fi
echo "Open http://127.0.0.1:5050 in your browser (Ctrl+C to stop)"
python demo_app/app.py
