# core/ — card & rules model (Foundation 0.1 + Pillar 1)

The single, verified, typed model of the game. Everything (search, eval, training) uses *this*
model so behavior is consistent. See `ARCHITECTURE.md` § Pillar 0.1 and Pillar 1.

## Planned modules
- `cards.py` — typed registry loaded from `../data/EN_Card_Data.csv` (HP, types, attacks, energy
  cost, abilities, evolution lines, ex/Mega rule-box flags). One cached loader.
- `engine.py` — thin tested wrapper over the local `cg` engine (`../data/sim/sample_submission/cg/`,
  fetch via `../scripts/fetch_sim_engine.py`). Methods: `battle_start`, `battle_select`, `search_*`.
- `obs.py` — typed parse of `obs_dict` → `Observation`, with explicit **public vs hidden** fields
  (RULINGS Part 4). 
- `rules_notes.md` — the consolidated *verified* rules digest (supersedes scattered `data/*` notes;
  those remain as source citations).

## First task (blocks the MDP pillar)
A test in `../tests/` that **empirically confirms the information model** against the live engine:
opponent `hand` exposes count only, opponent deck is `deckCount` only, prizes are face-down.
No load-bearing fact is taken from the API doc on trust again.
