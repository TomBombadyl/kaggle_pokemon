# STATE — current state & the single next action

> **Mindset:** `RULINGS.md` Part 0 · **Plan:** `ROADMAP.md` · **Upload gate:** `scripts/check_upload_eligible.py --suggest`

---

## As of 2026-06-26 (Session 52 — two-Final Archaludon strategy)

**Goal:** Two Finals worth keeping · drop Starmie (277.5 μ).

| Ref | Version | μ (latest) | Role |
|-----|---------|------------|------|
| **54083197** | R7 bench guard | **1196.1** | **Final #1 — lock** |
| **54088877** | R8a+R8b | **780.7** (climbing: 600→704→780) | Probe — swap in if beats 1196.1 |
| **54089078** | R8+R9 micro TO_HAND floor | PENDING | Probe — tiny delta vs 54088877 |

**R9 change:** `_to_hand_pick_floor` (~12 lines) — fixes TO_HAND stall; skips Explorer discard pass.

### THE SINGLE NEXT ACTION

**Kaggle UI:** Pin **54083197** as Final #1. **`track_ladder.py`** ≥40 min for **54088877** + **54089078** 2nd readings. Pick highest μ Archaludon for Final #2; **disable Starmie 54083513**.

---

## As of 2026-06-26 (Session 52 — R8 submitted)

| Field | Value |
|-------|-------|
| **Ref** | **54088877** (COMPLETE — 1st reading **600.0 μ**) |
| **Package** | `archaludon.tar.gz` |
| **Delta vs 54083197** | R8a TO_ACTIVE promote + R8b empty-bench tempo block |
| **Local gate** | **75.3%** full n=30 |
| **Final (locked)** | **54083197** @ **1196.1 μ** — swap only if 54088877 beats on ≥2 readings |

### THE SINGLE NEXT ACTION

**Wait ≥40 min**, then **`python scripts/track_ladder.py`** for ref **54088877** 2nd μ reading. **Keep 54083197 (1196.1 μ) pinned as Final** on Kaggle until 54088877 beats it on ≥2 readings.

---

## As of 2026-06-26 (Session 52 — R8 agent iterations)

**Two scoring passes in `agent/archaludon_agent.py`**, gated full suite n=30:

| Step | Change | Overall WR |
|------|--------|------------|
| Baseline (R7b) | — | **64.7%** |
| **R8a** | `_mandatory_promote_score` — TO_ACTIVE after active KO | **70.7%** |
| **R8b** | `_empty_bench_block_tempo` — no attach/items before bench basic | **75.3%** |

Champion ref **54083197** @ **1196.1 μ** — lock Final until probe **54088877** beats latest on ≥2 readings.

### THE SINGLE NEXT ACTION

**See R8 submitted block above.**

---

## As of 2026-06-26 (Session 52 — ladder μ refresh)

**Source:** Kaggle Submissions UI + `python scripts/track_ladder.py` (2026-06-26 evening).

| Ref | Package | Status | **Public μ (latest)** | μ trajectory |
|-----|---------|--------|----------------------:|--------------|
| **54083197** | `archaludon_ex_cinderace_r7_bench.tar.gz` | COMPLETE | **1196.1** | 600 → 731.3 → **1224.2** (peak) → **1196.1** |
| **54083513** | `starmie_froslass_ashleysandlin.tar.gz` | COMPLETE | **277.5** | 300.3 → **277.5** |

**Archaludon still #1** (+315 μ vs Dragapult 880.9). TrueSkill μ drifts with matchmaking — peak was 1224.2; **lock ref 54083197 as Final** unless a new probe beats latest on ≥2 readings.

### THE SINGLE NEXT ACTION

**Continue Archaludon refinement in `agent/archaludon_agent.py`** — TO_ACTIVE promotion after active KO (82068759); re-gate after changes. No re-upload of 54083197 without material delta (R12).

---

## As of 2026-06-26 (Session 52 — Archaludon primary track)

### Strategic shift

**All iteration → Archaludon** (`archaludon_rules` × `archaludon_ex_cinderace`, ref **54083197**, **1196.1 μ** latest / **1224.2 μ** peak).  
SearchScorer, Alakazam upload, Starmie, Dragapult re-probe: **paused**.

| Field | Value |
|-------|-------|
| **Champion ref** | **54083197** — lock Final; do not re-upload same tarball (R12) |
| **Public μ** | **1196.1** (peak **1224.2**) |
| **Local gate** | 67.3% full n=30 post R7b (filter only) |
| **Ladder WR** | **76.2%** n=42 public |
| **Loss priorities** | 2× `no_active`, 2× Dragapult prize, 2× Alakazam prize, 1× deck_out |

Plan: [`eval/archaludon_iteration.md`](eval/archaludon_iteration.md) · traces: [`eval/archaludon_no_active_trace.md`](eval/archaludon_no_active_trace.md)

### THE SINGLE NEXT ACTION

**See μ refresh block above.**

---

## As of 2026-06-26 (Session 51 — Archaludon ladder truth)

### Ladder bar moved

| Field | Value |
|-------|-------|
| **Ref** | **54083197** |
| **Package** | `archaludon.tar.gz` (Kaggle name: `archaludon_ex_cinderace_r7_bench.tar.gz`) |
| **Brain × deck** | `archaludon_rules` × `archaludon_ex_cinderace.csv` |
| **Local gate** | **67.3%** full n=30 post R7b bench fix (was 72.7%) |
| **μ trajectory** | 600.0 → 731.3 → **1224.2** (peak) → **1196.1** (latest) |
| **Prior bar** | Dragapult **880.9 μ** (53989933) — superseded |

**Verdict:** Community v5 + R7 empty-bench guard only. **Still #1 on ladder.** Peak 1224.2; μ drift normal. Local gate **underpredicted** ladder.

### THE SINGLE NEXT ACTION

**See Session 52 block above** — Archaludon refinement is the only active track.

---

## As of 2026-06-26 (Session 51 — Starmie upload)

### Submitted

| Field | Value |
|-------|-------|
| **Ref** | **54083513** |
| **Package** | `starmie_froslass_ashleysandlin.tar.gz` |
| **Brain × deck** | `starmie_rules` × `starmie_froslass_ashleysandlin.csv` |
| **Local gate** | Mirror **56.7%** n=30; full suite **9.3%** (filter only) |
| **Public μ** | **277.5** (was 300.3) |
| **R12** | New catalog row — exit 0 |

**Verdict:** COMPLETE; low μ — track paused. Not a Final candidate.

---

## As of 2026-06-26 (Session 51 — execute batch)

### Delivered this run

| Item | Result |
|------|--------|
| **Starmie / Froslass field opponent** | `agent/starmie_agent.py`, deck, `PrizeTracker`, `scripts/gate_starmie.py`; mirror **56.7%** n=30 (`eval/gate_starmie_session51.md`) |
| **SearchScorer stability fix** | Refresh `Battle.battle_ptr` each search (was crashing full-suite gate); re-gate **26.7%** n=30 (`eval/gate_search.md`) |
| **PrizeTracker → SearchScorer** | Deck-search contexts penalize inferred prized cards |
| **Archaludon ladder** | Ref **54083197** **COMPLETE** μ=**600.0** (first reading — wait ≥40 min for 2nd) |
| **verify_official_opponents** | 12 decks OK including `starmie_froslass_ashleysandlin` |

### THE SINGLE NEXT ACTION

**Track Starmie ref 54083513** + **Archaludon ref 54083197** (2nd reading **731.3 μ**) — `python scripts/track_ladder.py` after ≥40 min.

---

## As of 2026-06-26 (Session 51 — Archaludon ladder probe)

### Ladder probe submitted

| Field | Value |
|-------|-------|
| **Ref** | **54083197** |
| **Package** | `archaludon.tar.gz` |
| **Brain × deck** | `archaludon_rules` × `archaludon_ex_cinderace.csv` |
| **Delta** | Community v5 + R7 empty-bench guard only |
| **Local gate** | **72.7%** full suite n=30 (`eval/gate_archaludon.md`) |
| **Status** | **COMPLETE** μ=**600.0** (2026-06-26 16:19 UTC) — await 2nd reading |

**Next:** `python scripts/track_ladder.py` ≥40 min after first COMPLETE before treating 600 as stable.

---

## As of 2026-06-26 (Session 51 — Alakazam iteration)

### Measured

| Item | Result |
|------|--------|
| Alakazam bench guard A/B @ n=50 | Guard **regresses** (53.6% vs 56.8%) → **default OFF** |
| Dragapult levers on Alakazam | **58.7%** @ n=30 → **reverted** (hurt Lucario/Iono) |
| Latest gate (notebook deck, n=30) | **54.0%** (variance; S50 **62.0%** still reference) |
| Dragapult stack | Unchanged — full guard + Crispin rules; **880.9 μ** hold |

Full write-up: `eval/alakazam_iteration_session51.md`

### THE SINGLE NEXT ACTION

**Replay analysis** — Alakazam losses vs `dragapult_ex_sample` (stable ~33–37% weakness). No Kaggle upload until **two** n=30 gates ≥62% or paired n=50 beat baseline.

---

### Ladder truth

| Rank | Brain × deck | μ | Ref |
|-----:|--------------|----:|-----|
| 1 | archaludon_rules + R7 × `archaludon_ex_cinderace` | **1224.2** | 54083197 |
| 2 | dragapult_crispin + R7 × `dragapult_ex_sample` | **880.9** | 53989933 |
| 3 | SearchScorer × `real_mega_lucario_ex` | **660.5** | 53869254 |
| 4 | imported Alakazam best5 | **659.0** | 53913404 |
| 5 | basic MCTS model4 × Lucario | **651.3** | 53946742 |

**Bar:** **1224.2 μ**. **R12:** no duplicate uploads — iterate or don't upload.

### Session 50 delivered

| Item | Status |
|------|--------|
| B1 Alakazam port | `agent/alakazam_agent.py`, package, gate **62.0%** @ n=30 |
| R12 + `check_upload_eligible.py` | Blocks ports, weak local gates (<55%), duplicates |
| Native Alakazam opponents | `top_mined_alakazam` + `ryotasueyoshi_alakazam_best5` in official registry |
| LucarioScorer gate @ n=30 | **39.3%** — **do not upload** (`eval/lucario_scorer_baseline_session50.md`) |
| Duplicate Alakazam upload | Wasted slot — lesson in R12 |

### Session 50 measurements (native field full suite n=30)

| Brain | Deck | Overall WR | Report |
|-------|------|------------|--------|
| SearchScorer | `real_mega_lucario_ex` | **27.3%** | `eval/gate_search.md` |
| LucarioScorer | same | **39.3%** | `eval/lucario_scorer_baseline_session50.md` |
| Alakazam best5 | notebook deck | **62.0%** | `eval/alakazam_best5_baseline_session49.md` |

Note: ladder **660.5 μ** used different gate opponents than today's native full suite — local % is filter only.

### THE SINGLE NEXT ACTION

**Iterate SearchScorer toward 660.5+ μ** (home-grown bar) — one targeted fix, local gate, then `check_upload_eligible`:

```powershell
python scripts/gate_search.py --games 30 --suite full --report
# after a concrete fix:
python scripts/check_upload_eligible.py --brain SearchScorer `
  --deck agent_decks/real_mega_lucario_ex.csv `
  --change "SearchScorer: <delta>" --local-gate <WR>
```

**Parallel offline:** Alakazam levers (beat **62%** local before upload vs **659 μ**).

**Do not upload:** LucarioScorer @ 39.3%, Alakazam re-port, Dragapult without material change.

---

## Recent sessions

| Session | Result |
|---------|--------|
| **50** | B1 port; R12; upload gate; LucarioScorer 39.3%; duplicate upload lesson |
| **49** | Agent catalog; pilot×deck 10% collapse; epistemic reset |
