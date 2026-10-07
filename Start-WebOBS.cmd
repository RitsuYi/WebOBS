@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 monitor.py
) else (
    python monitor.py
)
pause
