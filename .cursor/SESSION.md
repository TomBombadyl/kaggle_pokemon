# Session state — PTCG AI Battle Challenge

> Ephemeral handoff for Cursor. **Canonical state:** `STATE.md`. **Decisions/evidence:** `RULINGS.md`.

## Current focus

Fresh local Lucario field RL+MCTS (CPU, d128) is the reference per-deck ML stack. Runtime rebuilt
from the official RL sample with opponent-deck `search_begin`, draw=0 labels, and LucarioScorer
fallback. **5-cycle training running in background** — cycle 2+ when last checked; **do not kill**
the `train_lucario_field_mcts.py` process. When training finishes: package `model_best.pth` +
`run_meta.json`, `gate_vs_public.py`, compare to SearchScorer 668 μ; upload only with user OK.

## Key context

- **Repo:** `Z:\kaggle\pokemon` | **Branch:** `main` | **Last commit:** `251da2b` (Lucario stack)
- **Python:** `C:\Users\tobin\AppData\Local\Programs\Python\Python313\python.exe`
- **Train:** `python scripts/train_lucario_field_mcts.py --device cpu --cycles 5 --time-budget-sec 21600`
- **Log:** `rl_mcts_field/lucarioex_v1/train.log` | **Metrics:** `metrics.csv`
- **Runtime:** `agent/lucario_mcts_runtime.py` (regen: `scripts/bootstrap_lucario_mcts_runtime.py`)
- **Wrapper:** `agent/lucario_mcts_policy.py` | **Trainer:** `scripts/train_lucario_field_mcts.py`
- **Engine:** `data/sim/sample_submission/cg/cg.dll`
- **Docs updated:** `STATE.md`, `RULINGS.md`, `ARCHITECTURE.md`, `data/{EVAL_PROTOCOL,PROJECT_PRIORITIES}.md`
- **Dragapult baseline:** `agent/dragapult_agent.py` — local gate only, ladder probe pending
- **Floor:** SearchScorer **668 μ** | **Smoke gate (pre-train):** 6.7% public suite
- **Retired:** `rl_mcts_basic/`, Kaggle notebook Lucario path, Track B/C loops

## Continue prompt

```text
Continue Lucario field RL+MCTS. Read first: @C:\Users\tobin\.cursor\USER-RULES-PASTE-THIS.txt, @STATE.md, @.cursor/SESSION.md, @scripts/train_lucario_field_mcts.py

Goal: Finish 5-cycle CPU train and gate champion vs public opponents.
Status: Background train — check rl_mcts_field/lucarioex_v1/train.log and metrics.csv.
Next: When all 5 cycles done, package model_best + run_meta, gate_vs_public (30+ games), compare to 668 μ.

Branch: main | Env: Python313 | Do not stop background training | Upload only with user OK
```

## Timeline

- **2026-06-22T14:28Z** | 5-cycle CPU train started
- **2026-06-22T15:40Z** | handoff by user | conv `093ff243`
- **2026-06-22T16:30Z** | full doc/state sync (STATE, RULINGS, EVAL_PROTOCOL, PROJECT_PRIORITIES, READMEs)
