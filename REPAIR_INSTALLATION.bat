@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Local Python environment is missing. Re-run the FINAL PC installer package.
 pause
 exit /b 1
)
echo Updating core dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo Installing/updating optional Google integration...
".venv\Scripts\python.exe" -m pip install -r requirements_google.txt
if errorlevel 1 echo WARNING: Google API packages could not be installed. Core Radar remains usable; Google Drive Desktop mode still works.
".venv\Scripts\python.exe" verify_install.py
if errorlevel 1 goto :fail
echo.
echo REPAIR COMPLETE. Your data folder was not deleted.
pause
exit /b 0
:fail
echo.
echo REPAIR FAILED. Your saved data has NOT been deleted.
pause
exit /b 1
