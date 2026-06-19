# Game Telemetry (20 games per ordered matchup)

One row in the CSV is one agent perspective for one game.

## Results By Agent

| Agent | Games | Wins | Losses | Draws | Win % | Avg turns | Avg missed attach turns | Avg first evolve turn |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 80 | 60 | 20 | 0 | 75.0 | 5.7 | 0.00 | 3.9 |
| random | 80 | 7 | 73 | 0 | 8.8 | 5.9 | 0.64 | 4.4 |
| safety | 80 | 53 | 27 | 0 | 66.2 | 5.8 | 0.00 | 4.0 |

## Results By First/Second

| Agent | Order | Games | Wins | Losses | Win % | Avg turns | Avg missed attach turns |
|---|---|---:|---:|---:|---:|---:|---:|
| current | first | 32 | 28 | 4 | 87.5 | 4.4 | 0.00 |
| current | second | 48 | 32 | 16 | 66.7 | 6.6 | 0.00 |
| random | first | 56 | 7 | 49 | 12.5 | 6.7 | 0.73 |
| random | second | 24 | 0 | 24 | 0.0 | 4.2 | 0.42 |
| safety | first | 32 | 26 | 6 | 81.2 | 5.8 | 0.00 |
| safety | second | 48 | 27 | 21 | 56.2 | 5.9 | 0.00 |

## Loss Reasons

| Agent | Reason | Losses | Avg turns | Avg deck left | Avg opp prizes left |
|---|---|---:|---:|---:|---:|
| current | no_active | 20 | 6.2 | 39.6 | 3.9 |
| random | no_active | 71 | 5.5 | 43.4 | 4.5 |
| random | prize | 2 | 18.0 | 28.0 | 0.0 |
| safety | no_active | 24 | 4.7 | 43.2 | 4.5 |
| safety | prize | 3 | 11.0 | 28.7 | 0.0 |

## Common Decision Contexts In Losses

| Agent | Context counts |
|---|---|
| current | MAIN:175;TO_HAND:38;SETUP_ACTIVE_POKEMON:20;IS_FIRST:16;TO_ACTIVE:10;DISCARD_ENERGY:10;ATTACH_TO:9;ATTACH_FROM:8;SETUP_BENCH_POKEMON:5;DRAW_COUNT:3 |
| random | MAIN:487;SETUP_ACTIVE_POKEMON:73;TO_HAND:46;IS_FIRST:38;TO_ACTIVE:24;DRAW_COUNT:24;ATTACH_TO:23;SETUP_BENCH_POKEMON:21 |
| safety | MAIN:191;TO_HAND:30;SETUP_ACTIVE_POKEMON:27;IS_FIRST:19;TO_ACTIVE:14;ATTACH_TO:11;ATTACH_FROM:11;SETUP_BENCH_POKEMON:8;DRAW_COUNT:8;DISCARD_ENERGY:2 |

## Active Attackers

| Agent | Attack counts | Last attacker counts |
|---|---|---|
| current | 723:123;721:116;722:79 | 723:55;721:18;722:7 |
| random | 722:88;721:27;723:19 | 722:39;721:12;723:10 |
| safety | 721:118;723:104;722:89 | 723:40;721:26;722:14 |
