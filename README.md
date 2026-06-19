# PTCG AI Battle Challenge — Strategy Category

Autonomous project workspace for the Kaggle competition
**[The Pokémon Company – PTCG AI Battle Challenge Strategy](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy)** (comp #131772).

---

## What this is

A self-managing project folder. A scheduled "bot" runs **every night at 9pm** and
picks up the next unfinished item in `TASKS.md`, works through tasks in order until
the run ends, then logs what it did to `PROGRESS.md` and leaves a clean handoff.

**State lives in this folder** — not in any single chat. That is what makes the
nightly runs continuous.

---

## Competition facts (verified June 2026)

- **Category:** Strategy (this comp). Runs **June 16 – Sep 14, 2026**.
- **Sibling comp:** Simulation Category (ends Aug 17) — the agent battles.
- **Provided by The Pokémon Company:** official rules, environment, a **simulator**
  for training/evaluation, and a **2,000-card Standard-format database**.
- **Agent interface:** each turn the agent receives an *observation* (game logs,
  board state, list of legal options) and returns the **indices of chosen options**.
- **Strategy ranking factors:** agent stability, deck design concepts, and
  performance in the simulation phase, plus a written strategy report.
- **Prizes:** top 8 advance ($30k each) to a Sep 2026 live tournament in Japan
  ($50k winner / $30k runner-up).

> Exact simulator API, observation schema, and submission format must be confirmed
> from the competition's own docs — that is **Task 1** in `TASKS.md`.

---

## You must provide

1. **Kaggle API token** — download `kaggle.json` from your Kaggle account
   (Settings → API → "Create New Token") and place it at:
   `Z:\kaggle\pokemon\.kaggle\kaggle.json`
   The bot uses this to fetch the data, simulator, and (later) submit.
2. **Keep this folder connected** when the 9pm run fires (see `PROGRESS.md` notes).

Without the token, the bot will still work on offline tasks (code, report drafting)
and log a note that download/submission is blocked.

---

## Layout

```
pokemon/
├─ README.md          ← this file
├─ PROJECT_RULES.md   ← durable operating rules for future Codex runs
├─ TASKS.md           ← sequential backlog (the bot's to-do list)
├─ PROGRESS.md        ← append-only run log
├─ requirements.txt   ← Python deps (re-installed each run)
├─ .gitignore
├─ agent/
│  └─ agent.py        ← agent skeleton (choose_action interface)
├─ scripts/
│  └─ setup_env.sh    ← bootstrap: deps + Kaggle auth + data download
├─ data/              ← downloaded card DB / simulator assets (git-ignored)
└─ report/            ← strategy report drafts
```
