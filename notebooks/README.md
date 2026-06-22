# Notebooks index

Official reference notebooks live at the **repo root** (not under `notebooks/`):

| Reference | Path |
|-----------|------|
| RL+MCTS sample | [`../reinforcement-learning-and-mcts-sample-code.ipynb`](../reinforcement-learning-and-mcts-sample-code.ipynb) |
| Lucario rule-based | [`../a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb`](../a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb) |

## Local field RL+MCTS (primary)

Fresh training from scratch — no Kaggle notebook required:

```powershell
python scripts/bootstrap_lucario_mcts_runtime.py   # once, after sample updates
python scripts/smoke_cg_engine.py
python scripts/train_lucario_field_mcts.py --device cpu
```

Outputs: `rl_mcts_field/lucarioex_v1/` (`model_best.pth`, `metrics.csv`, `run_meta.json`).

Package:

```powershell
python scripts/package_submission.py `
  --name track_d_lucarioex_field_v1 `
  --scorer lucario_mcts `
  --deck agent_decks/real_mega_lucario_ex.csv `
  --model rl_mcts_field/lucarioex_v1/model_best.pth `
  --meta rl_mcts_field/lucarioex_v1/run_meta.json
```

## Other

| Job | Path |
|-----|------|
| Imported Alakazam Kaggle kernel | [`ryotasueyoshi_rule_based_alakazam_best5/`](ryotasueyoshi_rule_based_alakazam_best5/) |
