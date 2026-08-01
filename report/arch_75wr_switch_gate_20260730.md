# Archaludon 75wr switch + Crustle lever re-gate (2026-07-30)

## Changes
1. **Main deck** `agent_decks/archaludon_ex_cinderace.csv` ← `sample_archaludon_75wr` shell  
   - Deltas vs legacy: Charmeleon line removed; Cinderace 3→4; Full Metal Lab 2→4; Metal Energy 10→11  
   - Legacy saved: `archaludon_ex_cinderace_legacy_charmeleon.csv`
2. **Crustle levers strengthened** in `agent/archaludon_agent.py`  
   - Harder MD ban (−12k), stronger RH primary (+12–28k), retreat ex/Relicanth, Boss/Lab/Cape priority, fuel Duraludon for RH, skip Relicanth/ex search
3. **Ship bar raised**: `ship_min_wr_pct=72`, `ship_crustle_min_wr_pct=70`, auto_submit min 72%; primary suite `dual`
4. Meta opponents forced back to **random** brain (native had no Crustle pilot → empty gates)

## Post-switch results (random pilot opponents)

### Dual (Crustle×2 + Grimmsnarl×3), 24 g/opp — **75wr + new levers**

| Opponent | WR | W/L |
|----------|---:|-----|
| flg Crustle | **58.3%** | 14/10 |
| Majkel Crustle | **66.7%** | 16/8 |
| Dries Grimmsnarl | **95.8%** | 23/1 |
| Luca Grimmsnarl | **95.8%** | 23/1 |
| LiamK Grimmsnarl | **91.7%** | 22/2 |
| **Overall** | **81.7%** | n=120 |

### Deep Crustle only, 40 g/opp

| Opponent | WR | W/L |
|----------|---:|-----|
| flg | **80.0%** | 32/8 |
| Majkel | **70.0%** | 28/12 |
| **Overall** | **75.0%** | n=80 |

## Verdict
- **Deep Crustle overall 75% ≥ 70% floor** (meets local Crustle ship criterion on deep n).
- Dual 24g flg variance (58%) shows Crustle still noisy — do **not** ship on dual-only vanity.
- Grimmsnarl remains soft under random pilot (90%+).
- **Submit hold**: still no evidence of beating live board μ ~680–710 with *real* decision quality; keep iterating, package ready at `dist/candidates/archaludon.tar.gz` (75wr deck inside).

## Package
- `dist/candidates/archaludon.tar.gz` dry-run OK (60 cards, 75wr shell)
