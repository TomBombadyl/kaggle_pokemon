# Field meta by μ band — 2026-07-31

**Purpose:** Stratify ladder episode volume and (where replays exist) deck archetype
performance by match skill tier. Informs R3 field-mixture weighting after R2 levers.

- Manifest episodes: **5426**
- Replays parsed for decks: **0**
- No new downloads.

## μ band definitions (by episode `avg_score`)

| Band | μ range | Manifest episodes | % of field sample | Mean avg μ |
|------|---------|-------------------:|------------------:|-----------:|
| elite_1200+ | 1200–99999 | 154 | 2.8% | 1239.0 |
| high_1000_1199 | 1000–1200 | 3067 | 56.5% | 1059.3 |
| mid_800_999 | 800–1000 | 2204 | 40.6% | 972.6 |
| rising_600_799 | 600–800 | 0 | 0.0% | 0.0 |
| floor_below_600 | 0–600 | 0 | 0.0% | 0.0 |

## Interpretation (manifest-only)

- `avg_score` in the episode manifest is the mean μ of both agents at match time.
- High-band volume shows where the ladder spends matchmaking effort.
- Deck archetypes require replay JSON (60-card lists in step 0).

## Our submissions (measured μ)

| Ref | Deck | Scorer | Peak μ | Local gate |
|-----|------|--------|-------:|------------|
| 53869254 | real_mega_lucario_ex.csv | SearchScorer | 660.5 | 29/30 local benchmark; best Lucario rules |
| 53854707 | a2_kyogre_33_energy.csv | HeuristicScorer | 672.7 |  |
| 53856711 | track_a_probes/probe_1_a2_kyogre_33_energy_e+2.csv | SearchScorer | 626.0 |  |
| 53886522 | real_mega_lucario_ex.csv | LucarioScorer+SmartBench | 535.6 | 9.0 |
| 53868798 | rl_deck/best_deck.csv | LearnedScorer | 585.1 | 87.5 |
| 53856676 | track_a_probes/probe_2_deck_e+4.csv | SearchScorer | 600.0 |  |
| 53856584 | pool_alakazam_dudunsparce.csv | LearnedScorer | 600.0 |  |
| 53856590 | pool_dragapult.csv | LearnedScorer | 600.0 |  |
| 53885445 | real_mega_lucario_ex.csv | LucarioMCTSScorer | 368.5 | 8.3 |
| 53890064 | top_mined_alakazam.csv | SearchScorer | 545.6 | Leader Alakazam probe #5 today; COMPLETE @600 validation — analyze ladder @40min |

## How to refresh

```powershell
python scripts/analyze_meta_by_mu_band.py --download-per-band 10
python scripts/update_from_kaggle.py
```

See also: `report/RESEARCH_AND_DECISION_BRIEF.md`