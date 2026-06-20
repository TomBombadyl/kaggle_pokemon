# Robust deck search (PSRO-lite)

Finds a 60-card deck that maximises win rate against the **whole field**, not the
mean vs a fixed suite. Self-contained; never touches the existing deck campaign
checkpoint (`report/rl_deck_campaign/`). Design: `report/robust_deck_optimization_design.md`.

## Run

```bash
# quick sanity
python scripts/robust_deck_search.py --smoke

# real run (CPU; minutes-to-hours by size)
python scripts/robust_deck_search.py --generations 30 --population 16 --games 10 --workers 8

# with the GPU win-rate surrogate (prunes confident matchups -> fewer sims)
python scripts/robust_deck_search.py --generations 30 --population 16 --games 10 --surrogate
```

Output: `report/robust_deck_rl/best_deck.csv` (+ `metrics.csv`, `state.json`).

## What makes it robust (vs the old mean-win-rate GA)

| Piece | Module | Role |
|---|---|---|
| **CVaR / maximin objective** | `rl/robust_fitness.py` | scores the *floor* of the matchup spread, not the mean — punishes any collapse matchup |
| **Zero-sum meta-solver** | `rl/meta_solver.py` | regret-matching Nash; re-weights opponents toward the hardest adversarial field (PSRO-lite) |
| **Opponent gauntlet** | `rl/gauntlet.py` | benchmark + agent_decks + **mined ladder decks** + self-play elites; train/holdout split |
| **Co-evolution** | `rl/robust_search.py` | best decks become opponents, so the field expands every gen |
| **GPU win-rate surrogate** | `rl/winrate_surrogate.py` | predicts P(A beats B); simulate only uncertain matchups (CUDA if torch present, NumPy fallback) |

## Key knobs

- `--alpha` 0..1 — 0 = pure worst-case, 1 = pure mean (default 0.5).
- `--cvar-q` — worst fraction averaged for the tail (default 0.3).
- `--games` — games per candidate-vs-opponent (more = less noisy; ~2,500 needed to resolve a 2% edge).
- `--surrogate` / `--surrogate-margin` — enable pruning; skip-sim when `|p-0.5| > margin`.
- `--no-meta-solver`, `--no-mined`.

## Feed it the real field (highest-value step)

The truest opponents are real ladder games. Daily episode datasets are indexed in
`report/deck_rl/episode_dataset_manifest.csv`.

```bash
# 1) download a day (Kaggle access; ~3-21 GB). Example:
kaggle datasets download kaggle/pokemon-tcg-ai-battle-episodes-2026-06-19 -p report/replays --unzip
# 2) extract strong opponents into the gauntlet:
python scripts/extract_gauntlet_from_replays.py --replays report/replays --min-score 900 --max-decks 60
# 3) just run the search — gauntlet auto-includes report/deck_rl/mined_decks/
python scripts/robust_deck_search.py --generations 30 --population 16 --games 10 --surrogate
```

## Reading metrics.csv

- `best_robust` — the objective (worst-case-weighted). Should climb across gens.
- `best_maximin` — win rate vs the single worst opponent. The robustness number.
- `holdout_robust` / `holdout_maximin` — on opponents **not** trained against = honest "vs anything".
- `games_simulated` vs `games_predicted` — surrogate's CPU savings.

**Watch for overfitting:** if `best_robust` rises but `holdout_robust` stalls, the
deck is gaming the train gauntlet — widen the field (mine more real decks).

## Tests

```bash
python -m pytest tests/test_robust_core.py tests/test_surrogate.py -q
```
