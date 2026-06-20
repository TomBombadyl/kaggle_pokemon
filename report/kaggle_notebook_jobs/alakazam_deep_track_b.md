# Alakazam Track B — deep GPU training (queued)

**Status:** NOT submitted. Local CPU runs (100k–200k) peaked ~21–29% eval WR; gate failed (32/110 pool).

**Deck:** `agent_decks/pool_alakazam_dudunsparce.csv`  
**Target artifact:** `dist/candidates/track_b_learned_alakazam_v2.tar.gz`

---

## Why GPU

Alakazam meta list is search-heavy; MaskablePPO needs **≥1M timesteps** and a large distill set
to match Search on pool opponents. CPU 200k is insufficient (see `report/rl_train/eval_alakazam-dudunsparce.json`).

---

## Kaggle notebook cell (attach repo + GPU)

```bash
cd /kaggle/working
# clone or upload pokemon repo, then:
python scripts/train_track_b_deck.py \
  --deck agent_decks/pool_alakazam_dudunsparce.csv \
  --slug alakazam \
  --timesteps 1000000 \
  --n-envs 6 \
  --opponents benchmark \
  --holdout a2_kyogre \
  --distill-episodes 500 \
  --distill-epochs 50 \
  --gate-games 40 \
  --package

# Download outputs:
#   agent/models/distilled_alakazam_v1.npz
#   dist/candidates/track_b_learned_alakazam.tar.gz
#   report/track_b_gates/track_b_learned_alakazam_gate.md
```

Rename archive locally to `track_b_learned_alakazam_v2.tar.gz` if gate passes.

---

## Submit only if

1. Gate ≥ prior best learned deck probe (~210/240 pool) OR clear improvement vs Search baseline
2. `scripts/smoke_test.py` passes
3. User explicit OK for upload

```bash
kaggle competitions submit pokemon-tcg-ai-battle \
  -f dist/candidates/track_b_learned_alakazam_v2.tar.gz \
  -m "Track B Learned Alakazam 1M+GPU gate=<W>/<T> per-deck distill"
```

---

## Prior ladder reference

| Ref | Agent | μ |
|-----|-------|---|
| 53856584 | track_b_learned_alakazam (old buggy distill) | 490.4 |

Goal: beat 490 locally before spending a daily upload slot.
