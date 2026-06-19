# cabt Engine — Confirmed Interface (T1)

Source: official **cabt Engine 0.1.0** docs
(https://matsuoinstitute.github.io/cabt/ and .../api.html), read 2026-06-19.
Cross-checked against the competition overview and a community agent repo
(github.com/wmh/ptcg-abc). Items marked *(community)* are NOT from official docs
and must be reconfirmed once the engine is downloaded.

## Tracks & deadlines
- **Strategy** (this project): `pokemon-tcg-ai-battle-challenge-strategy`, ends **2026-09-14**.
- **Simulation** (sibling, the live Elo ladder): `pokemon-tcg-ai-battle`, ends **2026-08-16/17**.
- Organizers: The Pokémon Company × HEROZ × Matsuo Institute (Univ. of Tokyo).
- Per-player time limit **10 minutes**; running out = immediate loss.

## Agent contract
```python
def agent(obs_dict: dict) -> list[int]
```
- Called once per decision point. Returns **0-based indices** into
  `obs_dict["select"]["option"]`.
- Number of indices must satisfy `minCount <= len(result) <= maxCount`;
  indices distinct and in range.
- **Deck-selection phase:** when `obs_dict["select"]` is `None` (and `current`
  is `None`), return a list of **60 card IDs** instead of option indices.
- Must **never crash** — always return a legal fallback — and respect the time limit.

## Observation structure (`obs_dict`)
- `logs`: list[Log] — events since the agent's last decision.
- `current`: State | None  (None during initial deck selection).
- `select`: SelectData | None  (None during initial deck selection).

### State (`current`)
- `players`: [PlayerState, PlayerState]
- `stadium`: Card | None
- turn count, first/second player, supporter/stadium/energy-used flags,
  retreat state (`retreated`), game result.

### PlayerState
- `active`: list size 0 or 1 (the Active Pokémon; element may be None if face-down).
- `bench`: list of Benched Pokémon (max 5; `benchMax` usually 5).
- `hand`: own cards visible; opponent shows **count only** (`handCount`).
- `prize`: prize cards; face-down = None. **First element = bottom, last = top.**
- `deckCount`, `discard`.
- Status flags: `poisoned`, `burned`, `asleep`, `paralyzed`, `confused`.

### SelectData (`select`)
| field | meaning |
|---|---|
| `type` | SelectType — category of choice (see below) |
| `context` | SelectContext — *why* we are choosing (49 values) |
| `minCount` / `maxCount` | inclusive bounds on number of indices to return (min can be 0) |
| `option` | list[Option] — the choices; **index into this is the action** |
| `remainEnergyCost` | when type==ENERGY: remaining required energy |
| `remainDamageCounter` | remaining damage counters that can be placed |
| `deck` | list[Card] when choosing from deck, else None |
| `contextCard` / `effect` | card driving the current effect (e.g. ACTIVATE) |

## SelectType (`select.type`) — drives which OptionTypes appear
| id | name | option types it yields |
|---|---|---|
| 0 | MAIN | PLAY, ATTACH, EVOLVE, ABILITY, DISCARD, RETREAT, ATTACK, END |
| 1 | CARD | CARD |
| 2 | ATTACHED_CARD | TOOL_CARD, ENERGY_CARD |
| 3 | CARD_OR_ATTACHED_CARD | CARD, TOOL_CARD, ENERGY_CARD |
| 4 | ENERGY | ENERGY |
| 5 | SKILL | SKILL |
| 6 | ATTACK | ATTACK |
| 7 | EVOLVE | EVOLVE |
| 8 | COUNT | NUMBER |
| 9 | YES_NO | YES, NO |
| 10 | SPECIAL_CONDITION | SPECIAL_CONDITION |

## OptionType (`select.option[i].type`) — entity each option refers to
| id | name | key fields |
|---|---|---|
| 0 | NUMBER | number |
| 1 | YES | — |
| 2 | NO | — |
| 3 | CARD | area, index, playerIndex |
| 4 | TOOL_CARD | area, index, playerIndex, toolIndex |
| 5 | ENERGY_CARD | area, index, playerIndex, energyIndex |
| 6 | ENERGY | area, index, playerIndex, energyIndex, count |
| 7 | PLAY | index (in hand) |
| 8 | ATTACH | area, index, inPlayArea, inPlayIndex |
| 9 | EVOLVE | area, index, inPlayArea, inPlayIndex |
| 10 | ABILITY | area, index |
| 11 | DISCARD | area, index |
| 12 | RETREAT | — |
| 13 | ATTACK | attackId |
| 14 | END | — (end turn) |
| 15 | SKILL | cardId, serial |
| 16 | SPECIAL_CONDITION | specialConditionType |

## AreaType (1=DECK, 2=HAND, 3=DISCARD, 4=ACTIVE, 5=BENCH, 6=PRIZE,
7=STADIUM, 8=ENERGY, 9=TOOL, 10=PRE_EVOLUTION, 11=PLAYER, 12=LOOKING)

## SelectContext (49 values) — the *purpose* of a selection
Examples: MAIN(0), SETUP_ACTIVE_POKEMON(1), SETUP_BENCH_POKEMON(2), SWITCH,
TO_ACTIVE, TO_BENCH, DISCARD, TO_DECK_BOTTOM, ATTACH_FROM/TO, DETACH_FROM,
DISCARD_ENERGY(30), ATTACK(35), EVOLVE(37), DRAW_COUNT(38), IS_FIRST(41,
yes/no), MULLIGAN(42, yes/no), ACTIVATE(43, yes/no), COIN_HEAD(46),
AFFECT/RECOVER_SPECIAL_CONDITION(47/48). (Full list in api.html.)

## Engine / Game API
- `battle_start(deck0, deck1) -> (Observation|None, StartData)`
- `battle_select(select_list) -> Observation`     # advance one step
- `battle_finish()` ; `visualize_data()` (debug string)
- Card data: `all_card_data()` (name, HP, energy...), `all_attack()`
  (damage, energy cost, text). **~2,000 cards** in Standard format.
- Search (lookahead): `search_begin(...)`, `search_step(search_id, select)`,
  `search_end()`, `search_release(search_id)` -> returns SearchState/ApiResult.

## kaggle-environments harness
```python
from kaggle_environments import make
env = make("cabt", configuration={"decks": [deck, deck]})
env.run([agent, agent])
open("result.html","w").write(env.render(mode="html"))
```
- Ladder uses **`kaggle-environments==1.30.1`** (requires **Python >= 3.11**).
- The `cabt` environment + `cg/` engine ship from the **Kaggle competition page**,
  not PyPI.

## deck.csv
60 card IDs, one per line (IDs from `all_card_data()`). Example:
```
278
278
...
7
```

## Submission *(community-sourced, reconfirm on official Data/Rules tab)*
- `submission.tar.gz` = `main.py` + `deck.csv` + engine `cg/`.
- 5 submissions/day; latest 2 are scored on the ladder.
