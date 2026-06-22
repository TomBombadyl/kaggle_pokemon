# meta/ — daily meta tracker (Pillar 2)

Every day, know what the field plays and what beats it (the meta is rock-paper-scissors and shifts
fast — RULINGS Part 4). See `ARCHITECTURE.md` § Pillar 2.

## Planned modules
- `build_map.py` — from `../episodes/store`: cluster opponents into archetypes, compute the
  **archetype × archetype win matrix** and population shares.
- `whatbeatswhat.py` — rank our candidate decks by **expected win rate vs the field mixture**:
  `E[win] = Σ_a share(a) · winrate(ours, a)`. (Not vs a single deck.)
- `reports/meta_YYYYMMDD.md` — one dated report per day (not fifteen scattered files).

## Seeds already present
- `../scripts/{analyze_winners,analyze_strategies,analyze_submission}.py` — fold useful analysis here.

Outputs: refresh `field/registry.json`; feed `discovery/`'s objective and the Pillar-3 opponent
prior. Automatable via `/schedule` once the `episodes/pull` is trusted.
