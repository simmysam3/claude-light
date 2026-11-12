# claude-light (Windows): stop the watcher and the ball, then start the watcher again.
#   restart.ps1            stop and start
#   restart.ps1 -StopOnly  stop only (used by uninstall.ps1)
param([switch]$StopOnly)
$R = Join-Path $HOME '.claude-light'
$mine = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -like '*.claude-light*' -and
    ($_.CommandLine -like '*lightd.py*' -or $_.CommandLine -like '*ball.ps1*')
}
foreach ($p in $mine) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
if ($StopOnly) { return }
$pythonw = (Get-Content -LiteralPath (Join-Path $R 'python.txt') -ErrorAction Stop | Select-Object -First 1).Trim()
Start-Process -FilePath $pythonw -ArgumentList ('"' + (Join-Path $R 'src\lightd.py') + '"') -WorkingDirectory $R -WindowStyle Hidden
Write-Host 'claude-light: started'
