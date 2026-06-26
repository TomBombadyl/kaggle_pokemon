# Agent catalog — every ladder submission decoded

**Purpose:** Single reference for what each submitted agent *actually is* (brain, deck, training, packaging).  
**Ground truth:** Kaggle public μ (user UI 2026-06-26) + `eval/kaggle_submissions_session45.csv`.  
**Use this before any new train/upload** — not local gates, not session handoffs.

**Related:** [`ladder_scoreboard_full_20260626.md`](ladder_scoreboard_full_20260626.md) (sorted μ only).

---

## 1. Brain taxonomy (what “agent” means here)

Every submission is **`brain × deck`** packaged for Kaggle `main.agent(obs)`.

| Brain ID | Type | Rules? | Search? | RL? | Code | Fallback |
|----------|------|:------:|:-------:|:---:|------|----------|
| **heuristic** | Hand-tuned MAIN priorities | ✓ | — | — | `agent/agent.py` `HeuristicScorer` | `_legal_fallback` |
| **search** | Heuristic + cg `SearchBegin` (~200ms) on promote/switch/setup | ✓ | shallow | — | `agent/search_policy.py` `SearchScorer` | HeuristicScorer |
| **lucario_search** | LucarioScorer MAIN + search on 3 contexts; search must be in Lucario top-2 | ✓ | shallow | — | `LucarioSearchScorer` | LucarioScorer |
| **lucario** | Official kiyotah Lucario sample port + smart bench + `matchup_levers` | ✓ | — | — | `agent/lucario_policy.py` | Agent scaffold |
| **rulecore** | Deck-agnostic attack *plan* from engine tables + `deck_tech` | ✓ | — | — | `agent/rule_core.py` | HeuristicScorer |
| **dragapult_crispin** | Official kiyotah Dragapult sample (standalone `agent()`); v3 adds R7 bench guard | ✓ | — | — | `agent/dragapult_agent.py` + optional `dragapult_bench_guard.py` | never-crash wrapper |
| **learned** | Distilled MaskablePPO policy (Track B) | — | — | ✓ PPO→npz | `agent/learned_policy.py` (**removed from repo**; tarballs only) | heuristic-ish |
| **lucario_mcts_basic** | Kaggle RL+MCTS sample notebook; transformer + MCTS@12; **narrow training opponents** | — | MCTS | ✓ | `agent/lucario_mcts_{policy,runtime}.py` + `rl_mcts_basic/*/model4.pth` (**deleted**) | LucarioScorer or RuleCore |
| **lucario_mcts_field** | Local `train_lucario_field_mcts.py`; MCTS@20 train / @12 submit; **official field pilots** | — | MCTS | ✓ | same runtime + `rl_mcts_field/lucarioex_v{2,5}_field/` | LucarioScorer |
| **alakazam_imported** | ryotasueyoshi best5 rules (ported S50) | ✓ | — | — | `agent/alakazam_agent.py` | never-crash wrapper |
| **archaludon_rules** | Community Archaludon/Cinderace v5 + R7 bench guard (S50) | ✓ | — | — | `agent/archaludon_agent.py` | never-crash wrapper |

**Packaging:**
- Standard brains → `scripts/package_submission.py --scorer {heuristic,search,lucario,...} --deck …`
- Dragapult → `scripts/package_dragapult.py` (standalone tarball, not `build_agent`)
- Alakazam best5 → `scripts/package_alakazam.py` (standalone tarball)

---

## 2. Every COMPLETE submission (22 rows)

### Archaludon ex / Cinderace — community v5 + R7 bench guard

#### #1 · μ **1196.1** (latest) · peak **1224.2** · ref `54083197` · `archaludon.tar.gz` (uploaded as `archaludon_ex_cinderace_r7_bench`)

| Field | Value |
|-------|-------|
| **Brain** | `archaludon_rules` — community public v5 + **R7 empty-bench guard** (`archaludon_bench_guard.py`) |
| **Deck** | `agent_decks/archaludon_ex_cinderace.csv` (public list, unchanged) |
| **RL / training** | **None** — ported rules + wrapper |
| **Local gate cited** | **72.7%** full native suite n=30 at upload; **67.3%** post R7b agent scoring (filter only) |
| **μ trajectory** | 600.0 → 731.3 → **1224.2** (peak) → **1196.1** (latest, 2026-06-26 UI) |
| **Rebuild** | `python scripts/package_archaludon.py` |
| **Verdict** | **Still #1 on ladder** (+315 μ vs Dragapult). **Lock Final Submission (54083197).** R12: no duplicate upload. |

#### R8 probe · ref `54088877` · `archaludon.tar.gz` · **PENDING**

| Field | Value |
|-------|-------|
| **Brain** | `archaludon_rules` + **R8a** `_mandatory_promote_score` + **R8b** `_empty_bench_block_tempo` |
| **Local gate** | **75.3%** full n=30 (64.7% → 70.7% → 75.3%) |
| **Delta vs 54083197** | Material scoring change — upload gate exit 0 |
| **Verdict** | Probe only — keep **54083197** Final until μ beats **1196.1** on ≥2 readings |

---

### Starmie / Froslass — ashleysandlin spread

#### · μ **277.5** · ref `54083513` · `starmie_froslass_ashleysandlin.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | `starmie_rules` — PrizeTracker + finish search + R7 bench guard |
| **Deck** | `agent_decks/starmie_froslass_ashleysandlin.csv` |
| **Local gate cited** | Mirror **56.7%** n=30; full suite **9.3%** |
| **μ trajectory** | 300.3 → **277.5** |
| **Verdict** | COMPLETE; **paused** — far below Archaludon / Dragapult bars. |

---

### Dragapult ex — official pilot

#### #2 · μ **880.9** · ref `53989933` · `dragapult_ex_sample.tar.gz` (v3)

| Field | Value |
|-------|-------|
| **Brain** | `dragapult_crispin` + **R7 empty-bench guard** (`dragapult_bench_guard.py`) |
| **Deck** | `agent_decks/dragapult_ex_sample.csv` (official Crispin list) |
| **RL / training** | **None** — verbatim public sample + wrapper |
| **Local gate cited** | 90.6% vs SearchScorer; 0 `no_active` losses |
| **Rebuild** | `python scripts/package_dragapult.py` |
| **Verdict** | **Prior bar** — superseded by Archaludon (1196.1 μ latest). |

#### #2 · μ **833.0** · ref `53950779` · `dragapult_ex_sample.tar.gz` (v2)

| Field | Value |
|-------|-------|
| **Brain** | `dragapult_crispin` + never-crash wrapper; **no** bench guard |
| **Deck** | `dragapult_ex_sample.csv` |
| **Change vs v1** | Fixed `main.py` `__file__` NameError (v1 **ERROR** ref `53950246`) |
| **Verdict** | Superseded by v3 |

---

### Mega Lucario ex — real mined list (`real_mega_lucario_ex.csv`)

#### #3 · μ **660.5** · ref `53869254` · `track_a_lucario_ex_search.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **SearchScorer** (generic rules + shallow search) |
| **Deck** | `agent_decks/real_mega_lucario_ex.csv` |
| **RL / training** | **None** |
| **Local gate cited** | 29/30 vs benchmark |
| **Package** | `--scorer search --deck agent_decks/real_mega_lucario_ex.csv` |
| **Verdict** | **Best home-grown brain on any deck.** Beat before trying new ML. |

#### #5 · μ **651.3** · ref `53946742` · `track_d_lucarioex_rl_mcts_model4.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **lucario_mcts_basic** — Kaggle sample notebook architecture (d128, 1+1 layers, search≈12) |
| **Deck** | `real_mega_lucario_ex.csv` |
| **Training** | `rl_mcts_basic/lucarioex_basic/model4` — **short Kaggle GPU run**, sample-style opponents (not full field registry); **80% eval WR claimed** |
| **Fallback at submit** | LucarioScorer |
| **Artifacts** | `rl_mcts_basic/` **deleted from repo** (Session 44 graveyard) |
| **Verdict** | **Beats v5 field MCTS on same deck** — evidence that *more* field RL hurt μ. |

#### #11 · μ **580.6** · ref `53995982` · `lucarioex_v5_field_mcts.tar.gz` (final)

| Field | Value |
|-------|-------|
| **Brain** | **lucario_mcts_field** champion `model_best.pth` |
| **Deck** | `real_mega_lucario_ex.csv` |
| **Training** | `scripts/train_lucario_field_mcts.py` **25 cycles**, CUDA, MCTS search=**20** train / **12** submit, 9 official kiyotah opponents, lever_blend=0.45, 30 games/opp/cycle, Lucario mirror 20g/cycle vs LucarioScorer |
| **Promote metric** | Field gate mean WR; peak **46.1%** (cycle 21) |
| **Submit stack** | MCTS → LucarioScorer fallback; **no** levers/clock at inference |
| **Report** | `report/eval/LUCARIOEX_V5_FIELD_REPORT.md` |
| **Verdict** | **Regression vs Search (660.5) and model4 (651.3). Do not train more v5 without new hypothesis.** |

#### #18 · μ **464.7** · ref `53978119` · same tarball family (cycle-13 checkpoint)

Earlier upload of v5 training (cycle ~13, 43.5% field eval). Superseded by 53995982.

#### #19 · μ **460.8** · ref `53962060` · `lucarioex_v2_field_mcts.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **lucario_mcts_field** (earlier config) |
| **Training** | **20 cycles** vs **10 opponents** (pre-v5 opponent set) |
| **Work dir** | `rl_mcts_field/lucarioex_v2` |
| **Verdict** | Worse than model4 and v5 final — field RL track v2 abandoned. |

#### #14 · μ **535.6** · ref `53886522` · `track_c_lucario_rulecore_smartbench.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **LucarioScorer** + `smart_bench` (1–2 depth bench guard) — description also mentions RuleCore; submission log: `LucarioScorer+SmartBench` |
| **Deck** | `real_mega_lucario_ex.csv` |
| **Episodes** | **2** (high σ — treat as inconclusive) |
| **Local gate** | 9.0% cited |
| **Verdict** | Under-sampled; Lucario rules alone not competitive on ladder. |

#### #20 · μ **368.5** · ref `53885445` · `track_d_lucario_rl_mcts.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **lucario_mcts_basic** iter-0 |
| **Training** | **2-cycle Kaggle GPU**; **85% vs random**; gate 97.5% vs random/mirror — **not field** |
| **Verdict** | **Retired** — classic wrong-opponent overfit. |

---

### Alakazam — mined (`top_mined_alakazam.csv` / pool variants)

#### #4 · μ **659.0** · ref `53913404` · `ryotasueyoshi_alakazam_best5.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **alakazam_imported** — `agent/alakazam_agent.py` (ported from ryotasueyoshi notebook, S50) |
| **Deck** | `agent_decks/ryotasueyoshi_alakazam_best5.csv` (notebook list — **not** identical to `top_mined_alakazam.csv`) |
| **Local gate** | 62.0% full suite @ n=30 (`eval/alakazam_best5_baseline_session49.md`); top_mined deck 59.3% |
| **Ladder gate cited** | 57.3% public gate @ 417 games (original upload) |
| **Source** | `notebooks/ryotasueyoshi_rule_based_alakazam_best5/` → `scripts/bootstrap_alakazam_best5.py` |
| **Rebuild** | `python scripts/package_alakazam.py` |
| **Verdict** | **Best non-Dragapult μ.** Ported to repo (S50). **Do not re-upload** without improvement (R12; ladder ref 53913404). Iterate levers locally first. |

#### #13 · μ **545.6** · ref `53890064` · `track_a_alakazam_leader_search.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **SearchScorer** (our generic rules) |
| **Deck** | Leader-mined Alakazam (TrustHub line) |
| **Verdict** | **−113 μ vs imported best5** on same archetype — pilot gap, not deck gap. |

#### #21 · μ **185.4** · ref `53946148` · `track_d_alakazam_rl_mcts_model4.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **lucario_mcts_basic** on Alakazam deck |
| **Training** | Sample notebook pipeline; **fixed Snorlax/sample_deck opponent** + mirror |
| **Verdict** | **Retired** — deck strong (659 rules), brain poisoned by training. |

#### #16 · μ **490.4** · ref `53856584` · `track_b_learned_alakazam.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **learned** (Track B PPO → distill) |
| **Deck** | `pool_alakazam_dudunsparce.csv` (proxy pool — **invalid opponent era**) |
| **Note** | Shared distill across decks — known bug |
| **Verdict** | **Retired** |

---

### Kyogre

#### #6 · μ **633.0** · ref `53854707` · `a2_kyogre.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **HeuristicScorer** |
| **Deck** | `agent_decks/a2_kyogre_33_energy.csv` |
| **Episodes** | Peaked **672.7** early, settled **633.0** |
| **Verdict** | Stable rules baseline; first `__file__` fix probe. |

#### #7 · μ **626.0** · ref `53856711` · `track_a_probe_1.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **SearchScorer** |
| **Deck** | `track_a_probes/probe_1_a2_kyogre_33_energy_e+2.csv` (+2 energy variant) |
| **Verdict** | Deck tweak did not beat heuristic Kyogre on μ. |

---

### Trevenant / Abomasnow / GA deck

#### #8 · μ **615.6** · ref `53916377` · `track_a_trevenant_leader_search.tar.gz`

| Brain: **SearchScorer** · Deck: mined Trevenant leader · Local L1 **15.3%** → ladder **615.6** (gates underrate).

#### #12 · μ **548.6** · ref `53856676` · `track_a_probe_2.tar.gz`

| Brain: **SearchScorer** · Deck: Abomasnow +4e probe (`track_a_probes/probe_2_deck_e+4.csv`).

#### #9 · μ **600.7** · ref `53930652` · `track_a_gen19_fast_basic_search.tar.gz`

| Brain: **SearchScorer** · Deck: **gen19 GA-evolved** fast-basic aggro · GA **did not beat** hand Kyogre on μ.

---

### Lucario hub deck (leader-suite “Lucario v2” — **not** `lucarioex_v2_field_mcts`)

#### #15 · μ **500.1** · ref `53930648` · `track_a_lucario_search.tar.gz`

| Field | Value |
|-------|-------|
| **Brain** | **LucarioSearchScorer** |
| **Deck** | Leader-suite “Lucario v2” list (**exact CSV path not in repo** — tarball only) |
| **Local gate** | Leader L1 **69.6%** / public **11.1%** |
| **Verdict** | **Local leader-suite lied** — 500 μ. Never trust leader-suite without ladder. |

---

### Track B — LearnedScorer (PPO + distill)

#### #10 · μ **585.1** · ref `53868798` · `track_b_learned_rl_deck_kaggle_20260619.tar.gz`

| Brain: **learned** · Deck: `rl_deck/best_deck.csv` (RL-evolved deck) · Train: 100k PPO, gate 87.5%.

#### #17 · μ **468.9** · ref `53856590` · `track_b_learned_dragapult.tar.gz`

| Brain: **learned** · Deck: `pool_dragapult.csv` proxy.

**Track B verdict:** All **< 600 μ** except RL-deck at 585. **Retired** per RULINGS; `learned_policy.py` removed from tree.

---

## 3. ERROR submissions (2)

| Ref | Tarball | Failure |
|-----|---------|---------|
| `53950246` | dragapult v1 | `main.py` `__file__` NameError on Kaggle |
| `53854588` | a2_kyogre v0 | Same `__file__` bug before fix |

---

## 4. Cross-submission lessons (ladder evidence only)

```
880.9  dragapult_crispin × official sample     ← only path >800
 833.0  dragapult_crispin v2
 660.5  SearchScorer × real Lucario             ← best OUR code
 659.0  imported Alakazam rules
 651.3  basic MCTS × real Lucario              ← beats 25-cycle field MCTS
 633.0  Heuristic × Kyogre
 …
 580.6  field MCTS v5 × real Lucario           ← wasted GPU vs above
 185.4  basic MCTS × Alakazam (Snorlax train)
```

| Hypothesis | Ladder verdict |
|------------|----------------|
| More field RL cycles improve μ | **False** — v5 (580.6) < model4 (651.3) < Search (660.5) |
| Lucario deck is dead | **False** — Search on same deck beats most agents |
| Dragapult deck on any pilot | **False** — Session 49: dragapult brain on Lucario list → **10%** local |
| Learned / Track B beats rules | **False** — all ≤585 |
| Leader-suite / local public gate predicts μ | **False** — Kyogre 13%→672, LucarioSearch 69.6%→500 |
| Imported rules worthless | **False** — 659 μ Alakazam |

---

## 5. Not submitted (blind spots)

| Brain × deck | Why it matters |
|--------------|----------------|
| SearchScorer × `dragapult_ex_sample` | Only official Crispin submitted on that list |
| SearchScorer × Alakazam after porting best5 | Close 660 vs 659 gap with our packaging |
| LucarioScorer × `real_mega_lucario_ex` @ n=30 | **39.3%** local (`eval/lucario_scorer_baseline_session50.md`) — upload blocked; beat Search **660.5 μ** |
| `real_dragapult_ex` mined deck | Never on ladder |
| Heuristic/Search × Lucario | Only Search tested |

---

## 6. Repo pointers (rebuild today)

| Agent | Rebuild command |
|-------|-----------------|
| Dragapult v3 | `python scripts/package_dragapult.py` |
| Archaludon v5 + R7 | `python scripts/package_archaludon.py` |
| Search × Lucario | `python scripts/package_submission.py --name lucario_ex_search --scorer search --deck agent_decks/real_mega_lucario_ex.csv` |
| Lucario v5 MCTS | `python scripts/repackage_champions.py --include-lucario` (needs `rl_mcts_field/` backup) |
| Imported Alakazam | `python scripts/package_alakazam.py` |

**Sync ladder after upload:** `python scripts/track_ladder.py` → append `report/ladder_history.csv` (do not rely on 6-row `eval/ladder_log.csv` alone).

---

## 7. Session 49 addendum (local only — not ladder)

`dragapult_agent` on `real_mega_lucario_ex.csv` → **10%** @ n=30 (`eval/pilot_deck_matrix_session49.md`).  
Confirms: **never move a pilot to another deck without a ladder probe.**
