@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. Run setup first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "scripts\start.py"
if errorlevel 1 pause
