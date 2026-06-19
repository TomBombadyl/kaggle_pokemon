# Finals strategy (massive-jump plan)

## Portfolio recommendation (2026-06-19 run 13)

Pending SPRT gates with larger game counts and user-approved Kaggle uploads.

| Slot | Agent | Deck | Rationale |
|------|-------|------|-----------|
| Generalist | Heuristic + SearchScorer (Track A) | `agent/deck.csv` (Abomasnow) | Best packaged random gate (A2 963/1000); search augments high-leverage turns |
| Exploiter-resistant | LearnedScorer / distilled numpy | `agent_decks/pool_crustle.csv` or best `deck_search` variant | Anti-ex line; diversify matchup coverage vs spread/aggro pool |

## Ladder probes (do not auto-submit)

- Record all submission IDs in `report/ladder_history.csv`
- Use `scripts/track_ladder.py` after each upload
- Five Simulation slots/day; two finals at deadline
- **μ interpretation:** ~600 on COMPLETE is post-validation starting μ (self-play
  gate), not field rank; real ladder W/L updates after matchmaking (~40+ min)

## Local gates (SPRT)

- Track A: `scripts/gate_track_a.py` — SearchScorer vs pool (currently **not passed** at smoke game count)
- Track B: `scripts/gate_track_b.py` — LearnedScorer vs pool
- Distill: `scripts/distill_policy.py` — latency + numpy-only packaging

## Nightly cadence

```bash
python scripts/nightly.py --run-all
```

Checkpoint: `report/nightly_checkpoint.json` (all 16 steps complete as of run 13).
