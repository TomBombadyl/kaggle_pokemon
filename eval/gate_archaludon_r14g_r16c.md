# Gate R14g + R16c (score_attack wiring)

## Infrastructure (important)
MAIN attack path previously used `best_attack_damage` only — `score_attack` matchup KO logic was dead code. Now wired.

## Results n=40
- baseline 50.6% (Draga 35 / Iono 27.5 / Aboma 70 / Luc 70)
- pure core 44.2% (Draga 47.5 / Iono 22.5 / Aboma 62.5)

## vs prior (R14d n=40)
- Iono 40% → 22–27% (R14f hurt; R14g still soft — variance + wiring interaction)
- Draga 40–42% → 35–47% (no clear stable lift)

## Submit: NO
