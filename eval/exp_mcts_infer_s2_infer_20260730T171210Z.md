# MCTS inference A/B

- Model: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\rl_mcts_field\lucarioex_v2\model_best.pth`
- Games/opp: 32
- Suite: core

| Variant | WR% | 95% CI | W/G | Elapsed | Desc |
|---------|-----|--------|-----|---------|------|
| sc12 | **4.2** | [1.6, 10.2] | 4/96 | 47.5s | SEARCH_COUNT=12 (old submit) |
| sc20 | **5.2** | [2.2, 11.6] | 5/96 | 99.6s | SEARCH_COUNT=20 (train-aligned) |
| sc20_prior02 | **5.2** | [2.2, 11.6] | 5/96 | 114.6s | sc20 + LucarioScorer prior blend 0.2 |

## Δ vs first

| Variant | ΔWR pp |
|---------|--------|
| sc20 − sc12 | +1.0 |
| sc20_prior02 − sc12 | +1.0 |
