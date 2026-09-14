@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Python environment missing. Follow README.md to install first.
  pause
  exit /b 1
)
start "StudyCopilot" ".venv\Scripts\pythonw.exe" -m studycopilot
