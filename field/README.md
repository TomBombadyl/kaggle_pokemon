# field/ — the real-field opponent registry (Foundation 0.2)

The opponents we are **allowed** to evaluate against (Ruling R2). No `pool_*` proxies, no random,
no mirror-only training or gating. See `ARCHITECTURE.md` § Pillar 0.2.

## Current location (pre-migration)

Until TASKS F2 migrates decks, the **canonical real-field lists** live in `../agent_decks/`:

| Prefix | Examples |
|--------|----------|
| `real_*` | `real_mega_lucario_ex`, `real_dragapult_ex`, `real_mega_abomasnow_ex`, `real_iono` |
| `top_mined_*` | `top_mined_alakazam`, `top_mined_trevenant`, `top_mined_dragapult_ex`, … |

**Lucario field trainer** (`scripts/train_lucario_field_mcts.py`) uses all 10 of these by default.

**Public agents** (imported notebooks): `python scripts/extract_public_agents.py` →
`../data/kaggle_ref/opponents/`. Consumed by `scripts/gate_vs_public.py`.

## Planned contents (after F2)
- `decks/` — migrated CSVs from `agent_decks/{real_*,top_mined_*}`.
- `agents/` — imported public agent tarballs/notebooks.
- `registry.json` — deck ↔ archetype ↔ source episode ↔ public-agent binding.

Refreshed daily by `meta/` from `episodes/`. Consumed by `eval/`, `meta/`, `discovery/`, and
Pillar-3 belief priors.
