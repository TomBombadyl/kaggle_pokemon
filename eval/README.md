# eval/ — the one evaluation harness (Foundation 0.4)

The single way we measure anything (Rulings R1, R2, R8). If a number didn't come through here
against the **real field**, it doesn't count. See `ARCHITECTURE.md` § Pillar 0.4.

## Interim (live scripts — use until `eval/harness.py` lands)

| Script | Purpose |
|--------|---------|
| `scripts/gate_vs_public.py` | Spine + packaged candidates vs real decks + public agents |
| `scripts/gate_dragapult.py` | Dragapult ex vs real-field set, seat-swapped, Wilson CI |
| `scripts/arena.py` | Seeded matchups, metadata rows |
| `scripts/smoke_test.py` | L0 legality / never-crash contract |
| `scripts/smoke_cg_engine.py` | L0 engine `battle_start` smoke |
| `scripts/stats_utils.py` | Wilson CI helpers |
| `scripts/track_ladder.py` | Ladder μ sync + log fetch |
| `scripts/verify_archive.py` | Post-package tarball smoke |

Full protocol: [`data/EVAL_PROTOCOL.md`](../data/EVAL_PROTOCOL.md).

## Planned modules (TASKS F2)
- `harness.py` — brain×deck vs `field/registry.json`, seeded, side-swapped.
- `gates.py` — L0–L3 pyramid (real field only).
- `ladder_log.csv` — append-only (absorbs `report/{ladder_history,submission_log}.csv`).

**Definition of "validated":** L0–L2 on the real field, then L3 with **≥2 stable μ readings**
≥40 min apart. Nothing ships otherwise.
