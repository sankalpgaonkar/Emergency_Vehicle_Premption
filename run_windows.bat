@echo off
REM One-click setup + run for Windows. First run installs everything (~5-10 min).
cd /d "%~dp0"
if not exist .venv (
  py -3.11 -m venv .venv || python -m venv .venv
  call .venv\Scripts\activate
  python -m pip install --upgrade pip
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip install -r demo_app\requirements.txt
) else (
  call .venv\Scripts\activate
)
echo Open http://127.0.0.1:5050 in your browser (Ctrl+C to stop)
python demo_app\app.py
