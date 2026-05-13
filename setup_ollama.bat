@echo off
chcp 65001 >nul
echo ========================================
echo   桌宠大模型配置工具
echo ========================================
echo.

echo [1/4] 检查 Ollama 安装状态...
where ollama >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Ollama 已安装
    goto check_model
) else (
    echo ❌ Ollama 未安装
    echo.
    echo 正在下载 Ollama 安装程序...
    start https://ollama.com/download/windows
    echo.
    echo ✅ 已打开 Ollama 下载页面
    echo.
    echo 请按以下步骤操作：
    echo 1. 下载并安装 Ollama
    echo 2. 安装完成后，重新运行此脚本
    echo.
    pause
    exit /b
)

:check_model
echo.
echo [2/4] 检查 Llama 3.2 模型...
ollama list | findstr "llama3.2" >nul
if %errorlevel% equ 0 (
    echo ✅ Llama 3.2 模型已存在
    goto test_model
) else (
    echo ❌ Llama 3.2 模型未找到
    echo.
    echo 正在下载 Llama 3.2 (3B 版本，约 2GB)...
    echo 这可能需要几分钟，请耐心等待...
    echo.
    ollama pull llama3.2:3b
    if %errorlevel% equ 0 (
        echo ✅ 模型下载完成
    ) else (
        echo ❌ 模型下载失败
        pause
        exit /b
    )
)

:test_model
echo.
echo [3/4] 测试模型连接...
echo.
echo 正在测试："你好，打开记事本"
echo.

ollama run llama3.2:3b "你好，打开记事本" --no-stream > test_output.txt 2>&1

if %errorlevel% equ 0 (
    echo ✅ 测试成功！
    echo.
    echo 模型回复：
    type test_output.txt
    del test_output.txt
) else (
    echo ❌ 测试失败
    pause
    exit /b
)

:install_python_lib
echo.
echo [4/4] 安装 Python 库...
pip install ollama -q
if %errorlevel% equ 0 (
    echo ✅ ollama 库已安装
) else (
    echo ❌ ollama 库安装失败
    pause
    exit /b
)

echo.
echo ========================================
echo ✅ 配置完成！
echo ========================================
echo.
echo 现在可以运行桌宠了：
echo   python desktop_pet.py
echo.
pause
