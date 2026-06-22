# STATE — current state & the single next action

> This is the **one** handoff file. It replaces the ~15 `*_HANDOFF_*` / `*_INSTRUCTIONS_*` /
> `ACTION_REQUIRED_*` files that used to litter the root (Ruling R10). Newest state on top.
> For *why* anything is the way it is, read `RULINGS.md`. For *what we're building*, `ARCHITECTURE.md`.

---

## As of 2026-06-22 (Session 44 — repo reset)

### What just happened
The repo was reset from 532 tracked files to ~100. Forty-three sessions of disjointed RL /
Track-A/B/C / deck-GA / MCTS / AZ experiments were pruned because **none beat hand-tuned rules on
the ladder** (RULINGS Part 1). Knowledge was preserved first:
- **`RULINGS.md`** — the honest scoreboard, everything tried + verdict, 10 standing rulings, the
  grounded game/rules facts.
- **`ARCHITECTURE.md`** — the cohesive rebuild across all 5 pillars on one shared foundation.
- **`graveyard/pre-reset-20260622`** (commit `5a17cfe`) — full pre-reset tree; restore anything with
  `git checkout graveyard/pre-reset-20260622 -- <path>`.

The working **spine survived intact**: `agent/` (HeuristicScorer + SearchScorer), the real-field
decks (`agent_decks/{real_*,top_mined_*}`), the surviving `scripts/`, and `report/replays` +
log CSVs. Pillar skeleton dirs created: `core/ field/ episodes/ eval/ meta/ discovery/` (each has
a README describing its contract).

### The true floor (what we can ship today)
- **SearchScorer × real Mega Lucario ex ≈ 668 μ** (best home-grown).
- **HeuristicScorer × Kyogre ≈ 633 μ** (simple, stable).
- Field scale: top ~1350, mid-pack ~1100+. **We are well below mid-pack — the climb is the point.**

### Open blocker (unchanged, now correctly scoped)
- Kaggle API has **no egress from the sandbox**. The episode pull (`episodes/pull.py`, seeded by
  `scripts/update_from_kaggle.py`) must run **on the user's machine**. This is *the* thing gating
  the meta tracker and belief priors — the highest-value unblock.

### THE SINGLE NEXT ACTION
**Build-order step 1: stand up `core/` and prove the foundation.**
1. `core/cards.py` — load `data/EN_Card_Data.csv` into a typed registry.
2. `core/engine.py` — wrap the local `cg` engine (`data/sim/sample_submission/cg/`).
3. `core/obs.py` + a test in `tests/` that **empirically verifies the information model** against
   the live engine (opponent hand = count only, prizes face-down — RULINGS Part 4). This must be
   done on a machine with Python ≥3.11 (the engine needs it; this sandbox is 3.10).

Then step 2 (eval/ harness + field/ registry → re-measure the 668 floor on the real field), then
step 3 (migrate the spine `agent/` → `agents/` *with the smoke test passing*). Full sequence:
`ARCHITECTURE.md` § Build order.

### Do NOT
- Resurrect `rl/`, deck-GA, or MCTS without addressing *why they failed* (RULINGS 2C/2A).
- Gate on `pool_*` proxies or random/mirror self-play (Ruling R2).
- Ship any ML method that hasn't beaten the rules floor on the real-field gate (Ruling R3).
- Rename/move the `agent/` spine until the smoke test runs (Ruling R7).
