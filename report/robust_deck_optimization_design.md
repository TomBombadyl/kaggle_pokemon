# Robust deck optimization — math, complexity, and GPU acceleration

**Goal (your words):** *win rate over anything* — find the deck that wins most
against the **whole field**, not just our 10 sparring partners. Known decks are fine.

Everything below is grounded in what the **PTCG AI Battle Challenge** actually gives
us. No generic hand-waving.

---

## 0. What the competition gives us (the ground truth)

| Thing the comp provides | What it means for this problem |
|---|---|
| **cabt engine** (`cg/` = `libcg.so` / `cg.dll`, compiled **CPU** library) | The game **only runs on CPU**. This single fact decides the whole acceleration story (see §5). |
| `battle_start/select/finish`, `search_begin/step/end`, `all_card_data()` | Our only ways to simulate games and look ahead. |
| **Agent contract:** `agent(obs_dict) -> list[int]`; deck phase returns **60 card IDs**; must **never crash**; **10 min / player / game** | The submitted brain must decide moves **within 10 min on Kaggle's (CPU) eval** — caps how heavy our pilot can be at *run* time. |
| **Deck rules:** 60 cards, ≤4 of a name (basic energy unlimited), 1 Ace Spec, ≥1 Basic; IDs from the **~2,022-card** DB | Defines the search space (§1) and legality filter. |
| **Simulation ladder** `pokemon-tcg-ai-battle`: episode-scored **μ** vs the field of **~2,090 teams' agents**; no private LB; **5 uploads/day, 2 Finals** | "Anything" = these ~2,090 **unknown** opponents. We can't query them — we must **approximate the field** (§3). |
| **Opponent proxies:** benchmark suite (4 anchor + 6 meta), sample agents (heuristic / search / RL-MCTS), public notebooks, **episode replays/logs** (`scripts/mine_episode_replays.py`) | These are the *only* legal stand-ins for the real field. Mined replay decks are the closest thing to "real opponents." |
| **Measured cost:** **23 ms / game / core** (heuristic pilot, this engine) | The unit of all our compute budgets. |

> **Key competition caveat (from `SUBMISSION_PLAYBOOK.md`):** *"Local random-gate win %
> does NOT predict ladder rank."* Beating random — or even beating a fixed 10 — does not
> mean robust. This is exactly why the objective and the opponent set must change.

---

## 1. The math: why you can't just search harder

**Deck space size.** Pick ~20 distinct non-basic-energy cards (≤4 each) from ~2,000
types, then split copies and energy:

```
distinct-card choices ≈ C(2000, 20) ≈ 4 × 10^47
× copy-count & energy arrangements  →  on the order of 10^50 legal decks (estimate)
```

- **Analogy:** there are ~10^50 atoms in the Earth. The deck space is **Earth-sized**.
  You will never enumerate it — search is the only option.

**The objective is a game, not a number.** "Best vs anything" is not "highest average."
Think of a giant table `M[i][j] = P(deck i beats deck j)`. The deck you want is the
one whose **worst column is least bad** — the **maximin** deck. Formally it lives in the
support of the **Nash equilibrium** of the deck-vs-deck zero-sum meta-game.

- **Analogy:** rock-paper-scissors. "Rock" has a great average if everyone plays scissors,
  but it's *exploitable*. The robust answer is a **mix** that no opponent can hard-counter.
  Optimizing the **mean** vs a fixed suite = building "Rock." Optimizing **maximin/Nash** =
  building the un-exploitable mix.

---

## 2. The complexity (where the hours go)

Two independent cost drivers:

**(A) Searching decks** — the outer GA/RL loop over a 10^50 space. Handled by smart
search (mutation/crossover/RL), not enumeration.

**(B) Estimating win rates** — the silent killer. Win rate from `n` games has standard
error `≤ 0.5/√n`:

| To resolve… | Games needed per matchup |
|---|---|
| 50% vs 60% (coarse) | ~100 |
| 50% vs 52% (fine, ladder-relevant) | **~2,500** |

**(C) The payoff matrix** — ranking `D` candidate decks against `D` opponents at fine
resolution:

```
D × D × 2,500 games.   D = 100  →  2.5 × 10^7 games
@ 23 ms/game, 12 cores (≈520 games/s)  →  ≈ 13.4 hours   (labeled estimate)
```

This **O(D²·G)** wall is the real enemy — not "the GPU is too slow." Beating it needs
three moves: **prune the matrix** (surrogate, §5), **reduce variance** (§4), and
**parallelize sims** (§5).

---

## 3. Defining "anything" honestly (the field)

We cannot run games against the 2,090 ladder agents. We approximate the field with a
**gauntlet** built only from competition-provided sources, weighted toward realism:

1. **Mined replay decks** — real opponents from downloaded episode logs (highest signal;
   `replay_index.csv` is wired but empty until you download replays).
2. **Sample + public agents** — heuristic, Search, RL-MCTS brains the comp/community ship.
3. **Benchmark suite** — the 4 anchor + 6 meta proxies (Dragapult, Crustle, Bellibolt,
   Alakazam, Greninja, Mega Greninja).
4. **Self-play elites** — strong/diverse decks our own search produces (co-evolution).

**Anti-overfit rule:** always hold out part of the gauntlet. Report win rate vs the
**held-out** slice — that is the honest proxy for "vs anything." Improving train-gauntlet
win rate while held-out stalls = overfitting (the "Rock" trap).

---

## 4. Variance control (so a "win" isn't luck)

Grounded in engine features we already have:

- **Common Random Numbers (CRN):** evaluate two decks on the **same seeded opening
  hands/shuffles** (engine seed arg in `evaluate_deck_vs_benchmark`). Cancels luck →
  same confidence with far fewer games. Deterministic RNG is already a project rule.
- **Sequential testing (SPRT):** already in `scripts/` — stop a matchup early once it's
  clearly won/lost instead of always playing 2,500.
- **Smart game allocation (bandits):** spend games where the ranking is *close* or the
  opponent is *high-weight*; don't waste 2,500 games proving a 90% matchup. (Successive
  halving / UCB over candidates.)

These routinely cut required games **5–20×** (labeled estimate) at the same confidence.

---

## 5. What CUDA / NVIDIA can and cannot do here (the honest part)

> ⚠️ **The cabt engine is a compiled CPU library.** The game simulation itself **cannot
> run on the GPU** without re-implementing the whole rules engine. Anyone who tells you
> "just put it on CUDA" is wrong about *this* competition. The simulation stays on CPU.

**CPU does the simulating (the workhorse):**
- Game sims via `ProcessPoolExecutor` across **all cores** (already used). This is where
  the 23 ms/game throughput lives. Scale = more cores, not a bigger GPU.

**GPU does the *thinking around* the sims (offline):**

| GPU use | NVIDIA tooling | Payoff |
|---|---|---|
| **Win-rate surrogate** — train a net `f(deckA_feats, deckB_feats) → P(A beats B)` on simulated matchups, then **predict the whole D×D matrix** and only simulate the **uncertain/high-impact** cells | **PyTorch CUDA** (+ AMP) | **Biggest win.** Turns O(D²·G) sims into O(D·k·G) + cheap GPU inference. Features come straight from `all_card_data()` (HP, type, attacks, cost, damage, weakness). |
| **Meta-game solver** — compute the maximin/Nash mixture from the payoff matrix (LP or regret-minimization / CFR) | **PyTorch / CuPy** | Matrix algebra; trivial on GPU even for large D. |
| **Offline pilot training** — the MaskablePPO policy (Loop B) and the Lucario MCTS transformer | **PyTorch CUDA**, CUDA Graphs | Already GPU; this is the legitimate "training" GPU load. |
| **Batched policy inference during *offline* eval** — if the gauntlet uses a neural pilot, batch its forward passes | **PyTorch CUDA** | Helps only when the pilot is a net; the heuristic pilot is already 23 ms/game on CPU. |
| Deck featurization / clustering / dedup | **CuPy / Numba-CUDA** | Minor. |

**Not applicable (don't waste time on it):** the NVIDIA **Omniverse / Isaac / Cosmos**
stack (those skills are for robotics/physics sim, not card games). For *this* problem
"NVIDIA acceleration" = **PyTorch-CUDA + CuPy/Numba-CUDA**, plus CPU multiprocessing for
the engine.

**Run-time vs train-time (critical):** Kaggle scores the submitted agent on its **CPU**
eval within **10 min/game**. So the **deployed** brain must be CPU-fast (heuristic, Search,
or a **small distilled** net). All the GPU work above is **offline preparation** — it picks
the deck and trains/distills the pilot; it does **not** run inside the submission.

---

## 6. The organized architecture (PSRO / double-oracle)

This is the textbook structure for "robust strategy in a huge game," mapped onto our loops:

```
        ┌─────────────────────────────────────────────────────────┐
        │  META LOOP  (empirical game theory, GPU)                 │
        │  • payoff matrix M[i][j] = P(i beats j)  (sparse, learned)│
        │  • solve maximin / Nash mixture over opponent population  │
        └───────────────┬─────────────────────────────────────────┘
                        │  current opponent distribution σ
                        ▼
        ┌─────────────────────────────────────────────────────────┐
        │  BEST-RESPONSE ORACLE  (our search, CPU+GPU)             │
        │  • Loop C deck GA  /  Loop B policy RL                    │
        │  • objective = maximin/CVaR win rate vs σ  (not the mean) │
        │  → produces a new deck that beats the current field      │
        └───────────────┬─────────────────────────────────────────┘
                        │  add new deck to population
                        ▼
        ┌─────────────────────────────────────────────────────────┐
        │  EVALUATION FARM                                         │
        │  • CPU process pool runs cabt games (23 ms/game/core)    │
        │  • GPU win-rate surrogate prunes which matchups to sim   │
        │  • CRN + SPRT + bandit allocation cut games 5–20×        │
        │  → fills/updates M, retrains surrogate                   │
        └─────────────────────────────────────────────────────────┘
                        │  repeat until the mixture stops changing
                        ▼
              robust deck (+ distilled CPU pilot) → package → ladder probe
```

- **Double-oracle / PSRO** provably drives the mixture toward the **robust (Nash)**
  strategy and only ever needs **best responses** — never the full 10^50 space or full
  D×D matrix.
- **Maps cleanly to the repo:** the deck GA (`rl/train_deck_campaign.py`) is the
  best-response oracle; `lane_elites.json` is the seed of the opponent population; we add
  the **payoff matrix + meta-solver + surrogate** on top.

---

## 7. Phased plan (each phase re-measured, per project rules)

| Phase | Change | Grounded in | GPU? | Risk |
|---|---|---|---|---|
| **A** | Objective → **maximin/CVaR** over an **expanded gauntlet** (benchmark ∪ self-play elites ∪ sample agents) + held-out validation | §1, §3; reuse `lane_elites.json` | no | low |
| **B** | **Payoff matrix + meta-solver** (PSRO mixture as opponent distribution) + **CRN/SPRT/bandit** game allocation | §4, §6; SPRT already in repo | small (solver) | med |
| **C** | **GPU win-rate surrogate** to prune the O(D²) matrix (active learning) | §5; features from `all_card_data()` | **yes** | med |
| **D** | **Mine real ladder replays** into the gauntlet; distill a **CPU-fast** pilot for the 10-min limit | §0, §3; `mine_episode_replays.py` | train only | med |

**Start at A** — it's the change that most moves "win rate vs anything," needs no new
infra, and tells us whether the objective swap alone helps before we build the surrogate.

---

## 8. How we'll know it worked (metrics, comp-grounded)

- **Held-out maximin win rate** — min win rate vs gauntlet decks we did **not** train on.
  This is the offline stand-in for ladder robustness.
- **Exploitability** — run the best-response oracle *against our chosen deck*; how high can
  it push its win rate? **Lower = more robust** (closer to Nash).
- **Confidence on every number** — report games played + 95% CI; never quote a bare win %.
- **Ladder truth** — final check is μ on `pokemon-tcg-ai-battle` (5/day, pick 2 Finals).
  Local numbers only *predict*; the ladder *decides*.

---

*Engine integration, the 23 ms/game figure, deck legality, and the API/contract facts in
§0 were verified against the repo's `data/sim/sample_submission/cg` engine and the
competition docs (`CABT_API.md`, `SUBMISSION_PLAYBOOK.md`, `EVAL_PROTOCOL.md`). Deck-space
and games-needed figures are labeled estimates derived from the ~2,022-card DB and the
standard-error formula. Throughput estimates assume ~12 CPU cores; adjust to your box.*
