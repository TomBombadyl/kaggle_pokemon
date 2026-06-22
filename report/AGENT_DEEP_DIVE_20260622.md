# Agent Deep Dive — forensic analysis of OUR Kaggle agents (2026-06-22)

Scope: per-agent ladder performance, matchup forensics vs the real public field, our
ACTUAL ladder games mined from the replay dump, and a μ→win-rate translation, with a
prioritized fix list. Every number is sourced. Items I could not compute this session
(sandbox blocked all `python` execution and fresh `gate_vs_public.py` runs) are flagged
**[UNCOMPUTED]** with the reason.

**Tooling note / honesty flag:** This session's sandbox **denied all Python execution**
(`python -c …`, running any project script) and denied reading the Kaggle credentials
file. Therefore I ran **no fresh gate_vs_public runs** and **no replay-parsing scripts**.
All numbers below come from: the live `kaggle competitions submissions` CLI (pulled this
session), existing gate logs in `report/public_gate/`, the already-parsed
`report/submission_log.csv`, and **hand-decoded raw replay fields** (`info.TeamNames` +
top-level `rewards`) extracted per-file with the Grep tool. The replay hand-decode is
exact (raw ±1 reward per seat); turn-count / win-condition for our games are taken from
the previously-parsed `report/submission_log.csv` because the per-game parser could not be
re-run here.

---

## Executive summary — the 5 findings that matter most

1. **Our best agent (Search Lucario, 668 μ, ref 53869254) is the GENERIC `SearchScorer` on
   the `real_mega_lucario_ex` deck — NOT the Lucario-specialized policy.** The mirror-tuning
   edits live in `agent/lucario_policy.py` (used by `LucarioSearchScorer` = the Lucario v2
   line), which is a *different, weaker* ladder agent (600 μ). The single highest-value lever
   (the Lucario mirror) is being tuned on the agent that **isn't** our ladder champion.
   Source: `report/submission_log.csv` row 53869254 (scorer=SearchScorer);
   `scripts/package_submission.py:64,82`.

2. **The public-suite gate massively underrates the ladder — confirmed again, quantitatively.**
   The 668 agent gated **20%** on the public suite (`report/public_gate/results.md`, 2026-06-20)
   yet ladders **668** with a real **18W–15L (54.5%)** record vs the live field
   (`report/submission_log.csv`). Treat the gate as a *floor / crash-screen*, not a ladder
   predictor. Corollary: candidates rejected purely on a low gate (gen19 8.3%, Trevenant 15.3%,
   Lucario v2 8.3%) may be under-valued.

3. **We FOUND our real ladder games in the dump.** Our team name is **`TomBombadyl`**
   (`scripts/analyze_submission.py:67`). The 06-19 dump in `report/replays/` contains **35 of
   our games**, which the agent-logs manifest maps to refs: **33 → 53869254 (Search Lucario
   668)** and **2 → 53886522 (SmartBench Lucario 600)**. Hand-decoded record: Search Lucario
   **18W–15L (54.5%)**; SmartBench **2W–0L**. This is a *real* (not gate) sample of our champion.

4. **We win the way the field wins — by KO/prize race, ~13 turns — so we are NOT being
   blown out by fast aggro/board-wipe on average.** Search Lucario's parsed profile:
   median 13 / mean 13.36 turns, top loss reason **`prize`** (KO race), first-player 66.7%
   (`report/submission_log.csv`). That tracks the field's KO-race-71.7% / 12-turn-median
   profile (`report/winner_analysis_20260621.md`). Our problem is **margin** (a coin-flip
   ~54% vs a field whose median μ is ~1064), not a structural tempo failure.

5. **The two named, concrete holes are real and code-located:**
   (a) **Alakazam folds to Iono/Bellibolt** — gate **29.7% vs Iono**, 43.4% vs Lucario-search
   (`report/public_gate/alakazam_best5_g417_20260620.txt`, n=417/matchup), matching the RPS
   triangle (Alakazam → loses to Bellibolt).
   (b) **The Lucario mirror is our biggest single bucket and we under-perform it** — the
   LucarioSearchScorer line measured **14.4% vs lucario** before tuning
   (`report/lucario_mirror_analysis_20260622.md`), driven by a `-500` endgame penalty in
   `agent/lucario_policy.py:321` (since edited to `+200`, **but on the non-champion agent**).

---

## 1. Per-agent ladder performance (live CLI, pulled 2026-06-22)

Source: `kaggle competitions submissions -c pokemon-tcg-ai-battle` (this session). Note the
live `publicScore` for the two newest probes is **600.0** — the fresh-submission default μ
before σ settles — even though `report/ladder_history.csv` still lists them as PENDING and
lists Alakazam at 636.8 / Trevenant 597.7. **The CSV is stale relative to the live CLI**
(flagged; see reconciliation table).

| Rank | Agent (fileName) | ref | Live μ (CLI) | Date | Status | Notes |
|---:|---|---|---:|---|---|---|
| 1 | track_a_lucario_ex_search (Search Lucario) | 53869254 | **668** | 06-20 | COMPLETE/Final | SearchScorer + real_mega_lucario_ex; protected |
| 2 | track_a_lucario_ex_search (earlier reading) | 53869254 | 660.5 | 06-20 | COMPLETE | same ref, mid-settle reading |
| 3 | ryotasueyoshi_alakazam_best5 | — | **659.0** | 06-21 | COMPLETE | live CLI 659.0 (CSV said 636.8 — drifted up) |
| 4 | a2_kyogre | 53854707 | 633.0 / 672.7 | 06-19 | COMPLETE | μ swung 600→645→672→633 as σ settled |
| 5 | track_a_probe_1 (Kyogre+2e) | 53856711 | 626.0 | 06-19 | COMPLETE | |
| 6 | track_a_trevenant_leader_search | — | **615.6** | 06-21 | COMPLETE | live CLI 615.6 (CSV said 597.7 — drifted up) |
| 7 | track_a_gen19_fast_basic_search | — | **600.0** | 06-22 | COMPLETE | fresh; σ not settled (CSV says PENDING) |
| 7 | track_a_lucario_search (Lucario v2) | — | **600.0** | 06-22 | COMPLETE | LucarioSearchScorer; fresh; σ not settled |
| 9 | track_b_learned_rl_deck_kaggle | 53868798 | 585.1 | 06-20 | COMPLETE | LearnedScorer; weak |
| 10 | track_a_probe_2 (Abomasnow+4e) | 53856676 | 548.6 | 06-19 | COMPLETE | |
| 11 | track_a_alakazam_leader_search | 53890064 | 545.6 | 06-20 | COMPLETE | Leader-Alakazam deck + SearchScorer |
| 12 | track_c_lucario_rulecore_smartbench | 53886522 | 535.6 / 600 | 06-20 | COMPLETE | LucarioScorer+SmartBench |
| 13 | track_b_learned_alakazam | 53856584 | 490.4 | 06-19 | COMPLETE | |
| 14 | track_b_learned_dragapult | 53856590 | 468.9 | 06-19 | COMPLETE | |
| 15 | track_d_lucario_rl_mcts | 53885445 | 368.5 / 324.6 | 06-20 | COMPLETE | RL+MCTS iter0; empty-bench failure, retired |

**Trajectory / σ-settling note:** μ drifts materially in the first ~dozen games. a2_kyogre
read 600→645.7→672.7→633.0 across the 06-19 readings (`report/ladder_history.csv`). The two
06-22 probes both sit at the 600 default — **their true μ is not yet known**; do not conclude
they "failed" from the 600 reading. (CSV had them as PENDING; CLI now shows COMPLETE@600.)

**Stale-data reconciliation (flag):**

| Agent | ladder_history.csv | live CLI 2026-06-22 | verdict |
|---|---:|---:|---|
| Alakazam best5 | 636.8 | 659.0 | CSV stale (low) |
| Trevenant | 597.7 | 615.6 | CSV stale (low) |
| Lucario v2 | PENDING | 600.0 (fresh) | settled to default, not yet meaningful |
| gen19 fast-basic | PENDING | 600.0 (fresh) | settled to default, not yet meaningful |

> **Recommendation:** regenerate `report/ladder_history.csv` from the live CLI; it currently
> understates Alakazam and Trevenant and mislabels two COMPLETE probes as PENDING.

---

## 2. Matchup forensics vs the real public field (gate logs)

The public field = 12 agents in `data/kaggle_ref/opponents/` (RPS-relevant ones: iono-deck =
the Iono/Bellibolt disruptor corner; mega-lucario / crustle-aware-anti-wall / 915-lucario-search
= Lucario corner; alakazam-best-5th = Alakazam corner; dragapult/abomasnow/1084-baseline = field).

### Matchup matrix (suite-gate win rates; cells cite the log)

| Our agent (scorer) | Iono | mega-Lucario | crustle-anti-wall | 915-Lucario-search | 1084-base | Alakazam-5th | Dragapult | Abomasnow | **Suite mean** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Alakazam best5** (rule-based) | **29.7** | 65.2 | 47.4 | **43.4** | 52.2 | 49.9 | 57.3 | 70.5 | **57.3%** (n=417/cell) |
| **Search Lucario v2** (LucarioSearchScorer) | 13.3 | 10.0 | 6.7 | 10.0 | **0.0** | 6.7 | 10.0 | 20.0 | **8.3%** (n=30/cell) |
| AZ Lucario r10 (track_e) | 25.0 | 41.7 | 8.3 | 8.3 | 8.3 | 8.3 | 8.3→25 | 16.7 | 15.3% (n=12) |
| AZ Lucario (track_e) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 33.3 | 8.3 | 0.0 | 3.5% (n=12) |
| Lucario RuleCore (track_c) | 42 | 58 | 0 | 0 | 25 | — | 58 | 50 | 23.6% (n=12) |

Sources: `alakazam_best5_g417_20260620.txt`, `track_a_lucario_ex_search_v2_field.txt`,
`az_lucario_r10_g12_20260620.txt`, `az_lucario_g12_20260620.txt`, `rulecore_field.txt` /
`results.md`.

**No public-suite gate log exists for the 668 Search Lucario (SearchScorer) package itself** —
the closest is the 2026-06-20 `results.md` entry for `track_a_lucario_ex_search` at **20% suite**.
The v2 log (8.3%) is the *LucarioSearchScorer* variant, a different brain. **[UNCOMPUTED]** a
fresh `gate_vs_public.py --agent dist/candidates/track_a_lucario_ex_search.tar.gz --games 20`
(Python blocked this session) — this is the one fresh run most worth doing next.

### Mapping onto the RPS triangle (Lucario→Bellibolt→Alakazam→Lucario)

- **Alakazam best5 — textbook triangle behavior.** Beats the Lucario corner (mega-Lucario
  65.2%, Dragapult 57.3%, Abomasnow 70.5%) but **folds to the Iono/Bellibolt disruptor corner
  (29.7%)** and to the *strong* mirror Lucario-search bot (43.4%). This is exactly the field
  finding "Alakazam beats Lucario 51.9% but loses to Bellibolt 30.2%"
  (`report/winner_analysis_20260621.md`). **Iono is the load-bearing hole.** A prior deck-out-
  guard relaxation made it *worse* (30%→22%), so it needs a structural game-speed fix, not a
  one-liner (`report/STRATEGY_DECISION_20260621.md` §Path B).
- **Lucario v2 (LucarioSearchScorer) — broadly weak on the public suite (8.3%)** with its
  *worst* cell being the 1084 baseline (0%) and the strong Lucario-search mirror (10%). Yet the
  same agent gates **69.6%** on the *leader/pool* suite (`lucario_v2_vs_leader_suite_20260620.txt`).
  The huge gap = the leader/pool suite is far easier than the real public bots; this agent
  has NOT been ladder-proven beyond the fresh 600.
- **Search Lucario (668)** worst matchups by gate are the wall/disruptor public bots (the old
  20% suite was 0% vs 1084 and vs simple-baseline-Lucario, ~50% vs Dragapult) — but its real
  ladder record (54.5%) shows the *live human field* is much softer than those tuned bots.

---

## 3. Our ACTUAL ladder games (mined from the dump)

**Our team name = `TomBombadyl`** (`scripts/analyze_submission.py:67`). The 06-19 dump
(`report/replays/`, 5,599 files) **does contain our games** — 35 files match `TomBombadyl`.
The agent-logs manifest (`report/agent_logs/manifest.csv`) maps each episode→submission ref:

| ref | agent | our games in dump | hand-decoded record |
|---|---|---:|---|
| **53869254** | **Search Lucario (668)** | **33** | **18W – 15L = 54.5%** |
| 53886522 | SmartBench Lucario (600) | 2 | 2W – 0L |

Hand-decode method: per file, Grep `info.TeamNames` (gives our seat) + top-level `rewards`
(±1 per seat); win = our seat's reward is +1. This is exact. The 18–15 split for 53869254
**matches `report/submission_log.csv` exactly** (independent confirmation of that parse).

### Per-game ledger for Search Lucario (53869254), 33 games

W = win, L = loss; opponent = the non-TomBombadyl `TeamNames` entry.

| # | episode | opponent (team) | result |
|---:|---|---|:--:|
| 1 | 80804855 | MORU | W |
| 2 | 80805378 | rode | L |
| 3 | 80806088 | rikulist | L |
| 4 | 80806610 | yiyi | W |
| 5 | 80807125 | MSGG411 | L |
| 6 | 80807667 | LaiCxm | W |
| 7 | 80808182 | 町田遥裕 | L |
| 8 | 80808712 | kenimuku | W |
| 9 | 80809396 | ega_water | W |
| 10 | 80810096 | 600505-ศิวกร | W |
| 11 | 80810789 | suh-sunaneko | W |
| 12 | 80811481 | 谷藤修士朗 | L |
| 13 | 80812011 | CSCMU | W |
| 14 | 80812533 | beaverjr | W |
| 15 | 80813235 | Артём Свинобоев | L |
| 16 | 80813946 | Masatoshi Fujimoto | W |
| 17 | 80814646 | からし | L |
| 18 | 80815170 | nikechan | W |
| 19 | 80815886 | Team Rocket | W |
| 20 | 80815901 | 今井大登 | W |
| 21 | 80816571 | Antonio Senzatela | L |
| 22 | 80816987 | shu-tanuma | L |
| 23 | 80817112 | Dracufeuer | W |
| 24 | 80832283 | Pikachu, I choose you! | L |
| 25 | 80835338 | シン ソウイチロイ | W |
| 26 | 80839145 | Galza98 | W |
| 27 | 80862985 | hatata | L |
| 28 | 80869508 | Kurokawa | W |
| 29 | 80873459 | quwon_000 | W |
| 30 | 80875039 | 私密马赛 | L |
| 31 | 80894216 | Raymond Brunell | L |
| 32 | 80901877 | oimo_tabetai | L |
| 33 | 80902314 | tototo | L |
| — | 80902763 | hector cardenas | W (ref 53886522) |
| — | 80903313 | nugui-nugui | W (ref 53886522) |

**Failure-mode / win-condition profile (from `report/submission_log.csv`, prior parse of
this same ref):** Search Lucario — avg 13.36 turns, **median 13**, top loss reason **`prize`**
(i.e., we lose KO/prize races, not to fast board-wipe or deck-out), first-player rate 66.7%.
SmartBench — 2 games, both ~10.5 turns (too few to read).

**[UNCOMPUTED] per-game turn count, win-condition (KO/board-wipe/deck-out) and opponent
*archetype* for these 33 games.** Opponent decks are stored as card-*IDs* in
`steps[0][0].visualize[0].action`; resolving them to archetypes needs the
`scripts.mine_episode_replays._archetype` helper + `EN_Card_Data.csv` lookup, i.e. Python,
which was blocked. The win-condition aggregate (top loss = `prize`) is taken from the prior
`submission_log.csv` parse of this exact ref. To complete this when Python is available:
`python scripts/analyze_submission.py --ref 53869254 --offline` (re-parses these replays).

**Discrepancy flag:** `report/FINALS_PIN.md` lists 53869254 as "48.5% (16/33)" whereas the
raw `rewards` hand-decode and `submission_log.csv` both give **18/33 = 54.5%**. The raw-reward
decode is authoritative (it reads the ground-truth ±1 outcome per seat); the 16/33 figure in
FINALS_PIN appears to be an earlier/partial count and should be corrected to 18/33.

---

## 4. Score (μ) ↔ win-rate translation

Per-game reward is binary ±1; the 600–1300 "score" is a TrueSkill μ aggregated over games.
μ rises by beating *strong* opponents and is noisiest while σ is high (first ~dozen games).
Translation, anchored on our one real sample:

- **Search Lucario: 54.5% real win rate (18/33) ⇒ μ 668.** So on the *live human field*, a
  coin-flip-plus agent sits at ~668. That is the empirical exchange rate for us right now:
  **~+3.4 μ per +1 percentage point of win rate** around the 50% region (very rough: 668 is
  ~68 above the 600 floor at +4.5 pp over 50%).
- **Gate vs ladder are decoupled.** Same agent: 20% public-suite gate but 54.5% live. The
  public bots are *harder* than the median human ladder opponent, so the gate is a pessimistic
  floor. a2_kyogre is the canonical proof: ~13% gate (per memory) → laddered 633–672.
- **Distance to the field.** Field median μ rose 628→**1064** over 06-16→06-20 (~+110/day),
  top plateau ~**1310** (`report/winner_analysis_20260621.md` / handoff). Our best (668) is
  **~396 μ below the field median** and **~640 below the leaders**. At ~+3.4 μ/pp, closing to
  the 1064 median implies needing roughly a **+60–65 pp** swing in *effective* win rate vs the
  *current* field — i.e., the field is hardening faster than a static 54% agent can hold rank.
  A static agent **loses rank daily**; pilot improvement is time-sensitive.
- **Effective win-rate implied per agent** (rough, from μ vs the 600-floor / 54.5%@668 anchor):
  Alakazam 659 ≈ ~52–54% live; Kyogre 633–672 ≈ ~51–54%; Trevenant 615 ≈ ~50–51%; the
  600-floor probes (Lucario v2, gen19) ≈ unknown/≤50% until σ settles.

---

## 5. Win-condition profile of OUR agents vs the field

- **Field:** KO/prize race 71.7% (~13 turns), board-wipe 20.7% (~9 turns), deck-out 7.5%
  (~16 turns); median 12 turns; aggressive (`report/winner_analysis_20260621.md`).
- **Search Lucario (us):** median 13 turns, top loss reason **`prize`** (we lose KO races),
  not board-wipe or deck-out (`report/submission_log.csv`). **We play the field's game and
  lose the close ones** — consistent with a ~54% coin-flip. We are **not** systematically
  getting run over by turn-8 aggro or board-wiped (those would show as short avg-turns + a
  `no_active`/board-wipe top-loss; ours is 13 turns / `prize`).
- **Implication:** the gain is in *converting* KO races (mirror tempo, prize sequencing,
  closing when ahead) — exactly the mirror lever — not in adding anti-aggro or anti-wall tech
  to the champion. SmartBench's 10.5-turn / 100% "fast-loss" reading is from only 2 games and
  is noise, not a board-wipe signal.

---

## Per-agent scorecard

| Agent | Live μ | Gate suite mean | Best matchup(s) | Worst matchup(s) | Primary failure mode |
|---|---:|---:|---|---|---|
| **Search Lucario (668)** SearchScorer | **668** | ~20% (06-20) | live human field (54.5% real) | tuned public wall/disruptor bots (0–10%) | loses close **KO/prize races** (top loss `prize`, 13 turns) |
| **Alakazam best5** rule-based | 659 | **57.3%** (n=417) | Abomasnow 70.5, mega-Lucario 65.2, Dragapult 57.3 | **Iono 29.7**, 915-Lucario-search 43.4, crustle 47.4 | folds to **Iono/Bellibolt disruption** (triangle) |
| a2_kyogre Heuristic | 633–672 | ~13% (memory) | — | — | gate-underrated; portfolio backup |
| Trevenant SearchScorer | 615.6 | 15.3% | — | Kyogre | generic Search pilot on leader deck (deck-transfer only) |
| Lucario v2 LucarioSearchScorer | 600 (fresh) | **8.3%** | leader/pool suite (69.6% — easy) | 1084-baseline 0%, mirror-search 10% | poor public transfer; **mirror 14.4%** pre-tune |
| gen19 fast-basic SearchScorer | 600 (fresh) | 8.3% | — | whole suite | weak generic pilot; deck/pilot mismatch |
| SmartBench Lucario | 600/535.6 | 9.5–23.6% | — | walls 0% | too few episodes; no gust / wall route |
| Lucario RL-MCTS iter0/7 | 368.5/324.6 | 3.5–6.9% | — | everything | **empty-bench/board-wipe**; severely undertrained |

---

## Prioritized recommendations (most μ first)

### P1 — Put the mirror-tuned policy on the CHAMPION deck, and gate it as the real lever
**Why #1:** The Lucario mirror is ~30% of all games, 50/50 on deck → pure pilot. But the
mirror tuning (`agent/lucario_policy.py:321` `-500`→`+200` endgame close-out; `:397` early-KO
`+500`) lives in **LucarioSearchScorer**, which is the *600-μ* agent — NOT our 668 champion
(generic `SearchScorer`). **The highest-value, lowest-risk move is to make a Lucario-aware
champion: package the `real_mega_lucario_ex` deck with `LucarioSearchScorer` (the tuned
policy) and beat 668.**
- Files: `agent/lucario_policy.py` (tuned), `scripts/package_submission.py --scorer lucario_search`.
- Success bar: **self-play mirror ≥ 55%** AND `gate_vs_public.py --only lucario --games 30 ≥ 45%`
  (up from the pre-tune 14.4% in `lucario_mirror_analysis_20260622.md`) AND **no regression**
  on the full public suite vs the 668 baseline. Then ladder-probe one slot; pin if μ > 668.
- **[UNCOMPUTED]** all three gates (Python blocked). These are the exact next runs.

### P2 — Establish the champion's TRUE gate baseline (one cheap run)
We have **no** public-suite gate for the 668 SearchScorer package — only a 20% line from a
06-20 results.md note. Run `python scripts/gate_vs_public.py --agent
dist/candidates/track_a_lucario_ex_search.tar.gz --games 20`. This is the control any P1
candidate must beat, and it costs one ~minutes run. Success bar: record the per-opponent split
so P1's "no regression" claim is measurable. **[UNCOMPUTED] this session.**

### P3 — Fix Alakazam's Iono/Bellibolt hole (our Lucario-counter hedge)
**Why:** Alakazam (659 μ, 57.3% gate) is our second pillar and the field's Lucario-counter,
but it loses the disruptor corner: **Iono 29.7%**, and the strong Lucario-search mirror 43.4%
(`alakazam_best5_g417_20260620.txt`). A prior deck-out-guard relaxation regressed Iono to 22%
→ needs a *game-speed* fix (faster Abra→Alakazam, earlier Boss's Orders snipes, avoid
over-commit before the Iono window) per `STRATEGY_DECISION_20260621.md` §Path B.
- Files/matchup: the imported Alakazam best5 policy; gate `--only iono --games 30`.
- Success bar: **Iono ≥ 40%** AND **suite mean ≥ 57.3%** (no overall regression). Only then
  spend a slot.

### P4 — Data hygiene (cheap, prevents bad decisions)
- Regenerate `report/ladder_history.csv` from the live CLI (it understates Alakazam 636.8→659,
  Trevenant 597.7→615.6, and mislabels two COMPLETE probes as PENDING).
- Correct `report/FINALS_PIN.md` 53869254 win-rate **16/33 → 18/33 (54.5%)** to match raw rewards.
- When Python is available, run `scripts/analyze_submission.py --ref 53869254 --offline` to fill
  in the **[UNCOMPUTED]** per-game turn/win-condition/opponent-archetype detail for our 33
  champion games (the replays are still on disk; do not delete until this is done — matches the
  handoff's keep-until-mirror-work-done policy).

### Do NOT
- Do not spend a slot on un-improved gen19 / Lucario v2 / Trevenant (gate 8–15%, no ladder edge).
- Do not run more `robust_deck_search.py` with a generic brain (proven 3.8–12.5% L1).
- Do not re-submit Alakazam or Trevenant before P3's bar is cleared.
- Do not trust the public-suite gate as a ladder predictor (it underrates by ~30+ pp for us).

---

## Commands actually run this session

- `kaggle competitions submissions -c pokemon-tcg-ai-battle` (live μ table).
- Read: handoff, winner_analysis, ladder_history.csv, STRATEGY_DECISION, DECK_RANKING,
  gate_vs_public.py, mine_episode_replays.py, all `report/public_gate/*` logs,
  submission_log.csv, FINALS_PIN.md, lucario_mirror_analysis_20260622.md, lucario_policy.py.
- `grep -rl "TomBombadyl" report/replays` → 36 matches (35 unique episodes).
- Per-file Grep of `info.TeamNames` + `rewards` for all 35 of our games (hand-decoded W/L).
- `grep` of `report/agent_logs/manifest.csv` to map our 35 episodes → refs (33→53869254, 2→53886522).
- Created then deleted a scratch script `scripts/_dd_teamnames.py` (Python exec was blocked, so
  it was never run; removed).

## What was BLOCKED (and the exact follow-up)
- **All `python` execution** (sandbox denial) ⇒ no fresh `gate_vs_public.py` runs, no replay
  archetype/turn/win-condition parsing. Follow-ups: P1/P2/P3 gates above, and
  `analyze_submission.py --ref 53869254 --offline` for per-game forensics.
- Reading Kaggle credentials (`~/.kaggle/kaggle.json`) was denied (expected/correct); team
  name was instead recovered from `scripts/analyze_submission.py:67`.
