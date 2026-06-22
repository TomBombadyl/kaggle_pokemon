# Project priorities (always-on)

Canonical checklist for every agent run. Read with [`AGENTS.md`](../AGENTS.md), [`STATE.md`](../STATE.md),
[`RULINGS.md`](../RULINGS.md), [`TASKS.md`](../TASKS.md).

**Reset note (2026-06-22):** Track B PPO, deck GA, and Kaggle-notebook Lucario RL are **retired**
(RULINGS 2C). The proven floor is rules/search (~668 μ). New ML must beat that on the real-field
gate before shipping (Ruling R3).

---

## Current workstreams

| Track | What | Where | Gate / submit |
|-------|------|-------|----------------|
| **Spine (floor)** | HeuristicScorer + SearchScorer | `agent/{agent,evalfn,search_policy}.py` | `scripts/gate_vs_public.py`, ladder μ |
| **Per-deck rule pilot** | Official sample + never-crash wrapper | e.g. `agent/dragapult_agent.py` | `scripts/gate_dragapult.py` |
| **Lucario field RL+MCTS** | Transformer + MCTS, **real field decks** | `scripts/train_lucario_field_mcts.py` → `rl_mcts_field/lucarioex_v1/` | Must beat SearchScorer 668; `lucario_mcts` scorer |
| **Foundation rebuild** | `core/`, `eval/`, `field/`, `episodes/` | See `TASKS.md` F1–F3 | Empirical obs test + real-field harness |

Do **not** mix brains across decks without retraining. Do **not** gate on `pool_*` proxies or
mirror-only self-play (Ruling R2).

---

## Environment (Windows)

| Use | Python | Why |
|-----|--------|-----|
| **Lucario field train, future GPU RL** | `C:\Users\tobin\AppData\Local\Programs\Python\Python313\python.exe` (`torch+cu128`) | RTX 4070 Ti SUPER |
| **Smoke tests, packaging, CPU train** | Python 3.13 | `cg.dll` engine; current 5-cycle run is CPU |
| **Avoid for RL** | miniconda3 default | installs `torch+cpu` only |

Fetch engine once: `python scripts/fetch_sim_engine.py` → `data/sim/sample_submission/cg/cg.dll`.

---

## Simulator = ground truth

Official Pokémon TCG rules **≠** competition simulator. Organizer stance: **simulator behavior is correct behavior.**

Always read [`SIMULATOR_RESOURCE_NOTES.md`](SIMULATOR_RESOURCE_NOTES.md) before changing attack logic,
prize sequencing, setup benching, or RL labels.

Key deltas:
- Unresolvable attack effects → attack **not selectable** (mask-driven legality).
- Setup phase may **force** benching Basics from opening hand.
- Simultaneous KOs → sequential prizes; all-prize simultaneous = **draw** (train label 0.0).
- Mega Zygarde Nullifying Zero → no target-order choice; coins L→R.

Train and gate only on **legal options from `cg`**, never from card-text inference alone.

---

## Ladder scoring & tempo

Read [`COMPETITION_SCORING.md`](COMPETITION_SCORING.md) — **full μ model**.

Summary:
- **μ = Gaussian skill rating**; validation self-play ~600 starting point.
- Each episode updates μ on **win / loss / draw only** (margin/speed **not** in formula).
- **Still avoid fast collapses** — deck-out / empty bench → many losses quickly.
- **Bench ≥1 Basic** whenever legal (`agent/agent.py`, `rule_core.py`, `bench_guard.py`).
- Local WR ≠ μ (Ruling R1). Require **≥2 ladder readings ≥40 min apart** before trusting μ.

---

## Real-field opponents (the only valid gate set)

Training and gating use mined lists in `agent_decks/`:

`real_mega_lucario_ex`, `real_dragapult_ex`, `real_mega_abomasnow_ex`, `real_iono`,
`top_mined_{alakazam,trevenant,dragapult_ex,iono,mega_abomasnow_ex,mega_lucario_ex}`.

Public agents: `python scripts/extract_public_agents.py` → `data/kaggle_ref/opponents/`.

---

## Submit discipline

1. User **explicit OK** for Kaggle upload.
2. L0: `scripts/smoke_test.py` + `scripts/smoke_cg_engine.py` (for MCTS agents).
3. L1: `scripts/gate_vs_public.py` (real field, 30+ games/opp).
4. [`SUBMISSION_PLAYBOOK.md`](SUBMISSION_PLAYBOOK.md) — max **5/day**; pick **2 Final Submissions** manually.
5. Package: `dist/candidates/<name>.tar.gz`.

---

## Agent candidates (2026-06-22)

| Agent | Status |
|-------|--------|
| SearchScorer × real Mega Lucario ex | **668 μ floor** — do not replace without beating it |
| Dragapult ex (official Crispin sample) | Local gate 78–88% vs pilots; ladder probe pending user OK |
| Lucario field RL+MCTS | **5-cycle CPU train in progress** → `rl_mcts_field/lucarioex_v1/` |
| Track B Learned / deck GA / old Kaggle Lucario RL | **Retired** (RULINGS 2C) |
