# Card Database Summary (T3)

Source: `EN_Card_Data.csv` - **2022 cards**, 17 columns.

## Columns
`Card ID`, `Card Name`, `Expansion`, `Collection No.`, `Stage (Pokémon)/Type (Energy and Trainer)`, `Rule`, `Category`, `Previous stage`, `HP`, `Type`, `Weakness`, `Resistance (Type)`, `Retreat`, `Move Name`, `Cost`, `Damage`, `Effect Explanation`

## Card supertype (`Stage (Pokémon)/Type (Energy and Trainer)`)
- Basic Pokémon: 958
- Stage 1 Pokémon: 618
- Stage 2 Pokémon: 229
- Item: 82
- Supporter: 61
- Pokémon Tool: 28
- Stadium: 26
- Special Energy: 12
- Basic Energy: 8

## Pokemon energy type (`Type`)
- {G}: 257
- {P}: 242
- {W}: 236
- {F}: 210
- {D}: 199
- {C}: 182
- {R}: 174
- {L}: 131
- {M}: 118
- 竜: 71
- {A}: 2
- {A}{A}: 1
- {Team Rocket}{Team Rocket}: 1
- {C}{C}{C}: 1

## Special subtype / mechanic (`Category`)
- Trainer's Pokémon（Team Rocket）: 85
- Tera(Stellar): 60
- Ancient: 26
- Trainer's Pokémon（N）: 26
- Trainer's Pokémon（Hop）: 21
- Future: 17
- Trainer's Pokémon（Ethan）: 15
- Trainer's Pokémon（Larry）: 13
- Trainer's Pokémon（Steven）: 12
- Trainer's Pokémon（Cynthia）: 11
- Trainer's Pokémon（Marnie）: 11
- Trainer's Pokémon（Erika）: 11
- Trainer's Pokémon（Misty）: 10
- Trainer's Pokémon（Arven）: 10
- Fossil: 10
- Tera(Fighting): 9
- Tera(Lightning): 9
- Trainer's Pokémon（Iono）: 9
- Trainer's Pokémon（Lillie）: 7
- Tera(Fire): 6
- Tera(Darkness): 3
- Tera(Grass): 3
- Tera(Water): 3
- Tera(Dragon): 3
- Technical Machine: 2

## HP distribution (Pokemon)
- count 1815, min 30, median 110, max 380

## Retreat cost
- 1:859, 2:554, 3:265, 4:70

## Rule box
- cards with a Rule entry (ex / Rule Box etc.): 324

## Sample rows
```
Card ID        Card Name Stage (Pokémon)/Type (Energy and Trainer)  HP   Type
      1 Basic {G} Energy                              Basic Energy n/a    {G}
      2 Basic {R} Energy                              Basic Energy n/a    {R}
      3 Basic {W} Energy                              Basic Energy n/a    {W}
      4 Basic {L} Energy                              Basic Energy n/a    {L}
      5 Basic {P} Energy                              Basic Energy n/a    {P}
      6 Basic {F} Energy                              Basic Energy n/a    {F}
      7 Basic {D} Energy                              Basic Energy n/a    {D}
      8 Basic {M} Energy                              Basic Energy n/a    {M}
      9 Boomerang Energy                            Special Energy n/a    {C}
     10 Neo Upper Energy                            Special Energy n/a {A}{A}
```
