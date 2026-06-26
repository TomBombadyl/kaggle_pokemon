# Archaludon: agent scoring vs + packaged bench guard

- Games per opponent per variant: **50**
- Suite: `full`
- Hero deck: `Z:\kaggle\pokemon\agent_decks\archaludon_ex_cinderace.csv`
- Both variants include in-agent `_empty_bench_basic_score` (R7b)

| Opponent | WR% (guard off) | WR% (+guard) | Δpp | no_active (off) | no_active (on) |
|----------|----------------:|-------------:|----:|----------------:|---------------:|
| dragapult_ex_sample | 66.0 | 52.0 | -14.0 | 5 | 4 |
| real_mega_abomasnow_ex | 76.0 | 76.0 | +0.0 | 0 | 0 |
| real_iono | 38.0 | 42.0 | +4.0 | 1 | 1 |
| real_dragapult_ex | 82.0 | 84.0 | +2.0 | 1 | 0 |
| real_mega_lucario_ex | 70.0 | 86.0 | +16.0 | 1 | 0 |

## Overall

- Guard off (agent only): **66.4%** (n=250), no_active: **8**
- + packaged guard: **68.0%** (n=250), no_active: **5**
- Δ: **+1.6 pp** vs paired A/B

**Ladder truth:** ref 54083197 @ 1224.2 μ. Probe only with material delta + upload gate.
