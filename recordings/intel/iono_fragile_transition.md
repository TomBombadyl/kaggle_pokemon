# Iono — earliest preventable transition into a fragile board

> **Outcome (iono lane, 2026-07-31 round 2).** Q1 closed the bench-depth lever
> family: a bench play is legal in only 11.55% of bench-empty entries, so
> `tomato_fork` had almost nothing to act on (NULL at floors 2 and 3). Q3's top
> mechanical signal, under-played Boss's Orders, became lever `tomato_boss`
> (`ARCH_IONO_LEVER=tomato_boss`, gust-for-the-KO pre-empt) and **KEEP**: pooled
> 6x800 **52.62% +-0.71** vs matched baseline **49.95% +-0.46**, ci95 disjoint.
> First lever to clear the ~52% tomato ceiling. Ship floor is still 55%.

Scanned **13380 games** (51.18% WR) over 14 schema-v2 shards.

## Q1 — when the bench first empties post-setup

- games that ever reach an empty bench after setup: **4026** (30.09% of games); of those **3131** lost (**77.77%** loss rate vs 48.82% overall)
- a bench play (Duraludon/Relicanth/Cinderace) was legal at that very decision in **465** cases (**11.55%** of entries)
- mean hand size at the entry decision: win 7.05 vs loss 6.22

## Q2 — do we spend our own Pokemon as a cost?

- games with >=1 own-Pokemon discard: **13134** (98.16% of games), WR **52.13%** vs base 51.18%

| discarded card | n | WR |
|---|---:|---:|
| Relicanth | 8767 | 46.61% |
| Duraludon | 85933 | 51.22% |
| Archaludon ex | 77775 | 53.8% |
| Cinderace | 18303 | 55.53% |

## Q3 — bucket-matched regret (MAIN decisions)

Within matched `(bench, active energy, turn band, own prizes)` buckets: win rate when the option was taken vs when it was legal and declined. Observational, policy-confounded — a candidate generator, not proof.

| option | card | chosen n | chosen WR | declined n | declined WR | delta | ci disjoint |
|---|---|---:|---:|---:|---:|---:|:--:|
| END | - | 5639 | 21.1% | 333284 | 54.66% | -33.56pp | yes |
| PLAY | Boss's Orders | 3706 | 89.42% | 77655 | 67.62% | +21.81pp | yes |
| EVOLVE | Archaludon ex | 30610 | 55.33% | 84934 | 66.76% | -11.43pp | yes |
| PLAY | Lillie's Determination | 14278 | 53.17% | 108330 | 63.18% | -10.02pp | yes |
| RETREAT | - | 12870 | 61.52% | 71087 | 55.51% | +6.01pp | yes |
| PLAY | -1 | 43033 | 57.89% | 112157 | 62.65% | -4.76pp | yes |
| ATTACK | - | 75126 | 58.87% | 232357 | 61.52% | -2.66pp | yes |
| PLAY | Duraludon | 34829 | 55.23% | 15225 | 57.69% | -2.46pp | yes |
| PLAY | Relicanth | 8594 | 58.01% | 5353 | 60.17% | -2.17pp | no |
| PLAY | Explorer's Guidance | 28401 | 56.45% | 41324 | 58.52% | -2.08pp | yes |
| PLAY | Ultra Ball | 15030 | 55.46% | 96082 | 54.26% | +1.20pp | yes |
| PLAY | Poke Pad | 23555 | 56.12% | 13484 | 55.98% | +0.13pp | no |
| PLAY | Pokegear 3.0 | 23176 | 55.64% | 13831 | 55.71% | -0.07pp | no |
| ATTACH | -1 | 55269 | 55.91% | 98494 | 55.95% | -0.04pp | no |