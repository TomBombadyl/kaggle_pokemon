# discovery/ — scoped deck search (Pillar 4)

Find decks that beat the **current field mixture**, scoped intelligently — replacing the blind,
collapse-prone GA that never beat hand-built decks (RULINGS R3/R4). Build this **after** the
Pillar-3 pilot floor ships, so we optimize the deck for a fixed strong pilot. See `ARCHITECTURE.md`
§ Pillar 4.

## Approach (math-grounded, not "try random combos")
- **Objective:** maximize `E[win vs field mixture]` (from `meta/`) for a fixed strong pilot.
- **Scoping:** search within a legal, type-coherent shell (one energy type / a defined archetype
  skeleton) so the space is tractable and every candidate is pilotable. Colorless/toolbox shells
  get a wider budget.
- **Method:** best-arm identification under noisy eval — successive halving / Hyperband, Wilson/SPRT
  to spend simulation budget on contenders; local card-swap search around elites.
- **Guardrail:** every survivor is validated by `eval/` against the real field before a ladder slot.

No code yet. Do not resurrect `rl/deck_*` or `robust_*` from the graveyard without a reason that
addresses why blind GA collapsed (RULINGS 2C).
