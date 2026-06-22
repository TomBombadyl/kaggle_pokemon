# episodes/ — the episode data pipeline (Foundation 0.3)

Turns the daily Kaggle dumps into structured truth — the "golden ticket" we have been wasting.
See `ARCHITECTURE.md` § Pillar 0.3. **Runs on the user's machine (Kaggle egress); the sandbox is
offline.**

## Planned modules
- `pull.py` — leaderboard snapshot + our submissions + new episode replays. Seed it from the
  existing `../scripts/update_from_kaggle.py`, then retire that script.
- `parse.py` — replay JSON → per-game records (decks, archetypes, turns, win condition, and
  per-decision (state, legal options, chosen action)). One documented schema.
- `store/` — partitioned, append-only, deduped by episode id.

## Seeds already present
- `../report/replays/` — manifest + replay JSON mined so far (move under `store/` on first run).
- `../scripts/mine_episode_{decks,replays}.py`, `episode_stats.py`, `extract_public_agents.py`,
  `extract_gauntlet_from_replays.py` — fold the useful logic into `parse.py`.

Outputs feed: `field/` registry, `meta/` map, the Pillar-3 belief prior, and offline BC data.
