# Search hybrid A/B experiment

- UTC: 2026-07-30T17:09:55Z
- Variants: budget200, budget400, lucario400

## Overall

| Variant | WR% | 95% CI | W/G | Elapsed | Desc |
|---------|-----|--------|-----|---------|------|
| budget200 | **11.7** | [7.1, 18.6] | 14/120 | 6.4s | SearchScorer budget=200ms (prod baseline) |
| budget400 | **17.5** | [11.7, 25.3] | 21/120 | 6.3s | SearchScorer budget=400ms |
| lucario400 | **25.8** | [18.8, 34.3] | 31/120 | 7.0s | LucarioSearchScorer 400ms guard_k=2 |

## Per-matchup

### budget200

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 10.0 | 4-36-0 |
| real_mega_abomasnow_ex | 15.0 | 6-34-0 |
| real_iono | 10.0 | 4-36-0 |

### budget400

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 17.5 | 7-33-0 |
| real_mega_abomasnow_ex | 12.5 | 5-35-0 |
| real_iono | 22.5 | 9-31-0 |

### lucario400

| Opponent | WR% | W-L-D |
|----------|-----|-------|
| dragapult_ex_sample | 27.5 | 11-29-0 |
| real_mega_abomasnow_ex | 20.0 | 8-32-0 |
| real_iono | 30.0 | 12-28-0 |

## Deltas vs first variant

| Variant | ΔWR pp |
|---------|--------|
| budget400 − budget200 | +5.8 |
| lucario400 − budget200 | +14.2 |

Note: local gate WR does **not** sort ladder μ (RULINGS). Use n≥32 as filter; promote only if ΔWR ≥ +2pp with non-overlapping CI or SPRT.
