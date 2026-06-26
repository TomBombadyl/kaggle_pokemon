# Archaludon — champion (community v5 + R7 bench guard)

**Canonical package name:** `archaludon` · Kaggle upload ref **54083197** was named `archaludon_ex_cinderace_r7_bench.tar.gz`.

**Status:** **Ladder COMPLETE** ref **54083197** — μ=**1196.1** latest (peak **1224.2**, 2026-06-26). **Ship track / lock Final.**  
**Delta vs public v5:** R7 empty-bench guard only (`agent/archaludon_bench_guard.py` — Duraludon → Relicanth priority). No prize-KO or deck tweaks.

---

## Source

Public Kaggle community share (2026-06-26, **v5**). Rule-based only — no ML.

| Field | Value |
|-------|-------|
| **Brain** | `agent/archaludon_agent.py` (community v5 + never-crash wrapper + bench guard) |
| **Deck** | `agent_decks/archaludon_ex_cinderace.csv` (public list, unchanged) |
| **Reference** | `notebooks/archaludon_ex_cinderace/archaludon_agent_public.py` |
| **Package** | `python scripts/package_archaludon.py` → `dist/candidates/archaludon.tar.gz` |

---

## Local gate (native full suite, n=30)

Full report: [`gate_archaludon.md`](gate_archaludon.md)

| Opponent | WR% | Record |
|----------|-----|--------|
| dragapult_ex_sample | 73.3 | W22/L8 |
| real_mega_abomasnow_ex | 66.7 | W20/L10 |
| real_iono | 43.3 | W13/L17 |
| real_dragapult_ex | 86.7 | W26/L4 |
| real_mega_lucario_ex | 93.3 | W28/L2 |

**Overall: 67.3%** [59.5, 74.3] (n=150) — post R7b bench fix (Session 52); was 72.7% pre-fix.

Bench guard alone vs public v5 reference on same harness ≈ **74.0%** (within n=30 noise). Broader prize-KO scoring was tried and **regressed** — ruled out for now.

---

## Rebuild

```powershell
python scripts/bootstrap_archaludon.py   # after reference updates
python scripts/gate_archaludon.py --games 30 --suite full --report
python scripts/package_archaludon.py
python scripts/check_upload_eligible.py --manifest dist/candidates/archaludon.manifest.json `
  --change "Archaludon v5 + R7 bench guard" --local-gate 72.7
```

**Upload:** ref **54083197** locked as Final candidate. Iterate per [`archaludon_iteration.md`](archaludon_iteration.md). R12: new row only with material delta.

---

## Future (optional — see archaludon_iteration.md)

- Deck list tweaks (trainer counts, Relicanth slot)
- Matchup levers if harness shows >5pp on one archetype
- Community v6 bootstrap when published

```powershell
# 1. Download raw Kaggle replays + agent logs + stats
python scripts/analyze_submission.py --ref 54083197

# 2. Convert to compact analysis JSON (~20 KiB each vs ~1 MiB raw)
python scripts/convert_submission_replays.py --ref 54083197 --name archaludon
```

| Location | Contents |
|----------|----------|
| `report/replays/{episode_id}.json` | Raw Kaggle trace (full game) |
| `report/submission_replays/archaludon/` | Parsed JSON per episode + `index.json` + `losses.json` |
| `report/submission_stats/54083197_stats.csv` | W/L, turns, loss reason per episode |

## Ladder replays (ref 54083197)
