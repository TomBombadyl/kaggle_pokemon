# PROGRESS LOG

Append-only. Newest entry on top. Each nightly run adds one dated block:
what task(s) were worked, what changed, current best win-rate, and the **exact next
step** so the following run can resume instantly.

---

## Template (copy for each run)

```
### YYYY-MM-DD (run)
- Worked on: T# ...
- Changed: ...
- Metrics: best win-rate = ?? % over ?? games
- Blockers: none | <describe>
- NEXT: <the single next action>
```

---

### 2026-06-19 (run 10 - packaged head-to-head validation)
- **Worked on:** strengthened pre-submit validation by testing packaged candidates
  against each other. No Kaggle submission attempted.
- **Changed:** added `scripts/verify_archive_matrix.py`, which imports packaged
  `main.py`/`deck.csv` from multiple candidate tarballs and runs side-swapped
  local cabt matches between the packaged artifacts. It writes CSV/Markdown under
  `report/eval/`. Updated `report/submission_candidates_2026-06-19.md` with the
  top-3 packaged head-to-head matrix.
- **Metrics:** `report/eval/archive_matrix_100_top3_candidates.md` compares A1,
  A2, and A4 over 100 games per ordered pair. A2 is currently the best first-slot
  candidate by combined evidence: packaged default-deck random gate 294/300 =
  98.0%, A2 vs A1 = 55/100, and A2 vs A4 = 58/100. A1 remains the best
  source-matrix/safety-regression candidate; A4 remains the diversity probe.
- **Official check:** in-app browser was unavailable in this session, so the
  current official check remained web-search snippets plus local downloaded API
  artifacts. Do not upload until a browser-visible Kaggle rules check is possible.
- **Verification:** `python -m py_compile scripts\verify_archive_matrix.py`
  passed; the packaged matrix completed with no draws or unfinished games.
- **NEXT (T15):** if the user explicitly confirms upload, perform a browser-visible
  Kaggle final rules/slot check, submit A2 first, then A1/A4 as remaining planned
  probes, recording submission IDs and scores.

### 2026-06-19 (run 9 - packaged artifact validation)
- **Worked on:** validating that the local candidate tarballs themselves behave like
  the source runs, not just that the source agent works. No Kaggle submission
  attempted.
- **Changed:** added `scripts/verify_archive.py`, which extracts a candidate
  `.tar.gz`, imports the packaged top-level `main.py`, uses packaged `deck.csv`,
  and runs side-swapped games against legal random. It supports `--opponent-deck`
  to distinguish mirror checks from cross-deck checks. Updated
  `report/submission_candidates_2026-06-19.md` with package-level evidence and
  current official Kaggle links/snippets.
- **Official constraints rechecked:** current Kaggle search snippets for the
  Simulation rules still show five submissions/day and two final submissions; the
  Simulation overview snippet still says `.tar.gz` with top-level `main.py` and
  `deck.csv`. API contract remains grounded in `data/CABT_API.md` and downloaded
  `data/sim/sample_submission/cg/api.py`.
- **Packaged artifact metrics vs default Abomasnow random deck (300 games each):**
  A0 safety 282/300 = 94.0%; A1 current 288/300 = 96.0%; A2 Kyogre 294/300 =
  98.0%; A3 Starmie 283/300 = 94.3%; A4 big-basic 291/300 = 97.0%. Mirror archive
  checks also passed for A1/A3/A4, with A1 at 287/300, A3 at 291/300, and A4 at
  294/300.
- **Verification:** `python -m py_compile scripts\verify_archive.py` passed; all
  package verification runs finished with no draws or unfinished games.
- **NEXT (T15):** if the user explicitly says to submit, use a browser-visible
  Kaggle final rules check, then submit A2/A1/A4 in that order unless the user
  chooses a different portfolio. Record submission IDs/scores in
  `report/submission_candidates_2026-06-19.md`.

### 2026-06-19 (run 8 - T15 five dry-run candidates)
- **Worked on:** T15 five distinct Simulation submission candidates. No Kaggle
  submission attempted.
- **Changed:** extended `scripts/package_submission.py` with `--deck`,
  `--agent-module`, and `--name`, and isolated per-archive build directories so
  candidate packages do not clobber each other. Added
  `report/submission_candidates_2026-06-19.md` with the five-slot portfolio and
  updated `report/research_and_submission_plan.md` from the stale 88.7% state to
  the current 96.3% local gate. Added/kept deck probes under `agent_decks/`.
- **Candidate archives:** dry-run built and import/deck-selection checked:
  `dist/candidates/a0_safety.tar.gz`,
  `dist/candidates/a1_current_963.tar.gz`,
  `dist/candidates/a2_kyogre.tar.gz`,
  `dist/candidates/a3_starmie.tar.gz`, and
  `dist/candidates/a4_big_basic.tar.gz`.
- **Metrics:** A1 is the recommended first slot if the user confirms submission:
  `matrix_300_current_pref_first` measured 578/600 = 96.3% vs legal random, and
  `matrix_120_current_pref_first_matrix` measured current beating safety 152/240
  across ordered rows. A4 had a promising 120-game gate but did not hold 95% on a
  300-game rerun; A2/A3 are diversity probes, not local-best candidates.
- **Verification:** `python scripts\smoke_test.py` = 17/17 pass;
  `python -m py_compile agent\agent.py agent_snapshots\v2_safety.py
  scripts\eval_matrix.py scripts\smoke_test.py scripts\selfplay.py
  scripts\package_submission.py` passed; all five candidate packages dry-run
  imported and returned 60-card decks. Official rules still require browser-visible
  recheck immediately before any upload.
- **NEXT (T15):** if the user explicitly confirms, open the Kaggle pages in browser
  for final rules/slot check, submit A1 first, and record submission ID/score.
  Otherwise continue reducing `no_active` losses and/or prepare a stronger A4
  anti-ex/basic candidate.

### 2026-06-19 (run 7 - T15 local 95% gate reached)
- **Worked on:** continued T15 toward a validated 95%+ local candidate while
  re-checking official/API constraints. No Kaggle submission attempted.
- **Changed:** kept the A1 current agent path and added two practical improvements:
  MAIN `PLAY` now scores playable cards and prioritizes benching Basic Pokémon
  when the bench is thin, and `IS_FIRST` now chooses to go first because current
  telemetry showed the upgraded pilot performs better from first-player tempo.
  Added role scoring for additional Water candidates (Black Kyurem ex, Veluza,
  Chien-Pao, Staryu/Mega Starmie ex) and smoke coverage for benching Basics before
  draw support. `scripts/eval_matrix.py` now supports `--tag` so candidate evidence
  is no longer overwritten by repeated `matrix_<games>` runs.
- **Deck probes added:** `agent_decks/a2_kyogre_33_energy.csv`,
  `agent_decks/a2_basic_heavy_31_energy.csv`,
  `agent_decks/a2_big_basic_31_energy.csv`,
  `agent_decks/a2_big_basic_29_energy.csv`,
  `agent_decks/a3_starmie_spread_33_energy.csv`, and
  `agent_decks/a4_basic_water_33_energy.csv`. These are test candidates only;
  `agent/deck.csv` remains the current submission deck.
- **Metrics:** best verified local random gate is now
  `report/eval/matrix_300_current_pref_first.*`: current vs random 289/300 and
  reciprocal random vs current 11/300, so current won **578/600 = 96.3%** over
  600 agent-perspective games, sides swapped. Broader tagged matrix
  `report/eval/matrix_120_current_pref_first_matrix.*`: current beat safety
  75/120 and reciprocal safety vs current 43/120, and beat random 235/240 across
  both ordered rows. Remaining losses in the 300-game telemetry are still
  `no_active` (22 losses), not deck-out.
- **Verification:** `python scripts\smoke_test.py` = 17/17 pass;
  `python -m py_compile agent\agent.py agent_snapshots\v2_safety.py
  scripts\eval_matrix.py scripts\smoke_test.py scripts\selfplay.py
  scripts\package_submission.py` passed; `python scripts\package_submission.py`
  built `dist/submission.tar.gz` and dry-run import/deck selection succeeded.
  Official Kaggle Simulation/Strategy rules pages were reopened on 2026-06-19 but
  returned only JavaScript page shells in the fetch; implementation/API grounding
  remains `data/CABT_API.md` plus downloaded `data/sim/sample_submission/cg/api.py`.
- **Blockers / notes:** the local 95% random benchmark is achieved, but the full
  goal is not complete: ladder/submission performance is still unproven and needs
  explicit user confirmation before any Kaggle upload. Pre-submit still requires a
  browser-visible official page check for current limits/rules.
- **NEXT (T15):** create a named submission candidate snapshot/package for the
  current 96.3% agent, then, only with explicit user confirmation, submit one
  Simulation slot and record ladder ID/score; otherwise continue reducing
  `no_active` losses and testing candidate diversity.

### 2026-06-19 (run 6 - T15 A1 initial candidate)
- **Worked on:** T15 first Simulation candidates, specifically A1
  attack/targeting upgrade. No Kaggle submission attempted.
- **Changed:** updated `agent/agent.py` only for the live agent path; preserved
  `agent_snapshots/v2_safety.py` unchanged. The current agent now lazily reads cabt
  attack/card metadata when available, scores attack choices by fixed damage and
  active-KO pressure, promotes developed attackers after KO, scores heal targets by
  damage/value, and targets opponent damaged/low-HP/high-prize Pokémon for damage
  counters/damage effects. Added smoke coverage for active promotion and opponent
  KO targeting.
- **Metrics:** requested matrix
  `python scripts\eval_matrix.py --games 20 --agents current,safety,random --deck
  current=agent\deck.csv` completed. Current/A1 aggregate in telemetry: 60 wins /
  20 losses over 80 agent-perspective rows (75.0%); safety aggregate: 53 wins / 27
  losses (66.2%). Ordered rows: current vs safety 12/20, current vs random 20/20,
  safety vs current 10/20, random vs current 2/20.
- **Verification:** `python scripts\smoke_test.py` = 16/16 pass;
  `python -m py_compile agent\agent.py agent_snapshots\v2_safety.py
  scripts\eval_matrix.py scripts\smoke_test.py scripts\selfplay.py
  scripts\package_submission.py` passed; requested 20-game matrix passed and wrote
  `report/eval/matrix_20.*` plus `report/eval/telemetry_20.*`.
- **Blockers / notes:** A1 is promising but not final; current losses in the
  telemetry are still all `no_active`, so the next candidate work should test more
  robust basic/bench/deck variants before any submission.
- **NEXT (T15):** build A2 reduced-energy Water deck candidate, then compare A0/A1/A2
  on the matrix before deciding whether A1 merits packaging as a Simulation slot.

### 2026-06-19 (run 5 - T14 telemetry)
- **Worked on:** T14 game telemetry for the local evaluation matrix.
- **Changed:** expanded `scripts/eval_matrix.py` with per-game telemetry collection
  and reporting. Normal matrix CSV/Markdown output is unchanged; telemetry is on by
  default and can be skipped with `--no-telemetry`. New outputs:
  `report/eval/telemetry_<games>.csv` (one row per agent perspective per game) and
  `report/eval/telemetry_<games>.md` (aggregate diagnosis by agent, first/second,
  loss reason, decision contexts in losses, and attacker usage).
- **Telemetry fields:** matchup, agent/opponent, actual seat, first/second order,
  result, cabt result reason (`prize`, `deck_out`, `no_active`, `card_effect`),
  turns/steps, prize/deck counts, first attack/evolution turns, evolution count,
  attachment opportunity/attachment/missed-attachment turns, last/top attackers,
  decision context counts, and decision type counts.
- **Metrics:** no new best win-rate claim. Small smoke matrix
  `python scripts\eval_matrix.py --games 4 --agents current,safety,random --deck
  current=agent\deck.csv` completed and wrote `matrix_4.*` plus `telemetry_4.*`.
- **Verification:** `python scripts\smoke_test.py` = 14/14 pass;
  `python -m py_compile agent\agent.py agent_snapshots\v2_safety.py
  scripts\eval_matrix.py scripts\smoke_test.py scripts\selfplay.py
  scripts\package_submission.py` passed; `python scripts\eval_matrix.py --games 2
  --agents current,random --no-telemetry` passed.
- **Blockers:** none for local telemetry. Actual Kaggle submission remains
  intentionally unattempted pending explicit user confirmation and fresh official
  page verification immediately before upload.
- **NEXT (T15):** use the matrix + telemetry reports to build the first five
  Simulation submission candidates: A0 safety baseline, A1 attack/targeting
  upgrade, A2 reduced-energy Water list, A3 Water spread variant, and A4
  anti-ex/single-prize variant.

### 2026-06-19 (run 4 - research roadmap + v2 snapshot + eval matrix)
- **Worked on:** T12 planning checkpoint after the user requested a saved progress
  handoff, deeper academically backed research directions, and preparation for the
  first five Simulation agent submissions.
- **Changed:** added `report/research_and_submission_plan.md` with the current
  baseline, official submission constraints to recheck, untried evaluation/agent/deck
  ideas, research-backed directions (heuristic search, offline imitation/RL,
  PPO/self-play caution, exploitability), and five proposed Simulation submission
  candidates. Updated `report/strategy_report_draft.md` to use the latest 88.7%
  local metric. Expanded `TASKS.md` with Phase 4 tasks T13-T17.
- **T12/T13 DONE:** froze the current v2 safety agent as
  `agent_snapshots/v2_safety.py` and added `scripts/eval_matrix.py`, which compares
  local agents/decks with side swapping and writes CSV/Markdown summaries under
  `report/eval/`. It supports named agents `current`, `safety`, and `random`, plus
  deck overrides such as `--deck current=agent\deck.csv`.
- **Research notes:** current-web snippets from official Kaggle pages indicate the
  Simulation competition allows five submissions per day and up to two final
  submissions, and uses a `submission.tar.gz` upload. Academic sources reviewed:
  RLCard for imperfect-information card-game RL tooling, Metamon/Pokemon offline
  RL for first-person trajectory reconstruction and offline fine-tuning, Hearthstone
  MCTS for heuristic-enhanced search under hidden information, and LOCM/ByteRL work
  for CCG RL/exploitability lessons. These support building telemetry and a local
  match matrix before heavy RL.
- **Metrics:** best win-rate remains **88.7% over 300 games** heuristic-vs-random
  (sides swapped). New harness smoke results: `python scripts\eval_matrix.py
  --games 20` and `python scripts\eval_matrix.py --games 6 --agents
  current,safety,random --deck current=agent\deck.csv` both completed and wrote
  reports in `report/eval/`.
- **Verification:** `python scripts\smoke_test.py` = 14/14 pass;
  `python -m py_compile agent\agent.py agent_snapshots\v2_safety.py
  scripts\eval_matrix.py scripts\smoke_test.py scripts\selfplay.py` passed.
- **Blockers:** no local blocker. Actual Kaggle submission remains intentionally
  unattempted pending explicit user confirmation and one more official Kaggle-page
  verification immediately before upload.
- **NEXT (T14):** add telemetry to `scripts/eval_matrix.py`/the self-play path so
  each matchup explains wins and losses by first/second, turns, prize/deck-out
  reason, active attacker, evolution timing, missed attachments, and decision
  context counts.

### 2026-06-19 (run 3 - T9/T10/T11 complete, package dry-run OK)
- **Worked on:** T9, T10, and T11. Kaggle pages were allowed by the user, but this
  pass did not need browser traversal because the local downloaded official
  `sample_submission/` and cabt engine artifacts were sufficient for the work.
- **T9 DONE:** kept a card-context scoring improvement in `agent/agent.py`:
  optional `TO_HAND` and `ATTACH_TO` selections now take useful visible cards/energy
  instead of declining when `minCount=0`; visible cards are ranked by current Water
  Mega Abomasnow deck roles; required discard/deck-bottom choices prefer lower-value
  cards first. Added smoke coverage in `scripts/smoke_test.py`.
- **Metrics:** current best win-rate = **88.7% over 300 games** heuristic-vs-random
  (sides swapped). Same run random-vs-random = 47.3%. Earlier same-code run measured
  86.3% over 300, both above the previous 78.0% best.
- **T10 DONE:** drafted `report/strategy_report_draft.md` covering verified agent
  interface, deck concept, rule logic, stability tests, local metrics, limitations,
  and next improvements.
- **T11 DONE:** added `scripts/package_submission.py`; built
  `dist/submission.tar.gz` locally; dry-run import returned 60 deck IDs; an unpacked
  archive completed one full cabt game locally. No Kaggle submission was attempted.
- **Verification:** `python scripts\smoke_test.py` = 14/14 pass;
  `python -m py_compile agent\agent.py scripts\smoke_test.py scripts\selfplay.py`
  passed; `python scripts\package_submission.py` passed; archive full-game smoke
  passed (`result=0`, 23 steps in the final run).
- **Blockers:** none for local work. Actual Kaggle submission remains intentionally
  unattempted pending explicit user confirmation and official Kaggle-page validation.
- **NEXT (T12):** before any real submit, use the browser/Kaggle pages to reconfirm
  current Strategy/Simulation submission requirements and limits, then polish
  `report/strategy_report_draft.md` and decide with the user whether to submit
  `dist/submission.tar.gz` or revise further.

### 2026-06-19 (run 2 - T7/T8 strategy v1 complete)
- **Worked on:** saved durable project operating rules, T7, and T8.
- **Changed:** added `PROJECT_RULES.md` with the project operating contract (manual
  run model; no scheduling assumptions); linked it from `README.md`.
- **T7 DONE:** rewrote `agent/agent.py` from attack-first v0 into setup-aware v1:
  MAIN priority is now evolve/play/attach/ability/attack; optional setup bench
  selections fill legal slots instead of declining; draw-count prompts choose the
  largest available number; common yes/no prompts prefer going second, mulligan
  redraws, and useful effect activation; attack and attach choices now use stable
  scoring helpers instead of first-option fallback.
- **T8 DONE:** mirrored `data/sim/sample_submission/deck.csv` to `agent/deck.csv`
  so deck-selection mode returns the intended 60-card list. Recorded the current
  Water Mega Abomasnow concept in `report/deck_concept_v1.md`.
- **Verification:** `python scripts\smoke_test.py` = 12/12 pass;
  `python -m py_compile agent\agent.py scripts\smoke_test.py scripts\selfplay.py`
  passed; `agent/deck.csv` loads 60 IDs.
- **Metrics:** current best win-rate = **78.0% over 200 games** heuristic-vs-random
  (sides swapped). Sanity matchup in same run: random-vs-random = 45.0% over 200.
  Previous best was 7.5% over 160, so v1 is a major local-harness improvement.
- **T9 attempt not kept:** tried a lazy `cg.api.all_attack()` damage/KO scorer for
  attacks. It measured **75.7% over 300 games**, below the 78.0% best, so the
  change was reverted. A post-revert 200-game check measured 77.0%, consistent
  with the kept v1 range.
- **Blockers / notes:** `bash scripts/setup_env.sh` was attempted first, but Windows
  pip rejected `--break-system-packages`; fallback `python -m pip install -r
  requirements.txt` succeeded on Python 3.13.12. No Kaggle submission attempted.
- **NEXT (T9):** add card-data-aware CARD/DISCARD/TO_HAND scoring (keep evolution
  pieces and draw/search supporters, discard excess Energy first), then rerun
  `python scripts\selfplay.py 300` and keep the change only if it beats 78.0%.

### 2026-06-19 (run 1d — ENGINE running, T4 + T5 done, first win-rates)
- **cabt engine fetched.** User joined the **Simulation** comp; added
  `scripts/fetch_sim_engine.{py,bat}` → downloaded its `sample_submission/` into
  `data/sim/`: starter `main.py`, a sample `deck.csv` (60 ids), and the engine
  `cg/` (`libcg.so` Linux + `cg.dll` Windows, `api/game/sim/utils.py`).
- **Engine RUNS IN THE SANDBOX (Python 3.10).** `cg/sim.py` is a ctypes wrapper that
  auto-loads `libcg.so` on Linux / `cg.dll` on Windows. So the **Python ≥3.11
  blocker is moot** for direct play — only `kaggle_environments` needs 3.11, which we
  bypass by calling `cg.game.battle_start/battle_select` directly.
- **T4 DONE.** `scripts/selfplay.py` plays full games to completion (game ends when
  `current.result != -1`; 0/1 = winner, 2 = draw). One game ≈ 50 decisions / ~14 turns.
- **T5 DONE — first measured win-rates (160 games/matchup, sides swapped, ~4s):**
  - random vs random = **48.1%** → harness is fair (sanity check passes).
  - **heuristic v0 vs random = 7.5%** → our naive "attack-first + first-option
    fallback" policy is **much worse than random**. Key insight: greedy attacking
    without board setup, and picking the first option for targeting/discards, plays
    badly. This is the concrete signal to drive T7.
- **Real interface confirmed from starter `main.py`:** `agent(obs_dict)` →
  `to_observation_class`; `obs.select is None` ⇒ return 60-card deck; else return
  indices in `[minCount,maxCount]`. Matches `agent/agent.py`.
- **Engine kept out of git** (`data/*` gitignored except `*.md`); reproducible via the
  fetch script. Card-supertype/energy enums confirmed in `cg/api.py`.
- **NEXT (T7):** Beat the random baseline. Replace the rigid MAIN priority with
  setup-aware logic: in the early game attach energy + develop bench/evolve before
  attacking; only attack when it KOs or trades up; for CARD/DISCARD/target contexts
  score options instead of taking the first. Re-run `python3 scripts/selfplay.py 200`
  and keep the change only if heuristic-vs-random clears ~50%+.

### 2026-06-19 (run 1c — data unblocked, T3 done)
- **Kaggle access fixed.** User signed in to Kaggle in the browser → competition
  data unlocked (rules gate cleared). Token auth path confirmed: the new `KGAT_`
  token works via `kagglehub` (the legacy `kaggle` CLI 1.6/1.7 does NOT read it).
- **Data downloaded** (sandbox can't reach kaggle.com, so fetched on the user's
  machine): added `scripts/fetch_card_data.py` + `fetch_card_data.bat` — reads the
  token from `.kaggle/access_token`, pulls the Strategy dataset via kagglehub, and
  copies the CSVs into `data/`. Now present: `data/EN_Card_Data.csv` (359 kB),
  `data/JP_Card_Data.csv`. (Big PDFs left in kagglehub cache to keep the repo lean.)
- **T3 DONE.** `scripts/summarize_cards.py` → `data/CARDS_SUMMARY.md`.
  **2,022 cards, 17 cols.** Supertype: 958 Basic / 618 Stage 1 / 229 Stage 2
  Pokémon; 82 Item, 61 Supporter, 28 Tool, 26 Stadium, 12 Special / 8 Basic Energy.
  HP min 30 / median 110 / max 380. Retreat 1:859 2:554 3:265 4:70. 324 cards have
  a Rule box (ex etc.). Note: real schema is **17 columns** (the Data-tab prose
  listing 34 fields was descriptive, not literal); "Category" holds mechanics
  (Ancient/Future/Tera/Trainer's Pokémon), supertype is in the Stage/Type column.
- **Still blocked for T4/T5:** the **cabt engine** is NOT in the Strategy dataset —
  it ships via the **Simulation** comp (`pokemon-tcg-ai-battle`) + starter
  notebooks. And the ladder harness `kaggle-environments==1.30.1` needs Python
  ≥3.11 (sandbox is 3.10; user's machine has 3.11/3.13 + Anaconda).
- **NEXT:** Get the engine: Join the **Simulation** competition, then fetch its
  code/engine (`cg/` lib) the same way (extend `fetch_card_data.py` or download a
  starter notebook's engine) into `data/cabt/`. Then wire `agent/agent.py` to
  `kaggle_environments.make("cabt", ...)` on Python 3.11 → **T4** (run one full
  game) and **T5** (random-baseline win-rate).

### 2026-06-19 (run 1b — read competition docs closely via browser)
- **Data tab (official):** the **Strategy** dataset is **card data + PDFs only**
  (4 files, 320.74 MB): `EN_Card_Data.csv`, `JP_Card_Data.csv`,
  `Card_ID List_EN.pdf`, `Card_ID List_JP.pdf`. CSV = **34 columns**
  (Card ID, Card Name, Expansion, Collection No., Stage/Type, Rule, Category,
  Previous stage, HP, Type, Weakness, Resistance, Retreat, Move Name, Cost,
  Damage, Effect Explanation, ...). This is the T3 card DB.
- **The cabt simulator/engine is NOT in the Strategy dataset.** It ships via the
  **Simulation** competition (`pokemon-tcg-ai-battle`) + starter notebooks (e.g.
  "Pokémon TCG EDA & Deck Engine", "EDA Starter Kit"). Needed for T4/T5.
- **ACCESS GATE (root cause):** the Data tab says *"To see this data you need to
  agree to the competition rules… Sign In."* The browser is **NOT signed in** to
  Kaggle and the competition is **not yet joined** ("Join Hackathon"). Kaggle API
  tokens also return 403 until the account has **joined/accepted rules**. So the
  download needs: (1) sign in, (2) Join (accept rules) — both **user-only** actions.
- **Prep done this run:** `scripts/summarize_cards.py` written + syntax-checked —
  parses `EN_Card_Data.csv` (schema-tolerant) → `data/CARDS_SUMMARY.md`. Runs the
  instant the CSV lands. `uv`/apt py3.11 routes tried; GitHub-release + kaggle.com
  egress both 403 from sandbox, so download must happen on the user's machine.
- **NEXT:** User signs in to Kaggle + clicks **Join Hackathon** on BOTH the
  Strategy and Simulation comps; then either (a) I drive the browser to download
  the 4 data files, or (b) user runs `kaggle competitions download -c
  pokemon-tcg-ai-battle-challenge-strategy -p data/` on Windows. Then run
  `python scripts/summarize_cards.py` → completes **T3**.

### 2026-06-19 (run 1)
- **Worked on:** T1 (done), T2 (partial/blocked), T6 (done). T3-T5 blocked offline.
- **T1 — interfaces CONFIRMED from official cabt Engine 0.1.0 docs**
  (matsuoinstitute.github.io/cabt + /api.html). Full schema written to
  `data/CABT_API.md`. Key facts:
  - Agent contract: `def agent(obs_dict) -> list[int]` returning **indices** into
    `obs_dict["select"]["option"]`, count in `[minCount, maxCount]`.
  - Deck phase: `select`/`current` are `None` → return **60 card IDs** (not indices).
  - obs keys: `logs`, `current` (State|None), `select` (SelectData|None).
  - 11 SelectTypes, 17 OptionTypes, 49 SelectContexts, 12 AreaTypes — all tabulated.
  - Engine API: `battle_start/select/finish`, `all_card_data()` (~2,000 cards),
    `all_attack()`, lookahead `search_begin/step/end`.
  - Harness: `make("cabt", configuration={"decks":[d,d]})`; ladder uses
    `kaggle-environments==1.30.1`.
  - Rewrote `agent/agent.py` to this real interface: legal/deterministic baseline
    with MAIN priority (attack>evolve>attach>ability>play>retreat>end) + a
    never-crash `_legal_fallback`. Added `scripts/smoke_test.py` → **10/10 pass**.
- **T2 — env partially configured.**
  - Deps install OK (numpy 2.2.6, pandas 2.3.3, kaggle 1.7.4.5, kagglehub 1.0.2).
  - **Kaggle token RECEIVED** (new `KGAT_` format) and stored at
    `.kaggle/access_token` (gitignored). `setup_env.sh` updated to use it.
  - **[BLOCKED] data download:** sandbox proxy returns **403 Forbidden** for
    `api.kaggle.com` AND `www.kaggle.com` — no Kaggle egress from this sandbox,
    even with a valid token. So card DB + `cg/` engine cannot be fetched here.
  - **[CONSTRAINT]** `kaggle-environments==1.30.1` needs **Python >= 3.11**;
    sandbox is **3.10.12** → exact ladder harness won't install here.
- **T6 — done:** `data/META_NOTES.md` (never-crash scaffold, per-context dispatch,
  MAIN priority, simple-deck-wins, fast meta + Crustle anti-ex, single-prize aggro).
- **Metrics:** none yet (no engine/data to measure win-rate).
- **Blockers:** (1) no Kaggle egress from sandbox (403) → blocks T3/T4/T5 here.
  (2) Python 3.10 vs required 3.11 for ladder harness. Both are ENVIRONMENT issues,
  not token issues. ASSUMPTION (label): submission format `submission.tar.gz` =
  main.py+deck.csv+cg/ is community-sourced; reconfirm on official Data/Rules tab.
- **NEXT:** Unblock data — either (a) run in an environment with kaggle.com egress
  + Python 3.11 and run `scripts/setup_env.sh` to download the card DB & `cg/`
  engine, or (b) have Dylan drop the competition download into `data/`. Then do
  **T3**: parse `all_card_data()` (~2,000 cards) and write `data/CARDS_SUMMARY.md`.

---

## Setup notes
- Project scaffolded 2026-06-19.
- Kaggle token (new `KGAT_` format) stored at `.kaggle/access_token` (gitignored).
- **Sandbox cannot reach kaggle.com (403 proxy block);** download/submit must run
  where kaggle.com egress is allowed (and Python >= 3.11 for the ladder harness).
- Folder must be connected/accessible when the 9pm run fires.
