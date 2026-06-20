"""Unit tests for the robust objective and the zero-sum meta-solver."""

import numpy as np

from rl.robust_fitness import MatchupResult, cvar, maximin, robust_score, weighted_mean
from rl.meta_solver import solve_zero_sum, adversarial_weights


def _mm(rates, weights=None):
    weights = weights or [1.0] * len(rates)
    return [MatchupResult(f"o{i}", r, w) for i, (r, w) in enumerate(zip(rates, weights))]


def test_mean_and_maximin():
    m = _mm([0.2, 0.6, 1.0])
    assert abs(weighted_mean(m) - 0.6) < 1e-9
    assert maximin(m) == 0.2


def test_cvar_is_lower_tail():
    m = _mm([0.1, 0.4, 0.7, 1.0])
    assert abs(cvar(m, q=0.25) - 0.1) < 1e-9
    assert abs(cvar(m, q=0.5) - 0.25) < 1e-9
    assert abs(cvar(m, q=1.0) - weighted_mean(m)) < 1e-9


def test_robust_score_penalises_bad_matchup():
    even = _mm([0.675, 0.675, 0.675, 0.675])
    spiky = _mm([0.9, 0.9, 0.9, 0.0])
    assert abs(weighted_mean(even) - weighted_mean(spiky)) < 1e-9
    assert robust_score(even, alpha=0.5, cvar_q=0.3) > robust_score(spiky, alpha=0.5, cvar_q=0.3)


def test_zero_sum_rock_paper_scissors():
    M = np.array([[0.5, 0.0, 1.0], [1.0, 0.5, 0.0], [0.0, 1.0, 0.5]])
    sol = solve_zero_sum(M, iters=20000)
    assert np.allclose(sol.row_strategy, [1 / 3, 1 / 3, 1 / 3], atol=0.03)
    assert np.allclose(sol.col_strategy, [1 / 3, 1 / 3, 1 / 3], atol=0.03)
    assert abs(sol.value - 0.5) < 0.02
    assert sol.exploitability < 0.03


def test_dominant_row_is_found():
    M = np.array([[1.0, 1.0], [0.0, 0.5]])
    sol = solve_zero_sum(M, iters=10000)
    assert sol.row_strategy[0] > 0.95
    assert sol.value > 0.95


def test_adversarial_weights_sum_to_one():
    M = np.array([[0.7, 0.2, 0.6], [0.4, 0.8, 0.3]])
    y = adversarial_weights(M, iters=5000)
    assert abs(float(y.sum()) - 1.0) < 1e-6
    assert bool((y >= -1e-9).all())
