# Set Python 3.11 as default version
$py311Path = "C:\Users\26774\AppData\Local\Programs\Python\Python311\"
$py311Scripts = "C:\Users\26774\AppData\Local\Programs\Python\Python311\Scripts\"

# Get current user PATH
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')

# Remove existing Python 3.11 paths
$pathArray = $userPath -split ';' | Where-Object {
    $_ -ne $py311Path -and
    $_ -ne $py311Scripts -and
    $_ -ne ($py311Path.TrimEnd('\')) -and
    $_ -ne ($py311Scripts.TrimEnd('\')) -and
    $_ -ne ''
}

# Add Python 3.11 paths to the front
$newPath = $py311Path + $py311Scripts + ($pathArray -join ';')

# Set new PATH
[Environment]::SetEnvironmentVariable('Path', $newPath, 'User')

Write-Host "Python 3.11 set as default (highest priority in user PATH)"
Write-Host "Please restart your command prompt for changes to take effect"
