$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\Dev Server Manager.lnk")
$Shortcut.TargetPath = "$ScriptDir\start.bat"
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Save()
Write-Host "Shortcut created at $DesktopPath\Dev Server Manager.lnk"
