# Detached single-instance factory launcher (E: workspace only).
# Usage: powershell -File scripts\start_factory.ps1
$ErrorActionPreference = "Stop"
$Proj = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
# scripts/ is under kaggle_pokemon → parent is kaggle_pokemon
$Root = Split-Path $PSScriptRoot -Parent
$Py = Join-Path (Split-Path $Root -Parent) ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = Join-Path $Root "..\.venv\Scripts\python.exe" }
$Py = (Resolve-Path $Py).Path
$Lock = Join-Path $Root "dist\aggressive_loop.lock"
$Out = Join-Path $Root "dist\aggressive_loop.out.log"
$Err = Join-Path $Root "dist\aggressive_loop.err.log"
$Dist = Join-Path $Root "dist"
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

# Kill only other aggressive_loop on this machine (leave train alone)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
  if ($_.CommandLine -and $_.CommandLine -like '*aggressive_loop*') {
    Write-Host "Stopping old loop pid=$($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
}
Start-Sleep -Seconds 1
Remove-Item $Lock -Force -ErrorAction SilentlyContinue

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $Py
$psi.Arguments = "-u scripts\aggressive_loop.py --poll-seconds 90"
$psi.WorkingDirectory = $Root
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
# Don't close when this launcher exits: inherit false + BeginOutputRead
[void]$p.Start()
# Drain to files asynchronously
$outWriter = [System.IO.StreamWriter]::new($Out, $true)
$errWriter = [System.IO.StreamWriter]::new($Err, $true)
$outWriter.AutoFlush = $true
$errWriter.AutoFlush = $true
Register-ObjectEvent -InputObject $p -EventName OutputDataReceived -Action {
  if ($EventArgs.Data) { $Event.MessageData.WriteLine($EventArgs.Data) }
} -MessageData $outWriter | Out-Null
Register-ObjectEvent -InputObject $p -EventName ErrorDataReceived -Action {
  if ($EventArgs.Data) { $Event.MessageData.WriteLine($EventArgs.Data) }
} -MessageData $errWriter | Out-Null
$p.BeginOutputReadLine()
$p.BeginErrorReadLine()
# Detach: don't WaitForExit; write pid marker
$marker = Join-Path $Dist "factory_launcher.pid"
"$($p.Id)" | Set-Content $marker -Encoding ascii
Write-Host "Factory started pid=$($p.Id) root=$Root"
Write-Host "Logs: $Out"
# Keep launcher alive briefly so async handlers attach, then exit (child keeps running)
Start-Sleep -Seconds 2
