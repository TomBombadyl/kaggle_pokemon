# Simulator Resource Notes

Date: 2026-06-22 (updated: setup forced-bench, draw labels, local field RL)

**Authority:** In this competition, **simulator behavior is correct behavior.** If official
Pokémon TCG rules disagree, follow the simulator and the legal option mask from `cg`.

Source inputs:

- Organizer announcement: differences between official Pokémon TCG rules and simulator (user paste 2026-06-20).
- Kaggle dataset page + daily episodes index:
  https://www.kaggle.com/datasets/kaggle/pokemon-tcg-ai-battle-episodes-index
- Kaggle CLI simulation tutorial:
  https://github.com/Kaggle/kaggle-cli/blob/main/docs/simulation_competitions.md
- Local card metadata: `data/EN_Card_Data.csv`, `data/JP Card Data.csv`
- PDF references: `Card_ID_List_EN.pdf`, `Card_ID_List_JP.pdf` (when downloaded)

These notes are operational guidance for this repo.

## Simulator Behavior To Model

### Attack selectability differs from official rules

Some attacks that could be declared under official Pokemon TCG rules may not be
selectable in the simulator if part of the effect cannot resolve.

Examples from the user-provided organizer note:

- attack puts a Basic Pokemon from deck onto Bench, but Bench is full
- attack draws cards, but the player's deck has 0 cards
- attack interacts with opponent hand, but opponent has 0 cards in hand

Implication for agents and RL:

- Do not infer legal attacks only from card text and energy cost.
- Always train/evaluate from the simulator-provided legal option mask.
- In feature engineering, include "attack unavailable despite apparent cost met"
  as a normal simulator state, not a bug.

### Mega Zygarde ex - Nullifying Zero

The official rules allow the attacking player to choose target-order assignment.
The simulator flips coins automatically from left to right and does not expose a
target-order choice.

Implication:

- Do not build strategy logic that assumes controllable target order for
  Nullifying Zero.
- If Mega Zygarde ex becomes a candidate archetype, validate expected behavior in
  `cg.game` before adding hand-coded target heuristics.

### Simultaneous knockouts and prize order

When both players' Pokemon are knocked out at the same time, the simulator takes
Prize cards sequentially:

1. next-turn player chooses Prize cards
2. next-turn player takes Prize cards
3. opponent chooses Prize cards
4. opponent takes Prize cards
5. next-turn player promotes Active first

The organizer note says simultaneous all-prize cases are treated as draws in
this competition.

Implication:

- Gate reports should keep draw counts explicit.
- Tactical logic should not rely on official simultaneous Prize semantics.
- RL reward shaping should treat simulator result as authoritative, especially
  in spread/self-damage archetypes where simultaneous KOs are more likely.
- **Training:** terminal value **0.0 for draws** (`result == 2`); do not backprop
  win/loss labels on simultaneous final-prize draws.

### Setup phase forced benching

During initial setup, the simulator may **require** placing additional Basic
Pokémon on the bench when they are in the opening hand (`minCount` on setup
selects). There is no manual "skip benching" toggle.

Implication:

- Do not assume the agent can hoard setup Basics for later turns.
- `agent/lucario_policy.py` scores `SETUP_BENCH_POKEMON` via `setup_bench_target_count`.
- RL self-play only sees **legal** setup options from the mask — no special case needed.

### Inference time budget (10 minutes per player)

Kaggle forfeits on cumulative decision-time overrun. Keep `SEARCH_COUNT` modest
at inference (default 12 via `LUC_SUBMIT_SEARCH_COUNT`). Training uses the same
count; bottleneck is simulator rollouts, not GPU.

## Episode Replay Dataset And BC/RL/IL Use

The episodes-index dataset and Kaggle CLI replay/log commands are useful for
building behavior cloning, imitation learning, scouting, and live-meta benchmark
updates.

High-value uses:

- Mine top-rated episode replays to identify archetypes, card packages, and
  matchup patterns that beat our protected Kyogre/Search pair.
- Extract first-person trajectories for behavior cloning:
  observation summary, legal options, selected option, terminal result, and
  turn/prize/tempo features.
- Build holdout benchmark decks from repeated top-ladder archetypes.
- Compare our agent logs against stronger agents for no-active, missed
  attachment, late first-attack, and deck-out failures.

Workflow from Kaggle CLI documentation:

```bash
kaggle competitions submissions pokemon-tcg-ai-battle
kaggle competitions episodes <submission_id> -v
kaggle competitions replay <episode_id> -p report/replays
kaggle competitions logs <episode_id> <agent_index> -p report/agent_logs
```

For top-team scouting, use leaderboard/team-submission routes when available:

```bash
kaggle competitions leaderboard pokemon-tcg-ai-battle -s
kaggle competitions team-submissions <team_id>
kaggle competitions episodes <top_submission_id>
```

Do not submit or download private/irreversible resources without user approval.
Read-only public replay/log mining is acceptable when credentials and access are
available.

## Card Metadata Use

Files provided by the competition dataset:

| File | Purpose |
|------|---------|
| `EN Card Data.csv` / `JP Card Data.csv` | Structured card metadata (same schema; language differs) |
| `Card_ID_List_EN.pdf` / `Card_ID_List_JP.pdf` | ID, name, expansion, collection #, card image |

**CSV columns:** Card ID, Card Name, Expansion, Collection No., Stage/Type, Rule, Category,
Previous stage, HP, Type, Weakness, Resistance, Retreat, Move Name, Cost, Damage,
Effect Explanation.

`data/EN_Card_Data.csv` is the local source for registry generation. It contains:

- card id, name, expansion, collection number
- stage/type/category/rule/previous stage
- HP, type, weakness, resistance, retreat
- move name, cost, damage, effect text

Use this for:

- role inference in `scripts/build_card_registry.py`
- evolution-chain validation
- energy-cost compatibility checks
- attack feature extraction
- archetype templates and seed notes

Do not parse official card text as the final legality source. The simulator's
legal option mask remains authoritative.

## Episode replays (competition dataset)

From the Submissions tab or CLI (see [`KAGGLE_SIMULATION_CLI.md`](KAGGLE_SIMULATION_CLI.md)):

- Download **your** episode replays per submission ref.
- Download **other teams'** replays from the Leaderboard (when available).
- **Daily top episodes export** — new datasets added to the episodes index (forum announcement); use for BC/RL/IL and meta mining.

Related local scripts: `scripts/fetch_agent_logs.py`, `scripts/mine_episode_decks.py`, `scripts/mine_episode_replays.py`.
