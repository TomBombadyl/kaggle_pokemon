# Crustle lane — the wall matchups are a DECK-OUT race, not a prize race

role=crustle, round 2, 2026-07-31. Supersedes the Crushing-Hammer theory in
`crustle_majkel_vs_flg_diagnosis.md` as the *primary* explanation of the gap.

## Why round 1 stalled

Round 1 diagnosed the majkel deficit from a **deck diff** (majkel runs 4x
Crushing Hammer, flg runs 0) and spent three levers on that axis — `latch`,
`hammer_prior`, `rhsoft` — all NULL/REJECT. The diff was real but it was never
checked against how games actually end.

## Method

`scripts/crustle_loss_profile.py` replays the matchups with a traced copy of
`harness.run_match` that snapshots the **terminal** state (the last obs is never
handed to a brain, so no existing tool could see it) and reads the `RESULT` log's
`reason` field: 1 = prizes, 2 = start turn with 0 deck, 3 = no Active, 4 = card
effect.

5 shards x 600 games per opponent = **3000 games each**.
Raw: `recordings/metrics/crustle_loss_profile.json`.

## Result — 76-82% of all losses are our own deck-out

| opponent | n | WR | loss: deckout | loss: no_active | loss: prizes |
|---|---|---|---|---|---|
| meta_crustle_majkel | 3000 | 88.3% | **290 (82.4%)** | 59 (16.8%) | 3 (0.9%) |
| meta_crustle_flg    | 3000 | 89.3% | **243 (75.9%)** | 69 (21.6%) | 8 (2.3%) |

We essentially **never lose the prize race** in these matchups (~1-2% of losses).
The Crushing Hammer theory predicted prize-race losses; the data shows almost none.

Wins tell the same story: only ~35-38% of wins are on prizes. The wall matchups
are attrition — both decks grind out and whoever runs out of cards first loses.

## The race is close, which is why it is winnable

From the majkel shard detail, in games we lose to deck-out:

- our deck: **0** (by definition), opponent deck: **6.8** cards left
- mean turn **34.7** (vs **21.2** in wins)
- our hand at the end: **6.9** cards — we have cards, we have no deck

So we lose the deck-out race **by about seven cards**. Any change that saves
~7+ cards of deck over a 35-turn grind converts a large share of 290+243 losses.

Secondary mode (17-22%): `no_active` — we run out of Pokémon in play, mean turn
~19, hero in-play 0. Note the Crustle override hard-skips Relicanth
(`-8000, "Crustle: skip Relicanth (MD path dead)"`) even though it is a free
body, and that override runs *after* the empty-bench guard, so it wins. That is
the natural **second** lever if deck conservation lands.

## Where our deck actually goes

Card text of every flow card in `archaludon_ex_cinderace.csv`:

| card | n | net deck cost |
|---|---|---|
| **Explorer's Guidance (1185)** | 4 | look at 6, take 2, **discard 4** -> **-6** |
| Ultra Ball (1121) | 4 | -1 |
| Poke Pad (1152) | 4 | -1 |
| Pokegear 3.0 (1122) | 4 | -1 (0 if no Supporter in top 7) |
| Night Stretcher (1097) | 4 | 0 (discard -> hand) |
| **Lillie's Determination (1227)** | 4 | shuffle hand in, draw 6/8 -> **~deck-neutral / positive** |

Explorer's Guidance is a 6-for-2 incinerator and is the only card in the deck
that burns the deck faster than one per use. Four copies in a 35-turn grind is
easily 12-24 cards — several times the ~7-card margin we lose by.

The existing guard only suppressed it at `deckCount <= 10`, which is far past the
point of no return, and it lumped in Lillie, which actually *refills* the deck.

## Lever under test

`ARCH_CRUSTLE_LEVER=deckcons` (`_crustle_explorer_allowed`, default OFF):
in the Crustle matchup, Explorer's Guidance is scored -5000 once
`deckCount <= ARCH_DECKCONS_FLOOR` (default 30) instead of `<= 10`.

Result: see `crustle_r2_deckcons_*` in `fleet/state/pooled_history.jsonl`.

## Caveat on the profiler's absolute level

The profiler reports a ~2pp higher majkel WR (88.3%) than `gate_archaludon.py`
at the same code (86.16%, n=7500). The loss *composition* is what this document
claims and that is unaffected by a level shift, but do not quote the profiler's
absolute WR as a gate number. All A/B verdicts in this lane are taken from
`gate_archaludon.py` via `Shard-Gate.ps1` only.
