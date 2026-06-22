# Session 44 — Repo reset & cohesive rebuild plan (2026-06-22)

## User directive
"Completely clean up the repo. Prune what didn't work but keep a ruling document of everything
tried (decks, rules, sets, agents). Back up and redo the repo around several mindsets: (1) daily
identification of decks that beat the field, (2) discovery RL / scoped combinatorial deck search,
(3) deeper rules + game understanding, (4) MDP decision-making like top players exploiting the
sim's visible information, (5) online learning after games, (6) far better use of daily episode
data. Ground everything in real math / RL / CS, not guessing. Structure the rework for ALL pillars
so we don't miss anything."

Decisions captured via AskUserQuestion: prune style = **delete + graveyard branch**; scope =
**full rebuild now**; first pillar = **all of them, designed cohesively**.

## What was done
1. **Safety snapshot** — committed full working state (`5a17cfe`) and branched
   `graveyard/pre-reset-20260622` (full pre-reset tree, restorable per file).
2. **Diagnosis** — root cause is process sprawl (15 top-level handoff files, 157 KB PROGRESS,
   334-file report tree) + every RL/MCTS/GA approach underperforming hand-tuned rules + gating on
   proxy opponents that mispredict μ + wasted episode data.
3. **Load-bearing correction** — confirmed from `data/CABT_API.md` that the game is
   **imperfect-information** (opponent hand/deck/prizes hidden). The "we can see opponent cards"
   premise is false; the MDP pillar must use determinized / information-set search + belief priors,
   not naïve minimax. Flagged for empirical re-verification against the local engine.
4. **`RULINGS.md`** — honest μ scoreboard, every agent/deck/loop tried + verdict, 10 standing
   rulings (R1–R10), grounded game/scoring/info facts, graveyard index.
5. **`ARCHITECTURE.md`** — all 5 pillars on one shared foundation (Pillar 0: core model, field
   registry, episode pipeline, eval harness), with the correct algorithm family per pillar and a
   measurable build order.
6. **Prune** — 532 → ~100 tracked files. Removed `rl/`, dead `report/` trees, dead `scripts/`,
   `pool_*`/variant decks, `notebooks/lucario`, RL/MCTS notebooks, ~10 top-level handoff files.
   Kept the spine (`agent/` Heuristic+Search), real-field decks, episode replays, log CSVs.
   Restored 3 modules the spine lazily imports (`deck_tech`, `rule_core`, `lucario_policy`);
   cleaned `package_submission.py` + `arena.py` of dead scorer branches. All kept code compiles;
   zero dangling references.
7. **Skeleton** — `core/ field/ episodes/ eval/ meta/ discovery/` each with a contract README.
8. **Docs retuned** — `README.md`, `AGENTS.md` (single operating contract), `PROJECT_RULES.md`
   (stub → pointer), `TASKS.md` (build-order backlog), `PROGRESS.md` (reset → pointer to STATE +
   graveyard), `STATE.md` (the one handoff).

## Spine floor (unchanged, to re-verify on real field)
SearchScorer × Lucario ≈ 668 μ; Heuristic × Kyogre ≈ 633. Field top ~1350 / mid ~1100.

## Next action
Build-order **F1**: stand up `core/` (cards, engine, obs) + the empirical information-model test on
a Python ≥3.11 machine. See `STATE.md`.
