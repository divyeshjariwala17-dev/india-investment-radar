@echo off
setlocal EnableExtensions
set "TARGET=%LOCALAPPDATA%\India_Investment_Radar"
set "BACKUP=%USERPROFILE%\Documents\India_Investment_Radar_Final_Backup"
cls
echo INDIA INVESTMENT RADAR - SAFE UNINSTALL
echo ========================================
echo.
if not exist "%TARGET%" (
  echo Radar is not installed in the normal location.
  pause
  exit /b 0
)
echo Choose what to remove:
echo   1 = Remove application only. KEEP data/backups in Documents backup folder.
echo   2 = Remove application + local cache/data after making a Documents backup.
echo   3 = Remove EVERYTHING local, including data/backups. NO automatic recovery.
echo   4 = Cancel
set /p CH=Choice [1-4]: 
if "%CH%"=="4" exit /b 0
if not "%CH%"=="1" if not "%CH%"=="2" if not "%CH%"=="3" goto BAD

if exist "%TARGET%\data\.runtime.json" (
  for /f %%P in ('py -c "import json,pathlib; p=pathlib.Path(r'%TARGET%\data\.runtime.json'); d=json.loads(p.read_text(encoding='utf-8')); print(int(d.get('pid',0)))" 2^>nul') do if not "%%P"=="0" taskkill /PID %%P /F >nul 2>nul
)

if "%CH%"=="1" goto BACKUPKEEP
if "%CH%"=="2" goto BACKUPKEEP
if "%CH%"=="3" goto REMOVEALL

:BACKUPKEEP
if exist "%BACKUP%" rd /s /q "%BACKUP%" >nul 2>nul
mkdir "%BACKUP%" >nul 2>nul
if exist "%TARGET%\data" robocopy "%TARGET%\data" "%BACKUP%\data" /E /XF .runtime.json >nul
if exist "%TARGET%\backups" robocopy "%TARGET%\backups" "%BACKUP%\backups" /E >nul
echo Safety copy created at:
echo %BACKUP%
if "%CH%"=="1" (
  echo Application files will be removed. Your safety copy remains in Documents.
)
rd /s /q "%TARGET%"
goto DONE

:REMOVEALL
set /p CONF=Type DELETE to permanently remove the local Radar and its local data: 
if /I not "%CONF%"=="DELETE" exit /b 0
rd /s /q "%TARGET%"
if exist "%BACKUP%" rd /s /q "%BACKUP%"
goto DONE

:BAD
echo Invalid choice.
pause
exit /b 1

:DONE
echo.
echo Local Radar removal completed.
echo Online/cloud deployments are separate and are NOT deleted by this local uninstaller.
pause
