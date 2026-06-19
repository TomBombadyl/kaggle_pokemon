# Session state — PTCG AI Battle Challenge

## Current focus

Competition goal: strong Simulation ladder agent plus offline Track B (BC/RL/distill) without regressing legality. A2 Kyogre submit ref **53854707** is live: validation μ **600.0** (self-play gate, not field rank), API ladder **672.7** after matchmaking; validation-vs-ladder interpretation is documented. RL pipeline finished (**50k MaskablePPO**); Track B SPRT gate **PASS 102/120** vs pool (Search 58/120); distill artifacts **bc_v1.npz** / **distilled_v1.npz** with **RL→numpy export still open** (distill used BC fallback). Agent log fetch is wired (`scripts/fetch_agent_logs.py`, `track_ladder.py --fetch-logs` → `report/agent_logs/`). **Immediate next:** fix RL weight export, `python scripts/gate_track_b.py --games 40`, rebuild **`track_b_learned.tar.gz`** before any Track B submit; post-submit run `--fetch-logs`. **No Kaggle submit without explicit user OK.**

## Key context

- **Repo:** `Z:\kaggle\pokemon` | **Branch:** `main` (up to date with `origin/main`)
- **Python:** 3.13.x | **RL:** `torch 2.6.0+cu124` (RTX 4070 Ti SUPER)
- **Ladder:** A2 Kyogre ref **53854707** — validation **600.0** → API **672.7** (`report/ladder_history.csv`, `data/META_NOTES.md`)
- **Agent logs:** `scripts/fetch_agent_logs.py`; `python scripts/track_ladder.py --fetch-logs` after submits
- **`track_ladder.py`:** dedupe fixed on `(ref, status, publicScore)` so score updates append
- **Track B:** BC + 50k RL OK; gate **102/120** PASS; smoke **17/17**; checkpoint `report/rl_train/checkpoint.json`
- **Open:** RL→numpy bridge for distill (not BC fallback); no **online RL** in submission (`META_NOTES.md`)
- **Packaging:** `dist/` gitignored; rebuild **`track_b_learned.tar.gz`** before Track B upload (do not rely on stale tarball)
- **Brains:** `agent/search_policy.py`, `learned_policy.py`, `evalfn.py`, `features.py`; orchestration `scripts/nightly.py`, `arena.py`, gates
- **`.gitignore`:** `report/agent_logs/*.json` (manifest CSV OK)
- **Secrets:** `.kaggle/` gitignored — never commit
- **Decision:** treat post-upload **600** validation score as expected; ladder μ is separate metric
- **Subagent doc:** `.cursor/agents/ptcg-rl-trainer.md`

## Continue prompt

```text
Continue PTCG Track B + ladder iteration. Read first: @C:\Users\tobin\.cursor\USER-RULES-PASTE-THIS.txt, @.cursor/SESSION.md, @PROGRESS.md, @scripts/distill_policy.py, @rl/train_rl.py

Goal: Fix RL→numpy weight export, re-distill, rebuild track_b_learned package, re-gate at 40+ games.
Status: A2 ref 53854707 ladder μ 672.7; Track B gate PASS 102/120; agent log fetch wired.
Next: Export MaskablePPO weights to numpy, run gate_track_b.py --games 40, package_submission track_b_learned.

Branch: main | Env: Python 3.13, torch 2.6.0+cu124 | No Kaggle submit without explicit user OK.
```

## Timeline

- **2026-06-19** | RL run | 50k MaskablePPO, gate Track B PASS, smoke 17/17
- **2026-06-19** | run 13 | massive-jump plan fully implemented; nightly 16/16 pass
- **2026-06-19T16:10:00Z** | A2 Kyogre uploaded #53854707 — validation μ 600.0 → ladder **670.3** (~40 min) → **672.7** (sync)
- **2026-06-19T18:45:00Z** | handoff by user | conv `48c36bcb`
