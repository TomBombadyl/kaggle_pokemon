# Search & Hybrid improvement plan — MCTS / SearchScorer

**Date:** 2026-07-31  
**Scope:** Lift home-grown SearchScorer (660.5 μ) and Lucario MCTS without rewriting the core loop.  
**Workspace:** `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon`

---

## 1. Current depth & quality audit

### 1.1 SearchScorer (best home-grown: **660.5 μ**)

| Knob | Value | Quality note |
|------|------:|--------------|
| `SEARCH_BUDGET_MS` | **200** | Shallow; only high-leverage card contexts |
| Contexts | TO_ACTIVE / SWITCH / SETUP_ACTIVE / SETUP_BENCH | MAIN/EVOLVE/ATTACH intentionally excluded (regressed) |
| Engine | cg `SearchBegin` / `SearchStep` | Determinized native search; no NN prior |
| Fallback | Full `HeuristicScorer` | Spine that ships |
| Local full-suite gate | **26.7%** @ n=30 | **Does not sort ladder** (Kyogre 13%→672 μ) |
| Prize tracker | On | Session 51: stability fix, no WR move |

**Depth verdict:** tactical re-rank only, not multi-ply game-tree search. Strength comes from **rules floor + sparse search overrides**, not from sims.

### 1.2 Lucario field MCTS CUDA (v5: **580.6 μ** final / model4 **651.3 μ**)

| Knob | Train v5 | Submit (shipped) | Gap |
|------|----------|------------------|-----|
| `SEARCH_COUNT` | **20** | **12** | Train/serve skew |
| Determinizations | **1** | **1** | Not true IS-MCTS |
| PUCT `c` | **0.4** hardcoded | same | Low vs AlphaZero-scale |
| Prior | NN softmax + Dirichlet | NN only | Rules prior only via lever visit bonus at train |
| Policy target | Relative Q (value) | n/a | Not visit-count π |
| Model | d128, 1 enc/dec | CPU | Small capacity |
| Field gate peak | **46.1%** | — | High variance @ 20g |
| Opp deck belief | real deck | **own deck** | Belief error at submit |

**Depth verdict:** ~12–20 root sims × single determinization ≈ **very shallow** AlphaZero-style MCTS. Literature (AlphaZero, Pluribus-style IS-MCTS, DouZero) shows value comes from **(sims × good prior × multi-belief)** together — not sims alone.

### 1.3 Sprint gate quality

| Gate | n | Role | Issue |
|------|--:|------|-------|
| `gate_search.py` full | 30 | Filter SearchScorer | Underpredicts ladder; CI wide |
| Field MCTS gate | 20/opp | Promote champion | Noise; cycle 22 promoted below cycle-21 peak |
| Upload gate | WR≥56% + legal | Ship | SearchScorer local 26.7% never clears — correct filter for *this* suite |

**Recommendation:** small A/B at **n=32–48/opp**, core suite first; promote only if **ΔWR ≥ +2 pp** and CI/SPRT support. Ladder remains truth.

---

## 2. Research synthesis (AlphaZero / IS-MCTS / SearchScorer)

| Idea | Source pattern | Map to our stack |
|------|----------------|------------------|
| **Neural prior + PUCT** | AlphaZero / MuZero | Already have NN prior; expose `PUCT_C`; blend rules prior into `child.prob` |
| **Visit-count policy targets** | AlphaZero π ∝ N^{1/τ} | `LUC_POLICY_TARGET=visits` for distillation closed loop |
| **IS-MCTS / multi-determinization** | Cowling et al.; PIMC | `LUC_DETERMINIZATIONS=K` root-visit aggregate (IS-MCTS-lite) |
| **Rules + shallow search** | Our SearchScorer 660.5; adaptive-search Baseline B | **Budget + guard_k** before any RL spend |
| **Belief prior quality** | ReBeL / opponent models | Later: replace stub hand/deck sample with archetype prior (not this sprint) |
| **Train/serve parity** | v5 report gap | Submit `SEARCH_COUNT=20` (meta-aligned) |

**Hard lesson from our ladder:** full AZ self-play (public L1 9.7%) and field RL v5 (580.6 μ) **lost** to SearchScorer. Hybrid improvements must **preserve the rules floor** (R3).

---

## 3. Landable improvements (no core-loop rewrite)

Implemented knobs (defaults = legacy behavior):

### SearchScorer / LucarioSearch

| Env / arg | Default | Experiment |
|-----------|--------:|------------|
| `SEARCH_BUDGET_MS` | 200 | 400, 600 |
| `SEARCH_GUARD_TOP_K` | 2 | 3 |
| `SEARCH_HEURISTIC_BLEND` | 0 | 0.15–0.25 |

### Lucario MCTS runtime

| Env / train flag | Default | Experiment |
|------------------|--------:|------------|
| `LUC_SEARCH_COUNT` / `--search-count` | 12 | 20–32 |
| `LUC_DETERMINIZATIONS` / `--determinizations` | 1 | 2–3 |
| `LUC_PUCT_C` / `--puct-c` | 0.4 | 0.8–1.2 |
| `LUC_PRIOR_BLEND` / `--prior-blend` | 0 | 0.15–0.35 (+ `set_lucario_lever_teaching`) |
| `LUC_POLICY_TARGET` / `--policy-target` | value | visits |
| Submit `DEFAULT_SEARCH_COUNT` | **20** (was 12) | match train |

### Distillation closed loop (minimal)

1. Collect with `SEARCH_COUNT≥20`, `POLICY_TARGET=visits`, optional `DETERMINIZATIONS=2`.  
2. Train existing Huber head on visit-mapped π (same loss path).  
3. Gate field mean vs champion; **only promote if beats SearchScorer local bar on same suite**.  
4. Do **not** ship if rules/search still win the gate (R3).

---

## 4. Small experiment ladder (n=32–48)

### Phase S0 — SearchScorer budget (hours, no GPU)

```powershell
cd E:\PTCG_AI_Battle_Challenge\kaggle_pokemon
$py = "..\.venv\Scripts\python.exe"
& $py scripts/exp_search_hybrid_ab.py --games 40 --suite core `
  --variants budget200 budget400 lucario400 --tag s0_budget
```

**Pass:** any variant ≥ baseline +2 pp overall **or** +5 pp on weakest matchup without ≤−2 pp elsewhere.

### Phase S1 — Lucario hybrid guard / blend

```powershell
& $py scripts/exp_search_hybrid_ab.py --games 40 --suite core `
  --variants lucario200 lucario400 lucario400_k3 lucario400_blend02 --tag s1_luc
```

### Phase S2 — MCTS inference knobs only (checkpoint frozen)

```powershell
# Requires model_best.pth; eval via train smoke gate or package + harness
$env:LUC_SUBMIT_SEARCH_COUNT = "24"
$env:LUC_DETERMINIZATIONS = "2"
$env:LUC_PRIOR_BLEND = "0.2"
# then gate_lucario / custom harness — n=32 core
```

### Phase S3 — 1–2 train cycles with visit targets (only if S2 helps)

```powershell
& $py scripts/train_lucario_field_mcts.py --device cuda --cycles 2 `
  --search-count 24 --determinizations 2 --prior-blend 0.2 `
  --policy-target visits --games-per-opponent 16 `
  --work rl_mcts_field/lucarioex_search_hybrid_s3
```

---

## 5. Expected vs measured local gate lift

### 5.1 Measured (core suite: dragapult_sample + aboma + iono)

Audit: cg search **does fire** (~10% of try_search eligible; 36/36 fired when eligible).

| Variant | n=40 WR | n=48 WR | Pooled | Δ vs budget200 pooled |
|---------|--------:|--------:|-------:|----------------------:|
| budget200 (prod) | 11.7% | 16.7% | **14.4%** (38/264) | — |
| budget400 | 17.5% | 19.4% | **18.6%** (49/264) | **+4.2 pp** |
| lucario400 | 25.8% | 24.3% | **25.0%** (66/264) | **+10.6 pp** |
| lucario400_blend02 | 28.3% | 19.4% | unstable | do not ship |
| lucario400_k3 | 21.0% | — | — | worse than k=2 |
| lucario200 | 16.7% | — | — | budget matters for Lucario hybrid |

Reports: `eval/exp_search_hybrid_s0_budget_*.md`, `s1_luc_*.md`, `s0_confirm48_*.md`.

### 5.2 Measured MCTS inference (lucarioex_v2 `model_best.pth`, n=32 core)

| Variant | WR% | W/G | Wall | Note |
|---------|----:|----:|-----:|------|
| sc12 | **4.2%** | 4/96 | 48s | Old submit depth |
| sc20 | **5.2%** | 5/96 | 100s | +1.0 pp, 2× time |
| sc20_prior02 | **5.2%** | 5/96 | 115s | No lift vs sc20 |

Report: `eval/exp_mcts_infer_s2_infer_*.md`.

**Verdict:** v2 checkpoint is **far below** SearchScorer core (~14–19%) and LucarioSearch (~25%). Deeper sims / prior blend do **not** close the gap. **Do not ship MCTS** until a new train cycle with `policy-target visits` + field opponents beats SearchScorer on the same suite (R3). Deeper sims alone are insufficient (AlphaZero lesson: prior quality > raw sims at this scale).

### 5.3 Ship recommendation (local filter only)

1. **Next SearchScorer ladder probe:** `SEARCH_BUDGET_MS=400` (pooled **+4.2 pp** core). Keep HeuristicScorer spine.  
2. **Local champion for iteration:** `LucarioSearchScorer(budget=400, guard_k=2)` (**+10.6 pp** pooled) — **but** historical ladder LucarioSearch was **500.1 μ** ≪ SearchScorer 660.5; treat as **local research**, not auto-upload.  
3. **Reject:** guard_k=3, unstable blend02 without another n=48 confirm.  
4. **MCTS:** knobs landed; run S2 only when `model_best.pth` present; must beat SearchScorer on same suite (R3).

**Conservative ship target:** Search budget 400 → ladder re-probe; MCTS only if it **beats SearchScorer** on the same local suite.

---

## 6. Code touch list

| File | Change |
|------|--------|
| `agent/search_policy.py` | Env knobs + heuristic blend helper |
| `agent/lucario_mcts_runtime.py` | PUCT_C, DETERMINIZATIONS, PRIOR_BLEND, POLICY_TARGET; split single-det helper |
| `agent/lucario_mcts_policy.py` | Submit search=20; env knobs; prior wiring |
| `scripts/train_lucario_field_mcts.py` | CLI for new knobs + run_meta |
| `scripts/exp_search_hybrid_ab.py` | Small-n A/B harness |

**Not touched:** PUCT selection loop structure, reward scheme, deck lists, opponent pilots.

---

## 7. Stop rules

1. If S0/S1 show **no +1 pp** at n=40 → stop search budget work; pivot to Dragapult pilot / levers.  
2. If MCTS S2 costs clock forfeits → cap `SEARCH_COUNT×DETERMINIZATIONS ≤ 40` effective sims.  
3. Never upload SearchScorer variant with local full-suite collapse; never re-open Track B PPO.

---

## 8. Crustle mainline hybrid (2026-07-31 push)

**Context:** Live mainline is Crustle MissingNo #1 (`agent_decks/crustle_MissingNo_rank1.csv`)
with **RuleCore** package (`crustle_MissingNo_v1.tar.gz`). Lucario MCTS is side-quest only
(v2 infer ≤5.2% core — do not ship). Search budget 400 remains the best generic SearchScorer
knob (+4.2 pp pooled).

### 8.1 Research map → Crustle

| Literature idea | Crustle landing |
|-----------------|-----------------|
| Neural prior + PUCT | **Rules decision prior** replaces weak NN prior: vs-ex promote, Boss non-ex, energy homes |
| Visit-count π distillation | Deferred until MCTS beats RuleCore on same suite (R3); knobs already in runtime |
| IS-MCTS multi-det | MCTS-only; Crustle ships RuleCore±search (10 min clock) |
| Rules + shallow search | **CrustleSearchScorer** = RuleCore floor + cg search + prior top-k guard |

### 8.2 Code landed (no core-loop rewrite)

| File | Change |
|------|--------|
| `agent/crustle_levers.py` | `decision_prior_*` unified API (promote / Boss / energy) |
| `agent/search_policy.py` | `CrustleSearchScorer` + prior rank + guard_k + blend |
| `scripts/exp_search_hybrid_ab.py` | Variants: `crustle_rules`, `crustle200`, `crustle400`, `crustle400_k3`, `crustle400_blend015` |
| `scripts/package_submission.py` | `--scorer crustle_search` |
| `scripts/arena.py` | scorer name `crustle_search` |
| `tests/test_crustle_decision_prior.py` | Offline prior + import smoke |

### 8.3 Phase C0 — Crustle RuleCore vs hybrid (n=32 core)

```powershell
cd E:\PTCG_AI_Battle_Challenge\kaggle_pokemon
$py = "..\.venv\Scripts\python.exe"
& $py scripts/exp_search_hybrid_ab.py --games 32 --suite core `
  --hero-deck agent_decks/crustle_MissingNo_rank1.csv `
  --variants crustle_rules crustle200 crustle400 --tag crustle_s0
```

**Pass:** hybrid ≥ rules +2 pp overall **or** +5 pp on weakest matchup without ≤−2 pp elsewhere.  
**Ship:** only if hybrid clears pass **and** wall-clock safe (budget ≤400ms on promote only).  
**Default package stays `rulecore`** until C0 confirms.

### 8.4 Expected local gate lift (pre-measure)

| Variant | Expected Δ vs `crustle_rules` | Rationale |
|---------|------------------------------:|-----------|
| crustle200 | 0 to +2 pp | Sparse search fire; prior guard rejects bad overrides |
| crustle400 | **+2 to +5 pp** | Same pattern as Search budget 400 (+4.2 on Lucario core) |
| crustle400_k3 | noisy / − | Looser guard hurt Lucario hybrid |
| crustle400_blend015 | +0 to +2 pp | Soft prior mix; confirm n=48 if n=32 looks good |

MCTS deeper sims alone: **rejected** for ship (sc20 = sc20_prior02 = 5.2%).  
Expert-iteration next step only if a visit-target train cycle beats RuleCore on Crustle deck (unlikely short-term).

### 8.5 Decision prior contract (CardIDs)

| Lever | Priority |
|-------|----------|
| Promote | Crustle (345) vs opp Active **ex** ≫ Kangaskhan early draw ≫ Ogerpon vs Ability single-prize |
| Boss (1182) target | non-ex no-Ability > non-ex Ability > pure ex |
| Energy attach | Crustle 345 > Ogerpon 117 > Kangaskhan 756 > Dwebble 344 |

---

*End of plan.*
