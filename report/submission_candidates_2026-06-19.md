# Simulation Submission Candidates

Date: 2026-06-19

No Kaggle submission has been made. These archives are local dry-run packages
under `dist/candidates/`. Re-open the official Kaggle pages in a browser and get
explicit user confirmation before uploading any slot.

Current official web snippets checked 2026-06-19 (reconfirmed via web search;
direct page fetch timed out — use browser before upload):

- Simulation rules: <https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/rules>
  says five submissions per day and up to two final submissions.
- Simulation overview: <https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/overview>
  says submissions are `.tar.gz` bundles with top-level `main.py` and `deck.csv`.
- API/agent contract remains grounded in `data/CABT_API.md` and
  `data/sim/sample_submission/cg/api.py`.

## Kaggle Submission Log

| # | Ref | Archive | Date (UTC) | Description | Status | Score | Notes |
|---:|---|---|---|---|---|---:|---|
| 1 | 53854588 | `a2_kyogre.tar.gz` | 2026-06-19 16:04 | A2 Kyogre deck — 963/1000 local gate | **ERROR** | — | `main.py` used `Path(__file__)`; Kaggle exec has no `__file__` |
| 2 | 53854707 | `a2_kyogre.tar.gz` | 2026-06-19 16:08 | A2 Kyogre — fix main.py __file__ for Kaggle exec | **COMPLETE** | **672.7** | Initial μ 600.0 after validation; **670.3** after ~40 min ladder matchmaking (2026-06-19 sync: 672.7) |

**Root cause (sub #1):** Kaggle loads `main.py` via `exec()` without defining `__file__`.
Module-level `Path(__file__).with_name("deck.csv")` raised `NameError` before deck selection.

**Fix:** `scripts/package_submission.py` now generates `main.py` with `read_deck_csv()` using
`deck.csv` / `/kaggle_simulations/agent/deck.csv` only (no `__file__`). Dry-run exec
simulates Kaggle's loader. Tar packaging deduplicated (files only, was ~2 MiB → ~1 MiB).

## Ladder scoring notes (verified 2026-06-19)

- **600.0 is starting μ, not failure.** After COMPLETE, the public score is the
  post-validation baseline (~600), not a rank vs the field.
- **Validation episode:** agent plays **against itself** (pass/fail gate only).
- **Ladder matchmaking** (~40+ min): score moves to real W/L vs other submitted
  agents (A2 observed **670.3**, later **672.7** as more matches finish).
- **Field context:** top ladder ~1350; mid-pack ~1100+. Local random-gate % does
  not predict ladder rank.
- Most new submissions likely start near 600 then spread as matches complete.
- Only **2 final** submissions count for standings; daily Simulation submits still
  play ladder games.

## Candidate Set

| Slot | Archive | Agent module | Deck | Purpose | Current local evidence |
|---|---|---|---|---|---|
| A0 | `dist/candidates/a0_safety.tar.gz` | `agent_snapshots.v2_safety` | `agent/deck.csv` | Frozen no-regression baseline | Packaged artifact vs default random deck: 282/300 = 94.0% |
| A1 | `dist/candidates/a1_current_963.tar.gz` | `agent.agent` | `agent/deck.csv` | Best current Abomasnow pilot | Packaged vs default random: **952/1000 = 95.20%** (Wilson 93.69–96.36); source matrix 578/600 = 96.3%; beats safety 152/240 |
| A2 | `dist/candidates/a2_kyogre.tar.gz` | `agent.agent` | `agent_decks/a2_kyogre_33_energy.csv` | Reduced Energy plus more Kyogre backups | Packaged vs default random: **963/1000 = 96.30%** (Wilson 94.94–97.30); 300-game gate 294/300 = 98.0% |
| A3 | `dist/candidates/a3_starmie.tar.gz` | `agent.agent` | `agent_decks/a3_starmie_spread_33_energy.csv` | Mega Starmie spread pressure | Packaged artifact vs default random deck: 283/300 = 94.3%; mirror package check: 291/300 = 97.0% |
| A4 | `dist/candidates/a4_big_basic.tar.gz` | `agent.agent` | `agent_decks/a2_big_basic_29_energy.csv` | Black Kyurem ex robustness probe | Packaged vs default random: **965/1000 = 96.50%** (Wilson 95.17–97.47); 300-game gate 291/300 = 97.0% |

## Package Artifact Verification

Command shape:

```powershell
python scripts\verify_archive.py dist\candidates\<archive>.tar.gz --games 300 --opponent-deck agent\deck.csv
```

This extracts the archive, imports the packaged top-level `main.py`, uses the
packaged `deck.csv`, and plays side-swapped games against legal random with the
default Abomasnow deck as the opponent deck.

| Archive | Opponent deck | Wins | Losses | Win % |
|---|---|---:|---:|---:|
| `a0_safety.tar.gz` | `agent/deck.csv` | 282 | 18 | 94.0 |
| `a1_current_963.tar.gz` | `agent/deck.csv` | 288 | 12 | 96.0 |
| `a2_kyogre.tar.gz` | `agent/deck.csv` | 294 | 6 | 98.0 |
| `a3_starmie.tar.gz` | `agent/deck.csv` | 283 | 17 | 94.3 |
| `a4_big_basic.tar.gz` | `agent/deck.csv` | 291 | 9 | 97.0 |

## 1000-Game Packaged Validation (2026-06-19)

Command shape:

```powershell
python scripts\verify_archive.py dist\candidates\<archive>.tar.gz --games 1000 --opponent-deck agent\deck.csv
```

Full audit with Wilson 95% CI: `report/candidate_package_audit.md`.

| Archive | Wins | Games | Win % | Wilson 95% CI | Draws | Unfinished |
|---|---:|---:|---:|---|---:|---:|
| `a2_kyogre.tar.gz` | 963 | 1000 | 96.30 | 94.94–97.30 | 0 | 0 |
| `a4_big_basic.tar.gz` | 965 | 1000 | 96.50 | 95.17–97.47 | 0 | 0 |
| `a1_current_963.tar.gz` | 952 | 1000 | 95.20 | 93.69–96.36 | 0 | 0 |

At 1000 games, A4 has the highest point estimate; A2 retains the stronger
head-to-head profile vs A1/A4 (see matrix below).

## Packaged Head-To-Head Check

Command shape:

```powershell
python scripts\verify_archive_matrix.py --games 100 --tag top3_candidates `
  --candidate A1=dist\candidates\a1_current_963.tar.gz `
  --candidate A2=dist\candidates\a2_kyogre.tar.gz `
  --candidate A4=dist\candidates\a4_big_basic.tar.gz
```

Report: `report/eval/archive_matrix_100_top3_candidates.md`.

| A | B | A wins | B wins | A win % |
|---|---|---:|---:|---:|
| A1 | A2 | 55 | 45 | 55.0 |
| A1 | A4 | 50 | 50 | 50.0 |
| A2 | A1 | 55 | 45 | 55.0 |
| A2 | A4 | 58 | 42 | 58.0 |
| A4 | A1 | 45 | 55 | 45.0 |
| A4 | A2 | 49 | 51 | 49.0 |

A2 has the strongest combined profile: positive head-to-head rows against A1/A4
and 963/1000 (96.30%) vs default random. A4 leads the 1000-game point estimate
(965/1000 = 96.50%) but loses head-to-head to A2 (49/100).

## Submission Order Recommendation

1. Submit A2 first — best head-to-head profile plus 963/1000 random gate.
2. Submit A4 second — highest 1000-game point estimate (965/1000), distinct deck.
3. Submit A1 third as the best source-matrix and safety-regression candidate.
4. Submit A0 only if we want a conservative baseline ladder anchor.
5. Hold A3 unless we want spread-deck diversity despite weaker cross-deck evidence.

## Remaining Validation Gap

The local 95% target is achieved by multiple packaged archives against legal
random. This is still not proof of Kaggle ladder performance. Actual ladder
validation requires a user-approved upload and recording the submission ID/score.
