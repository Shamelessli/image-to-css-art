@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 未找到 .venv 虚拟环境，请先在项目目录执行：
    echo     python -m venv .venv
    pause
    exit /b 1
)
".venv\Scripts\python.exe" gui.py
if errorlevel 1 pause