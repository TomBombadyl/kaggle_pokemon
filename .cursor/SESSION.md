# Session state — PTCG AI Battle Challenge

## Current focus

Fresh local Lucario field RL+MCTS (CPU, d128) is the reference per-deck stack. Runtime rebuilt from the official RL sample with opponent-deck `search_begin`, draw=0 labels, and LucarioScorer fallback. **5-cycle training is running in background** (~cycle 1 mirror phase when handed off); do not kill PID 27936 / the `train_lucario_field_mcts.py` process. When training finishes, package `model_best.pth` + `run_meta.json`, re-run `gate_vs_public.py`, compare to SearchScorer 668 μ floor; upload only with user OK.

## Key context

- **Repo:** `Z:\kaggle\pokemon` | **Branch:** `main`
- **Python:** `C:\Users\tobin\AppData\Local\Programs\Python\Python313\python.exe` (CPU train; GPU torch+cu128 available)
- **Train cmd:** `python scripts/train_lucario_field_mcts.py --device cpu --cycles 5 --time-budget-sec 21600`
- **Log:** `rl_mcts_field/lucarioex_v1/train.log` | **Outputs:** `model{cycle}.pth`, `model_best.pth`, `metrics.csv`, `run_meta.json`
- **Runtime:** `agent/lucario_mcts_runtime.py` (regen via `scripts/bootstrap_lucario_mcts_runtime.py`)
- **Submission wrapper:** `agent/lucario_mcts_policy.py`
- **Trainer:** `scripts/train_lucario_field_mcts.py` — 5 cycles × 10 field decks
- **Engine:** `data/sim/sample_submission/cg/cg.dll` (fetched; smoke via `scripts/smoke_cg_engine.py`)
- **Strategy doc:** `ARCHITECTURE.md` — one deck, one brain, matchup levers per archetype
- **Reference notebooks (repo root):** `reinforcement-learning-and-mcts-sample-code.ipynb`, `a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb`
- **Deleted/cleaned:** `notebooks/rl_mcts_field_train/`, `rl_mcts_basic/` (via `scripts/cleanup_old_rl_artifacts.py`)
- **Smoke gate:** public suite **6.7%** on smoke checkpoint (pre full train; expected)
- **Baseline floor:** SearchScorer **668 μ** — do not upload without beating/matching user bar
- **No resume** from Snorlax-era or `rl_mcts_basic` checkpoints
- **Blockers:** none for offline work; Kaggle upload needs explicit user OK

## Continue prompt

```text
Continue Lucario field RL+MCTS. Read first: @C:\Users\tobin\.cursor\USER-RULES-PASTE-THIS.txt, @.cursor/SESSION.md, @scripts/train_lucario_field_mcts.py, @agent/lucario_mcts_runtime.py

Goal: Finish 5-cycle CPU train and gate the champion vs public opponents.
Status: Background train running — check rl_mcts_field/lucarioex_v1/train.log and metrics.csv.
Next: When train.log shows all 5 cycles done, package model_best + run_meta, run gate_vs_public (30+ games), compare to SearchScorer 668 μ.

Branch: main | Env: Python313 (CPU train) | Do not stop background training | Upload only with user OK
```

## Timeline

- **2026-06-22T14:28Z** | 5-cycle CPU train started (`train_lucario_field_mcts.py`, PID 27936)
- **2026-06-22T15:40Z** | handoff by user | conv `093ff243`
