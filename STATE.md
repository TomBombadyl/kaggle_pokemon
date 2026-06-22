# STATE — current state & the single next action

> This is the **one** handoff file. It replaces the ~15 `*_HANDOFF_*` / `*_INSTRUCTIONS_*` /
> `ACTION_REQUIRED_*` files that used to litter the root (Ruling R10). Newest state on top.
> **Before acting, read `RULINGS.md` Part 0 — the operating mindset.** For *why* anything is the way
> it is, read the rest of `RULINGS.md`. For *what we're building*, `ARCHITECTURE.md`.
> Ephemeral session detail also lives in `.cursor/SESSION.md` (Cursor hook loads it).

---

## As of 2026-06-22 (Session 44c — Lucario field RL+MCTS, local fresh start)

**Reference per-deck ML stack** built per `ARCHITECTURE.md` § Per-deck agent template. Fresh start —
no Snorlax-era, `rl_mcts_basic/`, or Kaggle-notebook checkpoints.

### What shipped (commit `251da2b`, pushed `main`)
| Piece | Path |
|-------|------|
| Runtime (d128, opp deck in `search_begin`, draw=0 labels) | `agent/lucario_mcts_runtime.py` |
| Regen from official RL sample | `scripts/bootstrap_lucario_mcts_runtime.py` |
| Local field trainer (5 cycles × 10 real decks) | `scripts/train_lucario_field_mcts.py` |
| Submission wrapper + LucarioScorer fallback | `agent/lucario_mcts_policy.py` |
| Engine smoke | `scripts/smoke_cg_engine.py` |
| Stale artifact cleanup | `scripts/cleanup_old_rl_artifacts.py` |
| Reference notebooks | repo root: `reinforcement-learning-and-mcts-sample-code.ipynb`, `a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb` |
| Sim quirks (setup forced-bench, draw labels) | `data/SIMULATOR_RESOURCE_NOTES.md` |
| Train outputs (gitignored) | `rl_mcts_field/lucarioex_v1/` |

### Training status (IN PROGRESS — do not kill)
```powershell
# Running in background (Python 3.13, CPU):
python scripts/train_lucario_field_mcts.py --device cpu --cycles 5 --time-budget-sec 21600
```
- **Log:** `rl_mcts_field/lucarioex_v1/train.log`
- **Metrics:** `rl_mcts_field/lucarioex_v1/metrics.csv`
- **Progress when docs updated:** cycle 2 eval in flight; cycle 1 promoted (`mean_eval_wr=41%`, loss 0.164).
- **Known weak matchup:** Mega Abomasnow ex (0% through cycle 2 eval so far).
- **Smoke checkpoint public gate:** 6.7% suite mean (expected pre-train; not shippable).

### THE SINGLE NEXT ACTION (when train finishes)
1. Confirm all 5 cycles complete in `train.log` / `metrics.csv`.
2. Package champion: `scripts/package_submission.py --name track_d_lucarioex_field_v1 --scorer lucario_mcts --deck agent_decks/real_mega_lucario_ex.csv --model rl_mcts_field/lucarioex_v1/model_best.pth --meta rl_mcts_field/lucarioex_v1/run_meta.json`
3. `python scripts/extract_public_agents.py` (if needed) then `python scripts/gate_vs_public.py` — 30+ games/opp, Wilson CI.
4. Compare to **SearchScorer × real Mega Lucario ex ≈ 668 μ** floor (Ruling R3). **Upload only with explicit user OK** + ≥2 stable μ readings (Ruling R1).

Until train completes: **leave the background process running**; offline work can continue on foundation (`core/`, `eval/`) without touching `agent/lucario_mcts_*` or killing PID.

---

**First agent built on the rebuilt foundation.** Took the official Kaggle "Rule-Based Agent for
Dragapult ex" (Crispin aggressive variant) as the baseline and stood it up against our local engine
(which, contrary to old notes, runs here — Python 3.13, `cg` imports fine).

- **New files:** `agent/dragapult_agent.py` (sample logic + a never-crash/output-validation wrapper —
  IMPROVEMENT over the sample, which had no crash protection, Ruling R7), `agent_decks/dragapult_ex_sample.csv`
  (its exact 60-card list), `scripts/gate_dragapult.py` (asymmetric-deck, seat-swapped, Wilson-CI gate).
- **Local baseline (LOCAL FILTER, not ladder truth — RULINGS R1/R2):**
  - vs **HeuristicScorer** pilot, 30g/opp: Lucario 66.7% · Alakazam 73.3% · Trevenant 100% · Abomasnow 73.3% → **78.3% overall**.
  - vs **SearchScorer** pilot (our 668-μ brain), 20g/opp: Lucario 85% · Alakazam 85% · Trevenant 95% → **88.3% overall**.
  - Safety wrapper: re-gate showed no regression, 0 crashes, 0 unfinished.
- **Read this as:** the agent is clearly competent and we have a strong baseline to improve against —
  NOT a μ prediction (local has misled us before; the ladder is the only judge).
- **Note:** this is the *Crispin* variant (official sample), not the Dudunsparce/Alakazam variant
  originally discussed — the official agent's card logic is Crispin-specific.

**Next decisions (open):** (a) package this safe baseline for a **ladder probe** to get real μ (the
measurement that matters), and/or (b) improve it — best win-rate lever is opponent-aware
targeting/Boss's Orders using the visible board; the Dudunsparce deck variant would need the agent's
card-ID logic adapted. Each improvement gets gated vs this baseline before it counts.

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

### Ladder candidates (non-Lucario) — as of 2026-06-22
Lucario is already on the ladder and doing well; the user wants a *different* second archetype.
Evidence-ranked from the scoreboard (RULINGS Part 1), among current decks:
- **Retire now:** MCTS/transformer Alakazam (`model4.pth`) — **~185 μ** (user-reported), worst on
  record. Brain problem, not deck (RULINGS row 13).
- **Best non-Lucario play = Alakazam piloted by RULES/SEARCH, not a trained policy** — the same deck
  scored **659 μ** with the imported rule-based "best5" pilot
  (`notebooks/ryotasueyoshi_rule_based_alakazam_best5/`). Path: re-submit that proven agent, and/or
  gate our `SearchScorer` on `agent_decks/top_mined_alakazam.csv` on the real field.
- **Backup / most-distinct archetype:** Trevenant control + `SearchScorer` = **615.6 μ** (confirmed,
  our own agent; `agent_decks/top_mined_trevenant.csv`).
- **Reframe "train different decks":** every trained/RL/MCTS agent we shipped lost to plain
  rules/search (the 185 is the latest proof — Ruling R3). Correct sequence: build `eval/` (F2),
  gate the rules pilot across our real decks, ship the best; introduce trained policies only after
  they beat that floor on the real-field gate.

### Open blocker (unchanged, now correctly scoped)
- Kaggle API has **no egress from the sandbox**. The episode pull (`episodes/pull.py`, seeded by
  `scripts/update_from_kaggle.py`) must run **on the user's machine**. This is *the* thing gating
  the meta tracker and belief priors — the highest-value unblock.

### THE SINGLE NEXT ACTION (foundation — after Lucario train gates or in parallel)
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
