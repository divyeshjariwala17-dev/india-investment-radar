@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Python environment is missing. Run REPAIR_INSTALLATION.bat.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" verify_install.py
set RC=%errorlevel%
echo.
if "%RC%"=="0" (echo ALL OFFLINE INSTALLATION CHECKS PASSED.) else (echo VERIFY FAILED - see details above.)
pause
exit /b %RC%
