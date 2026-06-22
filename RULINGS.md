# RULINGS — what we tried, what happened, and the standing decisions

**Purpose.** This is the single, durable record of every approach we have tried in this
competition, the *measured* outcome, and *why* it worked or failed. It exists so that we can
delete dead code without losing the lesson, and so we never re-run a failed experiment by
accident. It replaces the ~15 scattered handoff/instruction files and the 157 KB append-only
`PROGRESS.md`.

**How to use it.**
- Part 1 is the **honest scoreboard** (measured ladder μ).
- Part 2 records **what we tried**, organized by category, each with a verdict.
- Part 3 is the **standing rulings** — decisions that constrain future work.
- Part 4 is the **grounded game/competition facts** (rules, scoring, information model).
- Part 5 is the **graveyard index** — what was deleted and how to resurrect it.

Every claim here cites its evidence. If a row has no evidence, it is an **assumption** and is
labelled as such. *Do not add unmeasured claims to Parts 1–4.*

Snapshot of the pre-reset repo: branch `graveyard/pre-reset-20260622`, commit `5a17cfe`.

---

## Part 1 — The honest scoreboard (measured ladder μ)

Source: `report/submission_log.csv`, `report/ladder_history.csv` (as of 2026-06-22).
Field scale for context: **top ~1350, mid-pack ~1100+** (`data/META_NOTES.md`). Everything we
have shipped sits at **~490–668 μ — well below mid-pack.**

| Rank | Agent (brain × deck) | Best μ | Verdict |
|------|----------------------|-------:|---------|
| 1 | **SearchScorer × real Mega Lucario ex** | **668** | Best home-grown result. 54.5% WR over 33 episodes. |
| 2 | **Imported public rule-based Alakazam ("ryotasueyoshi best5")** | **659** | *Someone else's notebook.* Beat our own deck-search line decisively. |
| 3 | HeuristicScorer × Kyogre (a2_kyogre_33) | 633 (peaked 672.7) | Simple hand-tuned rules. |
| 4 | SearchScorer × Kyogre+2e | 626 | |
| 5 | SearchScorer × Trevenant control leader | 615.6 | |
| 6 | SearchScorer × gen19 fast-basic (deck-RL output) | 598.8 | Best deck-RL deck — still below heuristic Kyogre. |
| 7 | LearnedScorer (Track B PPO+distill) × RL-deck | 585.1 | Best *learned* policy; still below hand-tuned rules. |
| 8 | SearchScorer × Abomasnow+4e | 548.6 | |
| 9 | "Lucario v2" Search probe | 500.1 | **Same agent earlier read 734.6.** See Ruling R1. |
| 10 | LearnedScorer × Alakazam (shared-distill bug) | 490.4 | Distill trained on wrong deck. |
| 11 | LearnedScorer × Dragapult | 468.9 | |
| 12 | LucarioMCTSScorer (RL+MCTS, early iter) × Lucario | 324.6 | Empty-bench losses; retired. |

**The one-sentence summary of 43 sessions:** *every reinforcement-learning, distillation, and
MCTS approach we built underperformed simple hand-tuned rules and search — and the single best
agent on our board was an imported public rule-based notebook.* That is the central fact the
rebuild must reckon with.

---

## Part 2 — What we tried, by category

### 2A. Agents / "brains" (the decision policy)

| Brain | What it is | Result | Verdict |
|-------|-----------|--------|---------|
| HeuristicScorer | Hand-tuned MAIN priority + context handlers (`agent/agent.py`) | 633 μ on Kyogre | **KEEP (baseline).** Simple, stable, our 3rd-best. |
| SearchScorer | Heuristic + shallow `search_*` rerank | 668 μ on Lucario | **KEEP (baseline).** Our best home-grown. |
| LucarioScorer | Port of public Lucario sample policy + smart bench | 600 (only 2 episodes) | Inconclusive; deck-specific. |
| RuleCoreScorer + deck_tech | Generic brain + per-deck "tech" overrides | Public gate 9–15% | **FAILED.** Crustle matchup never cleared ~15%. Over-engineered. |
| LearnedScorer (Track B) | MaskablePPO trained on one deck, distilled to npz | 469–585 μ | **FAILED to beat rules.** Per-deck retrain required; shared distill = bug. |
| LucarioMCTSScorer | RL policy + MCTS at inference | 324.6 μ | **FAILED.** Slow, empty-bench losses, early-iter checkpoint ≠ ladder. |
| AZ (AlphaZero port) | Self-play MCTS + policy/value net (`rl/az_train.py`) | Public L1 gate 9.7% | **FAILED.** Overfit to 1–2 training opponents; never gated. |

**Cross-cutting lesson:** none of the learned/search-heavy brains beat hand-tuned rules on the
ladder. Reasons recur: (a) trained/evaluated against the wrong opponents (random, mirror-only,
or `pool_*` proxies), (b) local win-rate did not predict μ, (c) checkpoints shipped before
gating, (d) latency/stability problems at inference.

### 2B. Decks / archetypes

Real-meta lists (mined from competition episodes) — these are the field, keep them:
`real_mega_lucario_ex`, `real_dragapult_ex`, `real_mega_abomasnow_ex`, `real_iono`,
`top_mined_{alakazam,trevenant,dragapult_ex,iono,mega_abomasnow_ex,mega_lucario_ex}`.

| Deck | Best result | Verdict |
|------|-------------|---------|
| Mega Lucario ex (real) | 668 μ (Search) | **Field wall + our best.** Both deck-search and RL pilots failed *against* a Lucario-dominated field. |
| Alakazam (single-prize aggro) | 659 μ (imported pilot) | **Strong when piloted well.** Our own pilots lose the Iono matchup (~13–30%). Pilot, not deck. |
| Kyogre (big-basic Water) | 633 μ | Stable, simple, good heuristic pilot. |
| Trevenant control | 615.6 μ | Mid. |
| Mega Abomasnow ex (Water) | 548.6 μ | Original "deck_concept_v1"; mediocre. |
| `pool_*` proxy decks (Crustle, Bellibolt, Greninja, …) | n/a | **RETIRE as eval opponents.** Memory + docs: worse than the real mined field; gating on them mispredicted μ. |
| deck-RL / GA outputs (gen19, robust_*) | 598.8 μ best | **Did not beat hand-built Kyogre.** Blind GA was collapse-prone. |
| `search_variants/*` energy-grid decks | ≤626 μ | Minor; the +2e Kyogre variant was the useful one. |

### 2C. Optimization loops / RL machinery

| Loop | Files | Verdict |
|------|-------|---------|
| Track A — rules + shallow search | `agent/{agent,evalfn,search_policy}.py`, `scripts/deck_search.py`, `gate_track_a.py` | **KEEP, slim down.** Source of every result ≥615 μ. |
| Track B — per-deck PPO + distill | `rl/{train_rl,train_ppo,cabt_env,league}.py`, `scripts/{distill_policy,train_track_b_deck,gate_track_b}.py` | **RETIRE.** Best output 585 μ < rules; high complexity. Lessons captured; code to graveyard. |
| Track C — deck GA / "robust deck search" | `rl/{deck_genome,deck_balance,train_deck_campaign,robust_search,robust_fitness,winrate_surrogate,meta_solver}.py`, `report/{deck_rl,robust_deck_rl*}` (~180 files) | **RETIRE.** Blind GA collapse-prone; outputs never beat hand decks. Replace with scoped, field-evaluated search (Pillar 4). |
| Lucario RL+MCTS notebook | `agent/lucario_mcts_*.py`, `notebooks/lucario/` | **RETIRE.** 324.6 μ; deferred indefinitely. |
| AZ self-play | `rl/az_train.py`, `report/az/` | **RETIRE.** Failed public gate; revisit only after Pillars 0–3 exist. |

### 2D. Validation / evaluation methods (the trust problem)

| Method | Verdict |
|--------|---------|
| Local win-rate vs `pool_*` proxy decks | **DISTRUST.** Repeatedly failed to predict μ (own docs: "local pool WR does not predict μ"). |
| Local win-rate vs *real mined* field + public agents (`gate_vs_public.py`) | **Closer, still imperfect.** Best local predictor we have; even it underrated Kyogre (13% local → 672 μ). |
| Self-play vs random / mirror-only | **INVALID for ladder.** Caused every RL overfit. Never use as a ladder proxy. |
| Kaggle ladder μ (after COMPLETE + ~40 min) | **GROUND TRUTH** — but slow, noisy early (high σ), and capped at 5 uploads/day. |
| Episode replay mining | **Underused golden ticket.** Scripts exist but ran on empty inputs (Kaggle egress blocked in sandbox). Pillar 0 fixes this. |

---

## Part 3 — Standing rulings (decisions that bind future work)

> These are the durable "rules of the game" for *us*. Change them only with measured evidence,
> and record the change here.

- **R1 — Trust no single μ reading.** A score is N(μ, σ²); early σ is large. The same Lucario
  agent read **734.6 then 500.1**. Require **≥2 readings ≥40 min apart**, and prefer agents whose
  μ is *stable*, not peak. (Evidence: submission_log, memory `never-assume-scores`.)
- **R2 — The real field is the only valid opponent set.** Gate against *mined real decks +
  imported public agents*, never `pool_*` proxies or random/mirror self-play. (Evidence: 2D.)
- **R3 — Rules/search is the proven floor; an ML method must beat it on the ladder to ship.**
  Nothing learned has beaten hand-tuned rules yet. New ML ships only after it clears the
  best rule-based μ on the *real-field gate* AND a ≥2-reading ladder probe. (Evidence: Part 1.)
- **R4 — Pilot dominates deck.** The same archetype swings 300+ μ on pilot quality (Alakazam
  490→659). Invest in the decision policy before chasing exotic decks. (Evidence: 2B.)
- **R5 — This is an imperfect-information game.** Opponent hand/deck/prizes are hidden (Part 4).
  Use determinized / information-set search + belief modeling, never naïve perfect-info minimax.
- **R6 — No in-game online learning.** Kaggle calls `agent(obs)` once per decision under a
  10-min/player clock with no training API and no torch in the tarball. "Online learning" means
  **between-submission daily retrain**, not in-match weight updates. (Evidence: Part 4, META_NOTES.)
- **R7 — Never crash; always return a legal selection.** A single exception forfeits the game;
  validation failure = ERROR (no ladder). Bench ≥1 Basic whenever legal (empty-bench → `no_active`
  loss was a real μ sink). (Evidence: COMPETITION_SCORING, repo_cleanup_plan.)
- **R8 — Every reported win-rate carries its metadata.** game count, opponent set, seed policy,
  deck path, brain name — or it does not count.
- **R9 — Margin/speed do not change μ.** Per-episode μ moves on W/L/draw only. Optimize win
  probability and stability, not blowout margin. (Evidence: COMPETITION_SCORING.)
- **R10 — One source of truth per concern.** Decisions → this file. Current state/next action →
  `STATE.md`. System design → `ARCHITECTURE.md`. Game/API facts → `data/` canon. No new
  top-level handoff/instruction files. (This ruling exists to prevent the sprawl we just cleaned.)

---

## Part 4 — Grounded game / competition facts

Cite the source doc; do not paraphrase from memory.

### Competition shape (`data/CABT_API.md`, `README.md`, `data/OFFICIAL_*`)
- Two sibling competitions. **Strategy** (this repo's primary, ends **2026-09-14**) is judged on
  agent stability, deck-design concepts, simulation performance, and a written report. The
  **Simulation** ladder (ends ~2026-08-16/17) is the live TrueSkill Elo that produces μ.
- Organizers: The Pokémon Company × HEROZ × Matsuo Institute. ~2,000-card Standard format.
- **Per-player clock: 10 minutes total per game.** Running out = immediate loss.

### Agent contract (`data/CABT_API.md`)
- `agent(obs_dict) -> list[int]`, called once per decision. Returns 0-based indices into
  `obs["select"]["option"]`, with `minCount ≤ len ≤ maxCount`, distinct, in range.
- **Deck-selection phase:** when `select` and `current` are both `None`, return **60 card IDs**.
- `select.type` (11 kinds: MAIN, CARD, ENERGY, ATTACK, EVOLVE, YES_NO, …) and `select.context`
  (49 purposes: MAIN, SETUP_*, SWITCH, ATTACK, EVOLVE, DISCARD, MULLIGAN, …) drive a
  per-context dispatch — the proven structure for a rule-based pilot.

### Information model — **imperfect information** (`data/CABT_API.md:38-44`)
> **This is the load-bearing correction for the rebuild.**

| Visible to us | Hidden from us |
|---------------|----------------|
| Our full hand | **Opponent hand → count only (`handCount`)** |
| Both actives, both benches | **Both deck orderings (`deckCount` only)** |
| Both discards, attached energy/tools | **Face-down prizes (`None`)** |
| Stadium, status conditions, turn flags | Opponent's hidden choices until revealed |

Implications: opponent's *board* (what they've committed) is public; their *resources* (hand,
draw, prizes) are private. Correct algorithms operate over **information sets / belief states**,
not a single known opponent state. **TODO (Pillar 1): verify this empirically against the local
engine (`cg.dll`/`libcg.so`) before building on it** — the API doc is mostly official but we no
longer take any load-bearing fact on trust.

### Scoring (`data/COMPETITION_SCORING.md`)
- Each submission's skill = Gaussian **N(μ, σ²)**. Per **episode** (one game vs one opponent),
  μ moves on **win/loss/draw only**; magnitude scales with surprise and current σ. **Margin and
  speed do not enter the μ update.** New agents get heavy episode volume (σ shrinks fast).
- μ ≈ 600 at COMPLETE is the *initialized* rating after a self-validation episode, **not** field
  performance. Real movement after ~40 min.
- Operationally tempo still matters: a fast loss is still a loss, and weak agents simply lose
  more episodes — so reduce loss modes (deck-out, `no_active`), don't chase blowouts.

### Submission limits (`data/SUBMISSION_PLAYBOOK.md`, `data/COMPETITION_SCORING.md`)
- **5 uploads / team / day.** **2 Final Submissions** count for final placement — *manually
  select them*; auto-select may pick the latest two, not your best two. "Disabled" ≠ timeout.

### Meta facts (`data/META_NOTES.md`)
- **Deck choice + clean piloting dominate** rule-based quality; simple linear gameplans beat
  fragile combo decks for a heuristic pilot.
- **Meta is rock-paper-scissors and shifts fast** (historic Crustle anti-ex spike → non-ex
  attackers gained). This is *why* we need a daily meta tracker (Pillar 2).
- **Single-prize aggro (Alakazam + Dudunsparce)** is a live, strong archetype.

---

## Part 5 — Graveyard index (deleted code, how to get it back)

Everything below was removed from `main` during the Session-44 reset. Full content is preserved
at branch **`graveyard/pre-reset-20260622`** (commit `5a17cfe`). To inspect or restore:

```bash
git show graveyard/pre-reset-20260622:<path>            # view one file
git checkout graveyard/pre-reset-20260622 -- <path>     # restore one file
git log graveyard/pre-reset-20260622                    # full pre-reset history
```

| Removed | Why (ruling) | Lesson captured in |
|---------|--------------|--------------------|
| Track B PPO/distill (`rl/train_rl.py`, `train_ppo.py`, distill scripts, `agent/learned_policy.py`) | R3 — never beat rules | 2A, 2C |
| Deck GA / robust search (`rl/deck_*`, `robust_*`, `meta_solver`, `winrate_surrogate`; `report/{deck_rl,robust_deck_rl*}`) | R3/R4 — collapse-prone, never beat hand decks | 2C |
| Lucario RL+MCTS (`agent/lucario_mcts_*`, `notebooks/lucario/`) | 324.6 μ; retired | 2A |
| AZ self-play (`rl/az_train.py`, `report/az`) | failed public gate | 2A |
| `pool_*` proxy decks | R2 — invalid opponents | 2B/2D |
| ~15 top-level handoff/instruction `.md`, scattered `report/*plan*.md` | R10 — sprawl, superseded | this file + STATE.md |

*(The prune commit lists exact paths; this table is the rationale.)*
