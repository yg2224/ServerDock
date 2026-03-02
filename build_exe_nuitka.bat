@echo off
echo ========================================
echo ServerDock - 使用 Nuitka 构建轻量 EXE
echo ========================================
echo.
echo 注意：Nuitka 构建速度较慢但生成的 EXE 更小更快
echo.

REM 检查是否安装了 Nuitka
py -3 -m pip show nuitka >nul 2>&1
if errorlevel 1 (
    echo [1/3] 安装 Nuitka...
    py -3 -m pip install nuitka
) else (
    echo [1/3] Nuitka 已安装
)

echo.
echo [2/3] 构建 EXE 文件...
echo 这可能需要 10-20 分钟，请耐心等待...
echo.

REM 使用 Nuitka 构建
py -3 -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-disable-console ^
    --output-dir=dist ^
    --output-filename=ServerDock.exe ^
    --include-data-file=index.html=index.html ^
    --include-data-dir=config=config ^
    --enable-plugin=anti-bloat ^
    --assume-yes-for-downloads ^
    ServerDock.py

if errorlevel 1 (
    echo.
    echo ❌ 构建失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 完成！
echo.
echo ========================================
echo ✅ 构建完成！
echo ========================================
echo.
echo EXE 文件位置: dist\ServerDock.exe
echo 文件大小:
dir dist\ServerDock.exe | find "ServerDock.exe"
echo.
echo 使用方法：
echo 1. 双击 dist\ServerDock.exe 启动
echo 2. 或者将 ServerDock.exe 复制到任意位置使用
echo.
pause
