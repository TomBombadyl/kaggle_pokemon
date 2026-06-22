# Notebooks index

Official reference notebooks live at the **repo root** (not under `notebooks/`):

| Reference | Path |
|-----------|------|
| RL+MCTS sample | [`../reinforcement-learning-and-mcts-sample-code.ipynb`](../reinforcement-learning-and-mcts-sample-code.ipynb) |
| Lucario rule-based | [`../a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb`](../a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb) |

**Retired:** `notebooks/rl_mcts_field_train/`, `notebooks/lucario/`, `notebooks/kaggle_rl_train.ipynb`
— use local scripts below instead (`scripts/cleanup_old_rl_artifacts.py` removes stale copies).

---

## Local Lucario field RL+MCTS (primary ML path)

Fresh training from scratch — real field opponents, no Kaggle notebook required:

```powershell
python scripts/fetch_sim_engine.py              # once: cg.dll
python scripts/bootstrap_lucario_mcts_runtime.py   # once, after sample updates
python scripts/smoke_cg_engine.py
python scripts/train_lucario_field_mcts.py --device cpu --cycles 5
```

Outputs (gitignored): `rl_mcts_field/lucarioex_v1/` (`model_best.pth`, `metrics.csv`, `run_meta.json`, `train.log`).

Gate + package:

```powershell
python scripts/extract_public_agents.py       # if opponents dir empty
python scripts/gate_vs_public.py --games 30
python scripts/package_submission.py `
  --name track_d_lucarioex_field_v1 `
  --scorer lucario_mcts `
  --deck agent_decks/real_mega_lucario_ex.csv `
  --model rl_mcts_field/lucarioex_v1/model_best.pth `
  --meta rl_mcts_field/lucarioex_v1/run_meta.json
```

**Ship bar:** beat SearchScorer **668 μ** on ladder (Ruling R3); user OK for upload.

---

## Per-deck rule pilots

| Archetype | Agent | Deck | Gate |
|-----------|-------|------|------|
| Dragapult ex (Crispin) | `agent/dragapult_agent.py` | `agent_decks/dragapult_ex_sample.csv` | `scripts/gate_dragapult.py` |
| Mega Lucario ex (rules) | `agent/lucario_policy.py` | `agent_decks/real_mega_lucario_ex.csv` | `scripts/gate_vs_public.py` with search/heuristic |

Pattern documented in `ARCHITECTURE.md` § Per-deck agent template.

---

## Other

| Job | Path |
|-----|------|
| Imported Alakazam Kaggle kernel (659 μ reference) | [`ryotasueyoshi_rule_based_alakazam_best5/`](ryotasueyoshi_rule_based_alakazam_best5/) |
