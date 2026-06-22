# ADR-001: Finals portfolio strategy — maximize μ with 2 Final slots

> **Superseded (2026-06-22 repo reset).** Track B / deck-GA recommendations here are retired.
> Current strategy: rules/search floor (~668 μ), per-deck agents (`ARCHITECTURE.md`), Lucario field
> RL+MCTS as R3-gated experiment. See `STATE.md`, `RULINGS.md`, `data/EVAL_PROTOCOL.md`.

**Status:** Historical (pre-reset)  
**Date:** 2026-06-19 (run 24)  
**Deciders:** Dylan (project owner)  

---

## Context

The Pokemon TCG Strategy competition ends **September 14, 2026** (87 days). Ranking is determined by **exactly two Final Submissions** selected by the user (or auto-selected by Kaggle as the most recent two COMPLETE agents). The ladder score **μ** is the tiebreaker and public ranking signal during competition.

**Official constraints** (Kaggle §2.2, §3.18(c)):
- **5 uploads/day** (hard cap)
- **Only 2 final submissions** count for official standing
- "Disabled due to active submission limit" ≠ ERROR; it means "not a Final slot" (see SUBMISSION_PLAYBOOK.md)

**Current best ladder signals** (as of run 23–24):
- Kyogre heuristic: **633.0 μ** (best overall, but not currently a Final slot)
- Search + Kyogre+2e: **625.0 μ** (≈ heuristic)
- Learned (wrong-deck single distill): 490.4, 468.9 μ (probes only; undercounted because trained on wrong deck)
- Deck RL campaign: in progress (overnight run 24)

**Three optimization loops** (from EVAL_PROTOCOL.md):
- **Track A (Search):** hand-tuned rules + optional search; any legal deck; no training
- **Track B (Learned):** MaskablePPO per deck → distill → LearnedScorer; requires per-deck retrain
- **Track C (Deck RL/GA):** optimize 60-card list vs benchmark suite; output deck

**Key finding:** Learned policy is **not deck-agnostic**. Single distilled `distilled_v1.npz` trained on default deck scores poorly (490 μ) when paired with Alakazam/Dragapult. **Per-deck retrain + distill is required** to fairly test Track B.

---

## Decision

**Primary strategy: Use both Final slots for per-deck-trained LearnedScorer agents (Track B).**

**Final Slot 1:** LearnedScorer on Kyogre (33-energy)  
**Final Slot 2:** LearnedScorer on a second meta archetype (Crustle or Dragapult, **retrained**)

**Rationale:**
1. Kyogre heuristic (633.0 μ) is current best but is a *heuristic*. Track B has higher ceiling if policy trains on the same deck used at inference.
2. Track A (Search) ≈ heuristic (625 μ observed); Search is not clearly better than heuristic, so heuristic is simpler (less inference latency, simpler stack).
3. Track B untested fairly; single wrong-deck distill (490 μ) is not evidence Track B is weaker — it's evidence we haven't tuned it yet.
4. **Upside:** per-deck Learned could exceed 633 μ if policy learns matchup-specific play. **Downside:** if Track B gates fail, heuristic Kyogre 633 stays as fallback.
5. Two Learned agents provide **archetype diversity** (e.g. Kyogre water control + Crustle physical tank) to cover meta breadth; heuristic + heuristic would be redundant.

---

## Options Considered

### Option A: Lock Kyogre heuristic + 1 Search probe (conservative)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low. Heuristic is stable (17/17 smoke). Search is hand-tuned. |
| Ceiling | ~640–660 μ (small margin above current 633 heuristic). |
| Time to production | Immediate; no retraining needed. |
| Risk | Low; both are proven. |
| Matchup coverage | Limited. Two Water-ish decks (Kyogre water, Search water) on field. |

**Pros:**
- Minimal risk. Both agents pass smoke and local gate.
- Known μ (633 heuristic vs field).
- Can finalize immediately.

**Cons:**
- Forgoes Track B entirely. If Learned can beat heuristic (not yet tested fairly), we miss the upside.
- Heuristic + Search is near-redundant on Kyogre (both score 625–633).
- Two Final slots are not diversified by archetype.

---

### Option B: Lock Kyogre heuristic + Kyogre Search with 2e changes (incremental)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low–Med. Deck search already done; Search gate at 40g pending. |
| Ceiling | ~640–650 μ (5–15 point margin). |
| Time to production | 1–2 nightly runs (deck_search + gate_track_a). |
| Risk | Low–Med. Search is unproven on ladder. |
| Matchup coverage | Low. Both agents are Water-primary. |

**Pros:**
- Faster than Track B (no RL training).
- Search + deck tuning could beat 633 if 2e energy split is correct.
- Lower latency than Learned (no neural network).

**Cons:**
- Same problem as Option A: two agents on the same archetype.
- Search gates not yet passing at 40g (per PROGRESS.md run 13).
- Small upside vs heuristic (25–50 μ is optimistic).

---

### **Option C: Kyogre LearnedScorer (retrained) + second archetype LearnedScorer (retrained)** ← **RECOMMENDED**

| Dimension | Assessment |
|-----------|------------|
| Complexity | High. Requires 2× `train_track_b_deck.py` runs. |
| Ceiling | **650–700+ μ** (if policy generalizes; 25–70 point upside). |
| Time to production | 3–5 nightly runs (policy RL + distill + gate × 2). |
| Risk | Med. Learned must gate and prove on ladder. |
| Matchup coverage | **High.** Kyogre (water control) + Crustle (physical tank) or Dragapult (mixed). |

**Pros:**
- **Fairest test of Track B.** Single wrong-deck distill (490 μ) is not evidence of weakness.
- **Archetype diversity.** Two decks cover different roles (water vs physical vs special).
- **Highest ceiling.** If Learned can exceed heuristic on per-deck training, upside is 50–100 μ.
- **Policy learns meta.** Each distill sees different deck's matchups; less overfitting to one line.
- **Leverage current progress.** Deck RL campaign (Track C) is running; if it outputs a strong new archetype, can retrain Learned on it.

**Cons:**
- **Time-to-production is long.** Each `train_track_b_deck.py` is ~30–60 min (RL 100k steps + distill + gate @40g).
- **Risk of gate failure.** If Learned doesn't beat Search baseline (SPRT) on either deck, fallback is heuristic + Search.
- **Requires manual Final slot selection on deadline.** Kaggle auto-select might pick the two most recent (which could be failed probes).

---

## Trade-off Analysis

| Factor | Option A (Heur+Search) | Option B (Heur+Search+deck) | **Option C (Learned×2)** |
|--------|----------|----------|----------|
| **Risk** | Lowest | Low–Med | Med–High |
| **Ceiling μ** | ~640 | ~650 | **650–700+** |
| **Time needed** | 0 days | 2–3 days | 5–7 days |
| **Archetype diversity** | No | No | **Yes** |
| **Gate complexity** | 1 (known passing) | 2 (pending) | **4 (gates × 2 decks)** |
| **Confidence on deadline** | Very high | High | Medium |

**Key insight:** Option C trades time and gate-risk for **ceiling upside** and **archetype diversity**. With 87 days until Sept 14, time is available. If Learned gates pass (best case), Option C is 50–100 μ better. If gates fail, fallback to heuristic.

---

## Consequences

### If Option C is adopted:

**Immediate (next run):**
- Finish deck RL campaign (run 24 in progress).
- After campaign completes, evaluate best deck from `report/rl_deck_campaign/best_deck.csv`.
- Parallel: retrain Track B on Kyogre using `train_track_b_deck.py --deck agent_decks/a2_kyogre_33_energy.csv --slug kyogre --timesteps 100000 --gate-games 40 --package --promote`.

**Gates (runs 25–27):**
- Track B gate on Kyogre: target ≥ 206/240 (SPRT accept_b or beat Search 197/240 baseline).
- If PASS: package `track_b_learned_kyogre.tar.gz`; upload as ladder probe; record μ.
- If FAIL: fallback to Option A (heuristic + Search).

**Second archetype (runs 28–30):**
- Choose second deck (Crustle, Dragapult, or output from deck campaign).
- `train_track_b_deck.py --deck agent_decks/<second> --slug <slug> --timesteps 100000 --gate-games 40 --package --promote`.
- Gate and ladder probe same as Kyogre.

**Final selection (by Sept 13):**
- Manually select 2 Final Submissions on Kaggle UI: Kyogre Learned + second archetype Learned (if both gates pass).
- If second gates fails, use heuristic Kyogre as Slot 2.

### Consequences of gates failing:

- **Learned on Kyogre fails SPRT:** Learned is weaker than Search; fallback to heuristic Kyogre (633) as Slot 1, Search as Slot 2 (650 optimistic).
- **Learned on second archetype fails:** Slot 2 becomes heuristic Kyogre again (redundancy), or Search on Kyogre if Search gates separately.
- **Both fail:** Use heuristic Kyogre + Search (Option A). Current best is still 633 μ.

### Upside if gates pass:

- **Kyogre Learned gates at 60%+:** likely 650–680 μ on ladder (20–50 point upside).
- **Second archetype Learned gates at 60%+:** likely 620–660 μ (new archetype, lower gate but diverse).
- **Both combined as Finals:** 2-agent portfolio covering water/physical; expected rank top-20% if each is 650+ μ.

---

## Action Items

### Phase 1: Validate Track B on Kyogre (runs 25–26, ~24 hours offline)

- [ ] **Run 25:** Complete `python scripts/train_track_b_deck.py --deck agent_decks/a2_kyogre_33_energy.csv --slug kyogre --timesteps 100000 --gate-games 40 --package --promote`
- [ ] Wait for RL training to complete (~15 min CUDA), distill (~5 min), gate (@40 games, ~10 min).
- [ ] Check `report/track_b_gate.md` for SPRT result.
  - PASS → **Action:** `python scripts/package_submission.py --name track_b_learned_kyogre --scorer learned --deck agent_decks/a2_kyogre_33_energy.csv --model agent/models/distilled_kyogre_v1.npz` and upload as ladder probe.
  - FAIL → Fallback to Option A; update this ADR status to "superseded."
- [ ] Record ref, μ, and gate result in `report/ladder_history.csv`.

### Phase 2: Validate Track B on second archetype (runs 27–28, ~24 hours offline)

- [ ] Choose second deck (recommend Crustle for physical/tank diversity; or output from deck campaign if it's competitive).
- [ ] **Run 27:** `python scripts/train_track_b_deck.py --deck <second_deck_path> --slug <slug> --timesteps 100000 --gate-games 40 --package --promote`
- [ ] Gate check same as Phase 1.
  - PASS → Upload as ladder probe; record in `report/ladder_history.csv`.
  - FAIL → Slot 2 remains heuristic Kyogre (or Search if Search gates separately).

### Phase 3: Final selection (by Sept 13, 2026)

- [ ] On Kaggle Submissions page, **manually select 2 Final Submissions:**
  - Final 1: `track_b_learned_kyogre` (assuming PASS)
  - Final 2: `track_b_learned_<second>` (assuming PASS) or fallback heuristic Kyogre
- [ ] **Do NOT rely on auto-select.** Kaggle auto-selects by recency; if your best μ is not your most recent upload, it will be disabled.

### Fallback (if Option C gates fail):

- [ ] Use Option A: heuristic Kyogre (633 μ current best) + Search if gate passes.
- [ ] Or use Option B: heuristic Kyogre + improved Search with deck tuning.

---

## Grounding (official rules)

- **Kaggle §2.2:** "You may submit a maximum of five (5) Submissions per day" and "You may select up to two (2) Final Submissions for judging."
- **§3.18(c):** "Final Submission ... selected by the user, or automatically selected by Kaggle in the event not selected by the user ... used for final placement on the competition leaderboard."
- **Scoring:** Per Simulation competition description, agents scored on episode W/L; leaderboard aggregated from all episodes played.

---

## Next Review

- **Run 26 (if Track B Kyogre gates):** Confirm Phase 2 start.
- **Run 28 (if both gate):** Confirm archetype diversity on ladder. If second probe underperforms (< 600 μ), consider re-tuning deck or trying a third archetype.
- **Run 50+ (mid-August):** Review ladder history; if Learned consistently > 633, lock Finals early. If Learned stalls, pivot to Option A before deadline.
