# Deck RL System Plan - 2026-06-20

Purpose: turn the existing Track B policy RL and Track C deck GA into a disciplined
deck discovery system for robust Pokemon TCG Simulation submissions.

This plan assumes the current repo state:

- Live best remains the Kyogre heuristic/search pair unless a new ladder probe
  beats it.
- Local gates are filters only; Kaggle ladder score is truth.
- Learned policies are deck-specific. Any serious deck candidate needs its own
  train, distill, gate, and package pass.
- The current benchmark suite is useful but incomplete because it is still a
  proxy for the live field.

## Target Outcome

Build a repeatable system that answers three questions for every archetype:

1. Is the deck legal, stable, and pilotable by our agent?
2. Does it beat a broad benchmark suite without collapsing into one bad matchup?
3. Does a deck-trained LearnedScorer or SearchScorer make it ladder-worthy?

The output is not one "best deck" guessed from local self-play. The output is a
portfolio of 2-5 ladder probes with different matchup profiles, then two final
submissions selected from live scores.

## System Architecture

### Layer 1 - Card and Archetype Registry

Input sources:

- `data/EN_Card_Data.csv`
- `agent_decks/*.csv`
- `agent_decks/benchmark/suite.json`
- `data/SIMULATOR_RESOURCE_NOTES.md`
- public/live logs when available

Build a generated registry under `report/deck_rl/`:

- card roles: basic attacker, evolution attacker, draw/search trainer, switch,
  gust/targeting, recovery, energy, special rule, ACE SPEC
- attack profile: cost, damage, color requirements, discard/self-cost, bench
  pressure, status/control
- evolution chains: Basic -> Stage 1 -> Stage 2 or Mega/ex lines
- energy profile: required types, colorless flexibility, attachment pressure
- archetype templates: big-basic, stage-1 ex, stage-2 control, spread, single
  prize, energy acceleration, draw-heavy consistency

Why: raw mutation over 2,022 cards is mostly noise. We need legal, coherent
archetype-aware search.

Simulator caveat: card text is a feature source, not the final legality source.
Some attacks may be unselectable in the simulator even when official rules would
allow declaring them and ending the turn after partial resolution. The deck RL
system must learn from `obs_dict["select"]["option"]` and the action mask, not
from card text alone.

### Layer 2 - Legal Deck Genome

Use `rl/deck_genome.py` as the base, but make the genome more semantic:

- core package: required attacker/evolution/energy cards
- support package: draw/search/switch/recovery/tech slots
- energy package: type and count bands
- flex package: meta techs and anti-archetype cards

Mutation operators:

- tune energy +/- 1-4 within archetype band
- swap support cards within the same role
- add/remove a secondary attacker line
- adjust evolution counts as a chain, not isolated card IDs
- add one tech card and remove lowest-impact flex card
- crossover only between compatible archetype templates

Hard legality constraints:

- 60 cards
- max 4 copies except basic energy
- at most one ACE SPEC
- valid evolution chains for intended attackers
- enough Basic Pokemon to avoid no-active losses
- energy type compatibility with all primary attacks

Soft penalties:

- too few Basics
- attacker line too thin
- energy too high or too low for attack costs
- trainer/draw density too low
- extreme reliance on one multi-prize attacker
- poor matchup spread even when aggregate win rate is high

### Layer 3 - Fitness Function

Do not optimize only aggregate win rate. Score candidates with:

```text
fitness =
  weighted_benchmark_win_rate
  - no_active_penalty
  - instability_penalty
  - matchup_collapse_penalty
  - complexity_penalty
  + diversity_bonus
```

Required per-candidate metrics:

- aggregate weighted win rate vs benchmark suite
- minimum win rate against any high-weight benchmark deck
- Kyogre head-to-head
- no-active rate
- deck-out rate
- draw rate, especially in simultaneous knockout/spread archetypes
- average turns to first attack
- missed attachment turns
- inference/crash/unfinished count

Promotion gate:

- L0: `python scripts/smoke_test.py`
- L0: `python scripts/validate_deck.py --deck <candidate>`
- L1: 8-12 games per benchmark opponent
- L2: 40 games per benchmark opponent or SPRT gate
- L3: package dry-run
- L4: Kaggle ladder only after explicit user approval

### Layer 4 - Search Loops

Run three loops in order. Do not mix signals.

### Layer 5 - Replay Mining For BC/RL/IL

Use the Kaggle episodes-index dataset and CLI replay/log commands to improve the
benchmark suite and learned policies.

Targets:

- top-rated episode replays from the daily export
- our own completed submissions' replays and logs
- public top-team episodes where available through Kaggle CLI

Outputs:

- `report/replays/` for replay JSON
- `report/agent_logs/` for per-agent logs
- `report/deck_rl/replay_index.csv`
- `report/deck_rl/mined_archetypes.md`
- `agent_decks/benchmark/live_*.csv` when an archetype can be reconstructed

Use cases:

- behavior cloning from strong public decisions
- imitation-learning pretraining before PPO
- failure mining for missed attachments, no-active losses, and late first attack
- live-meta benchmark refresh so deck GA does not overfit the local proxy pool

Do not copy opponent code. Use replays as data for legal-option behavior,
archetype identification, and benchmark construction.

#### Loop A - Template Search

Goal: find stable archetype families before expensive RL.

Method:

- start from known decks and real/meta proxy lists
- generate archetype-preserving variants
- evaluate with HeuristicScorer or SearchScorer
- keep diverse top candidates, not only the single aggregate winner

Outputs:

- `report/deck_rl/template_search.csv`
- `report/deck_rl/top_templates.md`
- candidate deck CSVs under `agent_decks/deck_rl/`

#### Loop B - Deck GA

Goal: improve candidate lists within each promising family.

Method:

- seed GA with top templates and current high performers
- evaluate vs `agent_decks/benchmark/suite.json`
- maintain an archive of elite decks per archetype
- require held-out opponents before promotion

Important change: use per-archetype leaderboards. A deck that is only 54% vs
Kyogre but crushes six meta proxies may still be valuable as a portfolio slot,
but it should not replace Kyogre as the protected best.

#### Loop C - Per-Deck Policy RL

Goal: train a brain for each promoted deck.

For every deck promoted from Loop A/B:

```bash
python scripts/train_track_b_deck.py \
  --deck <candidate.csv> \
  --slug <slug> \
  --timesteps 100000 \
  --gate-games 40 \
  --package \
  --promote
```

For serious candidates, use checkpoint sweep rather than final-only packaging:

- train in 100k chunks
- save every checkpoint
- distill each checkpoint with 300+ teacher episodes
- gate each distilled model
- package only the best checkpoint

This directly addresses the 1M-ramp failure mode where later training discarded
stronger intermediate policies.

## Benchmark Suite Strategy

Current benchmark tags:

- meta proxies: Dragapult, Crustle, Bellibolt, Alakazam, Greninja, Mega Greninja
- high performers: Kyogre, big-basic, Starmie
- baseline: default pilot deck

Upgrade path:

1. Mine public/live logs where possible.
2. Add confirmed strong archetypes as `agent_decks/benchmark/worlds_*.csv` or
   `live_*.csv`.
3. Assign weights:
   - 2.0 for live/high-confidence leaders
   - 1.5 for current high performers and our protected finals
   - 1.0 for meta proxies
   - 0.5 for sanity baselines
4. Hold out at least one strong archetype from each training run.

Do not call a deck "generalist" until it has a reasonable minimum matchup score,
not just a high average.

## Candidate Portfolio

Maintain separate lanes:

- Protected best: Kyogre heuristic/search until beaten on ladder.
- Learned generalist: best Track B deck-trained candidate.
- Anti-Kyogre: specifically improves the Kyogre matchup without collapsing.
- Spread/control: punishes bench setup and evolution dependency.
- Fast single-prize/basic: stability and prize-trade hedge.

Each lane should have one candidate package, one gate report, and one decision
line: submit, hold, retrain, or discard.

## Execution Plan

### Phase 1 - Organize Deck RL Outputs

Create:

- `agent_decks/deck_rl/`
- `report/deck_rl/`
- `report/replays/`
- `report/deck_rl/registry.json`
- `report/deck_rl/candidate_registry.csv`

Add a script:

- `scripts/build_card_registry.py`

Minimum useful version:

- parse `EN_Card_Data.csv`
- infer basic card roles
- emit card/evolution/energy summaries
- annotate simulator-sensitive effects such as draw-from-empty-deck, bench-full
  Basic search, opponent-hand interaction, spread/simultaneous-KO risk, and
  automatic target-order effects

Also add a replay-mining script stub:

- `scripts/mine_episode_replays.py`

Minimum useful version:

- read downloaded replay JSON/log files
- index agent IDs, winner, deck IDs where visible, turn count, result, and
  selected action contexts
- emit `report/deck_rl/replay_index.csv`

### Phase 2 - Make Deck Search Archetype-Aware

Extend or wrap:

- `rl/deck_genome.py`
- `rl/deck_balance.py`
- `rl/train_deck_campaign.py`

Add:

- chain-aware mutations
- role-aware support swaps
- per-archetype elite archive
- matchup-collapse penalty
- no-active penalty from telemetry

### Phase 3 - Run Cheap Search Before RL

Run template/GA search locally:

```bash
python rl/train_deck_campaign.py --phase deck --generations 20 --resume
```

Then promote only candidates that:

- validate legally
- beat the benchmark suite at L1
- do not have an obvious single matchup collapse
- are materially different from existing Kyogre/Search submissions

### Phase 4 - Train Per-Deck LearnedScorer

Use GPU/Kaggle for each promoted candidate:

```bash
python scripts/train_track_b_deck.py \
  --deck agent_decks/deck_rl/<candidate>.csv \
  --slug <candidate> \
  --timesteps 100000 \
  --n-envs 4 \
  --opponents benchmark \
  --gate-games 40 \
  --package \
  --promote
```

For top candidates, run checkpoint sweep:

- 100k, 200k, 300k, 400k, 500k
- distill 300 episodes initially
- re-distill best checkpoints at 500-1000 episodes
- re-gate at 80 games if close

### Phase 5 - Ladder Probe Discipline

Before upload:

- re-read `data/SUBMISSION_PLAYBOOK.md`
- recheck official Kaggle pages
- dry-run package
- verify archive locally
- get explicit user approval

After upload:

- record reference ID
- wait for ladder games
- fetch logs
- update `report/ladder_history.csv`
- decide whether it replaces one of the protected final slots

## Immediate Next Action

Implement Phase 1:

1. Add `scripts/build_card_registry.py`.
2. Generate `report/deck_rl/registry.json`.
3. Generate `report/deck_rl/archetype_seed_notes.md`.
4. Use the registry to design the first archetype-aware search lanes:
   anti-Kyogre, fast-basic, spread/control, and resilient-generalist.

This is the right next step because the current RL code can already train and
package deck-specific policies. The bottleneck is now candidate quality and
benchmark diversity, not another blank PPO loop.
