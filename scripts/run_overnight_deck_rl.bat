@echo off
REM Overnight deck + policy RL (local only). Safe interrupt: re-run with same args + --resume
cd /d "%~dp0.."
set PYTHONUNBUFFERED=1

echo === PTCG deck RL campaign (GPU policy + checkpoints) ===
python -c "from rl.gpu_config import detect_hardware, training_defaults; import json; h=detect_hardware(); print(json.dumps({'hw':h,'defaults':training_defaults(h)}, indent=2))" 2>nul
if errorlevel 1 (
  echo Installing training deps...
  python -m pip install torch gymnasium stable-baselines3 sb3-contrib
)

REM RTX 4070 Ti SUPER: policy on CUDA, 6 CPU sim envs, checkpoint every 10k steps
REM --cycles 4 extends past the existing checkpoint (was at 2 cycles done); --resume
REM keeps all prior policy + deck-GA progress and runs only the new cycles 3-4.
python rl\train_deck_campaign.py ^
  --phase full ^
  --cycles 4 ^
  --timesteps 100000 ^
  --device auto ^
  --resume ^
  --generations 20 ^
  --population 12 ^
  --games-eval 6 ^
  --scorer heuristic

echo.
echo Checkpoints:
echo   report\rl_deck_campaign\checkpoint.json
echo   report\rl_deck_campaign\policy_checkpoints\
echo   report\rl_deck_campaign\deck_ga.json
echo   report\rl_deck_campaign\best_deck.csv
echo.
echo To resume after interrupt: scripts\run_overnight_deck_rl.bat  (uses --resume)
