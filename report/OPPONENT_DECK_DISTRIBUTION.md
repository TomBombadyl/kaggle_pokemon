# Opponent Deck Distribution Tracker

**Purpose:** Track what decks competing agents are using to understand meta composition and tailor our strategy.

**Last Updated:** 2026-06-22 (Session 44d — draft; refresh via `update_opponent_tracker.py`)  
**Role:** **Phase 3 only** — field mixture weights for gates and RL sampling. Do not use to skip
global rules (phase 1) or matchup levers (phase 2). See `ARCHITECTURE.md` § Per-deck template.

---

## Current Known Submissions (Ranked by Ladder μ)

| Rank | Agent Name | Deck | μ | σ² | Episodes | Notes |
|------|-----------|------|---|----|----|-------|
| 1 | (Unknown) | ? | ~1332 | ? | ? | **Top of ladder (from episode metadata)** |
| 2 | (Unknown) | ? | ? | ? | ? | |
| ... | ... | ... | ... | ... | ... | |
| **Ours** | **Lucario v2 (SearchScorer)** | **Mega Lucario-EX** | **734.6** | **?** | **~70+** | Pinned, not re-submitting |
| **Ours** | **Alakazam best5 (rule-based)** | **Alakazam/Kadabra/Abra** | **636.8** | **?** | **~40+** | Slot 1, age ~24h |
| (Ready) | Trevenant SearchScorer | Trevenant ex | ? | ? | ? | Ready for Slot 2 |

---

## Known Public Baselines (From Public Gate)

These are from `data/kaggle_ref/opponents/` used in gating.

| Baseline Name | Deck Type | Inferred Archetype | Gate WR (ours) | Notes |
|---|---|---|---|---|
| `a-sample-rule-based-agent-iono-s-deck` | Iono/Disruptor | Control/Disruption | 13.3% (Alakazam) | Difficult matchup |
| `a-sample-rule-based-agent-mega-abomasnow-ex-deck` | Abomasnow-EX | Water/Spread | 13.3% (Alakazam) | |
| `a-sample-rule-based-agent-mega-lucario-ex-deck` | Mega Lucario-EX | Fighting/Mirror | 23.3% (AZ v1) | **Mirror matchup** |
| `a-sample-rule-based-agent-dragapult-ex-deck` | Dragapult-EX | Psychic/Tempo | 10.0% (AZ v1) | |
| `beating-the-day-1-1-crustle-bot` | Crustle | Wall/Control | 13.3% (AZ v1) | |
| `crustle-aware-mega-lucario-ex-anti-wall` | Lucario (anti-Crustle) | Fighting/Anti-wall | 6.7% (AZ v1) | **Specialized counter** |
| `pokemon-tcg-ai-battle-1084-5-baseline` | Unknown | Rule-based baseline | 0.0% (AZ v1) | Strongest baseline; we collapse vs this |
| `ptcg-public-915-lucario-search-baseline` | Lucario (search) | Fighting/Search | 3.3% (AZ v1), 23.3% (Alakazam) | **Known strong Lucario** |
| `public-scores-915` | Unknown | ? | 6.7% (AZ v1) | |
| `rule-based-not-psychic-alakazam-best-5th` | Alakazam | Psychic/Draw | 10.0% (AZ v1) | Public Alakazam |
| `simple-baseline-matchup-tests` | Unknown | Generic/Testing | 3.3% (AZ v1) | |
| `top-dragapult-ex-tempo-control-agent` | Dragapult-EX | Psychic/Tempo | 16.7% (AZ v1) | |

---

## Field Meta (From Episode Data Analysis)

**Source:** `report/winner_analysis_20260621.md` (5,584 decided games, 06-19 dump)

| Deck | Frequency | Win Rate | Notes |
|------|-----------|----------|-------|
| **Lucario (all variants)** | **~53%** | **52.5%** | **Dominant meta; hub deck** |
| Bellibolt | ? | Beats Alakazam (69.8%) | **Alakazam counter** |
| Alakazam | ? | Beats Lucario (51.9%) | **Lucario counter** |
| Dragapult | ? | ? | Tempo/control |
| Kyogre | ? | ? | Water/spread |
| Trevenant | ? | ? | Grass/wall |
| Unknown/Other | ? | ? | |

**Key Finding:** Lucario is ~53% of the field; mirror matches are ~30% of all games and heavily pilot-dependent.

---

## Deck Archetype Distribution (Inferred)

```
Fighting (Lucario variants):    ~53%
  ├─ Mega Lucario-EX Search:   ~35%
  ├─ Lucario w/ anti-Crustle:  ~5%
  ├─ Lucario (other tuning):   ~13%
  
Psychic (Alakazam/Dragapult):  ~15%
  ├─ Alakazam/Kadabra/Abra:    ~8%
  └─ Dragapult-EX:             ~7%
  
Water (Bellibolt/Kyogre):      ~12%
  ├─ Bellibolt (disruption):   ~6%
  └─ Kyogre (spread):          ~6%
  
Grass/Wall (Trevenant, Crustle): ~10%
  ├─ Trevenant ex:            ~5%
  └─ Crustle (wall):          ~5%
  
Other:                          ~10%
```

---

## Strategy Implications

### Strengths (Our Decks vs Meta)
- **Lucario v2:** Crushes Bellibolt (75% WR), strong vs Kyogre (75%), beats Dragapult (65.5%)
- **Alakazam:** Beats Lucario (51.9%), beats Dragapult (57.3%), beats Abomasnow (70.5%)

### Weaknesses (Our Decks vs Meta)
- **Lucario v2:** Loses to Alakazam (48.1%), weak vs Lucario mirror (50/50, pilot-dependent)
- **Alakazam:** Loses to Bellibolt (30.2%), **loses to Iono disruptors (29.7%)**, loses to strong Lucario-search (43.4%)

### Next Submissions (Slot 2-5 Priority)
1. **Trevenant:** Good vs Lucario (deck matchup unknown, estimated neutral-good)
2. **Kyogre:** Counter to Bellibolt (water-on-water)
3. **Anti-Iono Alakazam (if improved):** Would address biggest weakness
4. **Dragapult or other:** Diversify against unknown meta shifts

---

## How to Update This Tracker

**When new leaderboard snapshot available:**
1. Parse `report/leaderboard_snap_*.json`
2. Extract agent names, scores, submission dates
3. Look up agent submissions in `report/our_submissions.json`
4. Cross-reference with gate logs to infer decks
5. Update this tracker with new entries

**When running gates:**
1. Note which opponents are tested
2. Record win rates by opponent
3. Infer deck types from opponent names
4. Update "Known Public Baselines" section

**When analyzing episodes:**
1. Parse `data/episodes/raw/*.json` (when available)
2. Extract deck lists from winning/losing agents
3. Compute frequency distribution
4. Update "Field Meta" section

---

## Script: Auto-Generate Tracker

```python
# File: scripts/update_opponent_tracker.py
"""
Auto-generate OPPONENT_DECK_DISTRIBUTION.md from:
1. Leaderboard snapshot (team names, μ values)
2. Our submission history
3. Gate logs (opponent names, win rates)
4. Episode data (deck frequencies, archetype distribution)
"""

# TODO: Implement when leaderboard/episode data available
```

---

## Known Gaps

- ❌ **Exact deck lists for top-ranked agents** (need to sniff from games or replays)
- ❌ **Current leaderboard standings** (awaiting Kaggle API pull)
- ❌ **Per-deck win rates in current meta** (need full episode analysis)
- ❌ **Submission dates** (need leaderboard timestamps)
- ⚠️ **Episode data through 06-21** (manifest ready, JSON files need download)

---

## Related Files

- `STATE.md` / `TASKS.md` (R1–R3 pilot rules backlog)
- `ARCHITECTURE.md` § Per-deck agent template (phases 1–3)
- `scripts/update_opponent_tracker.py` — auto-update (needs leaderboard snapshot)
- `data/episodes/raw/manifest.csv` — episode index (when downloaded)
- `report/submission_log.csv` — our submission history

---

**Purpose (phase 3):** After global rules + levers are gated, use this to:
1. Weight eval gates by field share (`E[win] = Σ share·WR`)
2. Weight field RL opponent sampling
3. Inform upload priority — not to skip per-matchup rule work
