# Game Telemetry (4 games per ordered matchup)

One row in the CSV is one agent perspective for one game.

## Results By Agent

| Agent | Games | Wins | Losses | Draws | Win % | Avg turns | Avg missed attach turns | Avg first evolve turn |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 16 | 11 | 5 | 0 | 68.8 | 5.6 | 0.00 | 3.6 |
| random | 16 | 2 | 14 | 0 | 12.5 | 5.5 | 0.38 | 4.5 |
| safety | 16 | 11 | 5 | 0 | 68.8 | 6.4 | 0.00 | 3.9 |

## Results By First/Second

| Agent | Order | Games | Wins | Losses | Win % | Avg turns | Avg missed attach turns |
|---|---|---:|---:|---:|---:|---:|---:|
| current | first | 7 | 5 | 2 | 71.4 | 5.0 | 0.00 |
| current | second | 9 | 6 | 3 | 66.7 | 6.1 | 0.00 |
| random | first | 10 | 2 | 8 | 20.0 | 6.6 | 0.50 |
| random | second | 6 | 0 | 6 | 0.0 | 3.7 | 0.17 |
| safety | first | 7 | 5 | 2 | 71.4 | 5.6 | 0.00 |
| safety | second | 9 | 6 | 3 | 66.7 | 7.0 | 0.00 |

## Loss Reasons

| Agent | Reason | Losses | Avg turns | Avg deck left | Avg opp prizes left |
|---|---|---:|---:|---:|---:|
| current | no_active | 4 | 4.8 | 41.5 | 4.0 |
| current | prize | 1 | 12.0 | 32.0 | 0.0 |
| random | no_active | 14 | 5.0 | 43.3 | 4.5 |
| safety | no_active | 5 | 7.8 | 40.2 | 3.6 |

## Common Decision Contexts In Losses

| Agent | Context counts |
|---|---|
| current | MAIN:45;TO_HAND:9;SETUP_ACTIVE_POKEMON:5;ATTACH_TO:3;ATTACH_FROM:3;TO_ACTIVE:3;IS_FIRST:3;SETUP_BENCH_POKEMON:1 |
| random | MAIN:81;SETUP_ACTIVE_POKEMON:14;IS_FIRST:8;TO_HAND:8;ATTACH_TO:5;DRAW_COUNT:5;TO_ACTIVE:3;DISCARD_ENERGY:2;SETUP_BENCH_POKEMON:1 |
| safety | MAIN:51;TO_HAND:10;SETUP_ACTIVE_POKEMON:5;DISCARD_ENERGY:4;ATTACH_TO:3;ATTACH_FROM:3;TO_ACTIVE:3;IS_FIRST:3;DRAW_COUNT:1;SETUP_BENCH_POKEMON:1 |

## Active Attackers

| Agent | Attack counts | Last attacker counts |
|---|---|---|
| current | 723:29;722:16;721:11 | 723:11;721:3;722:2 |
| random | 722:14;723:8;721:6 | 722:5;721:4;723:3 |
| safety | 723:28;721:24;722:15 | 723:11;721:4;722:1 |
