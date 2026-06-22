# ARCHITECTURE — the rebuilt system, all pillars on one foundation

**Why this document exists.** The last 43 sessions produced disjointed experiments because each
ran on its own opponents, its own eval, and its own scratch files. This design fixes that by
forcing **every pillar to stand on one shared foundation** (Pillar 0): one card/rules model, one
real-field opponent set, one episode pipeline, one trustworthy eval harness. The pillars then
specialize, but they all *measure* the same way and *speak* the same data formats.

Read `RULINGS.md` first for *why* (the evidence). This file is *what we build and in what order*.

---

## The thesis (grounded, not guessed)

1. **Rules/search is the proven floor (μ ≈ 668).** Any new method must beat it on the real-field
   gate before it ships (Ruling R3). So we keep a strong rule-based pilot as the spine and grow
   capability *on top of it*, never replacing it speculatively.
2. **This is an imperfect-information game** (Ruling R5). The decision policy must reason over
   *belief states*, not a known opponent state. The correct tool family is **determinized /
   information-set search** (ISMCTS, PIMC) with **opponent/belief priors learned from episode
   data** — the same family that powers strong Poker/Bridge/Skat/Hanabi AIs. This is the
   single biggest source of untapped ceiling, and it is standard game-AI, not invention.
3. **Pilot dominates deck** (Ruling R4). Decision quality first; deck discovery second, scoped
   and field-evaluated; both validated against the same field.
4. **The episode data is the golden ticket** and has been wasted. The foundation turns it into:
   (a) the opponent set we gate on, (b) the belief priors the agent uses, (c) the daily meta map.

---

## Pillar 0 — Foundation (shared infra). *Build first; everything depends on it.*

The contract that makes the rest cohesive. Four components.

### 0.1 Card & rules model — `core/`
A single, verified, typed model of the game, used identically in training, search, and eval.
- `core/cards.py` — load `data/EN_Card_Data.csv` into a typed registry (HP, types, attacks,
  energy cost, abilities, evolution lines, rule-box flags like *ex/Mega*). One loader, cached.
- `core/engine.py` — thin, tested wrapper over the local `cg` engine (`battle_start`,
  `battle_select`, `search_*`). All engine access goes through here so quirks live in one place.
- `core/obs.py` — typed parse of `obs_dict` into our `Observation` (what's public vs. hidden,
  per Part 4 of RULINGS). **First task: a test that empirically confirms the information model**
  (opponent hand = count only, prizes face-down) against the live engine. No load-bearing fact
  on trust ever again.
- `core/rules_notes.md` — the consolidated, *verified* rules digest (replaces scattered
  `data/*` rule docs; those become source citations).

### 0.2 Real-field registry — `field/`
The opponents we are allowed to evaluate against (Ruling R2). No `pool_*`, no random, no mirror.
- `field/decks/` — the mined real-meta lists (`real_*`, `top_mined_*`), each validated.
- `field/agents/` — imported public agents (e.g. the Alakazam best5 notebook) as gate opponents.
- `field/registry.json` — single index: deck ↔ archetype ↔ source episode ↔ public-agent binding.
- Updated by Pillar 2 daily; consumed by everyone.

### 0.3 Episode pipeline — `episodes/`
Turns the daily Kaggle dumps into structured truth. **Runs on the user's machine (has Kaggle
egress); sandbox is offline** (Ruling R6 context).
- `episodes/pull.py` — pull leaderboard snapshot, our submissions, and new episode replays
  (the existing `scripts/update_from_kaggle.py` is the seed; fold it in).
- `episodes/parse.py` — replay JSON → per-game records (decks, archetypes, turns, win condition,
  per-decision state/action). One schema, documented.
- `episodes/store/` — partitioned parquet/jsonl, append-only, deduped by episode id.
- Outputs feed: the field registry (0.2), belief priors (Pillar 3), the meta map (Pillar 2),
  and behavior-cloning data if/when we revisit learned policies.

### 0.4 Eval harness — `eval/`
The one way we measure anything (Rulings R1, R2, R8).
- `eval/harness.py` — run brain×deck vs the **field registry**, seeded, side-swapped; emits a
  result row with full metadata (games, opponents, seeds, deck, brain, Wilson CI).
- `eval/gates.py` — the gate pyramid, real-field only:
  - **L0** legality/smoke (never crash; always legal; bench guard).
  - **L1** vs real-field decks + public agents, N≈30/opp, Wilson CI.
  - **L2** SPRT vs the current shipped champion (does the candidate *beat the floor*?).
  - **L3** ladder probe — **≥2 μ readings ≥40 min apart** (Ruling R1), recorded to the log.
- `eval/ladder_log.csv` — replaces the scattered submission/ladder CSVs; one append-only log.

> **Definition of "validated" for this repo:** passed L0–L2 on the real field, then L3 with two
> stable μ readings. Nothing ships otherwise. This single definition is what we were missing.

---

## Pillar 1 — Game & rules mastery. *Depends on 0.1.*

Goal: we actually understand the game well enough to encode correct play, and we can prove it.
- Verify the information model and core mechanics empirically (the `core/obs.py` test above).
- Encode the high-value rules a pilot must respect: prize math (single- vs 2-prize trades),
  energy attachment economy, evolution timing, retreat cost, status, ability windows, the
  ex/Mega rule-box interactions (the Crustle "immune to ex/Mega" class of effect).
- Deliverable: `core/rules_notes.md` + a suite of unit tests asserting engine behavior on a
  handful of canonical interactions. This is what lets every other pillar trust the simulator.

---

## Pillar 2 — Daily meta tracker. *Depends on 0.2, 0.3.*

Goal: *every day*, know what the field is playing and what beats it (Ruling — meta shifts fast).
- `meta/build_map.py` — from `episodes/store`: cluster opponents into archetypes, compute the
  **archetype × archetype win matrix** and population shares (who's popular, who's winning).
- `meta/whatbeatswhat.py` — given the current population, rank our candidate decks by **expected
  win rate against the field mixture** (not vs a single deck). This is a simple, correct objective:
  `E[win] = Σ_a share(a) · winrate(ours, a)`.
- Output: `field/registry.json` refresh + a dated `meta/reports/meta_YYYYMMDD.md` (one file per
  day, not fifteen). Feeds Pillar 4's objective and Pillar 3's opponent prior.
- Automatable later via `/schedule` once the pull is trusted.

---

## Pillar 3 — The decision policy (the MDP). *The ceiling. Depends on 0.1, 0.4, 2.*

This is where the real points are, and where we have been weakest. Framed correctly:

**The problem.** A turn is a sequence of `select` decisions in a **partially observable** game.
Formally a POMDP; in game-AI terms, we act on an **information set** (everything consistent with
what we've observed) rather than a known state.

**The approach (staged, each stage must beat the previous on the field gate):**

1. **Strong rule-based pilot (the spine).** Keep/clean the best of the current Heuristic/Search
   brains into one `agents/pilot.py` with a clean per-`context` dispatch and the bench guard.
   This is the floor every later stage must beat. *Ship this first* — it's already worth ~633–668.
2. **Bounded perfect-info lookahead (our side).** Use the engine's `search_*` to evaluate *our*
   candidate action sequences within the turn (we know our own hand) under a static-but-strong
   `eval/board_value`. This is well-defined and cheap and already partly exists (SearchScorer).
3. **Determinized opponent search (PIMC).** When the opponent's hidden resources matter, **sample
   K determinizations** of their hidden hand/deck consistent with (a) public info and (b) the
   meta deck prior from Pillar 2, run the lookahead against each, and average. This is *Perfect
   Information Monte Carlo* — the standard, debuggable first step for imperfect-info games.
4. **Information-Set MCTS (ISMCTS)** if PIMC's known weaknesses (strategy fusion, no information
   gathering) cost us measurable μ. Same belief sampler, proper tree search over information sets.
5. **Belief/opponent model from data.** Replace the uniform determinization prior with a learned
   prior: P(opponent hand/deck | public state, archetype) estimated from `episodes/store`. This is
   where episode data finally pays off, and where a learned component can *augment* (not replace)
   search — the only ML role Ruling R3 currently endorses, because it's gated by the search around it.

**Time budget (Ruling — 10 min/player):** every stage is anytime and depth/sample-capped; latency
is a first-class gate in L0. We never ship a brain that can time out.

**Why this order is correct, not guessed:** it's the textbook progression for imperfect-info game
AI (heuristic → determinized search → information-set search → learned belief priors / ReBeL-style),
each step independently shippable and independently measurable against the floor.

---

## Pillar 4 — Discovery deck search. *Depends on 0.4, 2. After Pillar 3 floor ships.*

Goal: find decks that beat the *current field mixture*, scoped intelligently — replacing the
blind, collapse-prone GA that never beat hand decks (Ruling R3/R4).

- **Objective (from Pillar 2):** maximize `E[win vs field mixture]` for a *fixed strong pilot*,
  so we measure the deck, not a confounded deck+brain.
- **Scoping (the user's instinct, formalized):** search within a legal, type-coherent shell
  (one energy type / a defined archetype skeleton), so the combinatorial space is tractable and
  every candidate is pilotable. Colorless/toolbox shells get a wider budget.
- **Method:** treat it as **best-arm identification under noisy evaluation** — successive
  halving / Hyperband over candidate lists, with Wilson/SPRT to spend simulation budget on the
  contenders, not the whole population. Local search (card swaps) around the elites. This is the
  mathematically honest version of "try lots of combinations smartly."
- **Guardrail:** every surviving deck is validated by Pillar 0's harness against the real field
  before it's allowed near a ladder slot.

## Pillar 5 — Continual / "online" learning. *Honestly scoped (Ruling R6).*

There is **no in-game learning** (no training API, no torch in the tarball, 10-min clock). So
"learning after every game" means a **daily between-submission loop**, which we *can* do well:

```
nightly: episodes/pull → parse → meta/build_map → refresh field registry & belief prior
         → re-run eval gates on champion + contenders → surface the single best next submission
```

- The belief/opponent prior (Pillar 3.5) and the meta map (Pillar 2) are the things that update
  daily from new data — that's the real, legitimate "continual learning" signal.
- If we later want a learned policy/value net, it is trained offline from `episodes/store`
  (behavior cloning + self-play), distilled to npz, and **must clear Ruling R3** before shipping.
- This pillar is mostly *orchestration* (`/schedule` a cron) once Pillars 0–2 are trustworthy.

---

## Per-deck agent template (standard for every archetype)

**Invariant:** one deck, one brain, matchup **levers** — never a separate full agent per opponent.

Every future Pokémon/deck we train (Lucario, Alakazam, Dragapult, …) follows the same stack:

| Layer | Start from | Role |
|-------|------------|------|
| **1. Rule pilot** | Official Kaggle sample for that archetype (e.g. kiyotah Lucario notebook → `agent/lucario_policy.py`) | Legal, never-crash spine; encodes how *this* deck is meant to be played |
| **2. Deck tech** | `agent/deck_tech.py` — gust/draw/search/stadium/setup priorities for *our* 60 | Small card-ID tables; not a second brain |
| **3. Matchup levers** | Opponent archetype detected from **visible** board (active/bench IDs) → tag | Thin score deltas (Boss timing, bench depth, race vs control, wall-breaker line) — not RuleCore-style per-opponent agents |
| **4. Optional search** | `SearchScorer` / shallow `search_*` on high-value contexts | Only after rules are stable; must beat rules-only on L1 gate |
| **5. Optional RL+MCTS** | Official RL+MCTS sample + **field** training (`scripts/train_*_field_mcts.py`) | Real opponent deck in `search_begin`; train vs `field/decks/`; champion gate; **LucarioScorer fallback** at inference |

**Bootstrap order for a new deck:**
1. Pull/import the organizer's rule-based sample notebook for that deck (if it exists).
2. Port to `agent/<archetype>_policy.py` + `deck_tech` entry + validate deck CSV.
3. Gate L0–L1 vs real-field registry before any ML.
4. Add matchup levers one archetype at a time (measure each change).
5. Only then: field RL+MCTS warm-start from rules, not from Snorlax/sample-deck training.

**Explicitly retired:** separate agents per opponent; `pool_*` proxies; mirror-only or random-only training/eval; shipping ML without beating the rule+search floor for *that* deck.

Lucario is the reference implementation: `lucario_policy.py` + `LUCARIO_TECH` + `train_lucario_field_mcts.py`.

---

## How the pillars interlock (the anti-sprawl invariant)

```
        episodes/ (0.3) ──► field/ (0.2) ──► eval/ (0.4) ◄── core/ (0.1)
            │                   │                ▲              │
            ├──► meta/ (P2) ────┤                │              │
            │      │            │                │              │
            ▼      ▼            ▼                │              ▼
   belief prior  field mixture  gate opponents   │        rules mastery (P1)
            │      │                             │
            ▼      ▼                             │
   agents/ decision policy (P3) ────────────────┤
            ▲                                    │
   decks from discovery search (P4) ────────────┘
   daily orchestration (P5) drives the whole loop
```

**Invariant:** a pillar may only *consume* the foundation's interfaces and *emit* into them. No
pillar invents its own opponents, its own eval, or its own scratch dir. That invariant is what
keeps this from re-fragmenting.

---

## Target repository layout — with current status

Legend: **[live]** = working code, do not break; **[scaffold]** = dir + README created, code to
come; **[migrate]** = working code that currently lives elsewhere and moves here per build order.

```
pokemon/
├─ README.md            # map + how to run                                   [live, rewritten]
├─ RULINGS.md           # decisions + evidence                               [live]
├─ ARCHITECTURE.md      # this file                                          [live]
├─ STATE.md             # current state + single next action                 [live]
├─ TASKS.md PROJECT_RULES.md AGENTS.md                                       [live, retuned]
├─ core/                # 0.1 card/rules/engine/obs model + Pillar 1         [scaffold]
├─ field/               # 0.2 real-field decks, public agents, registry      [scaffold]
├─ episodes/            # 0.3 pull + parse + store                           [scaffold]
├─ eval/                # 0.4 harness, gates, ladder_log                     [scaffold]
├─ meta/                # Pillar 2 daily meta map                            [scaffold]
├─ discovery/           # Pillar 4 scoped deck search                        [scaffold]
├─ agent/              # Pillar 3 spine: HeuristicScorer + SearchScorer      [live → migrate to agents/]
├─ scripts/            # surviving helpers (package, gate, mine, fetch)      [live, migrate piecemeal]
├─ agent_decks/        # real_* + top_mined_* + benchmark/                   [live → migrate to field/decks/]
├─ data/               # official rules/card CSVs + EN_Card_Data.csv         [live, source citations]
├─ report/             # replays/ + agent_logs/ + 2 log CSVs only           [live → migrate to episodes/, eval/]
└─ dist/               # packaged submissions only                          [live]
```

**Why `agent/` is not yet `agents/`:** the spine scored ~668 μ and must not break (Ruling R7),
and it cannot be smoke-tested in this sandbox (Python 3.10 vs the engine's ≥3.11). Renaming it
blind is exactly the kind of unvalidated change that caused past regressions. So the spine stays
in `agent/` until build-order step 3 migrates it **on a machine where the smoke test runs.**

Removed dirs (`rl/`, most of `report/`, dead `scripts/`, `notebooks/lucario`, `pool_*`/variant
decks, ~10 top-level handoff files) are preserved in `graveyard/pre-reset-20260622` (RULINGS Part 5).

---

## Build order (each step ends with something measurable; nothing speculative ships)

1. **P0.1 + P1:** `core/` model + the empirical information-model test. *Proves the foundation.*
2. **P0.4 + P0.2:** `eval/` harness + `field/` registry from existing mined decks/agents.
   *Re-measure the current champion on the real field — establish the true floor.*
3. **Spine:** consolidate the best current rules/search brain into `agents/pilot.py`; it must
   reproduce ~633–668 on the gate. *This is our shippable baseline.*
4. **P0.3 + P2:** episode pull/parse + first daily meta map (on the user's machine).
5. **P3 staged:** lookahead → PIMC → (ISMCTS) → learned belief prior, each gated vs the spine.
6. **P4:** scoped discovery search against the live field mixture.
7. **P5:** wire the daily loop; `/schedule` it once trusted.

> Steps 1–3 are this rebuild's "definition of done for the foundation." Pillars 3–5 are the
> ongoing climb from ~668 toward mid-pack and up.
