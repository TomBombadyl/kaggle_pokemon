# Notebooks index

GPU / Kaggle notebook jobs for this repo.

| Job | Path | Purpose |
|-----|------|---------|
| **Field RL+MCTS** | [`rl_mcts_field_train/`](rl_mcts_field_train/) | 5-cycle training vs mined `real_*` / `top_mined_*` opponent decks (Fix #2/#3) |
| **Lucario RL+MCTS** | [`lucario/lucario_rl_mcts.ipynb`](lucario/lucario_rl_mcts.ipynb) | Track D: 40-iter MCTS self-play on Mega Lucario deck (retired) |
| Lucario runtime (synced) | [`../agent/lucario_mcts_runtime.py`](../agent/lucario_mcts_runtime.py) | Mechanical copy of notebook training loop for local import |
| Lucario import script | [`../scripts/import_lucario_rl_outputs.py`](../scripts/import_lucario_rl_outputs.py) | Package downloaded `model_best.pth` → `track_d_lucario_rl_mcts.tar.gz` |
| Alakazam deep Track B | [`../report/kaggle_notebook_jobs/alakazam_deep_track_b.md`](../report/kaggle_notebook_jobs/alakazam_deep_track_b.md) | 1M GPU Learned spec (Python 3.13 + cu128) |

## Local Track B (no notebook)

```powershell
C:\Users\tobin\AppData\Local\Programs\Python\Python313\python.exe scripts/train_track_b_deck.py `
  --deck agent_decks/pool_alakazam_dudunsparce.csv --timesteps 1000000 --gate-games 40 --package
```

## After notebook run

1. Download `model_best.pth`, `metrics.csv`, `run_meta.json` from Kaggle working dir
2. Save under `report/kaggle_notebook_jobs/lucario/kaggle_download_<date>/`
3. `python scripts/import_lucario_rl_outputs.py --source <dir>`
4. `python scripts/record_local_battle.py` + `python scripts/analyze_submission.py --ref <ref>` before re-submit
