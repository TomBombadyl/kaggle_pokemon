# INTEL — 2026-07-31 (round 2, role `intel`)

Two independent findings this round, both measured, both pointing the same way:
**our local gates are scoring us against a field that no longer exists, piloted by
nobody.** That is the most parsimonious explanation for local 93% vs live μ ~790.

---

## 1. Ladder snapshot (live, Kaggle API, 2026-07-31 ~03:40Z)

| Item | Value |
|---|---|
| Top 1 | **Brahim 1162.4** |
| Top 2–4 | James Cox & Henry Chao 1151.2 · Raja Biswas 1146.6 · Luca 1141.1 |
| Our latest-2 | **55122053 = 790.9** · **55122059 = 742.8** (both COMPLETE) |
| Gap to Top1 | **~372 μ** |

Note `STATUS_BOARD.md` still shows 648.4 / 699.7 — those readings are stale; both
refs have matured upward. Also `report/meta/leaderboard_top_20260731.json` has
haggle at 1169.5 as Top1; haggle is no longer in the live top 8.

**The R7 spine that historically pinned 1196.1 is now scoring ~790 on the same
ladder.** The brain did not change. The field did. Section 3 says how.

---

## 2. FINDING A — every top-of-ladder gate opponent is piloted at random

`eval/harness.get_opponent_brain` resolves `opponent_brain` from
`field/registry.json`. For an archetype with no organizer sample pilot,
`agent/native_opponent.make_opponent_brain(kind="non_official", …)` falls through to
`non_official_brain="random"` → `agent.lucario_mcts_runtime.random_agent`, which is
literally `random.sample(range(len(options)), maxCount)`.

`agent/official_registry.py` ships pilots for exactly six archetypes:
`mega_lucario_ex`, `dragapult_ex`, `iono`, `mega_abomasnow_ex`, `alakazam_psychic`,
`starmie_water`. Crustle-Iwapalace, Marnie-Grimmsnarl and Kangaskhan-Ogerpon are
**not** among them — so **13 of 31 registry opponents are random**, including every
opponent in `meta_fast`, `dual` and `top6`:

| Suite | Used for | Opponents | Pilots |
|---|---|---|---|
| `meta_fast` | director baseline (92.20%) | 2 Crustle + 3 Grimmsnarl | **5/5 random** |
| `dual` | ship floor ≥90 | 2 Crustle + 3 Grimmsnarl | **5/5 random** |
| `top6` | top-of-ladder proxy | 6 LB decks | **6/6 random** |
| `crustle_min` (flg, majkel) | ship floor ≥89 | 2 Crustle | **2/2 random** |
| `real_iono` | ship floor ≥55 | Iono | **native** (real pilot) |

### Measured cost of the random pilot

`scripts/intel_pilot_ab.py` re-runs the identical hero, decks and seat-swap and
changes **only** the opponent pilot. `rulecore` = `agent.rule_core.RuleCoreScorer`,
the deck-agnostic pilot the repo already ships but never wires up, with an R7
legality guard (validate against the option mask, else legal random fallback;
measured fallback rate 1.4–5.5%).

| Arm | Opponent pilot | Pooled mean | stderr | ci95 | n |
|---|---|---:|---:|---|---:|
| A | `random` (status quo) | **94.30%** | 1.04 | [92.26, 96.34] | 4×180 |
| B | `rulecore` | **76.40%** | 1.78 | [72.91, 79.89] | 4×180 |

**Δ = −17.90pp**, 2×se_diff = 4.12 → **CONFIRMED**, ci95 disjoint. Control check:
independent baseline `intel_r2_base_top6` via `gate_archaludon.py` = 93.07% ± 0.87,
consistent with arm A.

Per-opponent (shard 0), random → rulecore:

| Opponent | Archetype | random | rulecore |
|---|---|---:|---:|
| `top_lb_01_flg` | crustle_iwapalace | 96.7% | 100.0% |
| `top_lb_02_dries` | marnie_grimmsnarl_ex | 96.7% | 73.3% |
| `top_lb_03_luca` | marnie_grimmsnarl_ex | 93.3% | 73.3% |
| `top_lb_04_james` | mega_kangaskhan_ogerpon | 86.7% | 73.3% |
| `top_lb_05_majkel` | crustle_iwapalace | 86.7% | 70.0% |
| `top_lb_06_liamk` | marnie_grimmsnarl_ex | 96.7% | 76.7% |

RuleCoreScorer is a *weak* generic pilot — it was written for our own archetypes and
needed a legality fallback on 1.4–5.5% of decisions on these decks. The real agents
behind μ 1130–1162 are far stronger. So **76.4% is still an upper bound**, and the
true gap between our gates and the ladder is larger than 17.9pp. This is exactly the
proxy gating Ruling R2 forbids.

---

## 3. FINDING B — `field/weights.json` describes a meta that is gone

Pulled 56 fresh public episodes from the live top-14 teams today
(`scripts/pull_high_value_episodes.py --top 14 --episodes-per-team 4`) and
classified every deck on both sides across all 198 replays on disk
(`scripts/intel_live_meta.py`, n=350 classified, 46 unknown).

| Archetype | Decks seen | Live share | 95% CI | `weights.json` v1 | Δ |
|---|---:|---:|---|---:|---:|
| `marnie_grimmsnarl_ex` | 230 | **0.657** | [0.606, 0.705] | **absent** | +0.657 |
| `mega_kangaskhan_ogerpon` | 28 | 0.080 | [0.056, 0.113] | **absent** | +0.080 |
| `dragapult_psychic` | 26 | 0.074 | [0.051, 0.107] | 0.365 | −0.291 |
| `crustle_iwapalace` | 20 | 0.057 | [0.037, 0.087] | **absent** | +0.057 |
| `alakazam_psychic` | 18 | 0.051 | [0.033, 0.080] | 0.189 | −0.138 |
| `rocket_spidops` | 18 | 0.051 | [0.033, 0.080] | **absent** | +0.051 |
| `lucario_mirror` | 6 | 0.017 | [0.008, 0.037] | 0.392 | −0.375 |
| `cynthia_line` | 4 | 0.011 | [0.004, 0.029] | **absent** | +0.011 |
| `iono_lightning` | **0** | **0.000** | [0.000, 0.043] | 0.041 | −0.041 |
| `kyogre_water` | 0 | 0.000 | [0.000, 0.043] | 0.014 | −0.014 |

`field/weights.json` is dated **2026-06-26** and its shares came from **47** parsed
replays, most of them in an `unmanifested_recent` bucket rather than a μ band.
`build_field_weights.py` cannot fix this on its own: the newest meta JSON
(`deck_by_mu_band_2026-07-31.json`) has `parsed_replays: 0`, so re-running it would
blank the weights.

Consequences, in order of size:

1. **Marnie-Grimmsnarl is ~2/3 of the top-band field and we model it nowhere** — no
   weight, no matchup lever, and its three gate opponents are piloted at random.
2. **Lucario went 0.392 → 0.017.** The largest weight in the file is now noise.
3. **Iono is 0 of 350 top-band decks** (CI upper bound 4.3%). It is the fleet's
   declared #1 priority and carries a hard ship floor of ≥55%.
4. **Crustle is 5.7%** yet owns a dedicated worker and a hard floor of ≥89, while
   Grimmsnarl at 65.7% has no floor at all. `dual` weights Crustle ~10× its share.
5. Two archetypes we have never modelled: `rocket_spidops` (5.1%), `cynthia_line`
   (1.1%). LB#1 Brahim's deck classifies **unknown** — Dunsparce / Dudunsparce /
   Hilda / Air Balloon.

**Caveat, stated plainly:** this is a *top-band* sample (teams at μ 1120–1162) with
46/396 decks unclassified, so every share is an upper bound on its archetype. Our
own agents sit at 742–791 μ and are currently matched lower than this band. But
1196.1 is the target, and this is the field that lives there.

---

## 4. What I did **not** do

- Did not touch `field/weights.json`, `field/registry.json`, any ship floor, any
  agent brain, or `scripts/director_*`. Changing the mixture or the pilot moves every
  weighted gate in the fleet at once — that is a director decision, and the proposals
  in `fleet/state/intel_PROPOSALS.md` are written as single levers so it can be A/B'd.
- No Kaggle submission or upload of any kind.

## 5. Artifacts

- `scripts/intel_pilot_ab.py` — random-vs-rulecore opponent-pilot diagnostic (new)
- `scripts/intel_live_meta.py` — live archetype mixture from replays (new)
- `recordings/intel/live_meta_20260731.json` — shares + Wilson CIs + proposed v2
- `report/OPPONENT_DECK_DISTRIBUTION_live.md` — generated table
- `recordings/episodes_high_value/` — 56 fresh top-14 replays (920 MB, under budget)
- `fleet/state/intel_r2_base_top6.pooled.json`, `intel_r2_pilotA_random.pooled.json`,
  `intel_r2_pilotB_rulecore.pooled.json`
