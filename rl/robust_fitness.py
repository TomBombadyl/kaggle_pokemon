"""Robust deck-fitness objectives.

The deck campaign's default fitness is the *weighted mean* win rate vs a fixed
benchmark suite. That rewards beating the suite but tolerates one terrible
matchup — the "Rock that loses to Paper" failure mode.

This module scores a deck on the *floor* of its matchup distribution so the
optimiser is pushed toward decks that are good against *anything*:

    robust_score = alpha * mean + (1 - alpha) * CVaR_q(worst matchups)

- ``mean``    : weighted mean win rate (all-round strength).
- ``CVaR_q``  : weighted mean of the worst ``q`` fraction of matchups
                (the tail; q -> 0 approaches strict maximin = single worst).
- ``alpha``   : 0 = pure worst-case, 1 = pure mean. Default 0.5.

All inputs are plain numbers, so this module has no engine/torch dependency and
is trivially unit-testable. See ``report/robust_deck_optimization_design.md`` §1.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchupResult:
    """One deck-vs-one-opponent outcome."""
    name: str
    win_rate: float
    weight: float = 1.0
    games: int = 0


def weighted_mean(matchups: list[MatchupResult]) -> float:
    tw = sum(m.weight for m in matchups)
    if tw <= 0:
        return 0.0
    return sum(m.win_rate * m.weight for m in matchups) / tw


def cvar(matchups: list[MatchupResult], q: float = 0.3) -> float:
    """Weighted mean of the worst ``q`` fraction of matchups (lower-tail CVaR).

    q must be in (0, 1]. The worst matchups are taken until their cumulative
    weight reaches ``q`` of the total (the boundary matchup is partially
    counted), so the result is continuous in q and the weights.
    """
    if not matchups:
        return 0.0
    q = min(1.0, max(1e-9, q))
    ordered = sorted(matchups, key=lambda m: m.win_rate)
    total_w = sum(m.weight for m in ordered)
    if total_w <= 0:
        return ordered[0].win_rate
    budget = q * total_w
    acc_w = 0.0
    acc_v = 0.0
    for m in ordered:
        take = min(m.weight, budget - acc_w)
        if take <= 0:
            break
        acc_v += m.win_rate * take
        acc_w += take
        if acc_w >= budget:
            break
    return acc_v / acc_w if acc_w > 0 else ordered[0].win_rate


def maximin(matchups: list[MatchupResult]) -> float:
    """Win rate vs the single worst opponent (strict worst-case)."""
    return min((m.win_rate for m in matchups), default=0.0)


def robust_score(
    matchups: list[MatchupResult],
    *,
    alpha: float = 0.5,
    cvar_q: float = 0.3,
) -> float:
    """Blend of mean win rate and lower-tail CVaR. Range [0, 1]."""
    if not matchups:
        return 0.0
    return alpha * weighted_mean(matchups) + (1.0 - alpha) * cvar(matchups, cvar_q)


def summarize(matchups: list[MatchupResult], *, alpha: float = 0.5, cvar_q: float = 0.3) -> dict:
    """Full scorecard for logging / checkpoints."""
    return {
        "robust_score": robust_score(matchups, alpha=alpha, cvar_q=cvar_q),
        "mean": weighted_mean(matchups),
        "cvar": cvar(matchups, cvar_q),
        "maximin": maximin(matchups),
        "n_opponents": len(matchups),
        "total_games": sum(m.games for m in matchups),
        "worst": min(
            ((m.name, round(m.win_rate, 3)) for m in matchups),
            key=lambda t: t[1],
            default=("", 0.0),
        ),
    }
