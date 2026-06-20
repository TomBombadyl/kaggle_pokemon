# 12:01 Submission — Go Package

**Prepared:** 2026-06-20 (just before midnight). Daily quota (5 uploads) resets at 00:00; fire at 12:01.

## Decision: what goes up at 12:01

**Primary (fire first):** `dist/candidates/track_b_learned_rl_deck_kaggle_20260619.tar.gz`
- Gate PASS — Learned **210/240 (87.5%)**, SPRT `accept_b`
- Re-verified tonight: **17/20 decided, 0 unfinished, 0 draws**, clean import, 60-card deck select OK
- Best validated *learned* (Track B) candidate we have. This is the right probe given the "learn" direction.

**Why not the 1M/3M ramps:** both gate lower (193/240, 201/240) — strictly weaker. Hold them.

**Why not a heuristic:** a2_kyogre is the proven ladder leader (633 μ) and a safe Final-slot anchor, but it does **zero** learning — off-strategy for tonight's probe. Keep it as the fallback Final slot, not the probe.

## Ready-to-fire command (run on your machine — sandbox has no kaggle egress)

```bash
kaggle competitions submit -c pokemon-tcg-ai-battle \
  -f dist/candidates/track_b_learned_rl_deck_kaggle_20260619.tar.gz \
  -m "Track B learned RL-deck (100k, gate 210/240 87.5% accept_b) — ladder probe"
```

After it shows COMPLETE (~40 min for μ to populate):
```bash
python scripts/track_ladder.py --fetch-logs
```
Then log ref + μ in `report/ladder_history.csv`.

## Quota plan for the day (5 slots)
1. **00:01** — Track B learned RL-deck (above) — probe
2–5. **Hold** until the online-learning agent below is built + gated. Don't burn slots on the weaker ramps.

## On "learn after every match" — the honest constraint + the plan
Kaggle re-instantiates the agent each episode; weights cannot be updated *between* ladder matches on their servers. Two achievable forms that actually deliver the intent:

- **A. In-agent online adaptation (within the match):** opponent-modeling / a bandit over OptionScorer weights that updates each turn from observed outcomes. Ships inside the tarball, runs live, no platform persistence needed. **← build this next; it's the real "learns as it plays."**
- **B. Self-improving harness loop (between uploads):** the checkpoint-sweep path — retrain → distill → gate → re-upload daily, each build learning from the prior ladder logs. This is "learn after every match" at the *campaign* level.

Recommendation: probe the frozen learned candidate tonight (slot 1), and start **A** as the headline workstream for the remaining slots.
