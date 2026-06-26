# Full ladder scoreboard — all COMPLETE submissions (ground truth)

**Source:** Kaggle submissions UI (2026-06-26 evening) + `report/ladder_history.csv`  
**Sort:** public μ descending. **Bar:** **1196.1 μ** latest (Archaludon ref 54083197; peak **1224.2**).

| Rank | μ | Brain | Deck | Tarball / ref | Notes |
|-----:|----:|-------|------|---------------|-------|
| 1 | **1196.1** | Community v5 + bench guard R7 | `archaludon_ex_cinderace` | archaludon · 54083197 | **Champion — lock Final** (peak 1224.2) |
| 2 | **880.9** | Official Crispin + bench guard R7 | `dragapult_ex_sample` | dragapult v3 · 53989933 | Prior bar |
| 3 | 833.0 | Official Crispin + wrapper | `dragapult_ex_sample` | dragapult v2 · 53950779 | Superseded |
| 4 | 660.5 | **SearchScorer** (home rules) | `real_mega_lucario_ex` | track_a_lucario_ex_search · 53869254 | **Best home-grown** |
| 5 | 659.0 | **Imported best5 rules** (external) | Alakazam mined | ryotasueyoshi_alakazam_best5 · 53913404 | Best non-Archaludon pilot |
| 6 | 651.3 | RL+MCTS model4 (basic notebook) | `real_mega_lucario_ex` | track_d_lucarioex_rl_mcts_model4 · 53946742 | **Beats v5 field MCTS** |
| 7 | 633.0 | HeuristicScorer | Kyogre | a2_kyogre · 53854707 | Peaked 672.7 early |
| 8 | 626.0 | SearchScorer | Kyogre +2e probe | track_a_probe_1 · 53856711 | |
| 9 | 615.6 | SearchScorer | Trevenant mined | track_a_trevenant · 53916377 | |
| 10 | 600.7 | SearchScorer | gen19 GA deck | track_a_gen19 · 53930652 | GA did not beat hand Kyogre |
| 11 | 585.1 | LearnedScorer (Track B PPO) | RL-deck | track_b_learned · 53868798 | ML < rules |
| 12 | 580.6 | **Field RL+MCTS v5** (25 cycles) | `real_mega_lucario_ex` | lucarioex_v5 · 53995982 | **Below model4 & Search** |
| 13 | 548.6 | SearchScorer | Abomasnow probe | track_a_probe_2 · 53856676 | |
| 14 | 545.6 | SearchScorer | Alakazam leader mined | track_a_alakazam_leader · 53890064 | Our Search << imported best5 |
| 15 | 535.6 | LucarioScorer + smart bench | Lucario sample | track_c_rulecore · 53886522 | |
| 16 | 500.1 | LucarioSearchScorer | Lucario v2 deck | track_a_lucario_search · 53930648 | |
| 17 | 490.4 | LearnedScorer | Alakazam mined | track_b_learned_alakazam · 53856584 | |
| 18 | 468.9 | LearnedScorer | Dragapult spread | track_b_learned_dragapult · 53856590 | Learned on Dragapult deck still fails |
| 19 | 464.7 | Field RL+MCTS v5 cycle13 | `real_mega_lucario_ex` | lucarioex_v5 early · 53978119 | |
| 20 | 460.8 | Field RL+MCTS v2 | `real_mega_lucario_ex` | lucarioex_v2 · 53962060 | |
| 21 | 368.5 | RL+MCTS iter0 (2-cycle GPU) | Lucario | track_d_lucario_rl_mcts · 53885445 | |
| 22 | **277.5** | Starmie rules + PrizeTracker | `starmie_froslass_ashleysandlin` | starmie · 54083513 | Session 51 probe; paused |
| 23 | **185.4** | RL+MCTS model4 (basic) | Alakazam mined | track_d_alakazam · 53946148 | Snorlax-opponent training |

**ERROR (not on ladder):** dragapult v1 (`__file__` bug), a2_kyogre first upload.

---

## Lessons from the full board (not from local gates)

### By brain family — best μ achieved

| Brain family | Best μ | Deck that achieved it |
|--------------|-------:|----------------------|
| Community Archaludon rules + R7 guard | **1196.1** (peak 1224.2) | archaludon_ex_cinderace |
| Official archetype rules (Crispin Dragapult) | **880.9** | dragapult_ex_sample |
| SearchScorer (our rules+search) | **660.5** | real_mega_lucario_ex |
| Imported external rules | **659.0** | Alakazam best5 |
| Basic RL+MCTS (notebook) | **651.3** | real_mega_lucario_ex |
| HeuristicScorer | **633.0** | Kyogre |
| Field RL+MCTS (25-cycle “champion”) | **580.6** | real_mega_lucario_ex |
| LearnedScorer / Track B | **585.1** | RL-deck |
| RL+MCTS wrong training | **185.4** | Alakazam |

### By deck — best μ achieved (pilot varies!)

| Deck archetype | Best μ | Best brain on that deck |
|----------------|-------:|-------------------------|
| Archaludon ex / Cinderace | **1196.1** (peak 1224.2) | Community v5 + R7 guard |
| Dragapult ex sample | **880.9** | Official Crispin |
| Mega Lucario ex real | **660.5** | SearchScorer (not field MCTS) |
| Alakazam mined | **659.0** | Imported best5 (not our Search 545.6) |
| Kyogre | **633.0** | HeuristicScorer |
| Trevenant | **615.6** | SearchScorer |
| Abomasnow | **548.6** | SearchScorer |
| GA gen19 | **600.7** | SearchScorer |

### What we should have concluded earlier

1. **Field RL+MCTS v5 (580.6) is a regression** vs basic model4 (651.3) and SearchScorer (660.5) on the **same Lucario deck**.
2. **Archaludon community v5 + R7 bench guard** peaked **1224.2 μ**, latest **1196.1 μ** — still +315 μ vs Dragapult. Local gates underpredicted again.
3. **Only Dragapult official pilot cleared 800 μ** before Archaludon — gap to #2 was **~220 μ**, not a few lever points.
4. **SearchScorer on Lucario** is the home-grown iteration path (660.5 μ). LucarioScorer gated **39.3%** @ n=30 — do not upload.
5. **Every LearnedScorer / Track B submission < 600 μ** except one RL-deck at 585.1.
6. **Local gates misordered Kyogre (13% local → 672 μ peak)**, Trevenant (15% L1 → 615.6 μ), Dragapult v3 (90.6% local → 880.9 μ), and Archaludon (72.7% local → **1224.2 μ**). Ladder is the only sort key.

### Not tried on ladder (gaps)

- SearchScorer × `dragapult_ex_sample` (only official pilot submitted)
- SearchScorer × Alakazam with imported best5 **code** packaged as ours
- Official Lucario sample pilot × `real_mega_lucario_ex` (only LucarioScorer/smartbench at 535.6)
- Any submission using **mined real_dragapult_ex** deck (only sample list on ladder)
- HeuristicScorer × Lucario / Alakazam (only Kyogre path explored on ladder)
