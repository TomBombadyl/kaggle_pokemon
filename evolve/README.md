# evolve/ — evolutionary parameter search (AlphaEvolve-style)

Automates the loop the project already runs by hand every session (`ROADMAP.md` Phase A step
A3: "one lever / session" — hand-pick a constant, re-gate, keep or discard). This module
generates many candidate parameter sets per round instead of one human guess, scores each
through the *same* `eval/harness.py` + `eval/gates.py` path already trusted (Ruling R2 — measure
on the real field only), and never edits a shipped agent file automatically.

## Pieces

- `targets.py` — declarative registry of evolvable parameter blocks. One entry today:
  Archaludon's `_ICE_CREAM_HP_THRESHOLD` / `_ATTACK_BASE_DMG` constants
  (`agent/archaludon_agent.py`), scored via `eval.gates.gate_archaludon_matchups`. Archaludon is
  the pilot because it's the only unpaused primary track right now (`ROADMAP.md` Sec 0).
- `evaluator.py` — candidate params → scalar score, via the real field harness. No new
  evaluation logic; every score carries the same games/opponents/seeds metadata Ruling R8
  requires, plus a weighted E[win] figure (see below) for context.
- `proposer.py` — candidate generation. Ships a working local perturbation strategy (bounded,
  keep-top-K survivors, not greedy single-best — `RULINGS.md` already documents blind
  single-point GA collapsing onto local-gate noise). `propose()` is the one function to swap
  for an LLM-driven proposer (the real AlphaEvolve API, or another model) later; nothing else in
  the pipeline needs to change.
- `run_evolution.py` — CLI orchestrator; writes `eval/evolve_<target>_gen<N>.md` reports.
- `promote.py` — manual, human-run step that prints the literal values to hand-paste into the
  real agent file. Nothing in `evolve/` edits `agent/*.py` on its own.

## Episode data (Phase C)

`evolve/run_evolution.py --refresh-episodes N` pulls N fresh episodes per μ-band via
`scripts/analyze_meta_by_mu_band.py --download-per-band N` and rebuilds `field/weights.json` via
`scripts/build_field_weights.py` before running — the same daily-episode pipeline `ROADMAP.md`
Phase C already uses. Each evolve report then includes a **weighted E[win]** column computed
against that mixture. This needs Kaggle creds + egress, so it runs on the dev machine, not this
sandbox.

**Weighted E[win] is informational only.** `AGENTS.md` is explicit that weighted gates are
"filter only until replay sample supports mixture," and Ruling R11 is "rules before mixture" —
so candidate ranking, survivor selection, and promotion decisions in this module all use the raw
local win-rate + Wilson CI, never the weighted figure alone. The weighted column exists so you
can see whether a candidate that wins on raw win-rate also looks reasonable against the current
meta mix, not to pick candidates by it.

## Guardrail

A winning candidate is not a ship decision. After promotion it goes through the unchanged
pipeline: full local gate n=30 (`scripts/gate_archaludon.py`) → `scripts/check_upload_eligible.py`
→ user-confirmed Kaggle upload → ≥2 ladder μ readings (`scripts/track_ladder.py`) — R12, same as
every other change in this repo.

## Usage

```
python evolve/run_evolution.py --target archaludon --generations 3 --population 6 --games 20 --report
```

Requires the same environment as `eval/harness.py` — Python ≥3.11 and the `cg` engine under
`data/sim/sample_submission` (see `README.md` / `AGENTS.md` "Environment") — so it does not run
in the Py3.10, no-Kaggle-egress sandbox this session may be running in.
