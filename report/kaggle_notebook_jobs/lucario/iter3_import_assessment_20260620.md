# Lucario RL iter 3 import — 2026-06-20

## Artifacts moved

From `C:\Users\tobin\Downloads\` →
[`kaggle_download_iter3_20260620/`](kaggle_download_iter3_20260620/)

| File | Role |
|------|------|
| `model_iter0.pth` … `model_iter3.pth` | Per-iteration training snapshots |
| `model_best.pth` | **Replaced with `model_iter2.pth`** — Downloads copy was stale (10:26) |
| `model_champion_iter2.pth` | Explicit champion copy (iter 2 gate winner) |
| `metrics.csv` | Rows 0–1 from download; rows 2–3 from notebook screenshot |
| `run_meta.json` | Import metadata + config (`search=43`, `iters=40`) |

## Training summary (search=43, d256/4h/512ff/2+2)

| iter | vs_random | gate | promoted | Notes |
|------|-----------|------|----------|-------|
| 0 | 0.850 | 0.975 | **1** | First champion |
| 1 | 0.917 | 0.575 | 0 | Beats random; loses gate vs iter 0 |
| 2 | **1.000** | **0.975** | **1** | **Current champion → `model_best.pth`** |
| 3 | 0.983 | **0.175** | **0** | **Not an improvement** — collapsed vs champion |

## Verdict: is iter 3 an improvement?

**No.** Iter 3 was **not promoted**. Gate win rate vs the incumbent champion was only **17.5%**
(vs **97.5%** threshold). High `vs_random` (98.3%) is misleading — the net trained on
self-play data regressed against the gated champion (iter 2).

**Use for submission:** `model_iter2.pth` / repaired `model_best.pth` — **not** `model_iter3.pth`.

**Prior ladder failure:** ref **53885445** (324.6 μ) used early iter-0 weights with empty-bench
losses. Iter 2 champion is strictly stronger on notebook metrics but still **unvalidated** on L1/L4.

## Re-import gate status

Per [`../handoffs/lucario_rl_reimport_status.md`](../handoffs/lucario_rl_reimport_status.md):

- ✅ **≥ 2 promoted iters** (iter 0, iter 2)
- ⏳ **iter ≥ 4 complete** — notebook was starting iter 4 self-play (1%) when captured; **not done**
- ⏳ Local L1 gate vs public field — not run yet on iter 2 champion

**Decision:** Keep **blocked for Kaggle upload** until iter 4+ finishes and L1 beats Search Lucario
baseline (~29% local / **668 μ** ladder). Safe to package locally for comparison.

## Next steps

```bash
# Package champion (iter 2), not iter 3
python scripts/import_lucario_rl_outputs.py \
  --source report/kaggle_notebook_jobs/lucario/kaggle_download_iter3_20260620 \
  --dest report/kaggle_notebook_jobs/lucario/imported_iter2_champion_20260620 \
  --name track_d_lucario_rl_mcts_iter2 \
  --gate-games 12

# Optional: package iter 3 for A/B (expected worse)
python scripts/package_submission.py \
  --scorer lucario_mcts \
  --model report/kaggle_notebook_jobs/lucario/kaggle_download_iter3_20260620/model_iter3.pth \
  --deck agent_decks/real_mega_lucario_ex.csv \
  --out dist/candidates/track_d_lucario_rl_mcts_iter3_ab.tar.gz
```

Re-download full `metrics.csv` + `run_meta.json` from Kaggle when iter 4+ completes.
