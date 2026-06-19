# Session state — PTCG AI Battle Challenge

## Current focus

All **5 daily Simulation slots used** (2026-06-19). Kyogre heuristic leads at **633.0** μ (#53854707);
Track B LearnedScorer probes landed lower after matchmaking — alakazam **490.4**, dragapult **468.9**.
Track A SearchScorer probes (TA1 Kyogre+2e #53856711, TA2 Abomasnow+4e #53856676) at validation **600.0**;
ladder μ still settling (~40 min). **Next:** sync ladder + fetch agent logs for all 5 refs; compare
brains/decks; plan tomorrow's probes (crustle/starmie Track B or Track A @40g gate).

## Key context

- **Repo:** `Z:\kaggle\pokemon` | **Branch:** `main` (ahead 1 — commit `ad479ed`, unpushed)
- **Today's ladder (latest μ):** Kyogre heuristic **633.0** | alakazam **490.4** | dragapult **468.9** | TA1/TA2 **600.0** (post-validation)
- **Refs:** #53854707 Kyogre | #53856584 alakazam | #53856590 dragapult | #53856711 TA1 | #53856676 TA2
- **Track B:** LearnedScorer + `distilled_v1.npz`; spread in `report/track_b_deck_spread.md`
- **Track A:** SearchScorer; probes in `report/track_a/ladder_probes.md`
- **RL/distill:** `torch_distill` 1096 decisions; gate 206/240 @40g (`report/distill_gate.md`)
- **Agent logs:** 15 episodes for Kyogre ref; fetch others: `python scripts/track_ladder.py --fetch-logs`
- **Ladder sync:** `python scripts/track_ladder.py` — history `report/ladder_history.csv`
- **Models:** `agent/models/distilled_v1.npz` local only (gitignored path pattern — not committed)
- **Decision:** 600 μ = validation baseline, not failure; real W/L updates after matchmaking
- **Decision:** Diversify decks across agents; Kyogre heuristic best ladder signal so far
- **No Kaggle submit** without explicit user OK (today's quota spent)

## Continue prompt

```text
Continue PTCG ladder analysis after 5/5 daily submits. Read first: @C:\Users\tobin\.cursor\USER-RULES-PASTE-THIS.txt, @.cursor/SESSION.md, @PROGRESS.md, @report/ladder_history.csv, @report/track_b_deck_spread.md

Goal: Sync ladder μ for all 5 refs, fetch agent logs, compare Track A vs B vs heuristic.
Status: Kyogre 633.0 μ; Learned alakazam 490.4, dragapult 468.9; TA1/TA2 at 600 validation.
Next: python scripts/track_ladder.py --fetch-logs; analyze misplays; prep tomorrow probes.

Branch: main (ahead 1) | Env: Python 3.13, torch 2.6.0+cu124 | No submit without user OK.
```

## Timeline

- **2026-06-19T17:35:00Z** | handoff by user | 5/5 ladder slots live
- **2026-06-19T17:33:00Z** | run 18 | TA1+TA2 submitted; ladder sync dragapult 468.9, alakazam 490.4
- **2026-06-19T17:24:00Z** | run 18 | Track B alakazam + dragapult submitted
- **2026-06-19** | run 16–17 | RL distill export; Track B deck spread; Track A probe tooling
- **2026-06-19T16:08:00Z** | A2 Kyogre #53854707 first successful upload
