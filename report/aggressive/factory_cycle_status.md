# Factory cycle status

**UTC:** 2026-07-30T23:26:09.526199+00:00  
**Policy:** Archaludon 75wr shell + Crustle lever · loop + CUDA MCTS · no Dra/Alak submit  
**Bottleneck:** Iono 40.0% (ship floor 55%, Arch≥85% needs ~55–60%); Crustle majkel 80.0% (<89%); dual 94.2% (<95%)

## Gates (latest)

| Metric | Latest | Rolling20 mean | Target | Gap |
|--------|-------:|---------------:|-------:|----:|
| Arch sprint overall | 85.4% | 84.3% | 85% | +0.4 |
| Iono | 40.0% | 31.5% | 55% | -15.0 |
| Crustle flg | 85.0% | 90.2% | 89% | -4.0 |
| Crustle majkel | 80.0% | 87.5% | 89% | -9.0 |
| Dual overall | 94.2% | 94.0% | 95% | -0.8 |

**Focus cycle:** 6 · **Loop cycle:** 60 · **Submits today:** 5 · **Arch mean8:** 84.3

## Processes (do not kill parent/child pairs)

| Role | PID | Py | MemMB |
|------|----:|----|------:|
| aggressive_loop | 123568 | sys | 176 |
| aggressive_loop | 112200 | venv | 4 |
| train_lucario_MCTS | 42132 | sys | 961 |
| train_lucario_MCTS | 99472 | venv | 4 |

## Matchup snapshot (last Arch sprint gate)

- `meta_crustle_majkel`: **91.1%**
- `meta_grimmsnarl_dries`: **94.6%**
- `meta_grimmsnarl_luca`: **100.0%**

## Next μ action

1. Keep workers healthy (venv launcher + sys worker pairs are normal).
2. Iono R14m single-lever live in `archaludon_agent` — measure focus iono mean.
3. Hold Crustle levers; majkel Hammer recovery already wired.
4. No Dra/Alak auto-submit; Arch only when iono floor + ship bar clear.

