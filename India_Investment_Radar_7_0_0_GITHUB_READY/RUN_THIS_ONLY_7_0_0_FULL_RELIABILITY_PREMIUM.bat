@echo off
setlocal EnableExtensions EnableDelayedExpansion
title INDIA INVESTMENT RADAR 7.0.0 - FULL RELIABILITY PREMIUM
color 1F

set "TARGET=%LOCALAPPDATA%\India_Investment_Radar"
set "PAYLOAD=%~dp0payload"
set "SAVE=%TEMP%\India_Investment_Radar_UserData_700"
set "PY_CMD="

echo.
echo ======================================================================
echo      INDIA INVESTMENT RADAR 7.0.0 - FULL RELIABILITY PREMIUM
echo ======================================================================
echo.
echo Full functions. Daily Recommendations. Visible progress. Configurable UI.
echo Existing portfolio/settings/data/backups are preserved during upgrade.
echo.

if not exist "%PAYLOAD%\app.py" goto BADPACKAGE
if not exist "%PAYLOAD%\verify_install.py" goto BADPACKAGE
if not exist "%PAYLOAD%\money_optimizer.py" goto BADPACKAGE
if not exist "%PAYLOAD%\ui_config.py" goto BADPACKAGE
if not exist "%PAYLOAD%\source_manager.py" goto BADPACKAGE
if not exist "%PAYLOAD%\daily_recommendations.py" goto BADPACKAGE
if not exist "%PAYLOAD%\launcher_mobile.py" goto BADPACKAGE
findstr /C:"7.0.0 FULL RELIABILITY PREMIUM WEB-READY" "%PAYLOAD%\config.json" >nul || goto BADPACKAGE
findstr /C:"Daily Recommendations" "%PAYLOAD%\app.py" >nul || goto BADPACKAGE
findstr /C:"run_update_pipeline" "%PAYLOAD%\app.py" >nul || goto BADPACKAGE
findstr /C:"build_ui_css" "%PAYLOAD%\app.py" >nul || goto BADPACKAGE
findstr /C:"find_free_port" "%PAYLOAD%\launcher.py" >nul || goto BADPACKAGE

where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py"
if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
  echo ERROR: Python 3.11 or newer is required for the first installation.
  echo Install Python from python.org with PATH or the Python launcher enabled.
  pause
  exit /b 1
)

%PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo ERROR: Python 3.11 or newer is required.
  pause
  exit /b 1
)

REM Stop only the previously recorded Radar process.
if exist "%TARGET%\data\.runtime.json" (
  for /f %%P in ('%PY_CMD% -c "import json,pathlib; p=pathlib.Path(r'%TARGET%\data\.runtime.json'); d=json.loads(p.read_text(encoding='utf-8')); print(int(d.get('pid',0)))" 2^>nul') do (
    if not "%%P"=="0" taskkill /PID %%P /F >nul 2>nul
  )
)
timeout /t 1 /nobreak >nul

REM Save user-created persistent data and backups only.
if exist "%SAVE%" rd /s /q "%SAVE%" >nul 2>nul
mkdir "%SAVE%" >nul 2>nul
if exist "%TARGET%\data" robocopy "%TARGET%\data" "%SAVE%\data" /E /XF .runtime.json >nul
if exist "%TARGET%\backups" robocopy "%TARGET%\backups" "%SAVE%\backups" /E >nul

REM Clean old program code so stale modules cannot survive.
echo Removing previous program files...
if exist "%TARGET%" rd /s /q "%TARGET%"
if exist "%TARGET%" (
  echo ERROR: Windows could not remove the old Radar folder.
  echo Close any Radar/Python window and run THIS SAME installer again.
  pause
  exit /b 1
)
mkdir "%TARGET%" >nul 2>nul

REM Copy new verified payload.
echo Copying India Investment Radar 7.0.0...
robocopy "%PAYLOAD%" "%TARGET%" /E /IS /IT >nul
if errorlevel 8 goto FAIL

REM Restore user data/backups after program copy.
if exist "%SAVE%\data" robocopy "%SAVE%\data" "%TARGET%\data" /E /XF .runtime.json >nul
if exist "%SAVE%\backups" robocopy "%SAVE%\backups" "%TARGET%\backups" /E >nul

findstr /C:"7.0.0 FULL RELIABILITY PREMIUM WEB-READY" "%TARGET%\config.json" >nul || goto FAIL
findstr /C:"Daily Recommendations" "%TARGET%\app.py" >nul || goto FAIL

REM Fresh private Python environment for Radar.
echo Creating fresh local Python environment...
%PY_CMD% -m venv "%TARGET%\.venv"
if errorlevel 1 goto FAIL

set "PIP_DISABLE_PIP_VERSION_CHECK=1"
echo Installing locked application packages...
"%TARGET%\.venv\Scripts\python.exe" -m pip install -r "%TARGET%\requirements.txt"
if errorlevel 1 goto FAIL

for /d /r "%TARGET%" %%D in (__pycache__) do @if exist "%%D" rd /s /q "%%D" >nul 2>nul
del /s /q "%TARGET%\*.pyc" >nul 2>nul

echo Running full installation verification...
pushd "%TARGET%"
"%TARGET%\.venv\Scripts\python.exe" "%TARGET%\verify_install.py"
if errorlevel 1 (
  popd
  goto FAIL
)
popd

REM Create Desktop and Start Menu shortcuts.
echo Creating shortcuts...
set "VBS=%TEMP%\radar700_shortcut_%RANDOM%.vbs"
>"%VBS%" echo Set sh = CreateObject("WScript.Shell")
>>"%VBS%" echo target = "%TARGET%"
>>"%VBS%" echo exe = target ^& "\.venv\Scripts\pythonw.exe"
>>"%VBS%" echo launcher = target ^& "\launcher.py"
>>"%VBS%" echo mobile = target ^& "\launcher_mobile.py"
>>"%VBS%" echo icon = target ^& "\India_Investment_Radar.ico"
>>"%VBS%" echo Set sc = sh.CreateShortcut(sh.SpecialFolders("Desktop") ^& "\India Investment Radar.lnk")
>>"%VBS%" echo sc.TargetPath = exe
>>"%VBS%" echo sc.Arguments = Chr(34) ^& launcher ^& Chr(34)
>>"%VBS%" echo sc.WorkingDirectory = target
>>"%VBS%" echo If CreateObject("Scripting.FileSystemObject").FileExists(icon) Then sc.IconLocation = icon
>>"%VBS%" echo sc.Save
>>"%VBS%" echo Set sc = sh.CreateShortcut(sh.SpecialFolders("Programs") ^& "\India Investment Radar.lnk")
>>"%VBS%" echo sc.TargetPath = exe
>>"%VBS%" echo sc.Arguments = Chr(34) ^& launcher ^& Chr(34)
>>"%VBS%" echo sc.WorkingDirectory = target
>>"%VBS%" echo If CreateObject("Scripting.FileSystemObject").FileExists(icon) Then sc.IconLocation = icon
>>"%VBS%" echo sc.Save
>>"%VBS%" echo Set sc = sh.CreateShortcut(sh.SpecialFolders("Desktop") ^& "\India Investment Radar - Phone Same WiFi.lnk")
>>"%VBS%" echo sc.TargetPath = exe
>>"%VBS%" echo sc.Arguments = Chr(34) ^& mobile ^& Chr(34)
>>"%VBS%" echo sc.WorkingDirectory = target
>>"%VBS%" echo If CreateObject("Scripting.FileSystemObject").FileExists(icon) Then sc.IconLocation = icon
>>"%VBS%" echo sc.Save
cscript //nologo "%VBS%"
if errorlevel 1 goto FAIL
del /q "%VBS%" >nul 2>nul

if exist "%SAVE%" rd /s /q "%SAVE%" >nul 2>nul

echo.
echo ======================================================================
echo             INSTALLATION COMPLETE - VERIFIED 7.0.0
echo ======================================================================
echo.
echo Normal use:
echo   1. Open India Investment Radar desktop shortcut.
echo   2. Run DAILY UPDATE when fresh data is needed.
echo   3. Review Daily Recommendations.
echo.
echo Phone on SAME WiFi:
echo   Use India Investment Radar - Phone Same WiFi shortcut.
echo.
echo Opening Radar now...
start "" "%TARGET%\.venv\Scripts\pythonw.exe" "%TARGET%\launcher.py"
pause
exit /b 0

:BADPACKAGE
echo.
echo WRONG OR INCOMPLETE 7.0.0 PACKAGE. Installation stopped safely.
pause
exit /b 1

:FAIL
echo.
echo ======================================================================
echo                         INSTALLATION FAILED
echo ======================================================================
echo.
echo Existing user data was preserved temporarily at:
echo %SAVE%
echo.
echo Take a screenshot of THIS window if help is needed.
pause
exit /b 1
