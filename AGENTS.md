# AGENTS — operating contract

The single operating contract for this repo (human or AI). Reset 2026-06-22 (Session 44). For the
*why* read `RULINGS.md`; for the *plan* read `ARCHITECTURE.md`; for *current state + next action*
read `STATE.md`.

## Start every session by reading, in order
1. `STATE.md` — current state and the single next action.
2. `RULINGS.md` — the standing rulings (R1–R10) and the record of what failed. **Do not re-run a
   ruled-out experiment.**
3. `ARCHITECTURE.md` — the pillar you're working on and its interface contract.
4. `TASKS.md` — the build-order backlog; do the next unchecked item.

## The competition (verify specifics in `data/` source docs)
- **Simulation** (`pokemon-tcg-ai-battle`): submit `submission.tar.gz`; public **μ** is truth.
- **Strategy** (`pokemon-tcg-ai-battle-challenge-strategy`, ends 2026-09-14): stability + deck
  concept + sim performance + written report.
- **Imperfect-information** game; 10-min/player clock; μ updates on W/L/draw only (margin/speed do
  not count). Full facts: `RULINGS.md` Part 4 (cites `data/CABT_API.md`, `data/COMPETITION_SCORING.md`).

## Hard rules (the agent itself)
- **Never crash; always return a legal selection** from the simulator option mask — never infer
  legality from card text (Ruling R7). A single exception forfeits the game.
- **Keep ≥1 Basic on the bench** whenever legal (empty bench → `no_active` loss).
- Optimize **win probability + stability**, not blowout margin (Ruling R9).
- Keep RNG deterministic where we control it, so win-rate deltas are real.

## How we work (process)
- **Measure on the real field only** (Ruling R2): `eval/` harness vs `field/` decks + public
  agents. Never `pool_*` proxies or random/mirror self-play.
- **Nothing ML ships until it beats the rules floor (~668 μ) on the real-field gate** plus a ≥2-reading
  ladder probe (Rulings R1, R3). Local win-rate is a filter, not truth.
- **Every reported win-rate carries metadata**: games, opponents, seeds, deck, brain (Ruling R8).
- **Don't break the spine.** `agent/` scored 668; do not rename/refactor it until the smoke test
  runs on a Python ≥3.11 machine (Ruling R7).
- **One source of truth per concern** (Ruling R10): decisions → `RULINGS.md`; state → `STATE.md`;
  design → `ARCHITECTURE.md`. No new top-level handoff/instruction files.
- Improve one concrete behavior at a time, re-measure, keep only what improves the gate or fixes
  legality/stability.

## Before any Kaggle upload
- Read `data/SUBMISSION_PLAYBOOK.md`: **5 uploads/day**, **2 Final Submissions** (select manually).
- Dry-run packaging (`scripts/package_submission.py --scorer {heuristic,search}`); never submit
  without explicit user confirmation.

## Environment
- Engine + episode pull need **Python ≥3.11** and run on the user's machine (this sandbox is 3.10
  with no Kaggle egress). GPU work (if ever revived): the Python313 torch+cu128 interpreter.
- `pip install -r requirements.txt`. Kaggle creds under `.kaggle/` stay gitignored.
- End-of-session: prepend a dated `STATE.md` block (state, files changed, measured result if any,
  blockers, the single exact next action).
