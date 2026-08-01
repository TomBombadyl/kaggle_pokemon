# Anti-meta autopilot

Updated: `2026-07-31T07:52:59+00:00`
Cycle: `56`

## Ship status

- Decision: `REGRESS`
- Reasons: iono 49.6875 < 55.0, dual 96.4625 < baseline 98.2375 (no regression)
- Iono: 49.6875
- Crustle min: 93.5375
- Arch: 85.4
- Dual: 96.4625
- Submits today: 2/5

## Latest learned artifacts

- Option-Q: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\artifacts\iono_q_v2\iono_option_q_20260731T080025Z.json` best_bce=0.6278596520423889 acc=0.6498023867607117
- Prior/BC: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\artifacts\iono_prior_v2\iono_prior_20260731T011433Z.json` win_multi_top1=0.5837962031364441

## Candidate ranking

| rank | candidate | smoke green | iono | crustle min | flg | majkel | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | tomato_fork_floor3 | True | 58.8 | 95.0 | 96.6 | 95.0 | 4.388 |
| 2 | tomato_fork_floor2 | True | 56.2 | 93.3 | 96.7 | 93.3 | 1.762 |
| 3 | tomato | False | 52.5 | 96.7 | 98.3 | 96.7 | -1.975 |

## Raw smoke gates

| candidate | kind | rc | real_iono | flg | majkel | overall |
|---|---|---:|---:|---:|---:|---:|
| tomato | iono | 0 | 52.5 | None | None | 52.5 |
| tomato | crustle | 0 | None | 98.3 | 96.7 | 97.5 |
| tomato_fork_floor2 | iono | 0 | 56.2 | None | None | 56.2 |
| tomato_fork_floor2 | crustle | 0 | None | 96.7 | 93.3 | 95.0 |
| tomato_fork_floor3 | iono | 0 | 58.8 | None | None | 58.8 |
| tomato_fork_floor3 | crustle | 0 | None | 96.6 | 95.0 | 95.8 |

Autopilot is local-only. It never submits to Kaggle.
