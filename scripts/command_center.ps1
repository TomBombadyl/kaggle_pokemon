$Host.UI.RawUI.WindowTitle = "PTCG #1 COMMAND CENTER"
$ErrorActionPreference = "SilentlyContinue"

function Bar([double]$pct, [int]$width = 26) {
  if ($pct -lt 0) { $pct = 0 }; if ($pct -gt 100) { $pct = 100 }
  $f = [int][math]::Round($width * $pct / 100.0)
  $color = if ($pct -ge 80) { "Green" } elseif ($pct -ge 55) { "Yellow" } else { "Red" }
  return @{ B = (("█"*$f)+("░"*($width-$f))); C = $color; P = $pct }
}
function Light([bool]$ok) {
  if ($ok) { Write-Host "●" -ForegroundColor Green -NoNewline } else { Write-Host "●" -ForegroundColor Red -NoNewline }
}

while ($true) {
  Clear-Host
  $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $utc = [DateTime]::UtcNow
  $until = ($utc.Date.AddDays(1) - $utc).TotalSeconds

  Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
  Write-Host "║     PTCG AI BATTLE  #1 COMMAND CENTER     $now     ║" -ForegroundColor Cyan
  Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

  # ========== 1. 我的牌組 ==========
  Write-Host "`n【1】我的牌組" -ForegroundColor Yellow
  Write-Host "  主線: Crustle (MissingNo. #1 複刻)" -ForegroundColor Green
  Write-Host "  檔案: agent_decks\crustle_MissingNo_rank1.csv" -ForegroundColor Gray
  Write-Host "  Package: dist\candidates\crustle_MissingNo_v1.tar.gz" -ForegroundColor Gray
  Write-Host "  核心: Dwebble×4 → Crustle×3 + Ogerpon + Mega Kangaskhan" -ForegroundColor White
  Write-Host "  關鍵技: Mysterious Rock Inn (免疫 ex 傷害) + Boss×4 + Lillie×4" -ForegroundColor White
  Write-Host "  備份: Grimmsnarl haggle / 舊 Archaludon (已降級，不自動交)" -ForegroundColor DarkGray

  # ========== 2. 策略 ==========
  Write-Host "`n【2】策略鎖定" -ForegroundColor Yellow
  Write-Host "  P0  對手 Active=ex → 推 Crustle 到 Active" -ForegroundColor Green
  Write-Host "  P0  Boss 優先抓「能打穿牆的非ex」" -ForegroundColor Green
  Write-Host "  P1  早期 Kangaskhan 抽牌，Crustle 就緒後換下" -ForegroundColor Green
  Write-Host "  P1  vs Ability 單獎 → Ogerpon" -ForegroundColor Green
  Write-Host "  提交  UTC午夜交 Crustle v1 | 禁交 Arch/Dra/Alak | CAP 5/日" -ForegroundColor Cyan

  # ========== 3. 本地分數 / gate ==========
  Write-Host "`n【3】本地分數 (Gate)" -ForegroundColor Yellow
  $gatePct = 0; $gateTxt = "尚無 best_gate.json"
  if (Test-Path dist\best_gate.json) {
    try {
      $bg = Get-Content dist\best_gate.json -Raw | ConvertFrom-Json
      $props = $bg.PSObject.Properties
      $gateTxt = ($bg | ConvertTo-Json -Compress)
      foreach ($k in @("wr","win_rate","overall","overall_wr","score")) {
        if ($bg.PSObject.Properties.Name -contains $k) {
          $gatePct = [double]($bg.$k)
          if ($gatePct -le 1) { $gatePct *= 100 }
          $gateTxt = "$k = $($bg.$k)"
          break
        }
      }
    } catch { $gateTxt = (Get-Content dist\best_gate.json -Raw).Substring(0, [Math]::Min(120, (Get-Content dist\best_gate.json -Raw).Length)) }
  }
  $gb = Bar $gatePct
  Write-Host -NoNewline "  Best Gate  "
  Write-Host $gb.B -ForegroundColor $gb.C -NoNewline
  Write-Host "  $gateTxt" -ForegroundColor Gray

  # arena 歷史粗估（若有 loop log 關鍵字）
  if (Test-Path report\aggressive\factory_cycle_status.md) {
    Write-Host "  --- factory ---" -ForegroundColor DarkGray
    Get-Content report\aggressive\factory_cycle_status.md -TotalCount 12 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
  }

  # ========== 4. 即時排名（聯網） ==========
  Write-Host "`n【4】即時 Meta / 排名" -ForegroundColor Yellow
  $myRankGuess = "?"
  $top1Score = $null; $top1Deck = "?"
  try {
    $teams = Invoke-RestMethod -Uri "https://ptcg-meta.vercel.app/api/teams.json" -TimeoutSec 12
    $list = @()
    if ($teams.teams) { $list = $teams.teams } elseif ($teams -is [array]) { $list = $teams }
    $top = $list | Sort-Object { [double]$_.score } -Descending | Select-Object -First 8
    $i = 1
    foreach ($t in $top) {
      $name = if ($t.team_name) { $t.team_name } elseif ($t.name) { $t.name } else { "?" }
      $deck = if ($t.main_pokemon_en) { $t.main_pokemon_en } elseif ($t.deck) { $t.deck } else { "?" }
      $sc = $t.score
      if ($i -eq 1) { $top1Score = [double]$sc; $top1Deck = "$deck ($name)" }
      $mark = if ($deck -match "Crustle|イワパレス") { " ◄ meta Crustle" } else { "" }
      Write-Host ("  #{0,-2}  {1,7}  {2,-22}  {3}{4}" -f $i, $sc, $deck, $name, $mark) -ForegroundColor $(if ($i -eq 1) {"Green"} else {"White"})
      $i++
    }
  } catch {
    Write-Host "  (無法拉 live API: $($_.Exception.Message))" -ForegroundColor DarkYellow
    if (Test-Path report\meta\leaderboard_top_20260730.md) {
      Write-Host "  --- 本地快取 leaderboard ---" -ForegroundColor DarkGray
      Get-Content report\meta\leaderboard_top_20260730.md -TotalCount 12 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    }
  }

  # ========== 5. 衝 #1 預測 ==========
  Write-Host "`n【5】衝 #1 路徑預測" -ForegroundColor Yellow
  $pathScore = 35  # base
  $reasons = @()
  if (Test-Path dist\candidates\crustle_MissingNo_v1.tar.gz) { $pathScore += 15; $reasons += "Crustle v1 package 就緒" }
  $hasLoop = $false; $hasGrok = $false; $hasWait = $false
  Get-CimInstance Win32_Process | ForEach-Object {
    $c = $_.CommandLine; if (-not $c) { return }
    if ($c -match "aggressive_loop") { $hasLoop = $true }
    if ($c -match "grok") { $hasGrok = $true }
    if ($c -match "wait_and_submit") { $hasWait = $true }
  }
  if ($hasLoop) { $pathScore += 15; $reasons += "aggressive_loop 在跑" } else { $reasons += "缺 loop（算力閒置）" }
  if ($hasWait) { $pathScore += 10; $reasons += "午夜自動提交已掛" }
  if ($hasGrok) { $pathScore += 5; $reasons += "Grok 顧問在線" }
  if ($gatePct -ge 80) { $pathScore += 15; $reasons += "本地 gate≥80" }
  elseif ($gatePct -ge 55) { $pathScore += 8; $reasons += "本地 gate 中等" }
  if ($top1Deck -match "Crustle") { $pathScore += 10; $reasons += "目前 #1 也是 Crustle（方向正確）" }

  $pb = Bar ([math]::Min(100, $pathScore))
  Write-Host -NoNewline "  路徑完整度  "
  Write-Host $pb.B -ForegroundColor $pb.C -NoNewline
  Write-Host ("  {0}%" -f [math]::Min(100,$pathScore)) -ForegroundColor White
  foreach ($r in $reasons) { Write-Host "    · $r" -ForegroundColor Gray }
  Write-Host "  預測:" -ForegroundColor White
  if ($pathScore -ge 75) {
    Write-Host "    方向正確。午夜交 Crustle 後看 μ；同時用 loop 磨 v2 規則可衝擊 Top。" -ForegroundColor Green
  } elseif ($pathScore -ge 50) {
    Write-Host "    中等。先確保午夜成功交 v1，再用算力專門打 Crustle gate / 專用規則。" -ForegroundColor Yellow
  } else {
    Write-Host "    偏弱。優先重開 loop + 確認 package/提交鏈，再談衝 #1。" -ForegroundColor Red
  }
  if ($top1Score) {
    Write-Host ("  現 #1 分數約 {0}  |  你的目標: 超過此值並穩定" -f $top1Score) -ForegroundColor Cyan
  }

  # ========== 6. 算力可視化 ==========
  Write-Host "`n【6】本地算力 (合理化使用)" -ForegroundColor Yellow
  # CPU
  try {
    $cpu = (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue
    $cpuB = Bar $cpu
    Write-Host -NoNewline "  CPU   "
    Write-Host $cpuB.B -ForegroundColor $cpuB.C -NoNewline
    Write-Host ("  {0:N0}%" -f $cpu) -ForegroundColor Gray
  } catch { Write-Host "  CPU   (讀取失敗)" -ForegroundColor DarkGray }

  # RAM
  try {
    $os = Get-CimInstance Win32_OperatingSystem
    $ramPct = 100.0 * ($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize
    $ramB = Bar $ramPct
    Write-Host -NoNewline "  RAM   "
    Write-Host $ramB.B -ForegroundColor $ramB.C -NoNewline
    Write-Host ("  {0:N0}%  ({1:N1} GB 使用)" -f $ramPct, (($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB)) -ForegroundColor Gray
  } catch {}

  # GPU (NVIDIA)
  $gpuLine = $null
  try {
    $gpuLine = & nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits 2>$null
  } catch {}
  if ($gpuLine) {
    foreach ($line in ($gpuLine -split "`n")) {
      if (-not $line.Trim()) { continue }
      $p = $line.Split(",").ForEach({ $_.Trim() })
      if ($p.Count -ge 5) {
        $util = [double]$p[1]
        $gB = Bar $util
        Write-Host -NoNewline "  GPU   "
        Write-Host $gB.B -ForegroundColor $gB.C -NoNewline
        Write-Host ("  {0}%  {1}  VRAM {2}/{3} MB  {4}°C" -f $p[1], $p[0], $p[2], $p[3], $p[4]) -ForegroundColor Gray
      }
    }
  } else {
    Write-Host "  GPU   (無 nvidia-smi 或非 NVIDIA — MCTS/CUDA 需確認環境)" -ForegroundColor DarkYellow
  }

  # 建議
  Write-Host "  建議:" -ForegroundColor White
  if (-not $hasLoop) {
    Write-Host "    → 立刻重開: python scripts\aggressive_loop.py" -ForegroundColor Red
  } else {
    Write-Host "    → loop 已吃 CPU：保持；空閒 GPU 時可開 train_lucario MCTS / arena 加深" -ForegroundColor Green
  }
  Write-Host ("    → 距午夜提交還有 {0:N1} 小時（保持 wait_and_submit_crustle）" -f ($until/3600)) -ForegroundColor Cyan

  # ========== 進程燈 ==========
  Write-Host "`n【7】進程" -ForegroundColor Yellow
  Write-Host -NoNewline "  "; Light $hasLoop; Write-Host " loop  " -NoNewline
  Light $hasGrok; Write-Host " grok  " -NoNewline
  Light $hasWait; Write-Host " wait_submit  " -NoNewline
  $hasFactory = [bool](Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "factory_cycle" })
  Light $hasFactory; Write-Host " factory"

  Write-Host "`n──────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
  Write-Host " 每 15 秒刷新 | Ctrl+C 退出（不殺訓練）| 目標: Kaggle #1" -ForegroundColor DarkGray
  Start-Sleep -Seconds 15
}
