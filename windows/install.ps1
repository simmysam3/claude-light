# claude-light installer for Windows. From a clone of the repo:
#   powershell -NoProfile -ExecutionPolicy Bypass -File windows\install.ps1
# Safe to run again (upgrades in place, keeps your settings). Needs Python 3 (python.org or
# `winget install Python.Python.3.12`); no admin rights.
$ErrorActionPreference = 'Stop'
$Src = Split-Path -Parent $PSScriptRoot
$R = Join-Path $HOME '.claude-light'
if ($env:CLAUDE_CONFIG_DIR) { $Settings = Join-Path $env:CLAUDE_CONFIG_DIR 'settings.json' }
else { $Settings = Join-Path $HOME '.claude\settings.json' }

function Find-Python {
    # A real interpreter, not the Microsoft Store placeholder python.exe (it prints nothing).
    foreach ($try in @(@('py', '-3'), @('python'), @('python3'))) {
        $exe = $try[0]; $rest = @($try | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $path = & $exe @rest -c "import sys; print(sys.executable)" 2>$null
            if ($path -and (Test-Path -LiteralPath $path.Trim())) { return $path.Trim() }
        } catch {}
    }
    return $null
}

$python = Find-Python
if (-not $python) { Write-Error 'claude-light needs Python 3: install it from python.org or run  winget install Python.Python.3.12' }
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) { $pythonw = $python }

Write-Host '1/6 tests'
Push-Location $Src
try { & $python -m unittest discover -s tests -q; if ($LASTEXITCODE -ne 0) { throw 'the tests failed; nothing was installed' } }
finally { Pop-Location }

Write-Host "2/6 files -> $R"
foreach ($d in @('src', 'windows', 'bin', 'state')) { New-Item -ItemType Directory -Force -Path (Join-Path $R $d) | Out-Null }
Copy-Item -Force (Join-Path $Src 'src\*.py') (Join-Path $R 'src')
Copy-Item -Force (Join-Path $Src 'windows\*.ps1') (Join-Path $R 'windows')
Copy-Item -Force (Join-Path $Src 'README.md') $R
Set-Content -LiteralPath (Join-Path $R 'python.txt') -Value $pythonw -Encoding ASCII

Write-Host '3/6 the bong'
& $python (Join-Path $R 'src\bong.py') (Join-Path $R 'bong.wav')

Write-Host '4/6 Claude Code hooks'
& $python (Join-Path $R 'src\settings_hooks.py') add-exec $pythonw $Settings
if ($LASTEXITCODE -ne 0) { throw 'could not add the hooks (see the message above); fix settings.json and run again' }

Write-Host '5/6 the claude-light command'
$cmd = @"
@echo off
if /i "%~1"=="restart" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.claude-light\windows\restart.ps1"
  exit /b
)
"$python" "%USERPROFILE%\.claude-light\src\lightctl.py" %*
"@
Set-Content -LiteralPath (Join-Path $R 'bin\claude-light.cmd') -Value $cmd -Encoding ASCII

Write-Host '6/6 start at sign-in (Startup folder) and start now'
$startup = [Environment]::GetFolderPath('Startup')
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $startup 'claude-light.lnk'))
$link.TargetPath = $pythonw
$link.Arguments = '"' + (Join-Path $R 'src\lightd.py') + '"'
$link.WorkingDirectory = $R
$link.Description = 'claude-light: a stop light for Claude Code'
$link.Save()
& (Join-Path $R 'windows\restart.ps1')

Write-Host ''
Write-Host 'claude-light is installed: a dot in the system tray holds every setting.'
Write-Host "Try it: $R\bin\claude-light.cmd preview yellow"
