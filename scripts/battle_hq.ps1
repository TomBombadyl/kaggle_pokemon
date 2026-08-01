$Host.UI.RawUI.WindowTitle = "PTCG #1  |  POKEMON BATTLE HQ"
$ErrorActionPreference = "SilentlyContinue"
try { $null = [Console]::OutputEncoding = [Text.UTF8Encoding]::new() } catch {}

function Bar([double]$p,[int]$w=20){
  if($p -lt 0){$p=0}; if($p -gt 100){$p=100}
  $f=[int][math]::Round($w*$p/100)
  $c=if($p -ge 80){"Green"}elseif($p -ge 50){"Yellow"}else{"Red"}
  @{B=(("█"*$f)+("░"*($w-$f)));C=$c}
}
function L([bool]$o){ if($o){Write-Host "●" -ForegroundColor Green -NoNewline}else{Write-Host "●" -ForegroundColor Red -NoNewline} }

while($true){
  Clear-Host
  $utc=[DateTime]::UtcNow
  $until=($utc.Date.AddDays(1)-$utc).TotalSeconds
  $local=Get-Date -Format "HH:mm:ss"

  # ===== LOGO =====
  Write-Host ""
  Write-Host "  ██████╗ ████████╗ ██████╗ ██████╗     " -ForegroundColor Yellow -NoNewline; Write-Host "██╗  ██╗ ██╗" -ForegroundColor Red
  Write-Host "  ██╔══██╗╚══██╔══╝██╔════╝██╔════╝     " -ForegroundColor Yellow -NoNewline; Write-Host "██║  ██║███║" -ForegroundColor Red
  Write-Host "  ██████╔╝   ██║   ██║     ██║  ███╗    " -ForegroundColor Yellow -NoNewline; Write-Host "███████║╚██║" -ForegroundColor Red
  Write-Host "  ██╔═══╝    ██║   ██║     ██║   ██║    " -ForegroundColor Yellow -NoNewline; Write-Host "██╔══██║ ██║" -ForegroundColor Red
  Write-Host "  ██║        ██║   ╚██████╗╚██████╔╝    " -ForegroundColor Yellow -NoNewline; Write-Host "██║  ██║ ██║" -ForegroundColor Red
  Write-Host "  ╚═╝        ╚═╝    ╚═════╝ ╚═════╝     " -ForegroundColor Yellow -NoNewline; Write-Host "╚═╝  ╚═╝ ╚═╝" -ForegroundColor Red
  Write-Host "  ── AI BATTLE CHALLENGE  ·  CRUSTLE OPS  ·  $local ──" -ForegroundColor Cyan

  # ===== 我的分數 / 排名（本地+API）=====
  $myMu=$null; $myRank=$null; $top1=0; $top1Name="?"
  # 本地 track / state
  foreach($p in @("dist\ladder_status.json","recordings\metrics\ladder.json","report\meta\my_score.json","STATE.md")){
    if(Test-Path $p){
      if($p -match "\.json$"){
        try{ $j=Get-Content $p -Raw|ConvertFrom-Json
          if($j.mu){$myMu=[double]$j.mu}
          if($j.score){$myMu=[double]$j.score}
          if($j.rank){$myRank=[int]$j.rank}
        }catch{}
      }
    }
  }
  # 從 submit / track 粗抓
  if(Test-Path dist\submit_log.jsonl){
    try{
      $last=(Get-Content dist\submit_log.jsonl -Tail 3|Select-Object -Last 1)|ConvertFrom-Json
      if($last.score){$myMu=[double]$last.score}
    }catch{}
  }

  $lb=@()
  try{
    $api=Invoke-RestMethod "https://ptcg-meta.vercel.app/api/teams.json" -TimeoutSec 10
    $lb=if($api.teams){$api.teams}else{$api}
    $lb=$lb|Sort-Object {[double]$_.score} -Descending
    if($lb){ $top1=[double]$lb[0].score; $top1Name=($lb[0].team_name+" / "+$lb[0].main_pokemon_en) }
  }catch{}

  Write-Host ""
  Write-Host "┌─ SCOREBOARD " -ForegroundColor Magenta -NoNewline; Write-Host ("─"*50) -ForegroundColor DarkMagenta
  $muTxt=if($myMu){"{0:N1}" -f $myMu}else{"(提交後才有 μ)"}
  $rkTxt=if($myRank){"#$myRank"}else{"未上榜/待同步"}
  Write-Host -NoNewline "│ " -ForegroundColor Magenta
  Write-Host "我 " -NoNewline -ForegroundColor White
  Write-Host $rkTxt -NoNewline -ForegroundColor Yellow
  Write-Host "  μ/分 " -NoNewline -ForegroundColor White
  Write-Host $muTxt -NoNewline -ForegroundColor Green
  Write-Host "  │  #1 " -NoNewline -ForegroundColor White
  Write-Host ("{0:N1}" -f $top1) -NoNewline -ForegroundColor Red
  Write-Host "  $top1Name" -ForegroundColor Gray
  if($myMu -and $top1){
    $gap=$top1-$myMu
    $gapPct=if($top1 -gt 0){[math]::Max(0,100*(1-$gap/([math]::Max($top1,1))))}else{0}
    $gb=Bar $gapPct 22
    Write-Host -NoNewline "│ 距#1 " -ForegroundColor Magenta
    Write-Host $gb.B -ForegroundColor $gb.C -NoNewline
    Write-Host ("  差 {0:N1} 分" -f $gap) -ForegroundColor Yellow
  } else {
    Write-Host "│ 距#1  午夜交 Crustle 後才能量化差距" -ForegroundColor DarkYellow
  }

  # ===== 牌組可視化 =====
  Write-Host "├─ DECK " -ForegroundColor Green -NoNewline; Write-Host ("─"*54) -ForegroundColor DarkGreen
  Write-Host "│ " -NoNewline -ForegroundColor Green
  Write-Host "CRUSTLE WALL" -NoNewline -ForegroundColor Green
  Write-Host "  MissingNo #1 replica" -ForegroundColor DarkGray
  Write-Host "│" -ForegroundColor Green
  Write-Host "│   " -NoNewline -ForegroundColor Green
  Write-Host "┌─────────┐  " -NoNewline -ForegroundColor Yellow
  Write-Host "┌─────────┐  " -NoNewline -ForegroundColor Cyan
  Write-Host "┌─────────┐" -ForegroundColor Magenta
  Write-Host "│   " -NoNewline -ForegroundColor Green
  Write-Host "│ CRUSTLE │  " -NoNewline -ForegroundColor Yellow
  Write-Host "│ OGERPON │  " -NoNewline -ForegroundColor Cyan
  Write-Host "│ KANGA   │" -ForegroundColor Magenta
  Write-Host "│   " -NoNewline -ForegroundColor Green
  Write-Host "│  ×3     │  " -NoNewline -ForegroundColor Yellow
  Write-Host "│  ×1     │  " -NoNewline -ForegroundColor Cyan
  Write-Host "│  ×2     │" -ForegroundColor Magenta
  Write-Host "│   " -NoNewline -ForegroundColor Green
  Write-Host "│ 免疫ex  │  " -NoNewline -ForegroundColor Yellow
  Write-Host "│ 抗Ability│ " -NoNewline -ForegroundColor Cyan
  Write-Host "│ 抽牌引擎 │" -ForegroundColor Magenta
  Write-Host "│   " -NoNewline -ForegroundColor Green
  Write-Host "└─────────┘  " -NoNewline -ForegroundColor Yellow
  Write-Host "└─────────┘  " -NoNewline -ForegroundColor Cyan
  Write-Host "└─────────┘" -ForegroundColor Magenta
  Write-Host "│  " -NoNewline -ForegroundColor Green
  Write-Host "Dwebble×4" -NoNewline -ForegroundColor DarkYellow
  Write-Host "  Boss×4  Lillie×4  Petrel×4  Hammer×4  Ice×4" -ForegroundColor Gray
  Write-Host "│  " -NoNewline -ForegroundColor Green
  Write-Host "策略 " -NoNewline -ForegroundColor White
  Write-Host "ex→上Crustle │ 非ex突破手→Boss │ 早中期Kanga抽牌" -ForegroundColor Cyan

  # ===== TOP5 即時 =====
  Write-Host "├─ LIVE TOP5 " -ForegroundColor Blue -NoNewline; Write-Host ("─"*50) -ForegroundColor DarkBlue
  if($lb -and $lb.Count -gt 0){
    $i=1
    foreach($t in ($lb|Select-Object -First 5)){
      $sc=[double]$t.score
      $dk=if($t.main_pokemon_en){$t.main_pokemon_en}else{"?"}
      $nm=if($t.team_name){$t.team_name}else{"?"}
      $col=if($i -eq 1){"Red"}elseif($dk -match "Crustle"){"Green"}else{"White"}
      $tag=if($dk -match "Crustle"){" ◄"}else{""}
      Write-Host ("│  #{0} {1,7:N1}  {2,-18} {3}{4}" -f $i,$sc,$dk,$nm,$tag) -ForegroundColor $col
      $i++
    }
  } else { Write-Host "│  (API 暫不可用，用本地 loop 分數)" -ForegroundColor DarkYellow }

  # ===== Gate + CAP + 午夜 =====
  $gate=0; $gTxt="n/a"
  if(Test-Path dist\best_gate.json){
    try{
      $bg=Get-Content dist\best_gate.json -Raw|ConvertFrom-Json
      foreach($k in @("wr","win_rate","overall","overall_wr")){
        if($bg.PSObject.Properties.Name -contains $k){ $gate=[double]$bg.$k; if($gate -le 1){$gate*=100}; $gTxt="$k=$($bg.$k)"; break }
      }
    }catch{}
  }
  $cap=0
  if(Test-Path dist\submit_count.json){
    try{ $sc=Get-Content dist\submit_count.json -Raw|ConvertFrom-Json
      if($sc.date -eq $utc.ToString("yyyy-MM-dd")){$cap=[int]$sc.count}
    }catch{}
  }
  Write-Host "├─ LOCAL / SHIP " -ForegroundColor Yellow -NoNewline; Write-Host ("─"*48) -ForegroundColor DarkYellow
  $b1=Bar $gate 18
  Write-Host -NoNewline "│ Gate " -ForegroundColor Yellow
  Write-Host $b1.B -ForegroundColor $b1.C -NoNewline
  Write-Host (" {0:N0}% {1}" -f $gate,$gTxt) -ForegroundColor Gray
  $b2=Bar (100*$cap/5) 18
  Write-Host -NoNewline "│ CAP  " -ForegroundColor Yellow
  Write-Host $b2.B -ForegroundColor $(if($cap -ge 5){"Red"}else{"Green"}) -NoNewline
  Write-Host (" {0}/5" -f $cap) -ForegroundColor Gray
  $midPct=[math]::Min(100,100*(1-$until/86400))
  $b3=Bar $midPct 18
  Write-Host -NoNewline "│ 午夜 " -ForegroundColor Yellow
  Write-Host $b3.B -ForegroundColor Cyan -NoNewline
  Write-Host (" {0:N1}h → 交 Crustle v1" -f ($until/3600)) -ForegroundColor Cyan

  # ===== 算力全力 =====
  Write-Host "├─ COMPUTE FULL SEND " -ForegroundColor Red -NoNewline; Write-Host ("─"*42) -ForegroundColor DarkRed
  $cpu=0; try{ $cpu=(Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue }catch{}
  $bc=Bar $cpu 18
  Write-Host -NoNewline "│ CPU  " -ForegroundColor Red
  Write-Host $bc.B -ForegroundColor $bc.C -NoNewline
  Write-Host (" {0:N0}%" -f $cpu) -ForegroundColor Gray
  try{
    $os=Get-CimInstance Win32_OperatingSystem
    $ram=100.0*($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize
    $br=Bar $ram 18
    Write-Host -NoNewline "│ RAM  " -ForegroundColor Red
    Write-Host $br.B -ForegroundColor $br.C -NoNewline
    Write-Host (" {0:N0}%" -f $ram) -ForegroundColor Gray
  }catch{}
  $gpuOK=$false
  try{
    $g=& nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits 2>$null
    if($g){
      $gpuOK=$true
      $p=($g -split ",")|ForEach-Object{$_.Trim()}
      $bg=Bar ([double]$p[0]) 18
      Write-Host -NoNewline "│ GPU  " -ForegroundColor Red
      Write-Host $bg.B -ForegroundColor $bg.C -NoNewline
      Write-Host (" {0}%  VRAM {1}/{2}  {3}°C" -f $p[0],$p[1],$p[2],$p[3]) -ForegroundColor Gray
    }
  }catch{}
  if(-not $gpuOK){ Write-Host "│ GPU  ░░░░░░░░░░░░░░░░░░  未偵測 NVIDIA" -ForegroundColor DarkYellow }

  $hasLoop=$false;$hasGrok=$false;$hasWait=$false;$hasMcts=$false;$hasFactory=$false
  Get-CimInstance Win32_Process|ForEach-Object{
    $c=$_.CommandLine; if(-not $c){return}
    if($c -match "aggressive_loop"){$hasLoop=$true}
    if($c -match "grok"){$hasGrok=$true}
    if($c -match "wait_and_submit"){$hasWait=$true}
    if($c -match "train_lucario|mcts|cuda"){$hasMcts=$true}
    if($c -match "factory_cycle"){$hasFactory=$true}
  }
  Write-Host -NoNewline "│ JOBS " -ForegroundColor Red
  L $hasLoop; Write-Host "loop " -NoNewline
  L $hasFactory; Write-Host "factory " -NoNewline
  L $hasMcts; Write-Host "mcts " -NoNewline
  L $hasGrok; Write-Host "grok " -NoNewline
  L $hasWait; Write-Host "ship"

  # 算力全開建議（自動提示，不強制殺進程）
  Write-Host "│ " -NoNewline -ForegroundColor Red
  if(-not $hasLoop){
    Write-Host "⚠ 重開訓練: python -u scripts\aggressive_loop.py" -ForegroundColor Yellow
  } elseif($gpuOK -and -not $hasMcts -and $cpu -lt 60){
    Write-Host "GPU 空閒→可加: python -u scripts\train_lucario_field_mcts.py 或 arena 加深" -ForegroundColor Yellow
  } else {
    Write-Host "算力使用中 · 保持 loop · 午夜交 Crustle 衝 μ" -ForegroundColor Green
  }

  Write-Host "└" -ForegroundColor DarkGray -NoNewline
  Write-Host ("─"*63) -ForegroundColor DarkGray
  Write-Host " 15s刷新 · Ctrl+C退出 · 目標 #1 · Crustle v1 待命" -ForegroundColor DarkGray
  Start-Sleep 15
}
