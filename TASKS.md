# TASKS — sequential backlog

The nightly bot works **top to bottom**. It does the next unchecked `[ ]` task,
checks it `[x]` when done, and logs details in `PROGRESS.md`. Sub-steps can be added
under any task. Do not skip ahead unless a task is blocked (mark `[blocked]` + reason).

---

## Phase 0 — Setup
- [x] **T1. Confirm competition rules & interfaces.** DONE 2026-06-19. Confirmed from
  official cabt Engine 0.1.0 docs; full schema in `data/CABT_API.md`; `agent/agent.py`
  rewritten to the real `agent(obs_dict)->list[int]` interface.
- [x] **T2. Configure environment.** DONE 2026-06-19. Deps install OK; `KGAT_` token
  stored at `.kaggle/access_token` (works via kagglehub). Data fetch automated in
  `scripts/fetch_card_data.{py,bat}`; card CSVs downloaded into `data/`. NOTE: sandbox
  has no kaggle.com egress (download runs on user's machine); ladder harness needs
  Python>=3.11 (sandbox 3.10; user machine has 3.11/3.13).
- [x] **T3. Load & sanity-check the card database.** DONE 2026-06-19.
  `scripts/summarize_cards.py` → `data/CARDS_SUMMARY.md` (2,022 cards, 17 cols).

## Phase 1 — Baseline agent
- [x] **T4. Wire the agent to the simulator.** DONE 2026-06-19. Engine fetched via
  `scripts/fetch_sim_engine.py` → `data/sim/sample_submission/cg/` (libcg.so + cg.dll).
  `scripts/selfplay.py` drives `cg.game.battle_start/battle_select` directly (no
  kaggle_environments; runs on Python 3.10). Full games complete with no errors.
- [x] **T5. Legal-move random baseline + win-rate.** DONE 2026-06-19. Over 160 games
  (sides swapped): random-vs-random **48.1%** (fair-harness sanity check). Heuristic
  v0 vs random **7.5%** — the naive "attack-first" priority is WORSE than random.
- [x] **T6. Study the sample rule-based agents** and document reusable patterns. DONE
  2026-06-19 → `data/META_NOTES.md` (also summarized in `PROGRESS.md`).

## Phase 2 — Strategy & iteration
- [x] **T7. Build a rule-based strategy v1** (priority: setup energy, develop board,
  knockouts, prize trade). DONE 2026-06-19. `agent/agent.py` now develops before
  attacking, benches optional setup Basics, picks max draw counts, and handles
  common yes/no prompts. Measured heuristic-vs-random **78.0% over 200 games**.
- [x] **T8. Deck design pass.** DONE 2026-06-19. Current Water Mega Abomasnow
  concept recorded in `report/deck_concept_v1.md`; mirrored `deck.csv` into
  `agent/deck.csv` for deck-selection mode.
- [x] **T9. Iterate the agent.** DONE 2026-06-19 for this pass. Added
  card-data-aware `CARD` context scoring: optional `TO_HAND`/`ATTACH_TO` choices
  now take useful visible cards/energy, and visible cards are ranked by current
  Water Mega Abomasnow deck roles. Measured heuristic-vs-random **86.3% over 300
  games**, then **88.7% over a second 300-game verification run**, beating the
  previous 78.0% best.

## Phase 3 — Report & submission
- [x] **T10. Draft the strategy report** in `report/` (logic, deck concept, stability).
  DONE 2026-06-19 -> `report/strategy_report_draft.md`.
- [x] **T11. Dry-run a submission** to confirm format; fix any packaging issues.
  DONE 2026-06-19. Added `scripts/package_submission.py`; built
  `dist/submission.tar.gz` locally, verified archive import/deck selection, and
  ran one full cabt game from the unpacked archive. No Kaggle submission attempted.
- [x] **T12. Polish report + finalize-agent planning checkpoint.** DONE 2026-06-19.
  - [x] 2026-06-19: Saved research-backed next-phase plan in
    `report/research_and_submission_plan.md`; updated stale strategy-draft metric
    from 86.3% to latest 88.7%.
  - [x] Freeze current v2 safety baseline as the first no-regression submission
    candidate.
  - [x] Build local evaluation matrix for multiple agents/decks before using the
    five daily Simulation slots.
  - Final Strategy report polish is now tracked as T17 so the next worker can
    continue research/measurement first.

## Phase 4 — Higher-ceiling agent research
- [x] **T13. Build a multi-agent/deck evaluation matrix.** DONE 2026-06-19.
  Added `agent_snapshots/v2_safety.py` and `scripts/eval_matrix.py`; supports
  frozen snapshots, random baseline, side swapping, deck overrides, and CSV/Markdown
  summaries under `report/eval/`.
- [x] **T14. Add game telemetry.** DONE 2026-06-19. `scripts/eval_matrix.py`
  now writes `report/eval/telemetry_<games>.csv` and `.md` unless
  `--no-telemetry` is passed. It logs first/second, turns/steps, result reason
  (`prize`, `deck_out`, `no_active`, `card_effect`), prize/deck counts, attackers,
  first attack/evolution turns, evolution counts, missed attachment turns, and
  decision context/type counts.
- [ ] **T15. Create first five Simulation submission candidates.** A0 current safety
  baseline; A1 state-aware attack/targeting; A2 reduced-energy Water list; A3
  Water spread variant; A4 anti-ex/single-prize variant. Re-open official Strategy
  and Simulation Kaggle pages before upload; reconfirm submission limits, package
  format, final-submission rules, report requirements, and deadlines. Dry-run all
  packages; submit only after explicit user confirmation.
  - [x] 2026-06-19: Implemented initial A1 attack/targeting upgrade in
    `agent/agent.py` while preserving `agent_snapshots/v2_safety.py`: lazy attack
    metadata scoring, KO-aware attack choice, powered-attacker promotion, healing
    target scoring, and opponent KO/damage target scoring. Verified on the
    requested 20-game matrix; keep testing before packaging as a submission.
  - [x] 2026-06-19: Rebuilt all five `dist/candidates/*.tar.gz` archives; ran
    1000-game packaged validation for A1/A2/A4 vs default Abomasnow deck (0
    draws, 0 unfinished). Audit + Wilson CI in
    `report/candidate_package_audit.md`. Submit order: A2 → A4 → A1 pending
    explicit user upload confirmation.
- [ ] **T16. Research-backed search/RL prototype.** Phase 0–3 foundation implemented
  2026-06-19 (run 13): validate_deck + pool, arena/SPRT, OptionScorer refactor,
  search/BC/RL pipelines, nightly orchestrator. Remaining: SPRT-passing gates and
  ladder-confirmed probes.
  - [x] 2026-06-19: `scripts/validate_deck.py` + 5 pool decks
  - [x] 2026-06-19: `scripts/arena.py`, `scripts/stats_utils.py`, eval_matrix deck agents
  - [x] 2026-06-19: `scripts/track_ladder.py`, pluggable `OptionScorer` in agent.py
  - [x] 2026-06-19: Track A — evalfn, search_policy, deck_search, gate_track_a
  - [x] 2026-06-19: Track B — features, collect_traces, train_bc, learned_policy, gate_track_b
  - [x] 2026-06-19: RL — `rl/cabt_env.py`, `rl/league.py`, `rl/train_rl.py`, `scripts/distill_policy.py`
  - [x] 2026-06-19: `scripts/nightly.py`, `report/finals_strategy.md`, `report/ladder_history.csv`
  - [ ] Run SPRT gates with sufficient games (40+); submit probes after user approval
- [ ] **T17. Final Strategy report polish.** Turn
  `report/strategy_report_draft.md` into the final Strategy submission after the
  next measured agent/deck pass and after official report requirements are
  rechecked.

---

## Done log
_(bot moves completed top-level tasks here with a date)_
