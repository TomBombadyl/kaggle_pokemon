# Search hybrid A/B experiment

- UTC: 2026-07-30T17:10:40Z
- Variants: lucario200, lucario400, lucario400_k3, lucario400_blend02, budget400_blend015

## Overall

| Variant | WR% | 95% CI | W/G | Elapsed | Desc |
|---------|-----|--------|-----|---------|------|
| lucario200 | **16.7** | [11.1, 24.3] | 20/120 | 7.2s | LucarioSearchScorer 200ms guard_k=2 |
| lucario400 | **25.8** | [18.8, 34.3] | 31/120 | 7.7s | LucarioSearchScorer 400ms guard_k=2 |
| lucario400_k3 | **21.0** | [14.7, 29.2] | 25/119 | 7.1s | LucarioSearchScorer 400ms guard_k=3 (looser) |
| lucario400_blend02 | **28.3** | [21.0, 37.0] | 34/120 | 6.9s | LucarioSearch 400ms + Lucario-rank blend 0.2 |
| budget400_blend015 | **19.2** | [13.1, 27.1] | 23/120 | 5.4s | SearchScorer 400ms + heuristic blend 0.15 |

## Per-matchup

### lucario200

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 12.5 | 5-35-0 |
| real_mega_abomasnow_ex | 15.0 | 6-34-0 |
| real_iono | 22.5 | 9-31-0 |

### lucario400

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 30.0 | 12-28-0 |
| real_mega_abomasnow_ex | 30.0 | 12-28-0 |
| real_iono | 17.5 | 7-33-0 |

### lucario400_k3

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 5.1 | 2-37-1 |
| real_mega_abomasnow_ex | 32.5 | 13-27-0 |
| real_iono | 25.0 | 10-30-0 |

### lucario400_blend02

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 25.0 | 10-30-0 |
| real_mega_abomasnow_ex | 22.5 | 9-31-0 |
| real_iono | 37.5 | 15-25-0 |

### budget400_blend015

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 12.5 | 5-35-0 |
| real_mega_abomasnow_ex | 22.5 | 9-31-0 |
| real_iono | 22.5 | 9-31-0 |

## Deltas vs first variant

| Variant | ΔWR pp |
|---------|--------|
| lucario400 − lucario200 | +9.2 |
| lucario400_k3 − lucario200 | +4.3 |
| lucario400_blend02 − lucario200 | +11.7 |
| budget400_blend015 − lucario200 | +2.5 |

Note: local gate WR does **not** sort ladder μ (RULINGS). Use n≥32 as filter; promote only if ΔWR ≥ +2pp with non-overlapping CI or SPRT.
