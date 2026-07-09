"""Deterministic evaluator: candidate params -> scalar score, via the existing harness.

Never implements new evaluation logic -- every score comes from the same
eval/harness.py + eval/gates.py path already trusted (Ruling R2: measure on the
real field only). Metadata on every result covers games, opponents, deck, brain
(Ruling R8). Game-level seeds are NOT captured: eval/harness.py's run_match /
gate_vs_opponent never fix or record a per-game random seed anywhere in this
codebase (MatchupResult.seeds exists but is always empty), so this is a
pre-existing gap in the harness, not something evolve/ invents or can fabricate
data for -- do not add a fake seeds field here.

Also reports weighted E[win] against the current field mixture
(field/weights.json, built from daily Kaggle episode pulls via
scripts/analyze_meta_by_mu_band.py + scripts/build_field_weights.py -- see
evolve/run_evolution.py --refresh-episodes). This is informational only: per
AGENTS.md ("Weighted gates: filter only until replay sample supports mixture")
and Ruling R11 ("rules before mixture"), candidate ranking and promotion decisions
use the raw local win-rate + Wilson CI, never the weighted figure alone.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from evolve.targets import EvolveTarget


@dataclass
class EvalResult:
    params: dict[str, dict]
    wr_pct: float
    ci_low_pct: float
    ci_high_pct: float
    games: int
    opponents: list[str]
    hero_brain: str
    hero_deck: str
    weighted_e_win_pct: float | None = None


def _resolve_gate_fn(dotted: str):
    module_name, fn_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, fn_name)


def evaluate(
    target: EvolveTarget,
    params: dict[str, dict],
    *,
    games_per_opp: int = 20,
    suite: str = "full",
) -> EvalResult:
    gate_fn = _resolve_gate_fn(target.gate_fn)
    result = gate_fn(suite=suite, games_per_opp=games_per_opp, param_overrides=params)

    weighted = None
    try:
        from eval.gates import compute_weighted_summary

        weighted = compute_weighted_summary(result).expected_win_pct
    except Exception:
        weighted = None  # field/weights.json missing/stale opponents -- filter signal only

    return EvalResult(
        params=params,
        wr_pct=result.overall_wr_pct,
        ci_low_pct=result.overall_ci_low_pct,
        ci_high_pct=result.overall_ci_high_pct,
        games=result.overall_games,
        opponents=result.opponents,
        hero_brain=result.hero_brain,
        hero_deck=result.hero_deck,
        weighted_e_win_pct=weighted,
    )
