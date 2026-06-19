# Simulation Submission Candidates

Date: 2026-06-19

No Kaggle submission has been made. These archives are local dry-run packages
under `dist/candidates/`. Re-open the official Kaggle pages in a browser and get
explicit user confirmation before uploading any slot.

Current official web snippets checked 2026-06-19:

- Simulation rules: <https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/rules>
  says five submissions per day and up to two final submissions.
- Simulation overview: <https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/overview>
  says submissions are `.tar.gz` bundles with top-level `main.py` and `deck.csv`.
- API/agent contract remains grounded in `data/CABT_API.md` and
  `data/sim/sample_submission/cg/api.py`.

## Candidate Set

| Slot | Archive | Agent module | Deck | Purpose | Current local evidence |
|---|---|---|---|---|---|
| A0 | `dist/candidates/a0_safety.tar.gz` | `agent_snapshots.v2_safety` | `agent/deck.csv` | Frozen no-regression baseline | Packaged artifact vs default random deck: 282/300 = 94.0% |
| A1 | `dist/candidates/a1_current_963.tar.gz` | `agent.agent` | `agent/deck.csv` | Best current Abomasnow pilot | Packaged artifact vs default random deck: 288/300 = 96.0%; source matrix mirror/random gate: 578/600 = 96.3%; beats safety 152/240 |
| A2 | `dist/candidates/a2_kyogre.tar.gz` | `agent.agent` | `agent_decks/a2_kyogre_33_energy.csv` | Reduced Energy plus more Kyogre backups | Packaged artifact vs default random deck: 294/300 = 98.0% |
| A3 | `dist/candidates/a3_starmie.tar.gz` | `agent.agent` | `agent_decks/a3_starmie_spread_33_energy.csv` | Mega Starmie spread pressure | Packaged artifact vs default random deck: 283/300 = 94.3%; mirror package check: 291/300 = 97.0% |
| A4 | `dist/candidates/a4_big_basic.tar.gz` | `agent.agent` | `agent_decks/a2_big_basic_29_energy.csv` | Black Kyurem ex robustness probe | Packaged artifact vs default random deck: 291/300 = 97.0%; mirror package check: 294/300 = 98.0% |

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

## Submission Order Recommendation

1. Submit A2 first if optimizing for the latest packaged default-deck random
   gate.
2. Submit A1 second as the best source-matrix and safety-regression candidate.
3. Submit A4 third as a distinct Black Kyurem robustness probe.
4. Submit A0 only if we want a conservative baseline ladder anchor.
5. Hold A3 unless we want spread-deck diversity despite weaker cross-deck evidence.

## Remaining Validation Gap

The local 95% target is achieved by multiple packaged archives against legal
random. This is still not proof of Kaggle ladder performance. Actual ladder
validation requires a user-approved upload and recording the submission ID/score.
