# Handoff Prompt for Claude Code Agent

**Current date:** 2026-06-20  
**Live submission:** Ref#53869254 (SearchScorer + Lucario, 660.5μ, pinned to Finals)  
**Context:** Top performers discovered to be Alakazam/Trevenant (1312.7μ), not Lucario. Current hybrid needs expanded L1 gate and deck mining from leader replays.

---

## READ FIRST (in order, ~10 min)

1. **`.cursor/SESSION.md`** — Current focus, continue prompt, key bug list
2. **`report/top_performer_reverse_engineering_20260620.md`** — Leader analysis (Alakazam/Trevenant tactics)
3. **`agent/search_policy.py`** — Search-guard implementation (top-2 filter)
4. **`data/KAGGLE_SIMULATION_CLI.md`** — Kaggle CLI for replay fetching
5. **`.cursor/USER-RULES-PASTE-THIS.txt`** — Project operating rules

**Optional context:** `report/FINALS_PIN.md`, `report/lucario_best_approach.md`

---

## CURRENT STATE

**Live submission (pinned Finals):**
- Ref: **53869254**
- Scorer: `SearchScorer` + `LucarioScorer` hybrid
- Score: **660.5μ**
- Issues: 58.8% fast_loss, 13.4 avg turns, search rarely active

**V2 in development (not shipped):**
- Code: `agent/lucario_policy.py` + `agent/search_policy.py`
- Package: `track_a_lucario_ex_search_v2`
- L1 gate (9.2%): only vs generic 9-deck suite
- **Blocker:** Needs full L1 @ 30g vs **expanded suite** (add Alakazam/Trevenant from replays)

**Top performers (Kaggle CLI discovery):**
- **Alakazam** (ref 53802029): 1312.7μ, 11 replays fetched
- **Trevenant** (ref 53880887): 1304.2μ
- **Tactic gap:** They win 20–23 turns; we collapse at 13.4 with 59% in 2–7 turn range

---

## IMMEDIATE TASKS (Priority order)

### T1: Fix `analyze_submission.py` agent_index bug (10 min)
**File:** `scripts/analyze_submission.py`  
**Issue:** Uses global `_guess_agent_index()` but agent seat alternates per episode. Breaks per-episode stats.  
**Fix:** Track seat from `episode_log["state"]["yourIndex"]` for each game, not guessed once.  
**Verify:** Run on `report/replays/top_*.json` — confirm agent_index matches `"yourIndex"` per episode.  
**Success:** analyze_submission.py correctly labels agent vs opponent for all 11 fetched replays.

---

### T2: Mine Alakazam & Trevenant decks from 11 fetched replays (20 min)
**Files:** 
- Input: `report/replays/top_*.json` and `ref*.json` (11 leader game replays)
- Script: `scripts/analyze_submission.py` (once fixed)

**What to do:**
1. Run `analyze_submission.py` on each replay — extract final deck state for both agents
2. Identify Alakazam and Trevenant lines (Abra/Kadabra, Phantump/Trevenant)
3. Save mined decks to: `agent_decks/benchmark/alakazam_leader_*.csv` and `agent_decks/benchmark/trevenant_leader_*.csv`
4. Validate with `scripts/validate_deck.py`

**Success criteria:**
- 2–3 distinct Alakazam variants (from refs 53802029, 53878567, 53800247)
- 2–3 distinct Trevenant variants (from refs 53880887, 53876944)
- All CSV pass `validate_deck.py`
- Recorded in summary: `report/mined_decks_20260620.md`

---

### T3: Update `agent_decks/benchmark/suite.json` with mined decks (10 min)
**File:** `agent_decks/benchmark/suite.json`  
**Action:**
```json
{
  "tag": "leader_tactics",
  "decks": [
    "agent_decks/benchmark/alakazam_leader_core.csv",
    "agent_decks/benchmark/alakazam_leader_spread.csv",
    "agent_decks/benchmark/trevenant_leader_control.csv"
  ]
}
```

**Verify:** `python scripts/arena.py --help` still works; `pool_decks()` loads new suite.  
**Success:** suite.json includes 2–3 Alakazam + 2–3 Trevenant; all decks in arena.py pool.

---

### T4: Full L1 gate for v2 vs expanded suite @ 30 games (30–45 min)
**Command:**
```bash
python scripts/gate_track_a.py \
  --games 30 \
  --agents lucario_search \
  --deck agent_decks/benchmark/suite.json \
  --output report/public_gate/lucario_v2_vs_leader_suite_20260620.txt
```

**What gates against:**
- Current 9-deck generic suite
- NEW: Alakazam variants
- NEW: Trevenant variants
- Total: ~15 decks, 30 games/opponent ≈ 450 games

**Success criteria:**
- L1 passes (≥50% WR)
- Report: `report/public_gate/lucario_v2_vs_leader_suite_20260620.txt`
- Record gate % in `report/LUCARIO_V2_GATE.md`

---

### T5: Search audit — why isn't search firing on ladder? (15 min)
**Hypothesis:** v2 search-guard (top-2 filter) is too strict OR search_begin_input never triggers.

**Diagnosis:**
1. Instrument `agent/search_policy.py` — add debug log: `"search_fired: {fired}, context: {context}, top_2: {top_2}"`
2. Run smoke_replay on 5 cached games from ref 53869254 logs
3. Check: Does `search_fired` ever go True on MAIN, ENERGY, RETREAT, etc?
4. If rarely true: search-guard is working as designed (being conservative)
5. If never true: search_begin_input not firing (deeper issue)

**Success:** Written analysis in `report/search_audit_20260620.md` with clear verdict.

---

## ACCEPTANCE CRITERIA (for all tasks)

- ✅ No Kaggle submission without explicit user OK
- ✅ All new CSVs pass `scripts/validate_deck.py`
- ✅ All scripts still pass `smoke_test.py` (17/17)
- ✅ Reports saved to `report/` with clear summary
- ✅ No deletions; only add/modify
- ✅ `.gitignore` respected (no `.claude/`, `rl_policy.zip`, etc.)

---

## OPTIONAL FOLLOW-ON (if T1–T5 complete early)

**T6: Fast_loss analysis** — why 59% of losses are 2–7 turns?
- Root causes: bench collapse, no active, dead hand early?
- Suggested: Add `bench_guard` + `max_bench=2` to v2

**T7: Submit v2 if it beats 660.5μ**
- Only if gate (T4) shows clear improvement
- Use `scripts/package_submission.py --name lucario_v2_leader_tactics --scorer lucario_search`
- DRY-RUN ONLY; wait for user OK

---

## KEY CONSTRAINTS

- **No Kaggle upload** without explicit user confirmation
- **Branch:** `main` (ahead 2, dirty)
- **Python:** 3.13 w/ cu128 (for RL/GPU work if needed)
- **Blockers:**
  - Opponent agent logs: 403 (cannot fetch)
  - Daily bulk datasets: Not local
  - `result_reason` parser: Broken for losses
  - Search audit: May reveal search never fires (expected, OK)

---

## HANDOFF CHECKLIST

**What you have:**
- ✅ 11 leader replays in `report/replays/`
- ✅ V2 code complete (search-guard, deck-out throttle)
- ✅ Package ready (`track_a_lucario_ex_search_v2`)
- ✅ `gate_track_a.py` ready for full L1
- ✅ Suite.json template ready for expansion

**What you don't have yet:**
- ❌ Mined Alakazam/Trevenant decks (T2)
- ❌ Updated suite.json with new decks (T3)
- ❌ Full L1 gate result (T4)
- ❌ Search audit (T5)

---

## SUCCESS CONDITION

✅ **At end of run:**
- T1–T5 complete, reports written
- V2 L1 gate vs leader suite: score recorded
- Clear decision: **ship v2** (if beats 660.5μ) **or keep 53869254** (if tie/worse)
- Next agent can decide on submission

---

**Ready to run. GL.**
