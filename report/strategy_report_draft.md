# PTCG AI Battle Challenge Strategy Report Draft

Date: 2026-06-19

## Summary

This submission uses a deterministic rule-based agent piloting a simple Water
Mega Abomasnow deck. The current priority is stability first: the agent always
returns legal selections, develops board state before attacking, and uses
deck-specific card scoring for the most common optional card-choice contexts.

Local self-play is used as a sanity benchmark, not as a ladder ranking claim.
The current kept local result is **88.7% over 300 games** against a legal random
policy using the same mirror deck with sides swapped.

## Verified Interface

The agent implements the cabt contract:

```python
def agent(obs_dict: dict) -> list[int]
```

During deck selection, when `obs_dict["select"] is None`, the agent returns a
60-card ID list from `agent/deck.csv`. During game decisions, it returns indices
into `obs_dict["select"]["option"]`, respecting `minCount` and `maxCount`.

The implementation is wrapped with a legal fallback so malformed or unexpected
selections do not crash the agent.

## Deck Concept

The current deck is the Water Mega Abomasnow list copied from the simulator
sample deck:

- 35 Basic Water Energy
- 4 Snover
- 4 Mega Abomasnow ex
- 2 Kyogre
- 4 Mega Signal
- 4 Lillie's Determination
- 4 Waitress
- 2 Cyrano
- 1 Maximum Belt

The list is intentionally linear. A simple rule-based pilot can execute the
plan reliably: bench Basic Pokemon, attach Water Energy, evolve Snover into
Mega Abomasnow ex, use draw/search supporters, and attack after setup actions
are exhausted.

## Agent Logic

The agent branches first by `select.type` and then by selected high-impact
contexts.

Main-action priority:

1. Evolve
2. Play a card
3. Attach Energy
4. Use Ability
5. Attack
6. Retreat
7. End turn

This replaced the original attack-first baseline, which measured only 7.5%
against random because it attacked before setting up.

Card-choice strategy:

- Setup bench choices fill available legal slots instead of declining optional
  Basics.
- Optional `TO_HAND` choices take visible useful cards instead of returning an
  empty selection.
- Optional `ATTACH_TO` choices take visible Energy when available.
- Visible cards are scored by the current deck roles: Mega Abomasnow ex and
  Snover are top setup pieces; Kyogre is the backup attacker; Mega Signal and
  supporters are consistency pieces; Water Energy is valuable when attachment
  is still available but lower priority otherwise.
- Required discard/deck-bottom choices prefer lower-scored cards first, which
  tends to shed excess Energy before core Pokemon/search pieces.

Count and yes/no strategy:

- Draw-count prompts choose the largest available count.
- The agent prefers going second for this simple attacking deck.
- Mulligan redraws and useful activation prompts prefer yes.

## Stability

The agent is deterministic where it controls randomness. It uses a seeded RNG
object but currently makes deterministic rule choices.

Smoke tests cover the important legal-contract cases:

- main priority behavior,
- forced and optional yes/no,
- multi-select bounds,
- optional setup bench,
- optional `TO_HAND`,
- optional `ATTACH_TO`,
- draw count,
- attack selection,
- empty/malformed option handling,
- deck-selection mode.

Latest smoke test result: 14/14 pass.

## Local Metrics

All measurements use `scripts/selfplay.py`, the downloaded cabt engine, the same
60-card mirror deck for both players, and side swapping to reduce first-player
bias.

| Agent version | Matchup | Games | Win-rate |
|---|---|---:|---:|
| v0 attack-first | heuristic vs random | 160 | 7.5% |
| v1 setup-aware | heuristic vs random | 200 | 78.0% |
| v2 card-context scorer | heuristic vs random | 300 | 86.3% |
| v2 card-context scorer | heuristic vs random | 300 | 88.7% |

The latest v2 benchmark run had random-vs-random at 47.3%, close enough for a
sanity check but still noisy. These local numbers are useful as regression tests,
not as claims about ladder strength.

## Known Limitations

- The local random baseline is not the real Kaggle ladder.
- The deck is probably too energy-heavy for a mature agent, but the density is
  useful while stabilizing attachment and evolution behavior.
- The first attack-damage estimator was tested and reverted because it measured
  worse than v1. Future attack scoring should be grounded in actual board state
  and should be kept only if it clears the current 86.3% local best.
- The current agent does not use search/rollout APIs yet.

## Next Improvements

1. Add a stronger benchmark opponent than random, such as frozen v1/v2 agents
   and simple deck variants.
2. Revisit attack scoring with state-aware KO/prize trade logic, not just static
   attack damage.
3. Start reducing excess Energy only after a stronger card-selection policy can
   still attach reliably.
4. Build the first five Simulation submission candidates as intentionally
   different agents/decks, with no real upload until user confirmation.
5. Explore narrow search and offline imitation/RL only after telemetry and local
   match matrices exist.
