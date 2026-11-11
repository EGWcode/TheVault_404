@echo off
rem The Pirate Cove - Windows installer. Created by Ethan Williams 11/9/26
rem Double-click this file. It makes a Python virtual environment (venv\),
rem installs the requirements, writes .env, sets up the PostgreSQL tables
rem and offers to create an admin. Safe to run again.

setlocal
cd /d "%~dp0"
title The Pirate Cove - Installer
echo === The Pirate Cove installer ===

rem Find Python 3.10 or newer: the "py" launcher first, then "python"
set "PY="
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python 3.10 or newer is needed.
    echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH",
    echo then run this installer again.
    start "" "https://www.python.org/downloads/"
    goto :fail
)

rem Make (or repair) the virtual environment
venv\Scripts\python.exe -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo Creating the virtual environment ^(venv\^)...
    if exist venv rmdir /s /q venv
    %PY% -m venv venv
    if errorlevel 1 goto :fail
)

echo Installing requirements (this can take a minute)...
venv\Scripts\python.exe -m pip install --quiet --upgrade pip
venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :fail

venv\Scripts\python.exe scripts\install_helper.py
if errorlevel 1 goto :fail

echo.
echo Done! Double-click "Launch Pirate Cove.bat" to start the site.
pause
exit /b 0

:fail
echo.
echo Setup did not finish. Fix the problem above and run the installer again.
pause
exit /b 1
