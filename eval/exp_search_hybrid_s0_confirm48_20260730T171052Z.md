# Search hybrid A/B experiment

- UTC: 2026-07-30T17:11:22Z
- Variants: budget200, budget400, lucario400_blend02, lucario400

## Overall

| Variant | WR% | 95% CI | W/G | Elapsed | Desc |
|---------|-----|--------|-----|---------|------|
| budget200 | **16.7** | [11.5, 23.6] | 24/144 | 7.0s | SearchScorer budget=200ms (prod baseline) |
| budget400 | **19.4** | [13.8, 26.7] | 28/144 | 6.9s | SearchScorer budget=400ms |
| lucario400_blend02 | **19.4** | [13.8, 26.7] | 28/144 | 8.2s | LucarioSearch 400ms + Lucario-rank blend 0.2 |
| lucario400 | **24.3** | [18.0, 31.9] | 35/144 | 8.2s | LucarioSearchScorer 400ms guard_k=2 |

## Per-matchup

### budget200

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 14.6 | 7-41-0 |
| real_mega_abomasnow_ex | 18.8 | 9-39-0 |
| real_iono | 16.7 | 8-40-0 |

### budget400

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 12.5 | 6-42-0 |
| real_mega_abomasnow_ex | 25.0 | 12-36-0 |
| real_iono | 20.8 | 10-38-0 |

### lucario400_blend02

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 12.5 | 6-42-0 |
| real_mega_abomasnow_ex | 20.8 | 10-38-0 |
| real_iono | 25.0 | 12-36-0 |

### lucario400

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 25.0 | 12-36-0 |
| real_mega_abomasnow_ex | 29.2 | 14-34-0 |
| real_iono | 18.8 | 9-39-0 |

## Deltas vs first variant

| Variant | ΔWR pp |
|---------|--------|
| budget400 − budget200 | +2.8 |
| lucario400_blend02 − budget200 | +2.8 |
| lucario400 − budget200 | +7.6 |

Note: local gate WR does **not** sort ladder μ (RULINGS). Use n≥32 as filter; promote only if ΔWR ≥ +2pp with non-overlapping CI or SPRT.
