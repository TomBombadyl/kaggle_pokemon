$Host.UI.RawUI.WindowTitle = "PTCG LIVE DASHBOARD"
while ($true) {
  Clear-Host
  $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $utc = [DateTime]::UtcNow.ToString("yyyy-MM-dd HH:mm:ss") + " UTC"
  $untilMidnight = ([DateTime]::UtcNow.Date.AddDays(1) - [DateTime]::UtcNow).TotalSeconds

  Write-Host "============================================================" -ForegroundColor Cyan
  Write-Host "  PTCG #1 LIVE DASHBOARD   local: $now" -ForegroundColor Cyan
  Write-Host "  UTC: $utc   |  距午夜提交: $([int]$untilMidnight)s" -ForegroundColor Cyan
  Write-Host "============================================================" -ForegroundColor Cyan

  Write-Host "`n[1] GROK 終端視窗" -ForegroundColor Yellow
  $grokWins = Get-Process powershell, pwsh -ErrorAction SilentlyContinue | Where-Object {
    try { $_.MainWindowTitle -match "Grok|Meta|Iono|Main|Search|Gate|Crustle|wait|DASHBOARD" } catch { $false }
  }
  if ($grokWins) {
    $grokWins | ForEach-Object {
      $t = if ($_.MainWindowTitle) { $_.MainWindowTitle } else { "(no title)" }
      Write-Host ("  PID {0,-8}  {1}" -f $_.Id, $t) -ForegroundColor Green
    }
  } else {
    Write-Host "  (沒偵測到 Grok 相關視窗)" -ForegroundColor DarkYellow
  }

  Write-Host "`n[2] grok CLI 進程" -ForegroundColor Yellow
  $grokProc = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and ($_.CommandLine -match "grok") }
  if ($grokProc) {
    $grokProc | ForEach-Object {
      $cmd = $_.CommandLine
      if ($cmd.Length -gt 90) { $cmd = $cmd.Substring(0, 90) + "..." }
      Write-Host ("  PID {0,-8}  {1}" -f $_.ProcessId, $cmd) -ForegroundColor Green
    }
  } else {
    Write-Host "  (無 grok CLI — 多半已回完在等輸入)" -ForegroundColor DarkYellow
  }

  Write-Host "`n[3] 訓練 / Loop / Gate 進程" -ForegroundColor Yellow
  $train = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
      $_.CommandLine -and (
        $_.CommandLine -match "aggressive_loop|continuous_focus|train_lucario|gate_|selfplay|arena|mainline|factory|wait_and_submit|midnight|package_submission"
      )
    }
  if ($train) {
    $train | ForEach-Object {
      $cmd = $_.CommandLine
      if ($cmd.Length -gt 100) { $cmd = $cmd.Substring(0, 100) + "..." }
      Write-Host ("  PID {0,-8}  {1}" -f $_.ProcessId, $cmd) -ForegroundColor Green
    }
  } else {
    Write-Host "  !!! 沒有訓練 loop 在跑 — 需要手動重開 !!!" -ForegroundColor Red
  }

  Write-Host "`n[4] 所有 Python 進程" -ForegroundColor Yellow
  $py = Get-Process python*, pythonw* -ErrorAction SilentlyContinue
  if ($py) {
    $py | Select-Object Id, @{N="CPU_s";E={[math]::Round($_.CPU,1)}}, @{N="RAM_MB";E={[math]::Round($_.WorkingSet/1MB,0)}}, StartTime |
      Format-Table -AutoSize | Out-String | Write-Host
  } else {
    Write-Host "  (沒有 python 進程)" -ForegroundColor DarkYellow
  }

  Write-Host "[5] 最近 10 分鐘更新的檔案" -ForegroundColor Yellow
  $cut = (Get-Date).AddMinutes(-10)
  $paths = @(
    "E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\recordings",
    "E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist",
    "C:\Users\KINGKAZMAX\ptcg-ai-battle\meta_intel",
    "E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\report"
  )
  $recent = @()
  foreach ($p in $paths) {
    if (Test-Path $p) {
      $recent += Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -gt $cut }
    }
  }
  if ($recent.Count -gt 0) {
    $recent | Sort-Object LastWriteTime -Descending | Select-Object -First 12 | ForEach-Object {
      $rel = $_.FullName.Replace("E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\", "").Replace("C:\Users\KINGKAZMAX\", "")
      Write-Host ("  {0:HH:mm:ss}  {1,8}B  {2}" -f $_.LastWriteTime, $_.Length, $rel) -ForegroundColor White
    }
  } else {
    Write-Host "  (10 分鐘內無新檔 — 可能都靜止)" -ForegroundColor DarkYellow
  }

  Write-Host "`n[6] 提交狀態" -ForegroundColor Yellow
  $pkg = "E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz"
  $cnt = "E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\submit_count.json"
  if (Test-Path $pkg) {
    $i = Get-Item $pkg
    Write-Host ("  package: OK  {0:N0} bytes  {1}" -f $i.Length, $i.LastWriteTime) -ForegroundColor Green
  } else {
    Write-Host "  package: 找不到" -ForegroundColor Red
  }
  if (Test-Path $cnt) {
    Write-Host ("  submit_count: {0}" -f ((Get-Content $cnt -Raw).Trim())) -ForegroundColor White
  }

  Write-Host "`n============================================================" -ForegroundColor DarkGray
  Write-Host "  每 10 秒刷新 | Ctrl+C 停止儀表板" -ForegroundColor DarkGray
  Write-Host "============================================================" -ForegroundColor DarkGray
  Start-Sleep -Seconds 10
}
