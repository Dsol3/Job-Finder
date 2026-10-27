@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
title job_finder - setup

echo.
echo   job_finder setup (Windows)
echo   ==========================
echo.

rem --- find a real Python 3.11+ (ignore the Microsoft Store stub) ----------
set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    echo   [X] Python is not installed.
    echo.
    echo       Install it with this one command:
    echo           winget install -e --id Python.Python.3.12
    echo.
    echo       Or download from https://www.python.org/downloads/
    echo       and TICK "Add python.exe to PATH" on the first screen.
    echo.
    echo       Then close this window, open a NEW one, and run setup.bat again.
    echo.
    pause
    exit /b 1
)

%PY% -c "import sys;raise SystemExit(0 if sys.version_info>=(3,11) else 3)"
if errorlevel 1 (
    echo   [X] Python is too old. Version 3.11 or newer is required.
    echo       Upgrade with:  winget upgrade -e --id Python.Python.3.12
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo   [ok] found %%v
echo.

rem --- config ------------------------------------------------------------
if not exist "config.toml" (
    copy /y "config.example.toml" "config.toml" >nul
    echo   [ok] created config.toml
)
echo.

rem --- telegram wizard ---------------------------------------------------
%PY% -m job_finder --setup-telegram %*
if errorlevel 1 (
    echo.
    echo   Setup did not finish. Nothing was saved.
    pause
    exit /b 1
)

echo.
echo   Checking everything end to end...
echo.
%PY% -m job_finder --doctor
echo.
echo   Next: double-click run-watcher.bat to start watching for jobs.
echo.
pause
