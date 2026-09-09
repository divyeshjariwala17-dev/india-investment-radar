@echo off
setlocal
set "TARGET=%LOCALAPPDATA%\India_Investment_Radar"
if not exist "%TARGET%\launcher_mobile.py" (
  echo India Investment Radar is not installed yet.
  echo Run RUN_THIS_ONLY_7_0_0_FULL_RELIABILITY_PREMIUM.bat first.
  pause
  exit /b 1
)
start "" "%TARGET%\.venv\Scripts\pythonw.exe" "%TARGET%\launcher_mobile.py"
exit /b 0
