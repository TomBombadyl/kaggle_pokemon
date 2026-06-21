# Deck-RL continuation handoff — 2026-06-21

**Purpose:** Resume the deck-RL / robust-deck-search line started 2026-06-20, with the
hard-won conclusion baked in. Updated after the 2026-06-21 ladder probes scored and the
field-analysis work.

Read first: this file → `report/winner_analysis_20260621.md` (the field map) →
`report/STRATEGY_DECISION_20260621.md` → top of `PROGRESS.md`. Memory:
`[[lucario-is-the-field-wall]]`, `[[episode-reward-is-winloss]]`, `[[quality-over-speed]]`,
`[[ladder-meta-and-standing-20260620]]`.

---

## Ladder state (2026-06-21, scored)

| agent | μ | note |
|---|---|---|
| Search Lucario (Final) | **668** | protected best |
| lucario_ex_search | 660.5 | prior |
| **Alakazam best5** | **636.8** | today's probe — Lucario *counter*, healthy |
| Kyogre (a2_kyogre) | 633.0 | already run |
| **Trevenant** | **597.7** | today's probe — weak, as 15% gate predicted |

**2 of 5 slots used today; HOLD the other 3** (nothing un-run beats 668). Do NOT re-submit
Alakazam or Trevenant. ⚠️ A stale autonomous doc (Session 38) says "submit Trevenant Slot 3" —
that's a double-submit trap; Trevenant is already done. See PROGRESS Session 39 correction.

---

## FIELD MAP (from `scripts/analyze_winners.py` on 5,584 decided games, 2026-06-21)

This is the daily lens the user wants: **understand *why winners win*, then fold it into the
pilot — don't just copy decks.** Key findings:

- **The meta is a rock-paper-scissors triangle:** **Lucario → Bellibolt → Alakazam → Lucario.**
  Lucario beats unknown 52.6%, Bellibolt 79.5%, Dragapult 65.5%, Kyogre 75%; only loses to
  Alakazam (48.1%). Alakazam beats Lucario 51.9% but loses to Bellibolt (30.2%).
- **Lucario is the hub:** ~53% of all decks played (6,118 slots), 52.5% win rate. It's the safe
  pick that crushes everything but its one counter.
- **THE LEVER — the Lucario mirror:** the single most common matchup is Lucario-vs-Lucario
  (**1,688 games ≈ 30% of all games**), and it's **50/50 on deck → decided purely by pilot.**
  Winning the mirror more often is the highest-value score gain available.
- **Field is aggressive, not grindy:** KO/prize race 71.7% (~13 turns), board-wipe 20.7%
  (~9 turns), deck-out only 7.5% (~16 turns). Median game 12 turns. Setup speed + KO tempo win.
- **First-player edge is small** (52.1%).
- **Field is hardening fast** (episodes-index): median agent score 628→1064 over 06-16→06-20
  (~+110/day) while top plateaus ~1320. A static agent loses rank daily → pilot work is
  time-sensitive. See `[[ladder-meta-and-standing-20260620]]`.

**Scoring (answer to "why score varies"):** per-game reward is binary ±1; the 600–1300 "score"
is a TrueSkill μ aggregated over games. μ compounds by beating *strong* opponents (= Lucario),
swings most while σ is high (first ~dozen games of a fresh submission), so "score a lot" =
win consistently vs a strong field. There is no hidden per-game point system.

### Daily routine (do this each time a new dump drops)
1. `kaggle datasets download kaggle/pokemon-tcg-ai-battle-episodes-<DATE> -p report/replays --unzip`
   (slugs in `report/deck_rl/episode_dataset_manifest.csv`; refresh it from
   `kaggle/pokemon-tcg-ai-battle-episodes-index`).
2. `python scripts/analyze_winners.py --replays report/replays` → dated
   `report/winner_analysis_<DATE>.md`. Track how the triangle / tempo / hardening shift.
3. (optional) `python scripts/extract_gauntlet_from_replays.py --min-score 1 --max-decks 60`
   to refresh real decks — but remember decks ≠ the win (pilot is).
4. **DELETE the raw dump** (`rm -rf report/replays/*.json`) once steps 2–3 are done. See policy below.

### Replay-data lifecycle / storage policy

**Raw replays are TRANSIENT and disposable — re-downloadable any day from the episodes-index.**
One day's dump = ~20 GB / ~5,500 JSON files. Z: has ~1.6 TB free, so disk isn't urgent, but
~20 GB/day creeps (~600 GB/month) — don't hoard.

- **Keep at most 1–2 days of raw replays** in `report/replays/` at once; delete after extracting.
  (`report/replays/*.json` is gitignored — never committed.)
- **The value is the small DERIVED artifacts, which we keep permanently & commit:**
  - `report/winner_analysis_<DATE>.md` (the daily field map — tiny)
  - `report/deck_rl/mined_decks/` (~72 KB) — refreshed each mining; overwrites in place
  - `report/deck_rl/episode_dataset_manifest.csv` (the index; lets us re-pull any day)
- **Current state:** the 06-19 dump (21 GB) is still on disk. The next task (Lucario-mirror
  pilot work) may want to mine mirror-match play from it, so **keep it until that's done, then
  delete**. Everything else has already been extracted from it.
- **Optional future enhancement:** append one row per day to a `winner_analysis_history.csv`
  (median turns, win-condition mix, top-archetype WRs, mirror %) so we track meta drift over
  time *without* keeping any raw data.

---

## TL;DR — the deck-RL line is validated *as a method* but is a DEAD END with a generic brain

Two independent runs + a pyramid gate proved it: **the bottleneck is the pilot (brain),
not the deck.** Do **not** spend more compute searching decks with a heuristic/Search brain
and expect ladder gains. The numbers:

| Candidate | Offline (gauntlet) | L1 vs real public field |
|---|---|---|
| Robust deck, **heuristic** pilot | ~48% holdout | **12.5%** |
| Robust deck, **Search** pilot | **78% mean** (mirror illusion) | **3.8%** |
| Imported **Alakazam best5** (tuned rule-based) | — | **57.3%** |
| (reference) tuned **Search Lucario** | — | ~29% / **668 μ** live |

**Why the 78% was fake:** `rl/gauntlet.py:winrate_vs` pilots **both sides with our own
brain**, so "78% mean" = our brain+deck beats our brain+opponent-decks (a mirror). Against
the *real tuned public agents* at L1, our generic Search brain loses ~96% regardless of deck.

**Conclusion:** deck robustness with a weak/generic pilot does not transfer. Only a **tuned
brain+deck combo** gates respectably. Pilot sophistication >> deck novelty.

---

## Current ladder state (as of this handoff)

- **Finals (protected):** `53869254` Search Lucario **668 μ** (both slots).
- **In flight:** `ryotasueyoshi_alakazam_best5.tar.gz` — PENDING ladder eval (~40 min for
  first reading). Decision thresholds when it lands:
  - **>660 μ** → pin as a Final; continue probes in other slots.
  - **550–660 μ** → keep probing; implement Iono fix (Path B) in offline time.
  - **<550 μ** → stop; do Iono/Crustle fixes before re-uploading.
- A `ScheduleWakeup` is set to fetch the score via
  `kaggle competitions submissions -c pokemon-tcg-ai-battle` and update the PENDING row in
  `report/ladder_history.csv`.

---

## Artifacts (what exists, where)

**Robust-search subsystem (self-contained; never touches `report/rl_deck_campaign/`):**
- Code: `rl/robust_search.py`, `rl/gauntlet.py`, `rl/robust_fitness.py`, `rl/meta_solver.py`,
  `rl/winrate_surrogate.py`, `rl/deck_genome.py`; CLI `scripts/robust_deck_search.py`.
- Heuristic-pilot run (30 gens): `report/robust_deck_rl/` — `best_deck.csv`, `metrics.csv`.
  Clean-field baseline backed up: `metrics_cleanfield.csv`, `best_deck_cleanfield.csv`.
- Search-pilot run (12 gens, this session): `report/robust_deck_rl_search/` — `best_deck.csv`,
  `metrics.csv` (mean ~78% / L1 3.8%).
- Mined real field: `report/deck_rl/mined_decks/` (60 winning decks: 17 alakazam, 16 lucario,
  2 bellibolt, 1 kyogre, 24 unknown). Auto-included by `rl/gauntlet.py`.
- Replays: `report/replays/` (5,473 episodes from 2026-06-19, 21 GB — safe to delete to reclaim disk).
- Packaged (NOT uploaded): `dist/candidates/track_e_robust_deck_search.tar.gz`,
  `dist/candidates/track_e_robust_deck_search_pilot.tar.gz`.

**Existing GA deck campaign (separate):** `report/rl_deck_campaign/` (`checkpoint.json`,
`deck_ga.json`, `best_deck.csv`, `population/`); driver `rl/train_deck_campaign.py`.

---

## Gotchas (don't re-trip these)

1. **Episode reward is win/loss (±1), NOT ELO.** Mine decks with `--min-score 1` (winners).
   The 600–1300 figures in `episode_dataset_manifest.csv` are ladder μ, absent per-replay.
   See `[[episode-reward-is-winloss]]`.
2. **The gauntlet pilots both sides with the same brain** (`winrate_vs` default
   `scorer="heuristic"`). High offline mean ≠ ladder strength — always confirm with
   `gate_vs_public.py` (real public agents).
3. **`gate_track_b.py --model` wants a distilled npz**, not a `.pth`. Lucario RL `.pth` is
   gated via `--scorer lucario_mcts --model <pth>` (or `import_lucario_rl_outputs.py`).
4. Kaggle **kernel-output pull is 403** for private notebooks — download `.pth` files by hand.

---

## What to do next (in priority order)

**The deck-RL line only pays off if decks are paired with a STRONG pilot, and the field map
says the #1 lever is the Lucario mirror.** Priority order:

1. **★ Win the Lucario mirror (highest leverage).** It's ~30% of ALL games and 50/50 on deck,
   so pilot skill is the entire edge. Improve our Search Lucario brain's *mirror* play
   (prize-trade sequencing, KO tempo by ~turn 12, setup speed — the field is aggressive, not
   grindy). Measure by self-play mirror win rate AND `gate_vs_public.py --only lucario --games 30`.
   This directly raises our best agent (668), which is already the right deck.
   - Lucario tooling: `agent/lucario_policy.py`, `agent/search_policy.py` (`LucarioSearchScorer`),
     `agent/lucario_mcts_*`. Package with `--scorer lucario_search` / `lucario_mcts`.

2. **Shore up Alakazam (our Lucario-counter hedge, 636.8).** Its hole is **Bellibolt 30.2% /
   Iono 29.7%** (matches the triangle: Alakazam loses to Bellibolt). Anti-disruption tuning;
   re-gate `gate_vs_public.py --only iono --games 30` (require Iono ≥40% AND suite ≥57.3%).
   `report/STRATEGY_DECISION_20260621.md` §Path B.

3. **Daily field analysis** — run `scripts/analyze_winners.py` on each new dump (see routine
   above); watch the triangle/tempo/hardening shift and re-aim the pilot work accordingly.

4. **Do NOT** run more `robust_deck_search.py` with a generic brain expecting ladder gains
   (proven 3.8–12.5% at L1), and do NOT spend an upload slot on an un-improved candidate.
   If ever continuing deck search, co-optimize deck+pilot (put a tuned brain in
   `rl/gauntlet.py:winrate_vs`).

---

## Resume commands

```bash
# fetch the Alakazam ladder score
kaggle competitions submissions -c pokemon-tcg-ai-battle

# gate any candidate vs the real public field (the only honest predictor)
python scripts/gate_vs_public.py --agent dist/candidates/<name>.tar.gz --games 20
python scripts/gate_vs_public.py --agent <dir-or-tar> --only iono --games 30

# package a deck + brain (no upload)
python scripts/package_submission.py --deck <deck.csv> --scorer search --name <name>

# (if ever needed) robust search — but pair with a strong pilot, see "What to do next"
python scripts/robust_deck_search.py --generations 30 --population 16 --games 10 --surrogate
```

**Never upload without explicit user OK.** Finals slots hold Search Lucario 668 μ — protect them.

---

## Single exact next action

**Start the Lucario-mirror pilot work** (handoff §"What to do next" #1) — it's ~30% of all
games, 50/50 on deck, decided purely by pilot, and it raises our already-best agent (668).
Baseline the current Search Lucario mirror win rate (self-play + `gate_vs_public.py --only
lucario --games 30`), then improve prize-trade sequencing / KO tempo (field is aggressive,
median 12 turns). Ladder scores are in (Alakazam 636.8, Trevenant 597.7); HOLD remaining slots,
no uploads without user OK.
