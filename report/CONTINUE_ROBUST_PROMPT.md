# Continuation prompt — paste into a new Cowork session

Continue the **robust deck-search** work in `Z:\kaggle\pokemon`.

First, refresh context (read in this order):
1. `ROBUST_DECK_HANDOFF.md` (state + exact next actions)
2. `report/robust_deck_optimization_design.md` (the math/architecture)
3. `report/robust_deck_rl/README.md` (how to run)
4. Top of `PROGRESS.md` and first unchecked task in `TASKS.md`

Then do this, in order, re-measuring after each step (keep RNG deterministic; do not
submit to Kaggle):

1. Run the robust search on my GPU box and report the curve:
   `python scripts/robust_deck_search.py --generations 30 --population 16 --games 10 --surrogate`
   Summarise `report/robust_deck_rl/metrics.csv`: is `best_robust` climbing, and is
   `holdout_robust` keeping up (not overfitting)? Confirm the surrogate backend printed
   `torch-cuda`.
2. Mine the real ladder field, then re-run:
   download a daily dataset from `report/deck_rl/episode_dataset_manifest.csv`,
   run `scripts/extract_gauntlet_from_replays.py --min-score 900 --max-decks 60`,
   then repeat step 1. Report how the gauntlet size and holdout numbers change.
3. If holdout looks strong, validate `report/robust_deck_rl/best_deck.csv` with the
   normal pyramid (L0 legality → L1 → L2 SPRT gate) paired with the Search brain, and
   dry-run packaging. Stop before any upload and show me the gate result.
4. Tell me whether to wire this as a `--robust` phase inside
   `rl/train_deck_campaign.py` or keep it standalone.

Before ending: prepend a dated `PROGRESS.md` entry (tasks worked, files changed,
best/holdout numbers, blockers, single exact next action) and update
`ROBUST_DECK_HANDOFF.md`.
