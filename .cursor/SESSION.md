# Session state — PTCG AI Battle Challenge

## Current focus

**Goal:** Improve RL+MCTS beyond the basic Kaggle sample using mined field opponents; ladder-probe only after field eval + stable μ.
**Status (2026-06-22):** Basic d128 RL+MCTS submitted and COMPLETE — Lucario ex ref **53946742** read **899.6 μ**, Alakazam ref **53946148** read **185.4 μ** (treat Lucario as early/unstable per Ruling R1 until a second reading ≥40 min apart). Field-opponent trainer built at `notebooks/rl_mcts_field_train/` (5 cycles × 10 mined decks, Fix #2/3) but **not yet committed or run on Kaggle**. **Next:** run field training on Kaggle with `--resume` from model4; commit the notebook folder; re-fetch Lucario μ before any Final pin.

## Key context

- **Repo:** `Z:\kaggle\pokemon` | **Branch:** `main` (ahead, not pushed)
- **Latest commit:** `cc34059` — `rl_mcts_basic/*/run_meta.json`; field trainer is **untracked** under `notebooks/rl_mcts_field_train/`
- **Ladder (basic MCTS probes):** Lucario **899.6** ref 53946742; Alakazam **185.4** ref 53946148 — verify stability before trusting
- **Protected baselines:** Search Lucario **668 μ**, imported Alakazam **659**, Kyogre heuristic **633**
- **Packaging:** `scripts/package_submission.py --scorer lucario_mcts --model <pth> --meta <run_meta.json>` — `run_meta.config` must be nested or model silently falls back to RuleCore
- **Field trainer:** `notebooks/rl_mcts_field_train/run_field_train.py` + `decks/` (10 `real_*`/`top_mined_*` CSVs) + `rl_mcts_field_train.ipynb`
- **Resume checkpoints (gitignored):** `rl_mcts_basic/lucarioex_basic/model4 (1).pth`, `rl_mcts_basic/alakazam_basic/model4.pth`
- **Prior failures:** basic sample/mirror-only → 324–500 μ; AZ Fix #2 → 9.7% L1; `pool_*` proxies mispredict μ (RULINGS R2)
- **Monitor:** `kaggle competitions submissions pokemon-tcg-ai-battle -v`; `python scripts/track_ladder.py`
- **Upload policy:** user OK; 5/day; manually pick 2 Finals on Kaggle
- **GPU:** `C:\Users\tobin\AppData\Local\Programs\Python\Python313\python.exe` (cu128)

## Continue prompt

```text
Continue field-opponent RL+MCTS training. Read first: @C:\Users\tobin\.cursor\USER-RULES-PASTE-THIS.txt, @.cursor/SESSION.md, @notebooks/rl_mcts_field_train/README.md, @notebooks/rl_mcts_field_train/run_field_train.py, @RULINGS.md

Goal: run 5-cycle field training on Kaggle (mined opponents), resume from model4, then package/gate any winner.
Status: basic MCTS probes COMPLETE — Lucario 899.6 (53946742), Alakazam 185.4 (53946148); field trainer built but uncommitted/unrun.
Next: commit notebooks/rl_mcts_field_train/, run rl_mcts_field_train.ipynb on Kaggle GPU with --resume model4; re-fetch Lucario μ before Final decision.

Branch: main | Env: Python313 cu128 | Upload only with user OK
```

## Timeline

- **2026-06-22T18:00:00Z** | handoff by user | conv `5c4c9d5d`
- **2026-06-22** | Built field-opponent trainer `notebooks/rl_mcts_field_train/`; basic MCTS ladder reads Lucario 899.6 / Alakazam 185.4
- **2026-06-22T12:59:00Z** | handoff by user | conv `5c4c9d5d`
- **2026-06-22** | Submitted basic RL+MCTS Alakazam (53946148) + Lucario ex (53946742); fixed run_meta packaging bug
- **2026-06-21** | Submitted Alakazam best5 (636.8) + Trevenant (597.7); HOLD remaining slots
- **2026-06-21** | Built `analyze_winners.py` field analysis → RPS triangle + Lucario-mirror lever
- **2026-06-21** | Robust deck search proven dead-end (Search-pilot L1 3.8%); pivot to pilot/mirror work
- **2026-06-20T17:05:00Z** | handoff by user | conv `lucario-top-performer-v1`
- **2026-06-20T20:30:00Z** | handoff by user | conv `lucario-hybrid-v2`
- **2026-06-20 EOD** | LucarioSearchScorer impl + partial L1; deck-out insight; strategy doc refresh
- **2026-06-20 EOD** | Alakazam 1M retired; Lucario iter3 assessed; repo cleanup
- **2026-06-20** | SmartBench + meta tactics; ref 53886522 submitted
- **2026-06-20** | Top-performer Kaggle CLI analysis — refs 53802029–53800247
- **2026-06-20T17:35:00Z** | handoff by user | conv `high-mu-submission-plan`
- **2026-06-20T18:00:00Z** | handoff by user | conv `alakazam-upload-iter45-rl`
- **2026-06-20T18:45:00Z** | handoff by user | conv `iter45-staged-handoff`
- **2026-06-20T19:30:00Z** | handoff by user | conv `full-commit-eod-handoff`
