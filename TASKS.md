# TASKS — build-order backlog

Work top to bottom. Each step ends with **something measurable**; nothing speculative ships
(Ruling R3). Check `[x]` when done and log it in `STATE.md`. The full rationale for this order is
`ARCHITECTURE.md` § Build order. The old 43-session backlog is in `graveyard/pre-reset-20260622`.

---

## Foundation (must come first — every pillar depends on it)

- [ ] **F1. `core/` model + prove the foundation.**
  - [ ] `core/cards.py` — typed registry from `data/EN_Card_Data.csv`.
  - [ ] `core/engine.py` — wrapper over local `cg` engine (`data/sim/sample_submission/cg/`).
  - [ ] `core/obs.py` + `tests/test_information_model.py` — **empirically verify** opponent hand =
        count only, deck = count only, prizes face-down (RULINGS Part 4). *Needs Python ≥3.11.*
  - [ ] `core/rules_notes.md` — consolidated verified rules digest.
- [ ] **F2. `eval/` harness + `field/` registry.**
  - [ ] Move `agent_decks/{real_*,top_mined_*}` → `field/decks/`; build `field/registry.json`.
  - [ ] `eval/harness.py` (seeded, side-swapped, Wilson CI) + `eval/gates.py` (L0–L3, real-field only).
  - [ ] **Re-measure the current spine on the real field** — establish the true ~668 floor with metadata.
- [ ] **F3. Migrate + freeze the spine.** Move `agent/` → `agents/`, fix imports + packager, and
      **confirm the smoke test passes** (Python ≥3.11) so we reproduce ~633–668. This is the
      shippable baseline. *(Until F3, the spine stays in `agent/` — Ruling R7.)*

## Episode data → meta (the golden ticket; runs on user's machine)

- [ ] **D1. `episodes/pull.py`** (from `scripts/update_from_kaggle.py`): leaderboard, our
      submissions, new replays. **User runs this — sandbox has no Kaggle egress.**
- [ ] **D2. `episodes/parse.py` + `store/`** — replays → per-game records (one schema).
- [ ] **D3. `meta/build_map.py` + `whatbeatswhat.py`** — archetype × archetype win matrix, field
      shares, expected-WR-vs-mixture ranking. First dated `meta/reports/meta_YYYYMMDD.md`.

## Decision policy (Pillar 3 — the ceiling; each stage gated vs the spine)

- [ ] **P1. Pilot spine** consolidated/clean in `agents/` (the floor). *(= F3.)*
- [ ] **P2. Bounded our-side lookahead** via engine `search_*` under a strong `board_value`.
- [ ] **P3. Determinized opponent search (PIMC)** — sample K opponent hands/decks consistent with
      public info + meta prior; average the lookahead.
- [ ] **P4. ISMCTS** — only if PIMC's known weaknesses cost measurable μ.
- [ ] **P5. Learned belief/opponent prior** from `episodes/store` (the only ML role Ruling R3
      currently endorses, because search gates it).

## Deck discovery (Pillar 4 — after the pilot floor ships)

- [ ] **K1. Objective + scoping** — maximize `E[win vs field mixture]` for a fixed pilot, within a
      type-coherent shell. Best-arm identification (successive halving / SPRT), not blind GA.

## Orchestration (Pillar 5)

- [ ] **O1. Daily loop**: pull → parse → meta → refresh field/prior → re-gate champion + contenders
      → surface the single best next submission. `/schedule` once trusted.

---

## Done log
_(move completed top-level steps here with a date)_
- 2026-06-22 (S44): repo reset — RULINGS/ARCHITECTURE/STATE written, 532→~100 files, spine preserved.
