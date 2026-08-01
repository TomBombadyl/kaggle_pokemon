# INTEL — 2026-07-31 (round 3, role `intel`)

Two questions this round, both answered with pooled multi-shard evidence:

1. **How much of each ship floor is an artifact of `opponent_brain: random`?**
   Round 2 answered it for `top6` (−17.9pp). This round answers it for the two
   floors that actually gate a submission: **`dual` (≥90)** and **`meta` (arch ≥83)**.
2. **Does the live field mixture survive an independent second sample?**
   Round 2's Grimmsnarl 0.657 came from one reading. This round re-pulls and
   re-reads with **disjoint episodes**.

Nothing was rolled back. No agent brain, ship floor, `field/weights.json`,
`field/registry.json`, or submission was touched. Round 2's report is archived at
`report/INTEL_20260731_r2.md`.

---

## 1. Ladder (read 2026-07-31 ~11:40 local / 03:40Z)

| Item | Value |
|---|---|
| Top 1 | **Brahim 1162.4** |
| Top 2–5 | James Cox & Henry Chao 1151.2 · Raja Biswas 1146.6 · Luca 1141.1 · THIRD PTCG Club 1139.0 |
| #14 (pull cutoff) | haggle 1121.7 |
| Our `55122053` | **790.9** (was 798.6 at 03:22Z) |
| Our `55122059` | **742.8** |
| Gap to Top 1 | ~372 μ |

Ladder is flat since round 2 — same Top 1, same value. Both our refs are mature
and both ~370 μ short.

---

## 2. CONFIRMED — the `dual` ship floor is ~20pp of random-opponent inflation

Same hero, same decks, same seat-swap, **only the opponent pilot changes**.
4 shards × 36 games/opponent × 5 opponents per arm.

| Arm | Pooled | se | ci95 |
|---|---:|---:|---|
| `dual` / `random` (what the ≥90 floor reads today) | **95.40%** | 0.80 | [93.83, 96.97] |
| `dual` / `rulecore` | **74.85%** | 1.54 | [71.83, 77.87] |

Δ = **−20.55pp**, se_diff 1.74, 2×se_diff 3.47, **z = −11.84**, ci95 disjoint → **CONFIRMED**.

Per opponent (n=144 decided per arm; every one moves the same direction):

| Opponent | random | rulecore | Δ |
|---|---:|---:|---:|
| `meta_crustle_flg` | 92.36% | 70.83% | −21.53 |
| `meta_crustle_majkel` | 94.41% | 73.61% | −20.80 |
| `meta_grimmsnarl_dries` | 95.83% | 82.64% | −13.19 |
| `meta_grimmsnarl_liamk` | 98.61% | 75.00% | −23.61 |
| `meta_grimmsnarl_luca` | 95.83% | 72.22% | −23.61 |

`rulecore` fell back to a legal random pick on only **1.3–3.3%** of decisions, so
this is a real policy playing ~97% of the game — and `rulecore` is still a *weak*
pilot. **74.85% is an upper bound** on our true `dual` number against the pilots
actually on the ladder.

`dual` and `meta_fast` are the **same five opponents** in `field/registry.json`.
The ship floor and the sentinel are not independent checks.

### Consequence for `crustle_min` (floor ≥89)

Both `crustle_min` opponents sit in the `dual` set, so this round measured them
twice. Pooling the two rulecore readings (n=240 each):

| Opponent | rulecore pooled | ci95 |
|---|---:|---|
| `meta_crustle_flg` | **68.75%** | [62.6, 74.3] |
| `meta_crustle_majkel` | **75.00%** | [69.2, 80.1] |
| `min()` | **68.75%** | vs floor **89.0** |

The crustle lane has been grinding variance on 85–89% against opponents that play
uniformly at random. Against a competent pilot the same matchup is ~69%.

---

## 3. CONFIRMED — the arch `meta` floor, with a built-in control

`meta` mixes 5 random-pilot and 4 native-pilot opponents, so a global pilot swap
would misstate arm A. Two new modes in `scripts/intel_pilot_ab.py` fix that:

- `--pilot as_registry` — native where the registry says native, random where it
  says random. **This reproduces the real gate**, including silently skipping
  `meta_kangaskhan_james` (brain=native, no official archetype) exactly as
  `gate_vs_opponent` does → 9 gated opponents.
- `--pilot upgrade` — identical, except the 5 `random` entries get `rulecore`.

4 shards × 24 games/opponent × 9 opponents = **n=864 per arm**.

| Arm | Pooled | se | ci95 |
|---|---:|---:|---|
| `meta` / `as_registry` | **79.95%** | 2.04 | [75.95, 83.95] |
| `meta` / `upgrade` | **66.58%** | 1.32 | [63.99, 69.17] |

Δ = **−13.37pp**, se_diff 2.43, 2×se_diff 4.86, **z = −5.50**, ci95 disjoint → **CONFIRMED**.

**Validity check:** arm A (79.95 ± 2.04) is statistically consistent with arch's
pinned `meta` 76.66 ± 0.50 and director's independent 76.72 ± 0.37
(diff 3.29 < 2×se_diff 4.20). The diagnostic reproduces the gate it audits.

**Internal control** — the 4 native-pilot opponents were untouched by the swap and
behave like it:

| Opponent | pilot | as_registry | upgrade | Δ |
|---|---|---:|---:|---:|
| `top_mined_alakazam` | native (control) | 56.25% | 56.25% | **+0.00** |
| `real_iono` | native (control) | 56.25% | 54.17% | **−2.08** |
| `ryotasueyoshi_alakazam_best5` | native (control) | 63.54% | 60.42% | **−3.12** |
| `dragapult_ex_sample` | native (control) | 63.54% | 59.38% | **−4.17** |
| `meta_grimmsnarl_dries` | random → rulecore | 98.96% | 85.42% | −13.54 |
| `meta_crustle_majkel` | random → rulecore | 94.79% | 77.08% | −17.71 |
| `meta_grimmsnarl_luca` | random → rulecore | 91.67% | 72.92% | −18.75 |
| `meta_grimmsnarl_liamk` | random → rulecore | 97.92% | 67.71% | −30.21 |
| `meta_crustle_flg` | random → rulecore | 96.88% | 65.62% | −31.25 |

Every control moves ≤4.17pp; every treated opponent moves ≥13.54pp. The drop is
caused by the pilot swap, not by shard noise or a hero-side change.

**The arch ≥83 floor sits above even the inflated reading (79.95), and ~16pp above
the honest one (66.58).**

### The summary the director needs

| Floor | Reads today | Same suite, competent pilot | Floor |
|---|---:|---:|---:|
| arch `meta` ≥83 | 79.95 ± 2.04 | **66.58 ± 1.32** | 83 |
| `dual` ≥90 | 95.40 ± 0.80 | **74.85 ± 1.54** | 90 |
| `crustle_min` ≥89 | ~85–89 | **68.75** | 89 |
| `real_iono` ≥55 | 54–56 | *already a real pilot* | 55 |

Three of the four floors are measured against uniform-random opponents. The one
floor with a real pilot — `real_iono` — is the only one that has ever looked hard,
and it is also the only one whose number would **not** move if we fixed the field.
That is a sufficient explanation for local 95% vs live μ 790, and it means the
three inflated floors carry almost no information about ladder μ.

---

## 4. CONFIRMED — the live field mixture, second independent sample

Re-pulled top-14 at 11:38 local (previous pull 03:27Z): 112 episodes kept, **114
replay files absent from the pre-pull snapshot**, 0 deleted, 1.44 GB of a 2.6 GB
budget. Classified only the disjoint 114 → an independent sample, not a re-read.

| Archetype | A share (n=350) | B share (n=204) | z | verdict | **pooled (n=554)** |
|---|---:|---:|---:|---|---|
| `marnie_grimmsnarl_ex` | 0.657 | 0.608 | 1.17 | CONSISTENT | **0.639 [0.598, 0.678]** |
| `dragapult_psychic` | 0.074 | 0.118 | −1.72 | CONSISTENT | 0.090 [0.069, 0.117] |
| `mega_kangaskhan_ogerpon` | 0.080 | 0.098 | −0.73 | CONSISTENT | 0.087 [0.066, 0.113] |
| `crustle_iwapalace` | 0.057 | 0.069 | −0.54 | CONSISTENT | 0.061 [0.044, 0.085] |
| `rocket_spidops` | 0.051 | 0.039 | 0.66 | CONSISTENT | 0.047 [0.032, 0.068] |
| `alakazam_psychic` | 0.051 | 0.039 | 0.66 | CONSISTENT | 0.047 [0.032, 0.068] |
| `cynthia_line` | 0.011 | 0.020 | −0.78 | CONSISTENT | 0.014 [0.007, 0.028] |
| `lucario_mirror` | 0.017 | 0.010 | 0.70 | CONSISTENT | 0.014 [0.007, 0.028] |
| `iono_lightning` | 0.000 | 0.000 | — | CONSISTENT | **0 of 554, ci95 [0, 0.0069]** |
| `kyogre_water` | 0.000 | 0.000 | — | CONSISTENT | 0 of 554, ci95 [0, 0.0069] |

**All eight observed archetypes agree across disjoint samples (every |z| < 1.96).**
Round 2's reading is confirmed, not a one-off. Against `field/weights.json`
(2026-06-26, n=47 replays):

- `marnie_grimmsnarl_ex` **0.639** — *absent from the file*
- `lucario_mirror` 0.392 → **0.014** (28× overweighted)
- `dragapult_psychic` 0.365 → **0.090** (4× overweighted)
- `iono_lightning` 0.041 → **0 of 554**, upper bound now **0.7%** (was 4.3%)
- unmodelled: `mega_kangaskhan_ogerpon` 0.087, `crustle_iwapalace` 0.061,
  `rocket_spidops` 0.047, `cynthia_line` 0.014

Representative deck of each top-14 team in this pull: **Grimmsnarl ×6**
(Raja Biswas, Luca, Dominic Peel, KantoRegionMaster, ntumlnoob, LiamK),
Kangaskhan-Ogerpon ×2, Dragapult ×2, and **Brahim (#1) classifies as `unknown` — a
Dudunsparce line we do not model at all.**

Unknown decks (70 of 624) are excluded from the denominator, so every share above
is an upper bound on its archetype.

**Still do not run `build_field_weights.py` as-is** — it reads the newest
`deck_by_mu_band_*.json`, and the 2026-07-31 one has `parsed_replays: 0`, which
blanks the weights. Use `recordings/intel/live_meta_20260731_sampleB.json`.

---

## 5. What this changes for each lane

- **director** — three of four floors read a number that is 13–20pp inflated. The
  floors are not the problem and must not be lowered; the *opponent pilots* are.
  Until `field/registry.json` has real pilots, a green `dual`/`crustle_min` tells
  you nothing about μ. `real_iono` is currently the only honest signal we own.
- **crustle** — your target is ~69% against a competent pilot, not 85–89%. Variance
  chasing on the random-pilot number cannot move μ.
- **arch** — the 4 native matchups are where all real headroom is, and this round's
  control arm re-measures them: alakazam 56.25 / 63.54, iono 56.25, dragapult 63.54.
- **iono** — `iono_lightning` is 0 of 554 top-band decks (ci95 upper **0.7%**), but
  `real_iono` is our only non-inflated gate. Those two facts point opposite ways;
  it is a director ruling, not an intel one.

---

## Artifacts

- `scripts/intel_pilot_ab.py` — added `--pilot as_registry|upgrade` (registry-faithful
  modes that reproduce the gate's own skip rule)
- `scripts/intel_live_meta.py` — added `--exclude-ids` / `--tag` for independent resampling
- `recordings/intel/live_meta_20260731_sampleB.json`
- `recordings/intel/replay_snapshot_pre_r3.json` (198 pre-pull episode ids)
- `report/OPPONENT_DECK_DISTRIBUTION_live_sampleB.md`
- `report/INTEL_20260731_r2.md` (round 2, archived)
- pooled: `intel_r3_dualA_random`, `intel_r3_dualB_rulecore`,
  `intel_r3_metaA_as_registry`, `intel_r3_metaB_upgrade`
