# Durable never-stop factory launcher for PTCG AI Battle Challenge.
# Restarts aggressive_loop.py if it exits. Logs to dist/factory_launcher.log
$ErrorActionPreference = "Continue"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
# Prefer script-relative project root (kaggle_pokemon)
$Proj = Split-Path $PSScriptRoot -Parent
$VenvPy = Join-Path (Split-Path $Proj -Parent) ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
  $VenvPy = "E:\PTCG_AI_Battle_Challenge\.venv\Scripts\python.exe"
}
$LogDir = Join-Path $Proj "dist"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LauncherLog = Join-Path $LogDir "factory_launcher.log"
$OutLog = Join-Path $LogDir "aggressive_loop.out.log"
$ErrLog = Join-Path $LogDir "aggressive_loop.err.log"

function Write-Launch([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Add-Content -Path $LauncherLog -Value $line -Encoding UTF8
  Write-Output $line
}

Write-Launch "factory launcher start proj=$Proj py=$VenvPy"
Set-Location $Proj
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONUTF8 = "1"

while ($true) {
  Write-Launch "starting aggressive_loop.py"
  $p = Start-Process -FilePath $VenvPy `
    -ArgumentList @("-u", "scripts\aggressive_loop.py", "--poll-seconds", "30") `
    -WorkingDirectory $Proj `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru -WindowStyle Hidden
  Write-Launch "pid=$($p.Id)"
  Wait-Process -Id $p.Id
  $code = $p.ExitCode
  Write-Launch "aggressive_loop exited code=$code — restart in 5s"
  Start-Sleep -Seconds 5
}
