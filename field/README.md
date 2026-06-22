# field/ — the real-field opponent registry (Foundation 0.2)

The opponents we are **allowed** to evaluate against (Ruling R2). No `pool_*` proxies, no random,
no mirror-only. See `ARCHITECTURE.md` § Pillar 0.2.

## Planned contents
- `decks/` — mined real-meta lists. **Migrate here** from `../agent_decks/{real_*,top_mined_*}.csv`
  once `eval/` reads from this path (build-order step 2). Validated by `core`/`eval`.
- `agents/` — imported public agents (e.g. the Alakazam best5 notebook) used as gate opponents.
- `registry.json` — single index: deck ↔ archetype ↔ source episode ↔ public-agent binding.

Refreshed daily by `meta/` from `episodes/`. Consumed by `eval/`, `meta/`, `discovery/`, and the
Pillar-3 belief prior.
