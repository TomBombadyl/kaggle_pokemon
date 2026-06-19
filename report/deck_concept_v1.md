# Deck Concept v1: Water Mega Abomasnow

Date: 2026-06-19

## Current List

Source: `data/sim/sample_submission/deck.csv`, mirrored to `agent/deck.csv`.

| Count | Card ID | Card | Role |
|---:|---:|---|---|
| 35 | 3 | Basic Water Energy | Consistency; makes manual attachment almost always available |
| 4 | 722 | Snover | Basic setup piece for Mega Abomasnow ex |
| 4 | 723 | Mega Abomasnow ex | Main attacker; 350 HP, Water Stage 1, attacks for 200 with Frost Barrier |
| 2 | 721 | Kyogre | Basic backup attacker; 150 HP, one-energy Riptide and three-energy Swirling Waves |
| 4 | 1145 | Mega Signal | Search/deck-thinning support for the Mega line |
| 4 | 1227 | Lillie's Determination | Draw/supporter consistency |
| 4 | 1235 | Waitress | Draw/supporter consistency |
| 2 | 1205 | Cyrano | Additional supporter/search consistency |
| 1 | 1158 | Maximum Belt | Damage boost/tool slot |

## Rationale

This is a deliberately simple pilot deck. The rule-based agent needs a linear
plan more than it needs a high-complexity combo shell:

1. Put Basic Pokemon into play during setup instead of declining bench slots.
2. Attach Water Energy every turn, prioritizing the Active attacker.
3. Evolve Snover into Mega Abomasnow ex as soon as legal.
4. Use draw/search supporters to find the evolution line and continue attaching.
5. Attack after setup actions are exhausted.

The list is energy-heavy, but that is useful for early agent development because
it sharply reduces missed attachment turns. T7's self-play jump from 7.5% to
78.0% versus random came from making the agent execute this linear plan.

## Known Weaknesses

- Mega Abomasnow ex gives up extra prizes and may be vulnerable to anti-ex
  attackers.
- The current local benchmark uses mirror decks against random choices; it is a
  sanity filter, not a ladder-strength estimate.
- The list likely has too much Energy for a mature agent. Once the policy is
  stable, use card-data analysis and simulator results to replace excess Energy
  with stronger search, switching, recovery, and non-ex coverage.

## Next Deck Work

Keep this list as the baseline deck until the rule-based pilot is stable. The
next deck-design pass should compare one low-complexity alternative with:

- a non-ex attacker line for anti-ex matchups,
- enough Basic Pokemon to avoid weak setup states,
- fewer dead late-game Energy draws,
- no additional combo branch unless the agent has explicit logic for it.
