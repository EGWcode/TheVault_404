@echo off
rem The Pirate Cove - Windows launcher. Created by Ethan Williams 11/9/26
rem Double-click to start the site and open it in your browser.
rem Keep this window open while using the site; close it to stop.

setlocal
cd /d "%~dp0"
title The Pirate Cove

venv\Scripts\python.exe -c "import flask" >nul 2>nul
if errorlevel 1 goto :notinstalled
if not exist .env goto :notinstalled

venv\Scripts\python.exe scripts\run_local.py
if errorlevel 1 (
    echo The site stopped with an error ^(see above^).
    pause
)
exit /b

:notinstalled
echo The Pirate Cove isn't installed yet. Double-click install.bat first.
pause
exit /b 1
