# Alakazam submission plan — reset after Lucario / Track B failures

Date: 2026-06-20  
Deck: [`agent_decks/pool_alakazam_dudunsparce.csv`](../agent_decks/pool_alakazam_dudunsparce.csv)  
Meta lane: **Psychic control / single-prize** (Alakazam + Dudunsparce)

Related: [`data/COMPETITION_SCORING.md`](../data/COMPETITION_SCORING.md), [`data/PROJECT_PRIORITIES.md`](../data/PROJECT_PRIORITIES.md), [`report/competition_insights.md`](competition_insights.md)

---

## Diagnosis: why Lucario RL got wrecked on ladder

| Issue | Cause | Fix |
|-------|--------|-----|
| **Loss in few turns** | Early `model_best.pth` (iter 0–1) trained **vs random only** — never learned to bench |
| **Empty bench → `no_active`** | MCTS/net skipped optional `CTX_SETUP_BENCH_POKEMON` and MAIN bench plays |
| **RuleCore fallback unused** | Model loaded OK → MCTS ran every turn; fallback only on crash |
| **8.3% public gate** | No meta tempo, no opponent guards, no bench discipline |
| **Submitted too early** | 2/40 notebook iters; champion promoted vs random, not field |

**Code fix (2026-06-20):** `agent/bench_guard.py` + `lucario_mcts_policy.py` — bench-critical selects route to **RuleCore** before MCTS. Re-package Lucario only after notebook finishes + public gate.

---

## Error log — Alakazam / Track B (do not repeat)

| # | Error | Impact | Correct action |
|---|--------|--------|----------------|
| E1 | Submitted **Learned** with **wrong deck** (shared `distilled_v1.npz`) | Ladder **490 μ** | Per-deck train + distill always |
| E2 | Used **miniconda3** python (`torch+cpu`) for RL | 200k steps useless on CPU | **Python313** + cu128 only |
| E3 | **100k–200k** timesteps on Alakazam meta deck | Train WR ~21–29%; gate **32/110** | **≥1M GPU** + heavy distill |
| E3b | **1M GPU** timesteps (2026-06-20) | Train WR **30.8%** @ 1M; Kyogre holdout **0%** (peak **21.1%** @ 120k) | **Retire Learned Alakazam** — use Search/RuleCore or new architecture |
| E4 | Gated vs **`pool_*` only** | Passed locally, failed ladder | Gate vs **public agent suite** |
| E5 | No **deck tech** for Alakazam | RuleCore used generic setup priorities | `ALAKAZAM_TECH` in `deck_tech.py` |
| E6 | Expected Learned to beat **Search** on complex meta list | Track B below rule floor (~600 μ) | **Search/RuleCore first**, Learned second |
| E7 | Ignored **bench policy** in RL path | Same fast-loss mode as Lucario | `bench_guard` + `evalfn` shaping |
| E8 | Uploaded before **L2 gate (40g)** or user OK | Wasted daily slot | Gate → package → explicit OK |

---

## Recommended approach (step back)

Public evidence ([`competition_insights.md`](competition_insights.md)): **600 μ = rule floor**; top agents are **rule core + opponent detection + matchup guards**, not raw PPO.

### Phase A — Ship a legal, bench-safe agent (this week)

**Brain:** `SearchScorer` or `RuleCoreScorer` (not Learned until gates clear).

**Deck:** Keep `pool_alakazam_dudunsparce.csv` (60 cards validated). Optional tune after public gate.

**Why not Learned yet:** GPU 1M run in progress (~140k/1M at last check); even if it finishes, must pass **L2 + public gate** before upload.

Commands:

```powershell
# Package Search + Alakazam (probe)
python scripts/package_submission.py `
  --name track_a_alakazam_search_v2 `
  --scorer search `
  --deck agent_decks/pool_alakazam_dudunsparce.csv

# Or RuleCore (opponent detection + Alakazam tech)
python scripts/package_submission.py `
  --name track_c_alakazam_rulecore_v1 `
  --scorer rulecore `
  --deck agent_decks/pool_alakazam_dudunsparce.csv

# Public gate (required before upload)
python scripts/gate_vs_public.py `
  --agent dist/candidates/track_c_alakazam_rulecore_v1.tar.gz `
  --games 12
```

**Submit only if** public suite mean beats our Lucario RL probe and clears **~600 μ** floor locally.

### Phase B — Learned Alakazam (after GPU 1M)

Monitor:

```powershell
# Must show device: cuda in checkpoint
Get-Content report/rl_train/checkpoint.json
```

When complete:

```powershell
python scripts/train_track_b_deck.py `
  --deck agent_decks/pool_alakazam_dudunsparce.csv `
  --slug alakazam `
  --skip-train --skip-distill `
  --gate-games 40 --package
```

**Submit Learned only if** gate ≥ **210/240** pool (our rl_deck bar) or beats Phase A on public gate.

### Phase C — Deck tuning (optional)

GA lane `fast-basic` / spread lists are separate Track B pairs — do not swap Learned brain onto Alakazam deck.

If Alakazam list underperforms in public gate, mutate **trainers/energy** only (`scripts/validate_deck.py` after each change).

---

## Policy rules (all Alakazam agents)

From [`data/COMPETITION_SCORING.md`](../data/COMPETITION_SCORING.md) + simulator notes:

1. **Simulator mask = legality** — never infer from card text ([`SIMULATOR_RESOURCE_NOTES.md`](../data/SIMULATOR_RESOURCE_NOTES.md)).
2. **Bench ≥1 Basic** from turn 1 whenever legal — setup + MAIN ([`agent/bench_guard.py`](../agent/bench_guard.py)).
3. **No attack on empty bench** unless lethal plan (RuleCore `_score_attack`).
4. **Develop Abra line** before spamming supporters (`ALAKAZAM_TECH.setup_priority`).
5. **μ moves on W/L only** — fast losses hurt because they **are losses**, not a separate speed penalty.
6. **Pull logs** after every upload: `kaggle competitions logs <episode> 0` — confirm loss reason ≠ `no_active`.

---

## Alakazam deck tech (added 2026-06-20)

[`agent/deck_tech.py`](../agent/deck_tech.py) → `ALAKAZAM_TECH`:

- Setup priority: **Abra (741)** > Dunsparce > evolution line
- Draw/search trainers wired for Psychic control
- RuleCore auto-selects when deck contains 741+742+(245|743)

---

## Success criteria

| Stage | Metric | Target |
|-------|--------|--------|
| L0 | `smoke_test.py` | 17/17 |
| L1 | pool gate 12g | Learned ≥ Search or SPRT pass |
| L2 | pool gate 40g | ≥ **210/240** (Learned) or package Search/RuleCore |
| L3 | public gate 12–30g | **≥600 μ floor** behavior; suite mean ↑ vs Lucario RL |
| L4 | Kaggle μ (40+ min) | Beat **490** old Alakazam Learned; aim **550+** probe |

---

## Immediate next actions

1. **Finish GPU 1M** Alakazam Track B (Python313) — do not submit mid-run.
2. **Package RuleCore or Search** Alakazam (Phase A) + public gate.
3. **Re-package Lucario** with `bench_guard` after Kaggle notebook completes — do not re-upload early checkpoint.
4. **Manually select Final Submissions** on Kaggle — pin Kyogre 633 + best new agent.
