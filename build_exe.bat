@echo off
echo ========================================
echo ServerDock - 构建 EXE 启动器
echo ========================================
echo.

REM 检查是否安装了 PyInstaller
py -3 -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [1/3] 安装 PyInstaller...
    py -3 -m pip install pyinstaller
) else (
    echo [1/3] PyInstaller 已安装
)

echo.
echo [2/3] 构建 EXE 文件...
echo 这可能需要几分钟，请耐心等待...
echo.

REM 使用 PyInstaller 构建
py -3 -m PyInstaller ^
    --name=ServerDock ^
    --onefile ^
    --windowed ^
    --icon=NONE ^
    --add-data="index.html;." ^
    --add-data="config;config" ^
    --hidden-import=uvicorn.logging ^
    --hidden-import=uvicorn.loops ^
    --hidden-import=uvicorn.loops.auto ^
    --hidden-import=uvicorn.protocols ^
    --hidden-import=uvicorn.protocols.http ^
    --hidden-import=uvicorn.protocols.http.auto ^
    --hidden-import=uvicorn.protocols.websockets ^
    --hidden-import=uvicorn.protocols.websockets.auto ^
    --hidden-import=uvicorn.lifespan ^
    --hidden-import=uvicorn.lifespan.on ^
    ServerDock.py

if errorlevel 1 (
    echo.
    echo ❌ 构建失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 清理临时文件...
rmdir /s /q build 2>nul
del ServerDock.spec 2>nul

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
