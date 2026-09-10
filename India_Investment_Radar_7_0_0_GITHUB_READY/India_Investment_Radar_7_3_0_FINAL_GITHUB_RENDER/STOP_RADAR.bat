@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
if not exist "data\.runtime.json" (
 echo No saved Radar runtime was found.
 pause
 exit /b 0
)
for /f "tokens=2 delims=:," %%A in ('findstr /i "\"pid\"" "data\.runtime.json"') do set PID=%%A
set PID=!PID: =!
if defined PID taskkill /PID !PID! /F >nul 2>&1
del /q "data\.runtime.json" >nul 2>&1
echo Radar local server stopped.
pause
