# Iono minimal lever baseline (diagnosis)

## Setup
- No Iono-specific apply_overrides (R14h pass-through)
- score_attack wired on MAIN
- R11 prize-race attach global
- Dragapult R16c still on

## Iono results
| Run | n | WR | CI |
|-----|--:|---:|----|
| baseline suite | 40 | 27.5% | 16.1–42.8 |
| pure core | 40 | 32.5% | 20.1–48.0 |
| iono-only | 60 | **30.0%** | 19.9–42.5 |

## Implication
Do not chase 40% as regression target — post-wiring true rate is ~30%.
Next A/B: single change only (e.g. only MD lethal +1500, nothing else) vs this 30% n=60 baseline.
