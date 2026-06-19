# Project Rules

This folder is the single source of truth for the Kaggle competition project:
`Z:\kaggle\pokemon`.

## Competition
- Competition: The Pokemon Company - PTCG AI Battle Challenge Strategy.
- Category: Strategy.
- Deadline: September 14, 2026.
- Kaggle page: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy

## Operating Contract
- Work with Kaggle Grand Champion expectations: verify assumptions, measure changes, and keep the agent legal and deterministic.
- Start each run by reading `PROGRESS.md` and `TASKS.md`. The top `PROGRESS.md` entry is the latest handoff; the first unchecked task in `TASKS.md` is the next task.
- Read `README.md` when project context is needed.
- Work tasks in order. Complete real work in this folder, mark completed tasks `[x]`, and continue to the next task when time allows.
- If a task is blocked, mark it `[blocked]` with a one-line reason, log it in `PROGRESS.md`, and move to the next task that can be done offline.
- Before ending a run, prepend a dated `PROGRESS.md` entry with tasks worked, files changed, current best win-rate if measured, blockers, and the single exact next action.

## Environment
- Re-run environment setup at the start of a run when possible: `scripts/setup_env.sh`.
- On Linux, use `pip install --break-system-packages` through the setup script.
- On Windows, if pip rejects `--break-system-packages`, run `python -m pip install -r requirements.txt` and log the setup-script incompatibility.
- Kaggle credentials are expected under `.kaggle/` and must stay gitignored.
- If Kaggle access is unavailable, continue with offline work: code, harnesses, card analysis, report drafting, and local self-play.

## Verification
- Ground competition-specific facts in official competition docs, official cabt docs, or downloaded competition artifacts. Label assumptions clearly in `PROGRESS.md`.
- Do not submit to Kaggle or perform external irreversible actions unless an explicit task calls for it. For first submission work, dry-run packaging first and leave actual submission for user confirmation.
- Keep RNG deterministic where the code controls randomness so win-rate comparisons are fair.
- Use local self-play as a sanity filter, not final ladder truth. Record game counts and matchup definitions with every reported win-rate.

## Agent Priorities
- The agent must never crash and must always return legal selections.
- Prefer simple strategies that the rule-based pilot can execute reliably.
- Improve one concrete behavior at a time, re-measure, and keep only changes that improve the current benchmark or clearly fix legality/stability.
