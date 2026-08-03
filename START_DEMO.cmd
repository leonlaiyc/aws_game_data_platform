@echo off
setlocal
cd /d "%~dp0"

if not exist "infra\.venv\Scripts\python.exe" (
  echo [ERROR] Python environment not found: infra\.venv\Scripts\python.exe
  echo Run the project setup first, then try again.
  pause
  exit /b 1
)

echo Starting LEON AWS operation demo...
echo The browser will open at http://127.0.0.1:8787
echo Keep this window open while using the demo. Press Ctrl+C to stop.
"infra\.venv\Scripts\python.exe" "demo_console\server.py"

