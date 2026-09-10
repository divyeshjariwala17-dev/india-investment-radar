@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto :missing
".venv\Scripts\python.exe" configure_google.py
pause
exit /b %errorlevel%
:missing
echo Environment missing. Run the PC installer first.
pause
exit /b 1
