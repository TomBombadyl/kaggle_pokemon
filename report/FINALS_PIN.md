# Finals pin checklist (user action on Kaggle)

Run episode analysis **before** pinning Finals:

```bash
python scripts/analyze_submission.py --ref 53869254   # Lucario Search 668
python scripts/analyze_submission.py --ref 53886522   # SmartBench Lucario 600
```

## L4 results (2026-06-20)

| Ref | μ | win_rate | avg_turns | fast_loss_pct | top_loss | Finals? |
|-----|---|----------|-----------|---------------|----------|---------|
| 53869254 | 668 | 48.5% (16/33) | 13.4 | 58.8% | unknown | **Final 1** |
| 53886522 | 600 | 50.0% (1/2) | 10.5 | 100% | unknown | **Do not pin** — too few episodes; short games |

**Recommendation:** Pin **53869254** (Search Lucario) as **both** Final slots until SmartBench accumulates more episodes and `avg_turns > 15` with `fast_loss_pct < 20%`. Re-run analysis after ~20 public episodes on 53886522.

## Decision matrix

| Candidate | Ref | μ | Pin as Final if… |
|-----------|-----|---|------------------|
| track_a_lucario_ex_search | 53869254 | 668 | Always Final 1 (best proven μ) |
| track_a_lucario_ex_search_v2 | — | — | L1 incomplete; partial mirror 23% — **do not pin** until beats 53869254 |
| track_c_lucario_rulecore_smartbench | 53886522 | 600+ | `avg_turns > 15`, `fast_loss_pct < 20%`, top loss ≠ `no_active` |
| a2_kyogre | 53854707 | 633 | Portfolio backup if Lucario slots filled |

## Steps on Kaggle Submissions page

1. Open [Submissions tab](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/submissions)
2. Manually select **2 Final Submissions** (do not rely on auto latest-2)
3. Recommended: **53869254** (Search Lucario) + best Lucario after L4 stats confirm

See [`data/SUBMISSION_PLAYBOOK.md`](../data/SUBMISSION_PLAYBOOK.md) §2.2.
