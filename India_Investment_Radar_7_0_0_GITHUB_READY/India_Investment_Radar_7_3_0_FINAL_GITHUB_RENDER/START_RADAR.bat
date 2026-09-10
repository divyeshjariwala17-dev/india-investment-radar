@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" launcher.py
  exit /b 0
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" launcher.py
  exit /b %errorlevel%
)
echo India Investment Radar environment is missing.
echo Run REPAIR_INSTALLATION.bat or reinstall/update the PC package.
pause
exit /b 1
