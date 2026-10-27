@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
title job_finder - watching Reddit

set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python not found. Run setup.bat first.
    pause
    exit /b 1
)

echo   Watching for new posts. Leave this window open. Ctrl-C to stop.
echo.
%PY% -m job_finder --loop --quiet
echo.
echo   Watcher stopped.
pause
