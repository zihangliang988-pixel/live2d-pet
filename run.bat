@echo off
chcp 65001 >nul
title Senko 桌宠 v9.1
cls
echo ================================================
echo   [Senko] 仙狐桌宠 v9.1
echo   可爱 Live2D 桌宠 + AI 对话 + 文件管理
echo ================================================
echo.

cd /d "%~dp0"

:: 检查 Ollama
ollama list >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Ollama 未运行，正在启动...
    start ollama serve
    timeout /t 5 /nobreak >nul
)

echo [INFO] 正在启动 Senko，请稍候...
echo.

python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARN] 启动失败，查看错误日志...
    if exist error.log (
        type error.log
    )
    echo.
    echo [INFO] 尝试安装依赖...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install PyQtWebEngine -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
    echo [INFO] 再次启动...
    python main.py
)

pause
