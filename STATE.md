# STATE — current state & the single next action

> **Mindset:** `RULINGS.md` Part 0 · **Plan:** `ROADMAP.md` · **Upload gate:** `scripts/check_upload_eligible.py --suggest`

---

## As of 2026-07-09 (evolve/ pilot run — real result: no improvement found, 3 gens)

**Ran for real** on the dev machine (this sandbox still has no `cg` engine / Kaggle egress —
these numbers are real games, run locally, not simulated here):

```
python evolve/run_evolution.py --target archaludon --generations 3 --population 6 --games 30 --report
gen0 baseline: 68.7% [60.9, 75.5] (n=150)
gen1: best 73.3% [65.7, 79.8] (n=150) vs baseline 68.7%
gen2: best 69.3% [61.5, 76.2] (n=150) vs baseline 68.7%
gen3: best 69.3% [61.5, 76.2] (n=150) vs baseline 68.7%
```

Full table: `eval/evolve_archaludon_gen3.md`. **Result: no candidate's Wilson CI cleared the
baseline's** — best raw win-rate (73.3%, gen1) still overlaps baseline `[60.9, 75.5]`. Per
Ruling R8's own statistical bar, that's noise, not signal. **Nothing promoted, nothing changed
in `agent/archaludon_agent.py`.** Legitimate negative result after one pilot, not a failure of
the tool — 18 candidates across 3 generations of ±15% bounded perturbation on 2 constant blocks
is a small search; three ways to read it: (a) the shipped constants are already close to a local
optimum for this gate, (b) 3 generations / population 6 is too small a budget to find a real
effect against this much game-outcome noise (n=150 total games has WR CI half-width ~7pp), or
(c) `_ICE_CREAM_HP_THRESHOLD` / `_ATTACK_BASE_DMG` aren't where the marginal win is — a different
target (matchup levers, a different constant block) might show more headroom.

**Bug found + fixed by running it for real:** `evolve/targets.py`'s `_archaludon_target()`
imported `agent.archaludon_agent` directly, which only sets up `sys.path` for the
Kaggle-packaged runtime, not a dev machine — `eval/harness.py` covers the dev-machine `cg` path
itself, but harness isn't imported until `evaluate()` resolves `gate_fn`, *after* `get_target()`
already tried and failed to import `archaludon_agent`. Fixed by calling the existing
`agent.cg_bootstrap.ensure_cg_engine()` (already used by dragapult/iono/abomasnow agents) at the
top of `_archaludon_target()`, before the archaludon_agent import. This is exactly the kind of
bug that only running against the real engine surfaces — the synthetic dry-run earlier this
session (fake `EvolveTarget`, monkeypatched `evaluate()`) never exercised the real
`_archaludon_target()` function at all, so it couldn't have caught this.

**THE SINGLE NEXT ACTION:** pick one of (a)/(b)/(c) above and re-run with a deliberate change —
e.g. `--generations 6 --population 10` for a bigger budget on the same target, or add a second
`evolve/targets.py` entry for a different constant block — rather than re-running the same
config expecting a different answer.

---

## As of 2026-07-09 (evolve/ landed — AlphaEvolve-style search, additive only)

**What landed:** `evolve/` module (targets.py, evaluator.py, proposer.py, run_evolution.py,
promote.py) — generates many candidate parameter sets per round against Archaludon's
`_ICE_CREAM_HP_THRESHOLD` / `_ATTACK_BASE_DMG` constants and scores each through the existing
`eval/harness.py` + `eval/gates.py` path (no new eval logic). Small additive hook added:
`agent/archaludon_levers.py` (mirrors `agent/dragapult_levers.py`'s override pattern) +
`param_overrides` kwarg on `eval.gates.gate_archaludon_matchups`. Nothing in `agent/*.py` is
edited automatically — promotion (`evolve/promote.py`) is a manual, human-reviewed step, and a
promoted candidate still goes through the unchanged `check_upload_eligible.py` / R12 pipeline
before any Kaggle upload. Full design: `evolve/README.md`.

**Safety net:** no repo state was destructively changed. Pre-overhaul tree is commit
`5e2116723004b6ed1985e90ae65f620c3513ddd4` (tip of `origin/main` and this branch before this
session) — `git checkout 5e2116723004b6ed1985e90ae65f620c3513ddd4` recovers it exactly. Frozen
ladder-proven baselines (unaffected either way, since Kaggle keeps submission history
regardless of repo state): `archaludon_rules × archaludon_ex_cinderace` ref **54083197** (peak
**1224.2 μ** / latest **1196.1 μ**); `dragapult_crispin × dragapult_ex_sample` ref **53989933**
(**880.9 μ**).

**Not yet done:** the pilot evolution run itself. This sandbox has no `cg` engine / Kaggle
egress (see `README.md` Environment), so `evolve/run_evolution.py` has been syntax-checked but
not run end-to-end. **Single next action:** on the dev machine (Py≥3.11), run
`python evolve/run_evolution.py --target archaludon --generations 3 --population 6 --games 20 --report`
and check whether any candidate's Wilson CI clears the current baseline's — that's the bar for
extending this past the pilot (per `evolve/README.md`).

---

## As of 2026-06-28 Session 57d (R12 probe uploaded — handoff)

**Leader:** **54083197** @ **1196.1 μ** (R12 — do not re-upload). **Latest probe:** **54139502** R7+R12 dead-active tempo — **PENDING** (local **70.7%** n=150, uploaded 2026-06-28T12:13 UTC). R11 **54138853** reading 2: **632.9 μ**.

**Posture:** Log every probe in `report/LADDER_BEST_SO_FAR.md` + `eval/ladder_log.csv`. Low μ = learning data. Continue small one-lever changes toward beating **1196.1 μ**.

| Ref | Lever | μ | Δ vs leader |
|-----|-------|---:|------------:|
| 54083197 | R7 | **1196.1** | — |
| 54088877 | R8a+R8b | 983.8 | −212 |
| 54109878 | R7+R8a | 967.3 | −229 |
| 54109826 | R7+R10 | 854.0 | −342 |
| 54089078 | R8+R9 | 841.0 | −355 |
| 54138853 | R7+R11 | 632.9 | −563 |
| 54139502 | R7+R12 | PENDING | — |

### THE SINGLE NEXT ACTION

Wait ≥40 min → `python scripts/track_ladder.py` for **54139502**. Log μ in `eval/ladder_log.csv` + `report/LADDER_BEST_SO_FAR.md`. If COMPLETE: `analyze_submission.py --ref 54139502 --skip-fetch` + deck logs. Leader still **54083197 @ 1196.1 μ** until beaten on ≥2 readings.

---

## As of 2026-06-28 Session 57c (scoreboard synced — keep iterating)

**Leader:** **54083197** @ **1196.1 μ** (R12 — do not re-upload this ref). **Latest probe:** **54138853** R11 @ **535.6 μ**.

**Posture:** Log every probe in `report/LADDER_BEST_SO_FAR.md` + `eval/ladder_log.csv`. Low μ = learning data, not a permanent ban. Continue **small one-lever changes** toward beating **1196.1 μ**.

| Ref | Lever | μ | Δ vs leader |
|-----|-------|---:|------------:|
| 54083197 | R7 | **1196.1** | — |
| 54088877 | R8a+R8b | 983.8 | −212 |
| 54109878 | R7+R8a | 967.3 | −229 |
| 54109826 | R7+R10 | 854.0 | −342 |
| 54089078 | R8+R9 | 841.0 | −355 |
| 54138853 | R7+R11 | 535.6 | −660 |

### THE SINGLE NEXT ACTION

Wait ≥40 min → `track_ladder.py` for **R12 probe** (just uploaded). Log row in `eval/ladder_log.csv` + `LADDER_BEST_SO_FAR.md`. Leader still **54083197 @ 1196.1 μ** until beaten.

---

## As of 2026-06-28 Session 57b (R11 probe uploaded)

**R11 implemented:** `_prize_race_attach_cap` — when behind in prizes and legal attack KOs Active, cap attach/evolve/tempo ≤5000, boost lethal attack ≥55000. **Reverted R8a** from `apply_overrides` (R7-only baseline).

| Metric | Value |
|--------|-------|
| Local gate (full n=30) | **58.7%** [50.7, 66.2] n=150 |
| no_active (agent-only n=250) | **9** (packaged guard 12 — do not ship guard) |
| Upload gate | exit 0 |
| Probe | **54138853** PENDING (uploaded 2026-06-28T11:42 UTC) |

**Champion unchanged:** **54083197** @ **1196.1 μ** (R12 — do not re-upload).

### THE SINGLE NEXT ACTION

Wait ≥40 min → `python scripts/track_ladder.py` for R11 probe ref. When COMPLETE: `analyze_submission.py --ref <ref> --skip-fetch` + deck logs. Replace champion only if μ beats **1196.1** on ≥2 readings. **R12 dead-active retreat** only if R11 misses.

---

## As of 2026-06-28 Session 57 (probe μ landed — champion retained)

**Both Session 55 probes COMPLETE** (`track_ladder.py` 2026-06-28T11:28 UTC):

| Ref | Lever | Local gate | **μ** | Δ vs champion | Verdict |
|-----|-------|------------|------:|--------------:|---------|
| **54083197** | R7 bench guard | 72.7% | **1196.1** | — | **Champion retained (R12)** |
| **54109878** | R7 + R8a promote | 62.7% | **967.3** | −229 | **Ruled out** |
| **54109826** | R7 + R10 prize-attack | 62.0% | **854.0** | −342 | **Ruled out** |

**Decision:** Neither probe beats **1196.1 μ**. Champion **54083197** stays finalist baseline. Do **not** re-upload (R12). R10 and R8a-on-R7 off the table.

**Ladder ranking (Archaludon):** 54083197 (1196) > 54088877 R8a+R8b (984) > 54109878 R8a-only (967) > 54109826 R10 (854) > 54089078 R9 (841).

**Episode pull:** Agent-log manifest has 26 ep (R10) + 25 ep (R8a). Replay download **blocked** — Kaggle API 429 on `GetEpisodeReplay`. Retry: `analyze_submission.py --ref <ref> --skip-fetch` then deck-log extract.

### THE SINGLE NEXT ACTION

**Offline (no upload):** Trace champion close prize losses **82062971**, **82073113**, **82073596** in `report/deck_logs/archaludon/`; design one replay-backed lever vs **54083197 R7-only** baseline. Revert working tree to R7 champion code before next experiment.

---

## As of 2026-06-28 Session 56.5 (Autonomous run — Kaggle auth blocker) — superseded

**Status:** Two probes from Session 55 remain PENDING on ladder (17+ hours elapsed).

**Blockers encountered:**
1. **Kaggle API auth:** `track_ladder.py` requires kaggle.json; KGAT_ bearer token format not compatible. Cannot fetch probe μ updates.
2. **Torch dependency:** Local gate testing blocked (torch commented out; install risky in 45-sec sandbox timeout).

**Ladder state** (last update 2026-06-27 13:28 UTC from `ladder_history.csv`):
- **54109826** (R10): PENDING, local 62.0%
- **54109878** (R8a): PENDING, local 62.7%
- **54088877** (R8a+R8b): μ = 979.2 (↓ from 983.8)
- **54083197** (champion): μ = 1196.1 (peak 1224.2)

**P0 code review:** `_empty_bench_basic_score` + `_mandatory_promote_score` guards present. No_active failures (82055480, 82068759) may be context-parsing issues in deck logs or score collision. **Probes should clarify**: 54109878 (R8a) is the P0 test; if μ > 1196.1, assume R8a fixes 82068759 class.

**Collected analysis:**
- Strategy data: 178 games, 65.7% WR; **Alakazam weak (48.6%)**; mirror Archaludon 0-3 (ban if 3-deck).
- Prize-loss traces from champion: R10 probe addresses (attach vs attack logic).
- P2 Iono harness @ 40% local (deferred until P0 probe resolves).

**THE SINGLE NEXT ACTION**

**Immediate (critical path):** Escalate Kaggle auth to Dylan. Options:
1. Set up KAGGLE_API_TOKEN env + kaggle.json in sandbox
2. or: Configure kaggle CLI to use KGAT_ bearer token format
3. or: Manual check Kaggle UI + copy μ into `report/ladder_history.csv` for manual import

**Timeline:** Probes uploaded 2026-06-27 13:28 UTC; deterministic ladder should settle μ within 6–24h (expect 2nd readings by 2026-06-28 13:28–19:28 UTC). **Do not iterate code until probe μ known** (gate ≠ ladder truth).

**Once auth fixed, script:** `python scripts/track_ladder.py` → interpret 54109826 + 54109878 μ trajectories → choose next lever or declare new champion.

---

## As of 2026-06-27 Session 56 (offline DS + handoff — probes in flight)

**Two ladder probes still PENDING** (uploaded Session 55):

| Ref | Lever | Local gate | Status | Hypothesis |
|-----|-------|------------|--------|------------|
| **54109826** | R7 + **R10** prize-attack KO scoring | 62.0% | **PENDING** | 10/10 champion prize losses ended behind in prize race; traces show attach (type 7) over attack (type 13) |
| **54109878** | R7 + **R8a-only** mandatory promote | 62.7% | **PENDING** | Target 82068759 promote without R8b side effects |

**Saved champion (R12 — do not re-upload):** **54083197** @ **1196.1 μ** · 50 episodes · **70.0% WR** · prize 10 · no_active 4 · deck_out 1.

**Offline DS (Session 56)** — `python scripts/analyze_archaludon_losses.py`:

| Ref | WR | no_active | prize | Lesson |
|-----|-----|-----------|-------|--------|
| 54083197 | 70.0% | 8.0% (4) | 20.0% (10) | Baseline |
| 54088877 R8a+R8b | 62.5% | **17.9%** (10) | 17.9% | Local gate overpredicted; **2× no_active** vs champion |
| 54089078 R8+R9 | 68.75% | **18.8%** (9) | 12.5% | R9 ruled out |

**Close prize losses to trace if probes fail:** 82062971 (2 vs 1 prizes), 82073113 (4 vs 1), 82073596 (4 vs 1). **no_active episodes:** 82055480, 82068759, 82076432, 82090639 (`eval/archaludon_no_active_trace.md`).

**Field meta:** `report/strategy_analysis_20260627.md` — 178 our games 65.7% WR; alakazam 48.6% aggregate (prize-race losses, not blowouts).

### THE SINGLE NEXT ACTION

Wait ≥40 min → `python scripts/track_ladder.py` for **54109826** + **54109878**. When COMPLETE: `analyze_submission.py --ref <ref>` + `extract_deck_perspective_logs.py` per ref. Replace champion only if probe beats **1196.1 μ** on ≥2 readings. **Do not ship another brain change until probe μ lands.**

---

## As of 2026-06-27 Session 55 (two probes uploaded + episode review gaps filled)

**Episode pipeline upgraded:** `extract_deck_perspective_logs.py` now captures `legal_options`, `chosen_indices`, `chosen_options`, `visualize_line` per our-turn (Kiyota JSON review pattern).

**Champion full pull (54083197):** 50 public episodes · **70.0% WR** · prize 10 · no_active 4 · deck_out 1.

**Two new ladder probes uploaded:**

| Ref | Lever | Local gate | Status |
|-----|-------|------------|--------|
| **54109826** | R7 + **R10** prize-attack KO scoring | 62.0% | PENDING |
| **54109878** | R7 + **R8a-only** mandatory promote | 62.7% | PENDING |

**Saved champion (unchanged):** **54083197** @ **1196.1 μ** — beat on ≥2 ladder readings to replace.

### THE SINGLE NEXT ACTION

Wait ≥40 min → `python scripts/track_ladder.py` for **54109826** + **54109878** 2nd μ readings. When COMPLETE: `analyze_submission.py --ref <ref>` + deck log extract for each probe.

---

**Blocker cleared:** torch available locally (`2.12.1+cpu`). Session 53 timeout was sandbox-only.

**Gate results** (`gate_archaludon.py --games 30 --suite full`):
- **Overall: 66.0%** [58.1, 73.1] n=150 — report `eval/gate_archaludon.md`

**no_active audit** (`compare_archaludon_bench_guard.py --games 50 --suite full`):
| Variant | Overall WR | no_active (n=250) |
|---------|------------|-------------------|
| Agent only (`ARCHALUDON_BENCH_GUARD=0`) | 64.8–67.6% | **5–7** |
| + packaged guard | 65.6–66.8% | **7–8** |

**P0 not met:** still **>0 no_active** @ n=250. Packaged guard does not fix promote path (82068759); TO_ACTIVE guard extension **tested and reverted** (no_active 7→8).

**Next action:** Fix in **`archaludon_agent.py`** — strengthen `_empty_bench_block_tempo` (R8b) for attach-before-bench on turn 2; verify `_mandatory_promote_score` (R8a) on TO_HAND vs TO_ACTIVE stalls. Re-gate; target 0 no_active before upload.

---

## As of 2026-06-27 Session 53 (Autonomous P0 diagnostic — superseded by S54)

**P0 task**: Traced no_active failures from 82055480 + 82068759 deck logs.

**Root causes identified:**
- 82055480: Bench stayed empty entire game (0 benched Pokémon). Current `_empty_bench_basic_score` should have boosted Duraludon/Relicanth to 50k in MAIN context; needs verification.
- 82068759: Active KO forced TO_ACTIVE context (step 65); promoted to Duraludon (step 66) then evolved to Archaludon (step 67). Current `_mandatory_promote_score` should have handled this; also needs verification.

**Current guards in place** (archaludon_agent.py):
1. `_empty_bench_basic_score` — boosts Duraludon/Relicanth when bench=0
2. `_mandatory_promote_score` — boosts forced promotions (TO_ACTIVE/SWITCH)
3. `_empty_bench_block_tempo` — blocks items/attach before benching a basic
4. `_to_hand_pick_floor` — R9 safety net for TO_HAND stalls

**Blocker:** Workspace torch dependency timeout during `gate_archaludon.py` n=30 verification. 

**Next action (next session):** 
1. Install torch via pip (or check if requirements.txt exists)
2. Run `python scripts/gate_archaludon.py --games 30 --suite full --report` 
3. Confirm 0 no_active @ n≥50 before any upload
4. If still seeing no_active: add extended guards to archaludon_bench_guard.py for SETUP_BENCH / TO_BENCH / TO_FIELD contexts (see archaludon_iteration.md P0 section)

---

## As of 2026-06-27 (Session 52 — iteration mode, ~2 months to deadline)

**Posture:** Save champion as finalist baseline; keep improving via small agent/deck changes. Final pins are a **Sep deadline** action — not urgent now. Use uploads as **ladder probes**; swap saved champion only when a probe beats **1196.1 μ** on ≥2 readings.

### Saved champion (do not re-upload tarball — R12)

| Ref | Code | **μ** | Role |
|-----|------|------:|------|
| **54083197** | R7 empty-bench guard only | **1196.1** (peak 1224.2) | **Finalist baseline** — beat this on ladder to ship |

### Probe learnings (catalog rows — keep for comparison)

| Ref | Change | Local gate | **μ** | Lesson |
|-----|--------|------------|------:|--------|
| 54088877 | R8a promote + R8b tempo block | **75.3%** n=30 | **983.8** (↑ climbing) | Local gate **overpredicted** again; promising but still −212 vs champion |
| 54089078 | + R9 `_to_hand_pick_floor` | **68.0%** n=30 | **841.0** | **Ruled out** — regressed local + ladder vs R8-only |
| 54083513 | Starmie (paused) | — | 277.5 | Not on Archaludon track |

**Takeaway:** Ladder μ is truth. Local full suite is a **filter only**. R9 off the table. Next experiments: **R8a-only** on R7 baseline (82068759 promote without R8b side effects); **P1 prize-loss** mining from `losses.json` (7/10 losses).

### THE SINGLE NEXT ACTION

**Offline:** Revert R9 in `archaludon_agent.py`; A/B **R8a-only** vs champion R7 baseline → `gate_archaludon.py` n=30 full. If gate holds/improves, package + upload probe (R12). **`track_ladder.py`** on schedule — no manual Final pin until Sep unless champion displaced.

---

## As of 2026-06-26 (Session 52 — two-Final Archaludon strategy)

**Goal:** Two Finals worth keeping · drop Starmie (277.5 μ).

| Ref | Version | μ (latest) | Role |
|-----|---------|------------|------|
| **54083197** | R7 bench guard | **1196.1** | **Final #1 — lock** |
| **54088877** | R8a+R8b | **780.7** (climbing: 600→704→780) | Probe — swap in if beats 1196.1 |
| **54089078** | R8+R9 micro TO_HAND floor | PENDING | Probe — tiny delta vs 54088877 |

**R9 change:** `_to_hand_pick_floor` (~12 lines) — fixes TO_HAND stall; skips Explorer discard pass.

### THE SINGLE NEXT ACTION

**Kaggle UI:** Pin **54083197** as Final #1. **`track_ladder.py`** ≥40 min for **54088877** + **54089078** 2nd readings. Pick highest μ Archaludon for Final #2; **disable Starmie 54083513**.

---

## As of 2026-06-26 (Session 52 — R8 submitted)

| Field | Value |
|-------|-------|
| **Ref** | **54088877** (COMPLETE — 1st reading **600.0 μ**) |
| **Package** | `archaludon.tar.gz` |
| **Delta vs 54083197** | R8a TO_ACTIVE promote + R8b empty-bench tempo block |
| **Local gate** | **75.3%** full n=30 |
| **Final (locked)** | **54083197** @ **1196.1 μ** — swap only if 54088877 beats on ≥2 readings |

### THE SINGLE NEXT ACTION

**Wait ≥40 min**, then **`python scripts/track_ladder.py`** for ref **54088877** 2nd μ reading. **Keep 54083197 (1196.1 μ) pinned as Final** on Kaggle until 54088877 beats it on ≥2 readings.

---

## As of 2026-06-26 (Session 52 — R8 agent iterations)

**Two scoring passes in `agent/archaludon_agent.py`**, gated full suite n=30:

| Step | Change | Overall WR |
|------|--------|------------|
| Baseline (R7b) | — | **64.7%** |
| **R8a** | `_mandatory_promote_score` — TO_ACTIVE after active KO | **70.7%** |
| **R8b** | `_empty_bench_block_tempo` — no attach/items before bench basic | **75.3%** |

Champion ref **54083197** @ **1196.1 μ** — lock Final until probe **54088877** beats latest on ≥2 readings.

### THE SINGLE NEXT ACTION

**See R8 submitted block above.**

---

## As of 2026-06-26 (Session 52 — ladder μ refresh)

**Source:** Kaggle Submissions UI + `python scripts/track_ladder.py` (2026-06-26 evening).

| Ref | Package | Status | **Public μ (latest)** | μ trajectory |
|-----|---------|--------|----------------------:|--------------|
| **54083197** | `archaludon_ex_cinderace_r7_bench.tar.gz` | COMPLETE | **1196.1** | 600 → 731.3 → **1224.2** (peak) → **1196.1** |
| **54083513** | `starmie_froslass_ashleysandlin.tar.gz` | COMPLETE | **277.5** | 300.3 → **277.5** |

**Archaludon still #1** (+315 μ vs Dragapult 880.9). TrueSkill μ drifts with matchmaking — peak was 1224.2; **lock ref 54083197 as Final** unless a new probe beats latest on ≥2 readings.

### THE SINGLE NEXT ACTION

**Continue Archaludon refinement in `agent/archaludon_agent.py`** — TO_ACTIVE promotion after active KO (82068759); re-gate after changes. No re-upload of 54083197 without material delta (R12).

---

## As of 2026-06-26 (Session 52 — Archaludon primary track)

### Strategic shift

**All iteration → Archaludon** (`archaludon_rules` × `archaludon_ex_cinderace`, ref **54083197**, **1196.1 μ** latest / **1224.2 μ** peak).  
SearchScorer, Alakazam upload, Starmie, Dragapult re-probe: **paused**.

| Field | Value |
|-------|-------|
| **Champion ref** | **54083197** — lock Final; do not re-upload same tarball (R12) |
| **Public μ** | **1196.1** (peak **1224.2**) |
| **Local gate** | 67.3% full n=30 post R7b (filter only) |
| **Ladder WR** | **76.2%** n=42 public |
| **Loss priorities** | 2× `no_active`, 2× Dragapult prize, 2× Alakazam prize, 1× deck_out |

Plan: [`eval/archaludon_iteration.md`](eval/archaludon_iteration.md) · traces: [`eval/archaludon_no_active_trace.md`](eval/archaludon_no_active_trace.md)

### THE SINGLE NEXT ACTION

**See μ refresh block above.**

---

## As of 2026-06-26 (Session 51 — Archaludon ladder truth)

### Ladder bar moved

| Field | Value |
|-------|-------|
| **Ref** | **54083197** |
| **Package** | `archaludon.tar.gz` (Kaggle name: `archaludon_ex_cinderace_r7_bench.tar.gz`) |
| **Brain × deck** | `archaludon_rules` × `archaludon_ex_cinderace.csv` |
| **Local gate** | **67.3%** full n=30 post R7b bench fix (was 72.7%) |
| **μ trajectory** | 600.0 → 731.3 → **1224.2** (peak) → **1196.1** (latest) |
| **Prior bar** | Dragapult **880.9 μ** (53989933) — superseded |

**Verdict:** Community v5 + R7 empty-bench guard only. **Still #1 on ladder.** Peak 1224.2; μ drift normal. Local gate **underpredicted** ladder.

### THE SINGLE NEXT ACTION

**See Session 52 block above** — Archaludon refinement is the only active track.

---

## As of 2026-06-26 (Session 51 — Starmie upload)

### Submitted

| Field | Value |
|-------|-------|
| **Ref** | **54083513** |
| **Package** | `starmie_froslass_ashleysandlin.tar.gz` |
| **Brain × deck** | `starmie_rules` × `starmie_froslass_ashleysandlin.csv` |
| **Local gate** | Mirror **56.7%** n=30; full suite **9.3%** (filter only) |
| **Public μ** | **277.5** (was 300.3) |
| **R12** | New catalog row — exit 0 |

**Verdict:** COMPLETE; low μ — track paused. Not a Final candidate.

---

## As of 2026-06-26 (Session 51 — execute batch)

### Delivered this run

| Item | Result |
|------|--------|
| **Starmie / Froslass field opponent** | `agent/starmie_agent.py`, deck, `PrizeTracker`, `scripts/gate_starmie.py`; mirror **56.7%** n=30 (`eval/gate_starmie_session51.md`) |
| **SearchScorer stability fix** | Refresh `Battle.battle_ptr` each search (was crashing full-suite gate); re-gate **26.7%** n=30 (`eval/gate_search.md`) |
| **PrizeTracker → SearchScorer** | Deck-search contexts penalize inferred prized cards |
| **Archaludon ladder** | Ref **54083197** **COMPLETE** μ=**600.0** (first reading — wait ≥40 min for 2nd) |
| **verify_official_opponents** | 12 decks OK including `starmie_froslass_ashleysandlin` |

### THE SINGLE NEXT ACTION

**Track Starmie ref 54083513** + **Archaludon ref 54083197** (2nd reading **731.3 μ**) — `python scripts/track_ladder.py` after ≥40 min.

---

## As of 2026-06-26 (Session 51 — Archaludon ladder probe)

### Ladder probe submitted

| Field | Value |
|-------|-------|
| **Ref** | **54083197** |
| **Package** | `archaludon.tar.gz` |
| **Brain × deck** | `archaludon_rules` × `archaludon_ex_cinderace.csv` |
| **Delta** | Community v5 + R7 empty-bench guard only |
| **Local gate** | **72.7%** full suite n=30 (`eval/gate_archaludon.md`) |
| **Status** | **COMPLETE** μ=**600.0** (2026-06-26 16:19 UTC) — await 2nd reading |

**Next:** `python scripts/track_ladder.py` ≥40 min after first COMPLETE before treating 600 as stable.

---

## As of 2026-06-26 (Session 51 — Alakazam iteration)

### Measured

| Item | Result |
|------|--------|
| Alakazam bench guard A/B @ n=50 | Guard **regresses** (53.6% vs 56.8%) → **default OFF** |
| Dragapult levers on Alakazam | **58.7%** @ n=30 → **reverted** (hurt Lucario/Iono) |
| Latest gate (notebook deck, n=30) | **54.0%** (variance; S50 **62.0%** still reference) |
| Dragapult stack | Unchanged — full guard + Crispin rules; **880.9 μ** hold |

Full write-up: `eval/alakazam_iteration_session51.md`

### THE SINGLE NEXT ACTION

**Replay analysis** — Alakazam losses vs `dragapult_ex_sample` (stable ~33–37% weakness). No Kaggle upload until **two** n=30 gates ≥62% or paired n=50 beat baseline.

---

### Ladder truth

| Rank | Brain × deck | μ | Ref |
|-----:|--------------|----:|-----|
| 1 | archaludon_rules + R7 × `archaludon_ex_cinderace` | **1224.2** | 54083197 |
| 2 | dragapult_crispin + R7 × `dragapult_ex_sample` | **880.9** | 53989933 |
| 3 | SearchScorer × `real_mega_lucario_ex` | **660.5** | 53869254 |
| 4 | imported Alakazam best5 | **659.0** | 53913404 |
| 5 | basic MCTS model4 × Lucario | **651.3** | 53946742 |

**Bar:** **1224.2 μ**. **R12:** no duplicate uploads — iterate or don't upload.

### Session 50 delivered

| Item | Status |
|------|--------|
| B1 Alakazam port | `agent/alakazam_agent.py`, package, gate **62.0%** @ n=30 |
| R12 + `check_upload_eligible.py` | Blocks ports, weak local gates (<55%), duplicates |
| Native Alakazam opponents | `top_mined_alakazam` + `ryotasueyoshi_alakazam_best5` in official registry |
| LucarioScorer gate @ n=30 | **39.3%** — **do not upload** (`eval/lucario_scorer_baseline_session50.md`) |
| Duplicate Alakazam upload | Wasted slot — lesson in R12 |

### Session 50 measurements (native field full suite n=30)

| Brain | Deck | Overall WR | Report |
|-------|------|------------|--------|
| SearchScorer | `real_mega_lucario_ex` | **27.3%** | `eval/gate_search.md` |
| LucarioScorer | same | **39.3%** | `eval/lucario_scorer_baseline_session50.md` |
| Alakazam best5 | notebook deck | **62.0%** | `eval/alakazam_best5_baseline_session49.md` |

Note: ladder **660.5 μ** used different gate opponents than today's native full suite — local % is filter only.

### THE SINGLE NEXT ACTION

**Iterate SearchScorer toward 660.5+ μ** (home-grown bar) — one targeted fix, local gate, then `check_upload_eligible`:

```powershell
python scripts/gate_search.py --games 30 --suite full --report
# after a concrete fix:
python scripts/check_upload_eligible.py --brain SearchScorer `
  --deck agent_decks/real_mega_lucario_ex.csv `
  --change "SearchScorer: <delta>" --local-gate <WR>
```

**Parallel offline:** Alakazam levers (beat **62%** local before upload vs **659 μ**).

**Do not upload:** LucarioScorer @ 39.3%, Alakazam re-port, Dragapult without material change.

---

## Recent sessions

| Session | Result |
|---------|--------|
| **50** | B1 port; R12; upload gate; LucarioScorer 39.3%; duplicate upload lesson |
| **49** | Agent catalog; pilot×deck 10% collapse; epistemic reset |
