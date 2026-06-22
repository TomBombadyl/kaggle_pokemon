# PTCG AI Battle Challenge — project workspace

Workspace for the Kaggle **[PTCG AI Battle Challenge](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy)**
(Strategy track, ends 2026-09-14) and its sibling **Simulation** ladder
([pokemon-tcg-ai-battle](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle), the live μ
ranking). The project was reset on 2026-06-22 (Session 44) — see `RULINGS.md` for why.

## Read in this order (the only 4 canonical docs)

| # | File | What it is |
|---|------|-----------|
| 1 | **`STATE.md`** | Current state + the single next action. The one handoff. |
| 2 | **`RULINGS.md`** | **Part 0 = our operating mindset — read it first.** Then: everything tried, measured outcomes, why, and the standing rulings. |
| 3 | **`ARCHITECTURE.md`** | The rebuilt system: all 5 pillars on one shared foundation. |
| 4 | **`AGENTS.md`** | Operating contract for anyone (human or agent) working here. |

`TASKS.md` is the build-order backlog. `data/` holds official rules/card CSVs (source citations).
There are no other top-level handoff/instruction files by design (Ruling R10).

## The one-paragraph situation

The game is an **imperfect-information** card game (opponent hand/deck/prizes are hidden —
`RULINGS.md` Part 4), scored by a TrueSkill-style μ on a live ladder. After 43 sessions, our best
agent is hand-tuned **search/rules at ~668 μ**; every prior RL/MCTS/deck-GA experiment underperformed
it and was pruned. The rebuild keeps the rules spine as the proven floor and grows capability on
top of it — determinized/information-set search + belief priors from episode data, daily meta, and
scoped deck discovery — all measured against the **real field**, never proxy decks.

**Active experiment (Session 44c):** a **fresh** local Lucario field RL+MCTS stack
(`scripts/train_lucario_field_mcts.py`, 5-cycle CPU train in progress). It must clear Ruling R3
(real-field gate + ladder) before it replaces SearchScorer; see `STATE.md`.

## Repository map

```
STATE.md RULINGS.md ARCHITECTURE.md AGENTS.md TASKS.md   # canon
.cursor/SESSION.md                                      # ephemeral session (Cursor hook)
core/        # card/rules/engine/obs model            (scaffold — build first)
field/       # real-field decks + public agents       (scaffold)
episodes/    # Kaggle episode pull/parse/store         (scaffold)
eval/        # the one eval harness + gates            (scaffold)
meta/        # daily meta map                          (scaffold)
discovery/   # scoped deck search                      (scaffold)
agent/       # SHIPPED spine + per-deck agents         (live — do not break)
  lucario_policy.py, lucario_mcts_{runtime,policy}.py, dragapult_agent.py, …
scripts/     # package, gate, train, fetch helpers     (live)
agent_decks/ # real_* + top_mined_* + benchmark/       (live → migrate to field/decks/)
rl_mcts_field/  # local Lucario train outputs (gitignored)
data/        # official rules + card CSVs + engine     (live)
dist/        # packaged submissions                    (live)
tests/       # legality/rules/harness tests            (to populate)
# Reference notebooks at repo root (not under notebooks/):
reinforcement-learning-and-mcts-sample-code.ipynb
a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb
```

## You must provide
- **Kaggle API token** at `.kaggle/` (gitignored) — used to fetch data and pull episodes.
- **A machine with Python ≥3.11** for the engine and the episode pull (this sandbox is 3.10 and has
  no Kaggle egress).
