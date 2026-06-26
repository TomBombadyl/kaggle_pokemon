# Session state — PTCG AI Battle Challenge

> **Canonical:** `STATE.md` · **Upload gate:** `scripts/check_upload_eligible.py --suggest`

## Current focus

**Session 52 — Archaludon two-Final strategy.** Champion **54083197** (R7 bench) @ **1196.1 μ** — lock Final #1. Two ladder probes uploaded today: **54088877** (R8a+R8b, μ climbing **780.7**) and **54089078** (R8+R9 TO_HAND floor, PENDING). Drop Starmie **54083513** (277.5 μ) from Finals. Primary code: `agent/archaludon_agent.py` (R7b + R8a + R8b + R9).

**Next:** `python scripts/track_ladder.py` after ≥40 min for 2nd+ μ on **54088877** / **54089078**; pin best two Archaludon refs on Kaggle UI.

## Key context

- Repo: `Z:\kaggle\pokemon` · branch **main** (ahead of origin) · Python **3.13**
- **Final #1:** ref **54083197** · R7 empty-bench guard · **1196.1 μ** (peak 1224.2)
- **Probe:** ref **54088877** · R8a promote + R8b tempo · **780.7 μ** (600→704→780)
- **Probe:** ref **54089078** · R8 + R9 `_to_hand_pick_floor` · PENDING
- **Retire from Finals:** Starmie **54083513** @ 277.5 μ
- **Local gate (R8+R9):** 75.3% → 68.0% n=30 full (variance; see `eval/gate_archaludon.md`)
- **Agent levers:** `_empty_bench_basic_score`, `_mandatory_promote_score`, `_empty_bench_block_tempo`, `_to_hand_pick_floor`
- **Tools added:** `scripts/compare_archaludon_bench_guard.py`, `trace_archaludon_no_active.py`, `extract_deck_perspective_logs.py`
- **Docs:** `eval/archaludon_iteration.md`, `eval/archaludon_no_active_trace.md`, `eval/archaludon_bench_guard_ab.md`
- **Deck logs (local, not committed):** `report/deck_logs/archaludon/` — ref 54083197, 42 episodes
- **R12:** no re-upload 54083197 tarball; probes need material delta + upload gate exit 0
- **Blocker:** ladder truth only — wait ≥2 μ readings ≥40 min apart before swapping Final #2

## Continue prompt

```text
Continue Archaludon two-Final ladder strategy. Read first: @C:\Users\tobin\.cursor\USER-RULES-PASTE-THIS.txt, @.cursor/SESSION.md, @STATE.md, @agent/archaludon_agent.py, @eval/archaludon_iteration.md

Goal: Keep 54083197 (1196.1 μ) Final #1; pick best probe (54088877 or 54089078) for Final #2; drop Starmie 54083513.
Status: R8+R9 uploaded; 54088877 μ climbing (780.7); 54089078 PENDING.
Next: python scripts/track_ladder.py — compare μ vs 1196.1; update Kaggle Final pins.

Branch: main | Env: Python 3.13
```

## Timeline

- **2026-06-26T16:20:00Z** | handoff by user | conv `archaludon-ladder-probe`
- **2026-06-26T18:30:00Z** | handoff by user | conv `session51-alakazam-offline`
- **2026-06-26T22:45:00Z** | handoff by user | conv `session51-starmie-upload`
- **2026-06-26T23:00:00Z** | handoff by user | conv `session51-handoff-commit`
- **2026-06-26T21:35:00Z** | handoff by user | conv `session52-archaludon-r8-r9`
