# eval/ — the one evaluation harness (Foundation 0.4)

The single way we measure anything (Rulings R1, R2, R8). If a number didn't come through here
against the `field/` registry, it doesn't count. See `ARCHITECTURE.md` § Pillar 0.4.

## Planned modules
- `harness.py` — run brain×deck vs the `field/` registry, seeded, side-swapped; emit a result row
  with full metadata (games, opponents, seeds, deck, brain, Wilson CI).
- `gates.py` — the real-field-only gate pyramid:
  - **L0** legality/smoke (never crash; always legal; bench guard).
  - **L1** vs real-field decks + public agents, N≈30/opp, Wilson CI.
  - **L2** SPRT vs the current shipped champion (does it beat the floor?).
  - **L3** ladder probe — **≥2 μ readings ≥40 min apart** (Ruling R1).
- `ladder_log.csv` — one append-only log (absorbs `../report/{ladder_history,submission_log}.csv`).

## Seeds already present
- `../scripts/{arena,gate_vs_public,stats_utils,track_ladder,verify_archive,smoke_test,validate_deck}.py`
  — consolidate the useful logic here.

**Definition of "validated":** passed L0–L2 on the real field, then L3 with two stable μ readings.
Nothing ships otherwise.
