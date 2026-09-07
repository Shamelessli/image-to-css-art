@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 未找到 .venv 虚拟环境，请先执行：
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r skills\image-to-css-art\requirements.txt tkinterdnd2 pyinstaller
    pause
    exit /b 1
)
echo [1/2] 安装 pyinstaller ...
".venv\Scripts\python.exe" -m pip install pyinstaller tkinterdnd2
if errorlevel 1 (
    echo pyinstaller 安装失败
    pause
    exit /b 1
)
echo [2/2] 打包 ImageToCssArt.exe ...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --onefile --noconsole --name ImageToCssArt --paths "skills\image-to-css-art\scripts" --collect-all tkinterdnd2 gui.py
if errorlevel 1 (
    echo 打包失败
    pause
    exit /b 1
)
echo 完成：dist\ImageToCssArt.exe
pause