@echo off
cd /d "%~dp0"
if not exist data mkdir data
start "" "%CD%\data"
