# Crustle lane diagnosis — why majkel < flg (2026-07-31, role=crustle round 1)

## 1. It is a mean deficit, not tail collapse

Task book hypothesised "variance / tail collapse". Pooled shard evidence says otherwise.

| arm | n | mean | shard sd | se | binomial sd expected at n=300/shard |
|---|---|---|---|---|---|
| `crustle_r1_base_majkel` | 5x300 | 87.18% | 1.88 | 0.84 | ~1.94 |
| `crustle_r1_base_flg`    | 5x300 | 88.92% | 0.86 | 0.38 | ~1.81 |

Observed shard sd is at or **below** the binomial expectation for 300 games at
p≈0.87. There is no excess between-shard variance, so there is no "some games
collapse to 0–50%" tail to mine. The earlier 80–92 swings were single-shard
sampling noise, not a real bimodal failure mode.

**Conclusion: min(flg, majkel) is short of 89 because the majkel matchup mean is
~87, full stop. Fix the mean; do not chase variance.**

Pooled base majkel across both round-1 runs (10 shards, n=3000):
`[88.0, 85.7, 84.7, 82.9, 92.0, 85.0, 85.3, 89.0, 88.3, 88.3]` -> **86.92 +- 0.84**

## 2. Structural cause: Crushing Hammer

Deck diff of `agent_decks/top_lb_majkel_crustle.csv` vs `top_lb_flg_crustle.csv`
(both are the same Dwebble/Crustle + Kangaskhan + Cornerstone Ogerpon wall shell):

| card | id | flg | majkel |
|---|---|---|---|
| **Crushing Hammer** | 1120 | **0** | **4** |
| Cook | 1212 | 0 | 1 |
| Battle Cage | 1264 | 1 | 0 |
| Tool Scrapper | 1137 | 1 | 0 |
| Colress's Tenacity | 1194 | 2 | 0 |
| Xerosic's Machinations | 1197 | 1 | 1 |

The only large, mechanically relevant delta is **4x Crushing Hammer**. Our hero
deck is Archaludon ex / Cinderace — a Metal Energy deck whose single win
condition into this wall is Raging Hammer on a fuelled Duraludon (Metal Defender
is hard-banned at `archaludon_agent.py:382` because it does 0 into the shell).
Coin-flip energy denial directly attacks the one line we have, which is exactly
the size of gap we measure (flg 88.9 -> majkel 86.9, ~2pp).

## 3. What is already implemented (do not re-invent)

`archaludon_agent.py` already carries a dense anti-Hammer package inside
`_apply_crustle_overrides` / `score_play`:

- `_opp_hammer_seen()` (:681) — Crushing Hammer in opponent discard
- `_energy_starved()` (:691) — Active attacker < 2 energy, or board metal <= 1,
  or >= 2 metal in discard with none in hand
- attach: bench Duraludon +14000/+16000, Active Duraludon <2 energy +15000/+20000
  re-fuel, Cinderace Turbo enable +10000 (:949-972)
- Night Stretcher metal recovery 24000 when starved/hammer-seen (:1774)
- never END with an unspent attach (:975), never discard metal from hand (:1001),
  prefer metal on any TO_HAND search (:992)

## 4. The gap in that package (next single lever)

**`_opp_hammer_seen()` is reactive.** It only fires once a Hammer has already
resolved and hit the discard — i.e. after we have already lost an energy. Against
majkel's 4-copy build, hammer pressure is live from turn 1.

Proposed next single lever (`ARCH_CRUSTLE_LEVER=hammer_prior`): treat hammer
pressure as presumed-live whenever `detect_matchup(obs) == "crustle"`, rather
than waiting for discard evidence.

Known cost to measure: flg runs **zero** Hammers, and the Crustle and flg/majkel
shells are visually identical on board, so we cannot condition on the actual
opponent. Playing around a Hammer that does not exist will cost some flg win
rate. This is acceptable only if **both** arms clear 89 — the ship floor is
`min(flg, majkel)`, so the A/B must gate flg and majkel together.
