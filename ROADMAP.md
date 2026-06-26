# The Plan — PTCG AI Battle (Session 49, 2026-06-26)

**This is the forward plan.** Backlog: `TASKS.md`. Now: `STATE.md`. Evidence: `eval/AGENT_CATALOG_FULL.md`.

**Competitions**
- **Simulation ladder** (`pokemon-tcg-ai-battle`): public **μ** is the only ship metric.
- **Strategy** (`pokemon-tcg-ai-battle-challenge-strategy`, **deadline 2026-09-14**): stability + deck concept + sim performance + written report.

---

## 0. North star

| Goal | Target | How we know |
|------|--------|-------------|
| **Simulation** | Hold / beat **1196.1 μ** latest (Archaludon ref 54083197; peak 1224.2) | Kaggle public score |
| **Interim bar** | **1196.1 μ** latest — was 880.9 Dragapult | Ladder |
| **Strategy comp** | Report + Archaludon deck/pilot story | Sep 2026 submission |

**Primary track (Session 52+):** Refine **`archaludon_rules` × `archaludon_ex_cinderace`** only. All other agents paused.

Plan: [`eval/archaludon_iteration.md`](eval/archaludon_iteration.md)

---

## 1. What we know (21 ladder submissions — do not re-litigate)

```
1196.1  archaludon_rules × archaludon_ex_cinderace   ← SHIP + REFINE (54083197; peak 1224.2)
880.9   dragapult_crispin × dragapult_ex_sample        ← superseded; Final backup
660.5   SearchScorer × real_mega_lucario_ex            ← PAUSED
659.0   imported Alakazam best5                        ← PAUSED
```

**Laws (from data, not opinion):**
1. **Ladder μ sorts agents.** Local gates, leader-suite L1, and weighted E[win] **misordered** agents (Kyogre 13%→672 μ; LucarioSearch 69.6%→500 μ).
2. **Pilot before deck.** Same dragapult brain on Lucario list → **10%** local (S49). Alakazam: imported 659 vs our Search 545.
3. **More field RL on Lucario hurt.** v5 (580.6) < model4 (651.3) < Search (660.5) on the **same deck**.
4. **Archaludon community v5 + R7 guard** peaked **1224.2 μ**, latest **1196.1 μ** — local gates underpredicted again.

Full decode: [`eval/AGENT_CATALOG_FULL.md`](eval/AGENT_CATALOG_FULL.md)

---

## 2. Operating rules (every session)

1. Read `STATE.md` → `eval/AGENT_CATALOG_FULL.md` → this file.
2. Before **train** or **upload**: name catalog row + one-sentence hypothesis.
3. **Upload gate (R12):** **New brain×deck row only** — check `eval/AGENT_CATALOG_FULL.md` first.
   No re-upload of COMPLETE rows except **final lock-in** near deadline. Then: L0 dry-run → local
   harness **n≥30** (filter) → Kaggle → **≥2 μ readings** (truth).
4. **5 uploads/day**, **2 Finals** — select manually before deadline (`data/SUBMISSION_PLAYBOOK.md`).
5. **Never:** field RL v6+, Dragapult boss levers, `pool_*` opponents, weighted E[win] as sole ship gate, swap pilots onto foreign deck lists, **duplicate ladder uploads (R12)**.

---

## 3. Phased plan

### Phase A — Protect + refine Archaludon (now)

**Objective:** Lock ref **54083197** as Final; iterate offline; upload only material improvements.

| Step | Action | Gate |
|------|--------|------|
| A1 | Lock Final | Kaggle UI — ref 54083197 |
| A2 | Replay pull | `analyze_submission.py` + `convert_submission_replays.py --name archaludon` |
| A3 | P0 fix | 0 `no_active` @ n=30 full suite |
| A4 | Ladder probe | New package name + R12 + `check_upload_eligible` |
| A5 | Monitor | `track_ladder.py` — beat **1196.1** latest on ≥2 readings before swapping Final |

**Success:** μ ≥ 1196.1 sustained OR 0 forfeit losses with stable μ.

---

### Phase B — PAUSED (Search / Alakazam / Lucario)

Was primary path to 700+ μ. **Superseded by Archaludon (1196.1 μ latest).** Reopen only if Archaludon stalls.

---

### Phase C — Data science (support decisions, not drive uploads)

**Objective:** Enough replay data to trust mixture weights and meta claims.

| Step | Action | Gate |
|------|--------|------|
| C1 | Expand replay pull | `python scripts/analyze_meta_by_mu_band.py --download-per-band 50` |
| C2 | Rebuild weights | `python scripts/build_field_weights.py` |
| C3 | Refresh meta report | `report/meta/deck_by_mu_band_*.md` |

**Use weights for:** lever prioritization research, report charts. **Do not use for:** upload ship decisions until replay n ≫ 47.

---

### Phase D — Matchup levers (R11 phase 2 — after real pilots)

**Objective:** Per-archetype bonuses only when harness proves **>5pp** with no core regression.

| Step | Action | Gate |
|------|--------|------|
| D1 | Alakazam levers | **Native best5 pilot** as opponent (S46 random pilot = inconclusive) |
| D2 | Trevenant levers | After Trevenant pilot exists |
| — | Dragapult boss levers | **Ruled out S48** |
| — | Abomasnow levers | **Ruled out S45** |

---

### Phase E — Strategy competition report (by Sep 2026)

**Objective:** Written report citing measured evidence.

| Section | Source |
|---------|--------|
| Scoreboard | `eval/AGENT_CATALOG_FULL.md` |
| What failed (RL, Track B, wrong opponents) | `RULINGS.md` Part 2 |
| Pilot×deck lesson | `eval/pilot_deck_matrix_session49.md` |
| Field meta (with caveats) | `report/meta/deck_by_mu_band_*.md` |
| Agent concept | Dragapult ship + rules uplift path |

---

## 4. What we are NOT doing

| Item | Evidence |
|------|----------|
| Lucario field RL v6+ | v5 580.6 < 651.3 < 660.5 |
| Track B LearnedScorer | All ≤585.1 |
| Dragapult boss_order levers | S48 negative/neutral |
| “Lucario deck is out” | Search 660.5 on that deck |
| Training on `pool_*` / Snorlax-only | 185.4 μ Alakazam MCTS |
| ISMCTS / belief priors | **Later** — only if rules plateau < 900 μ after Phase B |
| `agent/` spine refactor (F3) | Until Py≥3.11 smoke passes (R7) |

---

## 5. Decision tree (upload)

```mermaid
flowchart TD
  start[Want to upload?]
  catalog[Name AGENT_CATALOG row + hypothesis]
  dup{Duplicate ruled-out brain×deck?}
  stop[STOP]
  package[Dry-run package L0]
  local[Harness n>=30 filter]
  user[User confirms Kaggle submit]
  ladder[>=2 mu readings]
  pivot{Beat prior ref?}
  keep[Keep / pin Final]
  discard[Archive lesson in catalog]

  start --> catalog --> dup
  dup -->|yes| stop
  dup -->|no| package --> local --> user --> ladder --> pivot
  pivot -->|yes| keep
  pivot -->|no| discard
```

---

## 6. Calendar (rough)

| When | Milestone |
|------|-----------|
| **Jun 2026** | Session 49 reset done; Phase A pin; Phase B1 Alakazam port started |
| **Jul 2026** | Home-grown ladder probe(s); meta replay n↑; report outline |
| **Aug 2026** | Simulation deadline ~Aug; Finals selection; target 1000+ μ if Phase B breaks through |
| **Sep 2026** | Strategy comp deadline **2026-09-14**; report + 2 Finals |

---

## 7. Success metrics

| Milestone | Target | Measure |
|-----------|--------|---------|
| Hold | **≥ 880.9 μ** | 2 Kaggle readings |
| Home-grown breakthrough | **> 700 μ** | Ladder, our `agent/` |
| Mid-pack | **1000+ μ** | 2 readings |
| Strategy | Report + stable concept | Sep 2026 comp |

---

## 8. Command cheat sheet

```powershell
cd Z:\kaggle\pokemon

# Evidence
type eval\AGENT_CATALOG_FULL.md

# Phase A — ladder
python scripts/package_dragapult.py
python scripts/gate_dragapult.py --games 30 --suite full --report

# Phase B — rules
python scripts/gate_lucario_rules.py --games 30 --suite full --report
python scripts/package_submission.py --name lucario_ex_search --scorer search --deck agent_decks/real_mega_lucario_ex.csv

# Phase C — meta
python scripts/analyze_meta_by_mu_band.py --download-per-band 50
python scripts/build_field_weights.py

# After upload
python scripts/track_ladder.py
```

---

## 9. Single next action (today)

**Iterate — no duplicate uploads (R12).** B1 port is done. Next: **B3** LucarioScorer gate @ n≥30
(never properly laddered) or **B5** Search improvements — each must be a **new catalog row** before upload.

Parallel idle work: Phase C1 meta download on user machine.

**Do not:** re-upload Alakazam best5 (53913404), Dragapult without change, or Lucario v5 for μ.
