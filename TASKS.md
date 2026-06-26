# TASKS — build-order backlog

Work top to bottom. Check `[x]` when done; log in `STATE.md`.  
**Agent inventory:** [`eval/AGENT_CATALOG_FULL.md`](eval/AGENT_CATALOG_FULL.md) — check before any train/upload.

---

## NOW — Session 52 (Archaludon primary)

- [ ] **Archaludon P0 — no_active fix** — trace 82055480 + 82068759; extend R7 guard; 0 no_active @ n=30 (`eval/archaludon_iteration.md`).
- [ ] **Archaludon P1 — ladder loss decks** — mine unknown opponent signatures from replays; add to field if recurring.
- [ ] **Archaludon P2 — Iono harness** — 43.3% local; lever only if full-suite ≥5pp (`gate_archaludon.py`).
- [ ] **Archaludon ladder probe** — upload only after P0 gate + material delta vs 54083197 (R12).
- [ ] **Strategy report outline** — Archaludon story for Sep 2026 comp.

## PAUSED (do not spend upload slots)

- [ ] ~~SearchScorer iteration~~ — paused (26.7% local; 660.5 μ bar irrelevant vs 1224 μ).
- [ ] ~~Alakazam upload~~ — paused (54% local; 659 μ row exists).
- [ ] ~~Meta replay expansion~~ — use Archaludon replay set first.

## DONE — Session 49–51

- [x] **Agent catalog** — `eval/AGENT_CATALOG_FULL.md` (21 submissions decoded).
- [x] **Ladder log sync** — `eval/ladder_log.csv` from full Kaggle history (was 6 rows).
- [x] **Pilot×deck test** — dragapult brain on Lucario list 10% @ n=30 (`eval/pilot_deck_matrix_session49.md`).
- [x] **Docs reset** — STATE, ROADMAP, SESSION, RESEARCH brief, AGENTS, eval/README.
- [x] **Alakazam best5 port** — `agent/alakazam_agent.py` + package dry-run + gate n=30 (`eval/alakazam_best5_baseline_session49.md`).
- [x] **LucarioScorer gate @ n≥30** — **39.3%** full suite; do not upload (`eval/lucario_scorer_baseline_session50.md`).
- [x] **R12 upload gate** — `scripts/check_upload_eligible.py` + `data/EVAL_PROTOCOL.md` §9.
- [x] **Archaludon port + ladder** — **1196.1 μ** latest (peak 1224.2) ref 54083197; replays in `report/submission_replays/archaludon/`.
- [x] **Starmie upload** — ref 54083513 COMPLETE **277.5 μ** (paused).
- [x] **Starmie / Froslass field opponent** — ashleysandlin deck + `starmie_agent` pilot; suite `starmie`; `eval/gate_starmie_session51.md`.
- [ ] **Meta replay expansion** — `analyze_meta_by_mu_band.py --download-per-band 50`.
- [ ] **Strategy report outline** — from catalog + RULINGS (Sep 2026).

---

## Ruled out — do not reopen without new evidence

- [x] Lucario field MCTS v5 more cycles (580.6 < 651.3 model4 < 660.5 Search).
- [x] Dragapult boss_order levers (S48).
- [x] Abomasnow R2 levers (S45).
- [x] Alakazam levers vs random pilot (S46 inconclusive only).

---

## Pilot rules (R11: rules → levers → mixture)

### R1 — Global rules (phase 1)

- [x] Dragapult v3 — **880.9 μ** (53989933).
- [x] SearchScorer × Lucario — **660.5 μ** ladder (53869254).
- [x] Pilot×deck measured (S49).
- [x] Port Alakazam best5 rules into repo agent.
- [x] LucarioScorer gate @ n≥30 — **39.3%** local; upload blocked (weak vs Search 660.5).
- [ ] Beat **880.9 μ** before calling any upload “progress”.

### R2 — Matchup levers (phase 2)

- [x] Levers wired in `lucario_policy.py`; Dragapult Phase 2b sweep **ruled out**.
- [ ] Alakazam levers — gate vs **native** best5 pilot (not random).
- [ ] Trevenant levers — after real pilot exists.

### R3 — Field mixture (phase 3)

- [x] R3 lite: `field/weights.json` + `--weighted` (filter only).
- [ ] Rebuild weights **after** replay sample ≥200 parsed games.
- [ ] Weighted RL sampling — **deferred indefinitely**.

**Deferred / retired:** Lucario field RL v6+; Track B LearnedScorer; `pool_*` gates.

---

## Foundation

- [ ] **F1.** `core/` + `tests/test_information_model.py` (Py≥3.11).
- [x] **F2.** `eval/harness.py`, `eval/gates.py`, `field/registry.json`.
- [ ] **F3.** `agent/` → `agents/` after smoke (R7).

## Episodes & meta

- [x] **D2 partial.** `analyze_meta_by_mu_band.py`
- [ ] **D1–D3.** Expand replay pull → `meta/build_map.py`

## Decision policy (after rules floor)

- [ ] **P2–P5.** Lookahead → PIMC → ISMCTS — **only if rules < 900 μ after ported pilots**

---

## Done log

- 2026-06-26 (S49): Agent catalog; ladder_log 21 rows; pilot×deck; doc reset.
- 2026-06-26 (S48): Weighted gates; Dragapult boss levers ruled out.
- 2026-06-26 (S47): μ-band manifest meta.
- 2026-06-26 (S46): F2 harness; Lucario 44% local n=20.
- 2026-06-24: Lucario v5 final 580.6 μ — **do not extend**.
