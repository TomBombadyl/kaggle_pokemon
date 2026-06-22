# Lucario Mirror Tuning Analysis — 2026-06-22

**Current baseline:** 14.4% win rate vs lucario opponents (target: 50%+)
- vs sample-rule-based: 30% (9-21)
- vs crustle-aware-anti-wall: 10% (3-27)  
- vs public-915-baseline: 3.3% (1-29) ← CRITICAL

---

## Problem Diagnosis

### 1. Endgame Penalty (Line 321-322 in lucario_policy.py)
```python
if my_prize in (2, 3):
    base_score -= 500
```

**Issue:** Penalizes attacking when at 2-3 prizes left (endgame/ahead).

**Why this breaks mirror play:**
- Mirror is 50/50 on deck → decided purely by tempo/pilot
- Field is **aggressive**: KO/prize race 71.7% of games (~13 turns median)
- When ahead (3 prizes vs opponent 4+), we should keep pressure, not turtle
- This -500 penalty makes us stall exactly when we should close out

**Impact:** We likely play passively when winning, giving opponent time to equalize/come back.

---

### 2. Modest Attack Bonuses (Lines 390-401)
Current bonuses for KO opportunities:
- Mega Brave (2-prize targets): +450
- Mega Aura (2-prize targets): +300
- Solrock (1-prize targets): +350
- Hariyama (2-prize targets): +200

**Issue:** These bonuses exist but may not overcome defensive/setup priorities in early game.

**Impact:** We prioritize board development over early tempo/KO setup.

---

### 3. Turn-Gating (Line 278)
```python
if state.turn < 2:
    return
```

**Issue:** Attack plan only kicks in turn 2+. Early turns are unplanned (default heuristic).

**Implication:** No deliberate tempo strategy for turns 1-3 (crucial setup phase).

---

## Field Context (From Session 40 Analysis)

- **Lucario is ~53% of field**, 52.5% win rate (hub)
- **Lucario mirror = ~30% of ALL games** (1,688 / 5,584 decided)
- **Mirror is 50/50 on deck** → decided entirely by **pilot play**
- **Field median:** 12 turns, aggressive (71.7% KO race)
- **First-player edge:** small (52.1%)

---

## Proposed Tuning

### ✅ Immediate Fix (High Impact)
**Remove or reduce endgame penalty:**

Replace:
```python
if my_prize in (2, 3):
    base_score -= 500
```

With:
```python
if my_prize in (2, 3):
    base_score += 200  # Reward aggressive close-out
```

**Rationale:** Meta favors tempo. When ahead, stay aggressive.

---

### ✅ Secondary Tuning (Medium Impact)
**Increase early KO bonus (line 396-397):**

Current:
```python
if op_pokemon.hp <= 130:
    line_bonus += 300.0
```

Proposed:
```python
if op_pokemon.hp <= 130:
    line_bonus += 500.0  # +67% boost for early KO targets
```

**Rationale:** Reward finishing weakened targets faster.

---

### ⏳ Optional Enhancement (Measurement Phase)
**Add explicit turn-based tempo scoring:**

For turns 1-6 (early game), boost attack scores by turn number:
```python
tempo_bonus = min(state.turn, 6) * 20  # +20 per turn up to turn 6
```

**Rationale:** Encourages earlier attacks; reward tempo naturally.

---

## Validation Plan

1. **Self-play mirror:** Run 30 games Search Lucario vs itself, measure win rate
2. **Public gate:** `gate_vs_public.py --only lucario --games 30` → target >50%
3. **Suite gate:** Full suite vs top public field → ensure no regression elsewhere

---

## Files to Modify

- `agent/lucario_policy.py` (lines 321–322, potentially 396–397)
- Packaged with: `--scorer lucario_search` or `lucario_mcts`

---

## Next Steps (This Session)

1. Apply endgame penalty fix (line 321-322)
2. Increase early KO bonus (line 396-397)
3. Run self-play validation (30 games)
4. Run public gate (--only lucario, 30 games)
5. If >40% achieved: proceed with suite gate
6. If <40%: investigate additional tuning needs

Target: **Move 14.4% → 45%+ before end of session**

---

**Grounding:** Field map from Session 40 (`report/winner_analysis_20260621.md`), handoff (`report/handoffs/deck_rl_continuation_20260621.md`), official rules (Simulation, aggressive meta confirmed).
