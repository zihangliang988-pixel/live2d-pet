$WScript = New-Object -ComObject WScript.Shell
$Shortcut = $WScript.CreateShortcut("C:\Users\46282\Desktop\桌宠 - 仙狐.lnk")
$Shortcut.TargetPath = "C:\Users\46282\AppData\Local\Programs\Python\Python313\python.exe D:\桌宠\pet.py"
$Shortcut.WorkingDirectory = "D:\桌宠"
$Shortcut.Description = "桌宠 - 仙狐助手"
$Shortcut.IconLocation = "C:\Users\46282\Pictures\Screenshots\屏幕截图 2026-05-18 105607.png"
$Shortcut.WindowStyle = 1
$Shortcut.Save()

Write-Host "快捷方式创建成功！"
Write-Host "位置：C:\Users\46282\Desktop\桌宠 - 仙狐.lnk"
