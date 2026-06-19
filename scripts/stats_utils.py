"""Wilson CI, Elo, and SPRT helpers for variance-aware evaluation."""

from __future__ import annotations

import math


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for binomial win rate."""
    if n <= 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    low = (centre - margin) / denom
    high = (centre + margin) / denom
    return max(0.0, low), min(1.0, high)


def update_elo(r_a: float, r_b: float, score_a: float, k: float = 32.0) -> tuple[float, float]:
    """Update Elo ratings after one game. score_a in {1.0, 0.5, 0.0}."""
    exp_a = 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))
    exp_b = 1.0 - exp_a
    r_a_new = r_a + k * (score_a - exp_a)
    r_b_new = r_b + k * ((1.0 - score_a) - exp_b)
    return r_a_new, r_b_new


class SPRTResult:
    __slots__ = ("decision", "log_ratio", "games")

    def __init__(self, decision: str, log_ratio: float, games: int) -> None:
        self.decision = decision  # continue | accept_b | accept_a | max_games
        self.log_ratio = log_ratio
        self.games = games


def sprt_test(
    wins_b: int,
    games: int,
    p0: float = 0.50,
    p1: float = 0.55,
    alpha: float = 0.05,
    beta: float = 0.05,
    max_games: int = 10_000,
) -> SPRTResult:
    """Sequential probability ratio test: is B better than A?

    wins_b = number of wins for challenger B in `games` independent trials.
    Returns accept_b when evidence favors B, accept_a when favors A, continue otherwise.
    """
    if games <= 0:
        return SPRTResult("continue", 0.0, 0)

    losses_b = games - wins_b
    ll_h1 = wins_b * math.log(p1) + losses_b * math.log(1.0 - p1)
    ll_h0 = wins_b * math.log(p0) + losses_b * math.log(1.0 - p0)
    log_ratio = ll_h1 - ll_h0

    log_a = math.log(beta / (1.0 - alpha))
    log_b_boundary = math.log((1.0 - beta) / alpha)

    if log_ratio >= log_b_boundary:
        return SPRTResult("accept_b", log_ratio, games)
    if log_ratio <= log_a:
        return SPRTResult("accept_a", log_ratio, games)
    if games >= max_games:
        return SPRTResult("max_games", log_ratio, games)
    return SPRTResult("continue", log_ratio, games)
