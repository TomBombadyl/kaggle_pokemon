# Session state — PTCG AI Battle Challenge

> Ephemeral handoff for Cursor. **Canonical state:** `STATE.md`. **Decisions:** `RULINGS.md` (R11).

## Current focus

**Standing build order (Session 44d):** (1) global best rules per deck → (2) per-opponent matchup
levers → (3) field-mixture weighting. Meta tracker is phase-3 only — do not weight training or
upload picks by distribution until phases 1–2 pass L1 gates. Lucario field RL train may still be
running (check `metrics.csv`); RL does not replace missing global rules or levers (Abomasnow 0%).

## Key context

- **Repo:** `Z:\kaggle\pokemon` | **Branch:** `main`
- **Plan:** `ARCHITECTURE.md` § Per-deck template phases 1–3 | **Backlog:** `TASKS.md` R1–R3
- **Ruling R11:** rules before mixture (`RULINGS.md` Part 3)
- **Phase 1 next:** gate Lucario global rules (`lucario_policy.py`) vs real field — baseline WR
- **Phase 2 first lever:** Lucario vs Abomasnow spread (0% in train eval)
- **Phase 3 draft:** `report/OPPONENT_DECK_DISTRIBUTION.md`, `scripts/update_opponent_tracker.py`
- **Lucario RL:** `rl_mcts_field/lucarioex_v1/metrics.csv` — cycle 3+; gate when done, R3 floor 668 μ
- **Dragapult:** ladder ref `53950246` SUBMITTED_PENDING — wait for μ before Slot 2 decision
- **Python:** `C:\Users\tobin\AppData\Local\Programs\Python\Python313\python.exe`
- **Upload:** user OK only; ≥2 stable μ readings (R1)

## Continue prompt

```text
Continue pilot rules build (phases 1–3). Read first: @C:\Users\tobin\.cursor\USER-RULES-PASTE-THIS.txt, @.cursor/SESSION.md, @STATE.md, @ARCHITECTURE.md, @TASKS.md

Goal: Global rules per deck, then matchup levers, then mixture weighting — not the reverse.
Status: R11 solidified; Lucario RL train cycle 3+; opponent tracker is phase-3 draft.
Next: Gate Lucario global rules baseline (gate_vs_public rules-only), then add abomasnow_spread lever.

Branch: main | Env: Python313 | Defer meta-weighted training until R1+R2 pass
```

## Timeline

- **2026-06-22T14:28Z** | 5-cycle CPU Lucario train started
- **2026-06-22T15:40Z** | handoff | conv `093ff243`
- **2026-06-22T16:30Z** | full doc sync (Session 44c)
- **2026-06-22T17:15Z** | R11 rules-before-mixture + opponent tracker | handoff by user
