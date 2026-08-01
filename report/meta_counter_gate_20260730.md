# Archaludon vs Top-6 Meta Gate (2026-07-30)

## Setup
- Hero brain: `archaludon_agent` (R7 + crustle/grimmsnarl levers already in code)
- Opponent decks: LB top-6 restored lists (`agent_decks/top_lb_*.csv` / `mined_top/`)
- **Opponent brain: `random`** (no official pilots for these lists) — WR is **deck-pressure signal**, not ladder μ

## Results

### Dual suite (Crustle ×2 + Grimmsnarl ×3), 24 games/opp — default deck

| Opponent | Archetype | WR | W/L |
|----------|-----------|---:|-----|
| flg Crustle | crustle | **62.5%** | 15/9 |
| Majkel Crustle | crustle | **66.7%** | 16/8 |
| Dries Grimmsnarl | grimmsnarl | **91.7%** | 22/2 |
| Luca Grimmsnarl | grimmsnarl | **100%** | 24/0 |
| LiamK Grimmsnarl | grimmsnarl | **100%** | 24/0 |
| **Overall** | | **84.2%** | n=120 |

### Top6 suite, 20 games/opp — default deck

| Opponent | WR |
|----------|---:|
| flg Crustle | 65% |
| Dries Grimmsnarl | 95% |
| Luca Grimmsnarl | 100% |
| James Kangaskhan | 75% |
| Majkel Crustle | 60% |
| LiamK Grimmsnarl | 95% |
| **Overall** | **81.7%** |

### Dual suite — `nb_archaludon_75wr` hero deck, 20 games/opp

| Opponent | WR |
|----------|---:|
| flg Crustle | **85%** |
| Majkel Crustle | **80%** |
| Grimmsnarl (3 lists) | **95–100%** |
| **Overall** | **92.0%** |

### Deep Crustle only (40 games/opp)

| Hero deck | flg | Majkel | Overall |
|-----------|----:|-------:|--------:|
| default `archaludon_ex_cinderace` | 65.0% | 60.0% | **62.5%** |
| `nb_archaludon_75wr` | 80.0% | 77.5% | **78.8%** |

## Main findings
1. **Grimmsnarl lists are soft for Arch under random pilot** — existing grimmsnarl levers + Metal Defender race work (90–100%).
2. **Crustle is the real local bottleneck** (~60–65% default; 40g confirms).
3. **`sample_archaludon_75wr` deck list is clearly better vs Crustle** (~+16pp overall, 78.8% vs 62.5%).
4. Do **not** treat high local WR as ladder-ready: opponent brain is **random**, not flg/Dries decision quality.

## Actions
- Prefer hero deck **`nb_archaludon_75wr`** (or merge its shell into archaludon_ex_cinderace) for next packages.
- Keep Crustle levers (no Metal Defender into wall; Raging Hammer; skip ex evolve) hot.
- Submit only if ladder μ path > ~710–793 **and** Crustle gate stays ≥65% under deeper n + any stronger pilots later.
- Registry suites added: `dual`, `top6`, `meta_fast` now pure dual-meta.
