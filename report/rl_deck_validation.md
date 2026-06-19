# RL Deck Validation — `best_deck.csv` vs Meta Pool

**Run 25 — 2026-06-19.** Gate from `ADR_001` / EVAL_PROTOCOL: deck must clear **≥60% vs pool**
before spending Track B training budget (Phase 2).

Pilot is the **rule-based heuristic on both sides** (symmetric), so the only variable is the
deck list. Engine RNG is unseedable, so treat win-rates as noisy point estimates with Wilson CIs.

---

## Result — PASS (gate cleared decisively)

**Aggregate vs 6 `pool_*` meta decks: 209/240 = 87.1%** (95% CI [82.2, 90.7]), 40 games/opponent,
seats swapped, 0 draws, 0 unfinished.

| Opponent | W–L | Win% | 95% CI |
|---|---|---|---|
| pool_bellibolt | 38–2 | 95.0% | [83.5, 98.6] |
| pool_alakazam_dudunsparce | 37–3 | 92.5% | [80.1, 97.4] |
| pool_mega_greninja | 37–3 | 92.5% | [80.1, 97.4] |
| pool_greninja | 35–5 | 87.5% | [73.9, 94.5] |
| pool_dragapult | 33–7 | 82.5% | [68.0, 91.3] |
| pool_crustle | 29–11 | 72.5% | [57.2, 83.9] |
| **Aggregate** | **209–31** | **87.1%** | **[82.2, 90.7]** |

This confirms the GA fitness (0.898) holds at 240-game scale (0.871) — not a small-sample fluke.

---

## Caveats — read before trusting 87%

**1. The pool is not held out.** The GA optimized `best_deck.csv` *against this exact 6-deck pool*
(plus the 3 high-performers and baseline — see `agent_decks/benchmark/suite.json`). 87% vs the
training pool is an **in-distribution** score and is optimistic for the real ladder.

**2. The deck is weak vs the strongest local archetype.** Against the high-performer decks
(also in the GA suite, so still in-distribution) it manages only **54.2%** aggregate (65–55), and
it **loses to Kyogre: 11–19 = 36.7%**.

| Held-ish opponent | W–L | Win% |
|---|---|---|
| a3_starmie_spread | 22–8 | 73.3% |
| baseline pilot (Abomasnow) | 17–13 | 56.7% |
| a2_big_basic_31 | 15–15 | 50.0% |
| a2_kyogre_33 | 11–19 | **36.7%** |

**3. No truly independent test exists yet.** The suite has no real Worlds lists
(`agent_decks/benchmark/worlds_*.csv` still empty). Local win-rate is a filter, **ladder μ is truth.**

**4. Learned distills have historically underperformed on ladder.** Prior per-deck Learned probes
scored 490 (alakazam) / 469 (dragapult) μ — well below the 633 μ Kyogre heuristic. A strong local
deck does not guarantee a strong ladder Learned agent.

---

## Decision — Phase 2 greenlit, but GPU-gated and ladder-truthed

Per the ADR decision tree, **≥60% → retrain Learned on the RL deck (Phase 2).** Gate passed at 87%.

**Blocker:** Phase 2 training (MaskablePPO 100k) needs CUDA. This sandbox is CPU-only (no `torch`),
so training must run on the **user's GPU machine**. Validation work here is complete.

**Next action (user's GPU box):**

```bash
python scripts/train_track_b_deck.py \
  --deck report/rl_deck_campaign/best_deck.csv \
  --slug rl_deck --timesteps 100000 --n-envs 6 \
  --opponents benchmark --gate-games 40 --package --promote
```

Then gate (`gate_track_b.py` runs inside the pipeline), and only upload after the SPRT gate passes
**and** with explicit user approval. Treat the resulting μ as a **probe**; keep the Kyogre heuristic
(633 μ) as the Slot-2 fallback if RL-deck Learned does not beat it on ladder.

**Portfolio note:** RL deck losing to Kyogre (37%) is acceptable for a 2-slot portfolio — Slot 1
(Kyogre) and Slot 2 (RL deck) cover *different* matchups. It is a red flag only if both finals
share the same blind spot.
