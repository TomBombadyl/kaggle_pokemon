# Anti-meta local training director

Updated: `2026-07-31T01:13:02+00:00`

## Objective

Build an Archaludon anti-meta/router candidate without burning Kaggle CAP. Current binding targets: Iono >=55%, Crustle min >=89%, Arch overall >=83%, dual >=90/baseline.

## Current ship gate

- Decision: `HOLD`
- Reasons: iono 50.3125 < 55.0, crustle_min 86.575 < 89.0
- Arch: 85.4
- Iono: 50.3125
- Crustle min: 86.575
- Dual: 91.5625
- Submits today: 2/5

## Iono failure target

- Dataset games: 3260
- Pooled WR: 50.37%
- Main cluster: fragile_board_any = incomplete evolved active OR active energy <2 OR empty bench.

## Latest training artifact

- Summary: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\artifacts\iono_prior_v2\iono_prior_20260731T011433Z.json`
- Checkpoint: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\artifacts\iono_prior_v2\iono_prior_20260731T011433Z.pt`
- Decisions: 167282
- Best win multi-option top1: 0.5837962031364441
- Fragile decisions: 101214 (loss=53284, win=47930)

## Required KEEP gates before wiring/submission

Runtime smoke after wiring was **REJECTED**:

- `tomato` n80 vs real_iono: 52.5%
- `tomato_bc` with `ARCH_IONO_BC_ENABLE=1`, fragile scope, margin 2.0, n80 vs real_iono: 40.0%
- Safety: BC model inference is disabled by default unless `ARCH_IONO_BC_ENABLE=1`; plain `ARCH_IONO_LEVER=tomato_bc` falls back to tomato.

Do **not** submit or package this BC runtime. Keep the dataset/checkpoint as training evidence only.

```powershell
E:\PTCG_AI_Battle_Challenge\fleet\Shard-Gate.ps1 -Role iono -Script scripts\gate_archaludon.py -Games 300 -Extra @('--opponents','real_iono') -Env @{ARCH_IONO_LEVER='tomato_bc'} -Label iono_bc_fragile

E:\PTCG_AI_Battle_Challenge\fleet\Shard-Gate.ps1 -Role crustle -Script scripts\gate_archaludon.py -Games 120 -Extra @('--opponents','meta_crustle_flg','meta_crustle_majkel') -Env @{ARCH_IONO_LEVER='tomato_bc'} -Label guard_crustle_bc

E:\PTCG_AI_Battle_Challenge\fleet\Shard-Gate.ps1 -Role director -Script scripts\gate_archaludon.py -Games 80 -Suite meta_fast -Env @{ARCH_IONO_LEVER='tomato_bc'} -Label guard_meta_fast_bc
```

KEEP only if Iono clears 55% pooled and guard gates do not regress. Otherwise REJECT and keep tomato.
