# Mega Lucario ex — Best Approach (2026-06-20)

Deck: `agent_decks/real_mega_lucario_ex.csv`  
**Authoritative Lucario strategy doc** — SmartBench, hybrid search, loss modes, ship gates.

---

## Executive summary (end of day)

| Layer | Candidate | Scorer | μ / L1 | Verdict |
|-------|-----------|--------|--------|---------|
| **Production (Finals)** | `track_a_lucario_ex_search` | `SearchScorer` | **668 μ** (ref 53869254) | **Pin both Final slots** until beaten |
| **SmartBench** | `track_c_lucario_rulecore_smartbench` | `LucarioScorer` | 600 μ; L1 **10%**, mirror **43%** | Fixes empty-bench; weak cross-archetype |
| **Hybrid (new)** | `track_a_lucario_ex_search_v2` | `LucarioSearchScorer` | L1 **incomplete**; mirror **23%** (partial) | **Do not submit** — regressed mirror vs SmartBench |
| **RL** | `track_d_lucario_rl_mcts_iter2` | MCTS | iter2 champion only | Blocked until iter ≥4 + L1 |
| **Alakazam Learned 1M** | — | — | Kyogre holdout **0%** | **Retired** |

**One sentence:** Keep **Search Lucario (668 μ)** on Finals. The winning direction is **Search on promotion/setup + Lucario meta MAIN**, but today's naive merge (`LucarioSearchScorer`) hurt mirror play before L1 finished — next fix is **deck-out throttling** and **setup-bench search tuning**, not a blind upload.

---

## Current best approach (what we ship)

### Production agent — ref 53869254

```
Agent.act
  └─ bench_critical? → LucarioScorer (Lucario deck) / RuleCore (other decks)

SearchScorer.choose
  ├─ SEL_CARD + setup/switch/to-active → cg search_* (200 ms)
  └─ else → HeuristicScorer (generic MAIN)
```

- Package: `--scorer search --deck agent_decks/real_mega_lucario_ex.csv`
- L4: 48.5% WR (33 ep), avg turns 13.4, fast_loss 58.8%
- Weakness: generic heuristic MAIN misses Lucario-specific Jab/Brave/Gong lines

### Target architecture — `LucarioSearchScorer` (implemented, not promoted)

```
Agent.act
  └─ bench_critical? → LucarioScorer (unchanged)

LucarioSearchScorer.choose
  ├─ SEL_CARD + setup/switch/to-active → cg search_* (200 ms)
  └─ else → LucarioScorer (meta MAIN, smart bench scoring)
```

| File | Role |
|------|------|
| `agent/search_policy.py` | `_CgSearchMixin`, `SearchScorer`, **`LucarioSearchScorer`** |
| `agent/lucario_policy.py` | Official sample attack plan + meta + smart bench |
| `agent/bench_guard.py` | Empty-bench / setup-bench → Lucario (never skip first basic) |
| `agent/smart_bench.py` | Max 2 voluntary bench basics |
| `agent/agent.py` | Never-crash wrapper |

Package hybrid:

```bash
python scripts/package_submission.py \
  --name track_a_lucario_ex_search_v2 \
  --scorer lucario_search \
  --deck agent_decks/real_mega_lucario_ex.csv
```

**Ship gate:** L1 @ 30 games vs public field; must beat v1 Search Lucario on suite mean **and** hold mirror ≥40%. Pin Finals only if L1 + L4 improve over 53869254.

---

## Background: agent lineage

| Ref | Scorer | μ | Problem / strength |
|-----|--------|---|---------------------|
| **53869254** | SearchScorer | **668** | Best proven; search on setup/switch; generic MAIN |
| **53886522** | LucarioScorer + SmartBench | **600** | Mirror +43%; empty-bench fixed; no search layer |
| **53885445** | LucarioMCTSScorer (RL iter-0) | **324** | Retired — empty bench → `no_active` |
| iter2 RL | LucarioMCTSScorer | — | Packaged; not ladder until iter ≥4 + L1 |

μ alone hid RL failure modes. Always check episode stats: win rate, avg turns, `fast_loss_pct`, **`result_reason`**.

---

## Meta tactics (LucarioScorer MAIN)

Grounded in [Pokemon.com Mega Lucario ex deck strategy](https://www.pokemon.com/us/strategy/pokemon-tcg-deck-list-and-strategy-building-a-mega-lucario-ex-deck).

### Early game

- **Solrock + Lunatone** — complete pair early; Lunatone ability when discard has Fighting energy (Aura Jab fuel).
- **Search trainers** — Dusk Ball / Poké Pad when Riolu line missing; Fighting Gong / PPP when line needs energy; Lillie when engine missing.
- **Riolu line** — bench first backup; 2 energy; evolve Mega Lucario ex before over-committing to wall lines.

### Mid game (prize-aware)

- **Solrock Cosmic Beam (70)** — low-HP, single-prize targets.
- **Aura Jab (982)** — 130 + discard-to-bench accel when discard has Fighting energy.
- **Mega Brave (983)** — 270 on **2+ prize** KOs only; skip on 1-prize targets above 130 HP.
- **Hariyama** — Makuhita → Hariyama for gust targets and ex prizes; Jab feeds energy.
- **Gravity Mountain** — when opponent has Stage 2 in play (−30 HP in sim).
- **Brave cooldown** — retreat + Switch when Brave unavailable but another Brave turn planned.

### Deliberately not done

- Blanket END-over-ATTACK when bench empty — END does not fix empty bench; guard only forces **PLAY when legal**.

---

## Loss modes (simulator ground truth)

All three cost **one full loss** on μ — no turn-margin bonus ([`data/COMPETITION_SCORING.md`](../data/COMPETITION_SCORING.md)).

| `result_reason` | When | Lucario relevance |
|-----------------|------|-------------------|
| `prize` | Opponent takes all prizes | Normal win/loss |
| **`deck_out`** | Loser's **`deckCount` ≤ 0** and must draw | **High** — Lucario thins with search/draw |
| `no_active` | No Pokémon to promote | **Fixed** by bench_guard + smart bench |
| `card_effect` | Card-specific | Rare |

**Deck-out insight (2026-06-20):** Running out of cards to draw **ends the episode as a loss**. Lucario is a thinning deck (Dusk Ball, Poké Pad, Lillie, Carmine, Lunatone, Jab accel). Long wall/spread games deck out if we keep searching.

**Existing guards in `LucarioScorer`:**

- `deck_count <= 10` → block **Dusk Ball** and **Poke Pad** (`return -1.0`).

**Gaps (next levers):**

- **Carmine / Lillie** still score positively at low deck — should throttle like search cards.
- **Lunatone ability** can keep thinning late in long games.
- **Crustle/wall matchups** — slow games + thinning = `deck_out` losses (0% vs crustle-bot in L1).
- **`RuleCoreScorer`** already penalizes draw/search more aggressively (`low_deck`, deck ≤35 in wall mode) — pattern to port into Lucario MAIN.

---

## Measurement results

### L0

```bash
python scripts/smoke_test.py      # 17/17
python scripts/smoke_replay.py    # 13/13 (incl. lucario_search_scorer_instantiates)
```

### L1 public gate @ 30 games

**SmartBench** (`track_c_lucario_rulecore_smartbench`, `LucarioScorer`):

| Metric | Value |
|--------|-------|
| Suite mean | **10.0%** (36/360) |
| vs Lucario sample | **43.3%** (13/30) |

**Hybrid v2** (`track_a_lucario_ex_search_v2`, `LucarioSearchScorer`) — **partial run** (gate interrupted; 7/12 opponents logged):

| Opponent | WR |
|----------|-----|
| Lucario sample | **23.3%** (↓ from 43%) |
| Dragapult / Iono / Abomasnow samples | 10.0% |
| 1084 baseline | 6.7% |
| Crustle bot | 0.0% |
| anti-wall | 3.3% |

**Interpretation:** Naive search-on-setup overlay **regressed mirror** (search may over-bench or pick non-Lucario setup lines vs SmartBench's capped 1–2 bench). Cross-archetype WR flat ~10%. **Re-run full L1** before any decision; consider excluding `SETUP_BENCH_POKEMON` from search while keeping switch/to-active/setup-active.

**v1 Search baseline** (53869254): ~20% suite in prior `report/public_gate/results.md`; 6.7% vs Lucario search in SmartBench table.

### L4 (Kaggle episodes)

| Ref | win_rate | avg_turns | fast_loss_pct |
|-----|----------|-----------|---------------|
| 53869254 (Search) | 48.5% (33 ep) | 13.4 | 58.8% |
| 53886522 (SmartBench) | 50% (2 ep) | 10.5 | 100% |

---

## Why mirror was 43% but overall ~10%

**Mirror (~43% SmartBench):** Meta tactics fix Lucario-specific openings — Riolu, energy, Solrock/Lunatone, Jab → Hariyama/Brave.

**Overall (~10%):** Public field wins on **lookahead** (promotion, switch, gust) vs diverse decks. SearchScorer (668 μ) has search but generic MAIN. SmartBench has Lucario MAIN but no search. **Hybrid must combine both without breaking smart bench or deck clock.**

---

## Portfolio & blockers

| Track | Status |
|-------|--------|
| **Finals** | **53869254 ×2** ([`report/FINALS_PIN.md`](FINALS_PIN.md)) |
| **Hybrid upload** | Blocked — partial L1 shows mirror regression |
| **SmartBench upload** | ref 53886522 live; too few L4 episodes to replace Finals |
| **Lucario RL** | iter2 packaged; iter3 not promoted; notebook iter ≥4 |
| **Alakazam Learned 1M** | Retired — see [`report/handoffs/alakazam_track_b_1m_status.md`](handoffs/alakazam_track_b_1m_status.md) |
| **Kaggle Simulation** | **No upload without explicit user OK** (5/day limit) |

---

## Commands reference

```bash
# SmartBench
python scripts/package_submission.py \
  --name track_c_lucario_rulecore_smartbench \
  --scorer lucario \
  --deck agent_decks/real_mega_lucario_ex.csv

# Hybrid (current best code path — not yet ship-worthy)
python scripts/package_submission.py \
  --name track_a_lucario_ex_search_v2 \
  --scorer lucario_search \
  --deck agent_decks/real_mega_lucario_ex.csv

# L1 @ 30 (complete interrupted run)
python scripts/gate_vs_public.py \
  --agent dist/candidates/track_a_lucario_ex_search_v2.tar.gz \
  --games 30

# Compare v1 Search baseline
python scripts/gate_vs_public.py \
  --agent dist/candidates/track_a_lucario_ex_search.tar.gz \
  --games 30

# Post-upload
python scripts/analyze_submission.py --ref <submission_ref>
```

---

## Exact next actions

1. **Complete L1 @ 30** for `track_a_lucario_ex_search_v2` vs v1 Search tarball.
2. **Deck-out pass** — throttle Carmine/Lillie/Lunatone when `deck_count <= 10–15`; consider opponent prize count / turn clock.
3. **Hybrid tuning** — if mirror stays <40%, drop `SETUP_BENCH_POKEMON` from search contexts; keep switch/to-active/setup-active only.
4. **Re-gate**; upload only with user OK if suite mean beats 53869254 local benchmark **and** L4 stats improve.

---

## Files changed (2026-06-20 Lucario pass)

- `agent/search_policy.py` — `_CgSearchMixin`, **`LucarioSearchScorer`**
- `agent/lucario_policy.py` — meta trainers, Jab/Brave, energy/evolve priority
- `agent/bench_guard.py`, `agent/smart_bench.py`, `agent/agent.py`
- `scripts/package_submission.py` — `--scorer lucario_search`
- `scripts/smoke_replay.py` — golden tests incl. hybrid instantiate
- `report/submission_log.csv`, `report/FINALS_PIN.md`
- `data/KAGGLE_SIMULATION_CLI.md` §8–9, `data/EVAL_PROTOCOL.md`
