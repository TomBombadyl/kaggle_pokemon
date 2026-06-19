# Research and Submission Plan

Date: 2026-06-19

## Current Position

Current kept agent: deterministic rule-based Water Mega Abomasnow pilot with
A1 attack/targeting, safer Basic benching, and first-player preference.

Current local best (packaged, 1000 games vs default Abomasnow random deck):
A4 **965/1000 = 96.50%**, A2 **963/1000 = 96.30%**, A1 **952/1000 = 95.20%**.
Head-to-head: A2 beats A1/A4. See `report/candidate_package_audit.md`.

Current package: `dist/submission.tar.gz`, dry-run validated locally. Five local
candidate archives also exist under `dist/candidates/`; see
`report/submission_candidates_2026-06-19.md`. No Kaggle submission has been made.

## Official Constraints To Preserve

- Simulation competition: official Kaggle rules/search snippets indicate **five
  submissions per day** and up to **two final submissions** for judging.
- Simulation overview/search snippets indicate the submission package is a
  `submission.tar.gz` built from the working directory and uploaded from the My
  Submissions tab.
- Strategy competition: official Kaggle snippets indicate cumulative submission
  allowance depends on submissions per day multiplied by elapsed competition days.
- Any actual Kaggle submit remains blocked until the user explicitly confirms it.

These are current-web-checked notes from 2026-06-19, but the next pre-submit run
must re-open the official Kaggle pages before upload.

## What We Have Not Tried Yet

### Evaluation

- Frozen-policy regression matches: current agent vs v1/v2 snapshots, not only
  random.
- Cross-deck matches: our agent vs sample deck variants and simple non-ex aggro
  decks.
- Per-context telemetry: win/loss split by opening hand, first/second, main
  attacker, evolution timing, missed attachment turns, deck-out losses, and
  crashes/timeouts.
- Submission-slot discipline: package five intentionally different agents, not
  five near-identical random tweaks.

### Agent Logic

- State-aware attack scoring using actual board HP, prize pressure, energy
  discard costs, and bench damage.
- Targeting policy for damage counters, switch effects, bench selection, and
  active promotion after KO.
- Supporter/play-card policy by card effect, not just static card ID priority.
- Search-based tactical checks using cabt `search_*` for a small whitelist of
  high-leverage choices, with strict time limits.
- Opponent-aware heuristics from visible discard, active Pokemon, prize tempo,
  and known deck archetype.

### Decks

- Lower-energy Water Mega Abomasnow variants once attachment reliability is
  proven.
- Mega Starmie ex / Water spread variant: similar energy type, simpler Stage 1
  line, bench damage pressure.
- Single-prize or non-ex attacker package for anti-ex matchups.
- Fast Basic attacker deck to reduce evolution dependency.
- A deliberately conservative "submission safety" deck that maximizes legal play
  and avoids timeout/crash risk.

## Research-Backed Directions

### 1. Strong Heuristic Baseline Plus Narrow Search

CCG research on Hearthstone supports MCTS as useful under hidden information,
especially when it is enriched with a strong heuristic. For this project, full
MCTS is likely too risky under the per-player time budget, but shallow search for
specific choices is plausible:

- whether to attack or set up,
- which target to damage or KO,
- which attacker to promote,
- whether a supporter/play line improves the board immediately.

Implementation path: add a timeout-safe search wrapper around cabt `search_*`,
falling back to the current heuristic on any error or budget exceedance.

### 2. Offline Imitation / Offline RL From Self-Play Logs

Recent Pokemon battle work shows a useful pattern: reconstruct first-person
trajectories, train sequence models or policies offline, then fine-tune with
self-play. We do not currently have human PTCG logs, but we can build the same
kind of dataset from cabt self-play:

- observation summary,
- legal option features,
- chosen action,
- terminal result,
- step/turn/prize tempo features.

Implementation path: first collect deterministic expert traces from our current
agent and variants, then train a light reranker that scores legal options. Do not
replace the full policy until the reranker beats the heuristic in frozen matches.

### 3. PPO / Self-Play Is Possible But Not First

LOCM CCG papers show PPO/self-play can produce very fast neural agents, but also
warn that performance can remain limited without strong representations and
careful reward design. For this repo, PPO is a second wave after telemetry,
snapshots, and feature extraction exist.

Implementation path:

1. Serialize observations into fixed features.
2. Train behavior cloning from heuristic traces.
3. Fine-tune against frozen opponents with PPO or another policy-gradient method.
4. Distill back into a small deterministic model or table-driven policy if the
   Kaggle runtime/package constraints make model inference risky.

### 4. Exploitability And Ladder Diversity Matter

CCG work on ByteRL/LOCM highlights that strong learned agents can still be
exploitable by specialized opponents. We should expect Kaggle ladder submissions
to have rock-paper-scissors dynamics. The first five submissions should therefore
be diverse enough to reveal matchup structure.

## First Five Simulation Submission Candidates

Do not submit these until official pages are rechecked and the user confirms.

1. **A0 Safety Baseline:** current v2 agent and current Water Mega Abomasnow deck.
   Purpose: establish stable ladder signal.
2. **A1 Attack/Targeting Upgrade:** v2 plus state-aware attack and active-promotion
   logic. Purpose: convert setup advantage into faster wins.
3. **A2 Deck-Reduced Energy:** same policy, lower Energy count, more search/draw
   or secondary attackers. Purpose: test whether current 35 Energy is overfit to
   random.
4. **A3 Water Spread Variant:** Mega Starmie ex or another Water Stage 1 attacker
   if deck analysis supports it. Purpose: pressure bench and avoid exact mirror
   dependence.
5. **A4 Anti-ex / Single-Prize Variant:** simple non-ex attacker plan. Purpose:
   probe expected anti-Mega/ex ladder counters.

Each package should record:

- git/file snapshot or archive checksum,
- deck list,
- smoke test result,
- local match matrix,
- ladder submission ID and score,
- whether it is eligible as one of the final two submissions.

## Immediate Next Work

1. Re-open the official Kaggle Simulation pages in a browser before upload.
2. If the user confirms, submit **A2 → A4 → A1** and record ladder IDs/scores.
3. **T16 deck search (no RL yet):** grid/random search over `agent_decks/` variants;
   score each with `verify_archive.py --games 300`. Only explore RL or cabt
   `search_*` after deck grid search plateaus.
4. Continue reducing `no_active` losses in telemetry.
5. T17 Strategy report polish after next measured agent/deck pass.
