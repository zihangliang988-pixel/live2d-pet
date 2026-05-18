@echo off
chcp 65001 >nul
echo ============================================
echo 🦊 桌宠快捷方式生成器
echo ============================================
echo.

set PYTHON_EXE=C:\Users\46282\AppData\Local\Programs\Python\Python313\python.exe
set PYTHON_SCRIPT=D:\桌宠\pet.py
set ICON_PATH=C:\Users\46282\Pictures\Screenshots\屏幕截图 2026-05-18 105607.png
set DESKTOP_PATH=C:\Users\46282\Desktop
set SHORTCUT_PATH=%DESKTOP_PATH%\桌宠 - 仙狐.lnk

echo 📍 目标程序：%PYTHON_EXE% %PYTHON_SCRIPT%
echo 🎨 图标路径：%ICON_PATH%
echo 📁 快捷方式位置：%SHORTCUT_PATH%
echo.

REM 检查图标是否存在
if not exist "%ICON_PATH%" (
    echo ❌ 图标文件不存在：%ICON_PATH%
    pause
    exit /b 1
)

echo ✅ 图标文件存在
echo.

REM 创建快捷方式
powershell -Command "
$WScript = New-Object -ComObject WScript.Shell
$Shortcut = $WScript.CreateShortcut('%SHORTCUT_PATH%')
$Shortcut.TargetPath = '%PYTHON_EXE% %PYTHON_SCRIPT%'
$Shortcut.WorkingDirectory = 'D:\桌宠'
$Shortcut.Description = '桌宠 - 仙狐助手'
$Shortcut.IconLocation = '%ICON_PATH%'
$Shortcut.WindowStyle = 1
$Shortcut.Save()
"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✨ 快捷方式创建成功！
    echo 📍 位置：%SHORTCUT_PATH%
    echo 🎨 图标：%ICON_PATH%
    echo.
    echo 💡 现在可以在桌面上找到「桌宠 - 仙狐」快捷方式啦~
) else (
    echo.
    echo ❌ 创建失败
)

pause
