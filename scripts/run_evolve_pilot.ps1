# One-command local runner for the evolve/ pilot: checks git state, resolves any
# pending ladder probe, verifies the cg engine is importable, then runs
# evolve/run_evolution.py and prints the report path. Does NOT touch Kaggle upload --
# that stays a separate, explicitly-confirmed step per R12 (see AGENTS.md).
#
# Usage from repo root:
#   powershell -File scripts/run_evolve_pilot.ps1
#   powershell -File scripts/run_evolve_pilot.ps1 -Generations 6 -Population 10 -Games 30
#   powershell -File scripts/run_evolve_pilot.ps1 -SkipLadderCheck   # if Kaggle auth is still broken

param(
    [string]$Target = 'archaludon',
    [int]$Generations = 6,
    [int]$Population = 10,
    [int]$Games = 30,
    [string]$Suite = 'full',
    [switch]$SkipLadderCheck
)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "=== 1. Git state ===" -ForegroundColor Cyan
$dirty = git status --porcelain
if ($dirty) {
    Write-Host $dirty
    Write-Error "Uncommitted changes present -- commit or 'git stash push -u' before pulling on top of them. Aborting (nothing was touched)."
}
$branch = git rev-parse --abbrev-ref HEAD
Write-Host "On branch: $branch"
git fetch origin $branch
$behind = git rev-list --count "HEAD..origin/$branch"
if ([int]$behind -gt 0) {
    Write-Host "$behind commit(s) behind origin/$branch -- pulling..."
    git pull origin $branch
} else {
    Write-Host "Up to date with origin/$branch."
}

Write-Host "`n=== 2. Python + cg engine ===" -ForegroundColor Cyan
$pyVersion = python --version
Write-Host "Using: $pyVersion"
python -c "import cg" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "cg engine not importable -- running scripts/fetch_sim_engine.py..."
    python scripts/fetch_sim_engine.py
    if ($LASTEXITCODE -ne 0) {
        Write-Error "fetch_sim_engine.py failed -- check .kaggle/access_token / KAGGLE_API_TOKEN, then re-run this script."
    }
}

if (-not $SkipLadderCheck) {
    Write-Host "`n=== 3. Resolve any pending ladder probe ===" -ForegroundColor Cyan
    python scripts/track_ladder.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "track_ladder.py failed (Kaggle auth?) -- continuing without it. Re-run with -SkipLadderCheck to silence this." -ForegroundColor Yellow
    }
} else {
    Write-Host "`n=== 3. Skipped ladder check (-SkipLadderCheck) ===" -ForegroundColor Cyan
}

Write-Host "`n=== 4. Running evolve pilot: target=$Target gens=$Generations pop=$Population games=$Games suite=$Suite ===" -ForegroundColor Cyan
python evolve/run_evolution.py --target $Target --generations $Generations --population $Population --games $Games --suite $Suite --report
if ($LASTEXITCODE -ne 0) {
    Write-Error "evolve/run_evolution.py failed -- see output above."
}

$reportPath = "eval/evolve_${Target}_gen${Generations}.md"
Write-Host "`n=== Done ===" -ForegroundColor Green
Write-Host "Report: $reportPath"
if (Test-Path $reportPath) {
    Write-Host "`n--- Top of report ---"
    Get-Content $reportPath -TotalCount 15
}
