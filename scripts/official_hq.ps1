$Host.UI.RawUI.WindowTitle = "PTCG OFFICIAL HQ | 最强小智"
$ErrorActionPreference = "SilentlyContinue"
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new() } catch {}

# 官方色：黃=品牌 / 藍=資訊 / 紅=警示與#1 / 綠=我方
function Bar([double]$p,[int]$w=18){
  if($p -lt 0){$p=0}; if($p -gt 100){$p=100}
  $f=[int][math]::Round($w*$p/100.0)
  $c=if($p -ge 75){"Yellow"}elseif($p -ge 40){"Cyan"}else{"Red"}
  @{B=(("█"*$f)+("░"*($w-$f)));C=$c}
}
function Dot([bool]$ok){ if($ok){Write-Host "●" -ForegroundColor Yellow -NoNewline}else{Write-Host "●" -ForegroundColor Red -NoNewline} }

$TEAM = "最强小智"

while($true){
  Clear-Host
  $utc=[DateTime]::UtcNow
  $until=($utc.Date.AddDays(1)-$utc).TotalSeconds
  $t=Get-Date -Format "HH:mm:ss"

  # ===== OFFICIAL LOGO =====
  Write-Host ""
  Write-Host "  ████████╗██╗  ██╗███████╗    " -ForegroundColor Yellow -NoNewline
  Write-Host "██████╗  ██████╗ ███╗   ███╗" -ForegroundColor Blue
  Write-Host "  ╚══██╔══╝██║  ██║██╔════╝    " -ForegroundColor Yellow -NoNewline
  Write-Host "██╔══██╗██╔═══██╗████╗ ████║" -ForegroundColor Blue
  Write-Host "     ██║   ███████║█████╗      " -ForegroundColor Yellow -NoNewline
  Write-Host "██████╔╝██║   ██║██╔████╔██║" -ForegroundColor Blue
  Write-Host "     ██║   ██╔══██║██╔══╝      " -ForegroundColor Yellow -NoNewline
  Write-Host "██╔═══╝ ██║   ██║██║╚██╔╝██║" -ForegroundColor Blue
  Write-Host "     ██║   ██║  ██║███████╗    " -ForegroundColor Yellow -NoNewline
  Write-Host "██║     ╚██████╔╝██║ ╚═╝ ██║" -ForegroundColor Blue
  Write-Host "     ╚═╝   ╚═╝  ╚═╝╚══════╝    " -ForegroundColor Yellow -NoNewline
  Write-Host "╚═╝      ╚═════╝ ╚═╝     ╚═╝" -ForegroundColor Blue
  Write-Host "  Pokémon TCG AI Battle Challenge  ·  Simulation Ladder  ·  $t" -ForegroundColor Cyan
  Write-Host "  TEAM: " -NoNewline -ForegroundColor White
  Write-Host $TEAM -ForegroundColor Yellow

  # ===== 載入 token =====
  foreach($tp in @(
    "E:\PTCG_AI_Battle_Challenge\.kaggle\access_token",
    "E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\.kaggle\access_token",
    "$env:USERPROFILE\.kaggle\access_token"
  )){
    if(Test-Path $tp){
      $tok=(Get-Content $tp -Raw).Trim().Split("`n")[0].Trim()
      if($tok){ $env:KAGGLE_API_TOKEN=$tok; break }
    }
  }

  # ===== 即時榜：ptcg-meta + 搜尋最强小智 =====
  $myMu=$null; $myRank=$null; $myDeck="?"; $top1=0; $top1Name="?"
  $lb=@()
  try{
    $api=Invoke-RestMethod "https://ptcg-meta.vercel.app/api/teams.json" -TimeoutSec 12
    $lb=if($api.teams){$api.teams}else{@($api)}
    $lb=@($lb)|Sort-Object {[double]$_.score} -Descending
    if($lb.Count -gt 0){
      $top1=[double]$lb[0].score
      $top1Name="$($lb[0].team_name) / $($lb[0].main_pokemon_en)"
    }
    # 精確找最强小智
    $mine=$lb|Where-Object {
      $_.team_name -eq $TEAM -or $_.team_name -match [regex]::Escape($TEAM) -or
      ($_.team_name -and $_.team_name.Replace(" ","").Contains("最强小智"))
    }|Select-Object -First 1
    if(-not $mine){
      # 模糊
      $mine=$lb|Where-Object { $_.team_name -match "小智|Ash|最強|最强" }|Select-Object -First 3
      if($mine -is [array]){ $mine=$mine[0] }
    }
    if($mine){
      $myMu=[double]$mine.score
      $myDeck=if($mine.main_pokemon_en){$mine.main_pokemon_en}else{$mine.deck}
      # rank
      $r=1
      foreach($row in $lb){
        if($row.team_name -eq $mine.team_name -and [double]$row.score -eq $myMu){ $myRank=$r; break }
        $r++
      }
    }
  }catch{
    Write-Host "  meta API: $($_.Exception.Message)" -ForegroundColor DarkYellow
  }

  # 本地 track / kaggle CLI 補強
  if(-not $myMu){
    foreach($f in @("dist\ladder_status.json","recordings\metrics\ladder.json","report\meta\my_score.json","recordings\metrics\track_ladder.json")){
      if(Test-Path $f){
        try{
          $j=Get-Content $f -Raw|ConvertFrom-Json
          if($j.mu){$myMu=[double]$j.mu}
          if($j.score){$myMu=[double]$j.score}
          if($j.rank){$myRank=[int]$j.rank}
          if($j.team){ if(-not $myDeck -or $myDeck -eq "?"){ $myDeck=$j.team } }
        }catch{}
      }
    }
  }
  # kaggle CLI leaderboard（若有）
  try{
    if(Get-Command kaggle -ErrorAction SilentlyContinue){
      $kl=kaggle competitions leaderboard pokemon-tcg-ai-battle -v -q 2>$null
      # 解析含最强小智的行（CSV）
      if($kl){
        $lines=$kl -split "`n"
        foreach($line in $lines){
          if($line -match $TEAM -or $line -match "最强小智"){
            $cols=$line -split ","
            # 嘗試常見欄位
            foreach($c in $cols){
              if($c -match "^\d+(\.\d+)?$" -and [double]$c -gt 100){ $myMu=[double]$c }
            }
          }
        }
      }
    }
  }catch{}

  # 本地 scripts/track_ladder 產物
  if(Test-Path report\meta\leaderboard_top_20260730.json){
    try{
      $loc=Get-Content report\meta\leaderboard_top_20260730.json -Raw|ConvertFrom-Json
    }catch{}
  }

  Write-Host ""
  Write-Host "  ┌─ MY STANDING " -ForegroundColor Blue -NoNewline
  Write-Host ("─"*48) -ForegroundColor DarkBlue
  Write-Host -NoNewline "  │ Team " -ForegroundColor Blue
  Write-Host $TEAM -ForegroundColor Yellow -NoNewline
  Write-Host "   Rank " -NoNewline -ForegroundColor White
  if($myRank){ Write-Host ("#{0}" -f $myRank) -ForegroundColor Yellow -NoNewline } else { Write-Host "搜尋中" -ForegroundColor DarkYellow -NoNewline }
  Write-Host "   μ " -NoNewline -ForegroundColor White
  if($myMu){ Write-Host ("{0:N1}" -f $myMu) -ForegroundColor Yellow -NoNewline } else { Write-Host "—" -ForegroundColor DarkYellow -NoNewline }
  Write-Host "   Deck " -NoNewline -ForegroundColor White
  Write-Host $myDeck -ForegroundColor Cyan
  Write-Host -NoNewline "  │ #1   " -ForegroundColor Blue
  Write-Host ("{0:N1}" -f $top1) -ForegroundColor Red -NoNewline
  Write-Host "  $top1Name" -ForegroundColor Gray
  if($myMu -and $top1){
    $gap=$top1-$myMu
    $pct=if($top1 -gt 0){ [math]::Max(0,[math]::Min(100,100*($myMu/$top1))) } else {0}
    $b=Bar $pct 22
    Write-Host -NoNewline "  │ vs#1 " -ForegroundColor Blue
    Write-Host $b.B -ForegroundColor $b.C -NoNewline
    Write-Host ("  差 {0:N1}" -f $gap) -ForegroundColor $(if($gap -le 0){"Yellow"}else{"Red"})
  }

  # ===== DECK 可視化（官方色）=====
  Write-Host "  ├─ DECK " -ForegroundColor Yellow -NoNewline
  Write-Host ("─"*53) -ForegroundColor DarkYellow
  Write-Host "  │  " -NoNewline -ForegroundColor Yellow
  Write-Host "[CRUSTLE×3]" -NoNewline -ForegroundColor Yellow
  Write-Host " " -NoNewline
  Write-Host "[OGERPON×1]" -NoNewline -ForegroundColor Cyan
  Write-Host " " -NoNewline
  Write-Host "[KANGA×2]" -ForegroundColor Blue
  Write-Host "  │  " -NoNewline -ForegroundColor Yellow
  Write-Host "Dwebble×4  Boss×4  Lillie×4  Petrel×4  Ice×4  Hammer×4" -ForegroundColor White
  Write-Host "  │  " -NoNewline -ForegroundColor Yellow
  Write-Host "Plan: ex→Crustle | breaker→Boss | early Kanga draw | ship Crustle@UTC" -ForegroundColor Cyan

  # ===== TOP8 + 高亮我 =====
  Write-Host "  ├─ LIVE BOARD " -ForegroundColor Blue -NoNewline
  Write-Host ("─"*49) -ForegroundColor DarkBlue
  if($lb.Count -gt 0){
    $i=1
    foreach($row in ($lb|Select-Object -First 8)){
      $sc=[double]$row.score
      $dk=if($row.main_pokemon_en){$row.main_pokemon_en}else{"?"}
      $nm=if($row.team_name){$row.team_name}else{"?"}
      $isMe=($nm -eq $TEAM -or $nm -match [regex]::Escape($TEAM) -or ($myMu -and [math]::Abs($sc-$myMu) -lt 0.05 -and $nm -match "小智"))
      if($isMe){
        Write-Host ("  │ ▶#{0,-2} {1,7:N1}  {2,-16} {3}" -f $i,$sc,$dk,$nm) -ForegroundColor Yellow
      } elseif($i -eq 1){
        Write-Host ("  │  #{0,-2} {1,7:N1}  {2,-16} {3}" -f $i,$sc,$dk,$nm) -ForegroundColor Red
      } elseif($dk -match "Crustle|イワパレス"){
        Write-Host ("  │  #{0,-2} {1,7:N1}  {2,-16} {3}" -f $i,$sc,$dk,$nm) -ForegroundColor Cyan
      } else {
        Write-Host ("  │  #{0,-2} {1,7:N1}  {2,-16} {3}" -f $i,$sc,$dk,$nm) -ForegroundColor White
      }
      $i++
    }
  } else {
    Write-Host "  │  (榜單暫不可用 — 檢查網路 / token)" -ForegroundColor DarkYellow
  }

  # ===== Gate CAP 午夜 =====
  $gate=0
  if(Test-Path dist\best_gate.json){
    try{
      $bg=Get-Content dist\best_gate.json -Raw|ConvertFrom-Json
      foreach($k in @("wr","win_rate","overall","overall_wr")){
        if($bg.PSObject.Properties.Name -contains $k){ $gate=[double]$bg.$k; if($gate -le 1){$gate*=100}; break }
      }
    }catch{}
  }
  $cap=0
  if(Test-Path dist\submit_count.json){
    try{
      $sc=Get-Content dist\submit_count.json -Raw|ConvertFrom-Json
      if($sc.date -eq $utc.ToString("yyyy-MM-dd")){$cap=[int]$sc.count}
    }catch{}
  }
  Write-Host "  ├─ OPS " -ForegroundColor Yellow -NoNewline
  Write-Host ("─"*55) -ForegroundColor DarkYellow
  $b1=Bar $gate; Write-Host -NoNewline "  │ Gate " -ForegroundColor Yellow; Write-Host $b1.B -ForegroundColor $b1.C -NoNewline; Write-Host (" {0:N0}%" -f $gate) -ForegroundColor White
  $b2=Bar (100.0*$cap/5); Write-Host -NoNewline "  │ CAP  " -ForegroundColor Yellow; Write-Host $b2.B -ForegroundColor $(if($cap -ge 5){"Red"}else{"Yellow"}) -NoNewline; Write-Host (" {0}/5" -f $cap) -ForegroundColor White
  $b3=Bar ([math]::Min(100,100*(1-$until/86400))); Write-Host -NoNewline "  │ UTC  " -ForegroundColor Yellow; Write-Host $b3.B -ForegroundColor Cyan -NoNewline; Write-Host (" {0:N1}h → Crustle ship" -f ($until/3600)) -ForegroundColor Cyan

  # ===== COMPUTE =====
  Write-Host "  ├─ COMPUTE " -ForegroundColor Red -NoNewline
  Write-Host ("─"*51) -ForegroundColor DarkRed
  $cpu=0; try{$cpu=(Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue}catch{}
  $bc=Bar $cpu; Write-Host -NoNewline "  │ CPU  " -ForegroundColor Red; Write-Host $bc.B -ForegroundColor $bc.C -NoNewline; Write-Host (" {0:N0}%" -f $cpu) -ForegroundColor White
  try{
    $os=Get-CimInstance Win32_OperatingSystem
    $ram=100.0*($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize
    $br=Bar $ram; Write-Host -NoNewline "  │ RAM  " -ForegroundColor Red; Write-Host $br.B -ForegroundColor $br.C -NoNewline; Write-Host (" {0:N0}%" -f $ram) -ForegroundColor White
  }catch{}
  try{
    $g=& nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits 2>$null
    if($g){
      $p=($g -split ",")|ForEach-Object{$_.Trim()}
      $bg=Bar ([double]$p[0])
      Write-Host -NoNewline "  │ GPU  " -ForegroundColor Red; Write-Host $bg.B -ForegroundColor $bg.C -NoNewline
      Write-Host (" {0}%  {1}/{2}MB  {3}°C" -f $p[0],$p[1],$p[2],$p[3]) -ForegroundColor White
    }
  }catch{ Write-Host "  │ GPU  (no nvidia-smi)" -ForegroundColor DarkYellow }

  $hasLoop=$false;$hasGrok=$false;$hasWait=$false;$hasFactory=$false;$hasMcts=$false
  Get-CimInstance Win32_Process|ForEach-Object{
    $c=$_.CommandLine; if(-not $c){return}
    if($c -match "aggressive_loop"){$hasLoop=$true}
    if($c -match "grok"){$hasGrok=$true}
    if($c -match "wait_and_submit"){$hasWait=$true}
    if($c -match "factory_cycle"){$hasFactory=$true}
    if($c -match "mcts|train_lucario"){$hasMcts=$true}
  }
  Write-Host -NoNewline "  │ JOBS " -ForegroundColor Red
  Dot $hasLoop; Write-Host "loop " -NoNewline
  Dot $hasFactory; Write-Host "fac " -NoNewline
  Dot $hasMcts; Write-Host "mcts " -NoNewline
  Dot $hasGrok; Write-Host "grok " -NoNewline
  Dot $hasWait; Write-Host "ship"

  Write-Host "  └" -NoNewline -ForegroundColor DarkGray
  Write-Host ("─"*62) -ForegroundColor DarkGray
  Write-Host "  12s · 黃=你/品牌  藍=資訊  紅=#1/算力  · 目標 #1" -ForegroundColor DarkGray
  Start-Sleep 12
}
