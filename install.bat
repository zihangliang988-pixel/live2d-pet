@echo off
chcp 65001 >nul
echo ========================================
echo 🐾 桌宠助手 - 安装脚本
echo ========================================
echo.

echo [1/3] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)
echo ✅ Python 已安装
echo.

echo [2/3] 安装依赖...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)
echo ✅ 依赖已安装
echo.

echo [3/3] 创建快捷方式...
echo 正在创建桌面快捷方式...
powershell -Command "^$WshShell = New-Object -ComObject WScript.Shell; ^$Shortcut = ^$WshShell.CreateShortcut(^\"%USERPROFILE%\Desktop\桌宠助手.lnk^\"); ^$Shortcut.TargetPath = ^\"%~f0^\"; ^$Shortcut.WorkingDirectory = ^\"%~dp0^\"; ^$Shortcut.Save()"
echo ✅ 快捷方式已创建
echo.

echo ========================================
echo 🎉 安装完成！
echo ========================================
echo.
echo 双击桌面上的"桌宠助手"即可启动
echo.
pause
