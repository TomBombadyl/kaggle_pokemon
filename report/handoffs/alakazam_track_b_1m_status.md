# Alakazam Track B 1M GPU run — not submission-worthy (2026-06-20)

**Status:** `[blocked]` — do **not** distill/gate/package/submit this checkpoint.

## Command run

```powershell
python scripts/train_track_b_deck.py \
  --deck agent_decks/pool_alakazam_dudunsparce.csv \
  --slug alakazam --timesteps 1000000 --n-envs 6 \
  --holdout a2_kyogre --distill-episodes 500 --distill-epochs 50 \
  --gate-games 40 --package --promote
```

## What completed

| Phase | Status |
|-------|--------|
| RL train (1M steps, CUDA, 6 envs) | **Done** — `report/rl_train/checkpoint.json` status `ok` |
| Distill → gate → package | **Not run** on this 1M weights (pipeline stopped after train) |

Artifacts: `agent/models/rl_policy.zip` (1M), `report/rl_train/eval_alakazam-dudunsparce.json`.

`distilled_alakazam_v1.npz` is still from the earlier **100k** run (gate **32/110**, failed).

## Verdict: not a great run

| Signal | Result | Notes |
|--------|--------|-------|
| Train pool WR @ 1M | **30.8%** (4/13) | Bounced 12–40% entire run; no stable climb |
| Peak train WR | **40.0%** @ 460k | |
| Kyogre holdout peak | **21.1%** @ 120k | Best generalization moment |
| Kyogre holdout @ 1M | **0%** (0/16) | Collapsed — pool overfit pattern |
| Prior L1 gate (100k distill) | **32/110** vs Search **119/240** | Failed |
| RuleCore Alakazam L1 | **5.6%** | Better path than Learned for this deck |

**Conclusion:** 1M PPO did not fix the Alakazam Learned path. Kyogre holdout collapse +
failed Track B gate history → **retire this line** unless architecture changes (Search-first,
RuleCore + tech, or checkpoint sweep finds a rare mid-run spike — unlikely from this curve).

## Do not

- Run `--skip-train` distill/gate on final 1M weights expecting a ladder probe
- Submit Track B Learned Alakazam
- Spend another 1M GPU steps without a new hypothesis (curriculum, bench shaping, Search teacher)

## Better alternatives (unchanged)

1. **Finals:** Search Lucario ref **53869254** (668 μ)
2. **Local L2 passed:** gen19 fast-basic / spread-control Track B (`dist/candidates/track_b_gen19_*.tar.gz`)
3. **Lucario next:** `LucarioSearchScorer` hybrid; RL iter **2** champion when notebook + L1 ready
4. **Alakazam:** RuleCore + `ALAKAZAM_TECH` if revisiting — not Learned PPO at 1M

## Machine log

[`report/track_b_runs/alakazam_1m_20260620_train_only.json`](../track_b_runs/alakazam_1m_20260620_train_only.json)
