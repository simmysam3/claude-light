# claude-light uninstaller for Windows: stops it, removes its Startup shortcut and its hooks, deletes
# %USERPROFILE%\.claude-light.  -KeepHooks leaves the hooks (they do nothing without .claude-light).
#   powershell -NoProfile -ExecutionPolicy Bypass -File windows\uninstall.ps1 [-KeepHooks]
param([switch]$KeepHooks)
$R = Join-Path $HOME '.claude-light'
if ($env:CLAUDE_CONFIG_DIR) { $Settings = Join-Path $env:CLAUDE_CONFIG_DIR 'settings.json' }
else { $Settings = Join-Path $HOME '.claude\settings.json' }

$restart = Join-Path $R 'windows\restart.ps1'
if (-not (Test-Path -LiteralPath $restart)) { $restart = Join-Path $PSScriptRoot 'restart.ps1' }
& $restart -StopOnly
Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath('Startup')) 'claude-light.lnk') -ErrorAction SilentlyContinue

if (-not $KeepHooks) {
    $python = $null
    $saved = Join-Path $R 'python.txt'
    if (Test-Path -LiteralPath $saved) { $python = (Get-Content -LiteralPath $saved | Select-Object -First 1).Trim() }
    if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
    $hooks = Join-Path $R 'src\settings_hooks.py'
    if (-not (Test-Path -LiteralPath $hooks)) { $hooks = Join-Path (Split-Path -Parent $PSScriptRoot) 'src\settings_hooks.py' }
    & $python $hooks remove $Settings
}
Remove-Item -LiteralPath $R -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'claude-light removed (a backup of your settings is next to it: settings.json.claude-light-backup)'
