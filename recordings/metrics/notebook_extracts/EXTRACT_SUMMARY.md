# Notebook extract summary — 2026-07-30T23:36:50Z

Source: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\notebooks\kaggle_pull`
Agents: `extracted_agents` | Decks: `agent_decks\from_notebooks`

| Slug | Status | Entrypoints | Writefiles | Decks |
|------|--------|-------------|------------|------:|
| advanced_heuristic | **ready_integrate** | def agent(...) | main.py | 1 |
| alakazam_2304_audit | **needs_rewrite** | def agent(...), cg battle loop | — | 0 |
| alakazam_search_v12 | **analysis_only** | cg battle loop | — | 0 |
| alakazam_search_v9 | **needs_rewrite** | def agent(...), cg battle loop | — | 0 |
| archaludon_metal_gpu_v28 | **ready_integrate** | def agent(...), def act(...), MCTS/UCB keywords, RL library | README.txt, deck.csv, gpu_submission_inference_v28.py, group.txt | 1 |
| dragapult_ucb1 | **ready_integrate** | def agent(...), MCTS/UCB keywords, RL library | main_baseline_a.py, main_baseline_b.py, main.py | 0 |
| meta_router_844 | **analysis_only** | — | — | 0 |
| official_abomasnow | **ready_integrate** | def agent(...) | main.py | 0 |
| official_dragapult | **ready_integrate** | def agent(...), RL library | main.py | 0 |
| official_iono | **ready_integrate** | def agent(...), RL library | main.py | 0 |
| official_lucario | **ready_integrate** | def agent(...) | main.py | 0 |
| official_rl_mcts | **needs_rewrite** | MCTS/UCB keywords, cg battle loop | — | 0 |
| pub_1070_alakazam | **analysis_only** | — | — | 0 |
| pub_1084_baseline | **ready_integrate** | def agent(...), cg battle loop | main.py | 1 |
| pub_1208_loader | **analysis_only** | cg battle loop | — | 0 |
| pub_950_v10 | **ready_integrate** | def agent(...), MCTS/UCB keywords | main.py | 1 |
| pub_control_v11 | **ready_integrate** | def agent(...), cg battle loop, RL library | main.py | 0 |
| pub_meta_score_band | **analysis_only** | — | — | 0 |
| sample_archaludon_75wr | **ready_integrate** | def agent(...) | main.py, deck.csv | 1 |

## Archaludon usage tips

- **official_* rule agents**: use as field opponents (already in `agent/`); re-extract keeps reference main.py
- **official_rl_mcts**: copy train/MCTS loop ideas into CUDA field train; do not ship raw torch in submission
- **alakazam_search_***: search/audit patterns for matchup levers; decks if present → from_notebooks
- **sample_archaludon_75wr / archaludon_metal_gpu_***: highest priority for Archaludon imitation
- **meta_router / advanced_heuristic**: strategy notes + heuristics, usually needs rewrite
