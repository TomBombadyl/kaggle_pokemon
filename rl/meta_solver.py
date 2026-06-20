"""Zero-sum meta-game solver for robust deck selection.

The deck-vs-deck meta-game is two-player zero-sum: rows = our candidate decks,
columns = opponent decks, entry M[i][j] = P(row i beats col j). The robust
("good vs anything") answer is the **maximin / Nash** mixed strategy — the
opponent column-mixture ``y`` is the hardest adversarial field, and a deck's
robust value is its win rate vs ``y``.

We solve it with **regret matching (CFR-style) self-play**, which converges to a
Nash equilibrium of a zero-sum game and needs only NumPy — no LP solver, no GPU
(though for large D the same loop runs on GPU via CuPy if desired). See
``report/robust_deck_optimization_design.md`` §6.

Returns row mixture ``x``, column (opponent) mixture ``y``, and game value
``v = x^T M y`` (our equilibrium win rate). Exploitability measures distance to
equilibrium: 0 = exact Nash.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MetaSolution:
    row_strategy: np.ndarray      # x: distribution over our decks
    col_strategy: np.ndarray      # y: adversarial distribution over opponents
    value: float                  # equilibrium win rate for the row player
    exploitability: float         # 0 at exact Nash


def solve_zero_sum(payoff: np.ndarray, iters: int = 5000, seed: int = 0) -> MetaSolution:
    """Solve maximin for a zero-sum game via regret matching.

    payoff[i][j] in [0, 1] = row i's win prob vs col j (col player minimises it).
    """
    M = np.asarray(payoff, dtype=np.float64)
    if M.ndim != 2 or M.size == 0:
        raise ValueError("payoff must be a non-empty 2D array")
    n, m = M.shape

    row_regret = np.zeros(n)
    col_regret = np.zeros(m)
    row_strategy_sum = np.zeros(n)
    col_strategy_sum = np.zeros(m)

    def _match(regret: np.ndarray, k: int) -> np.ndarray:
        pos = np.maximum(regret, 0.0)
        s = pos.sum()
        return pos / s if s > 0 else np.full(k, 1.0 / k)

    for _ in range(max(1, iters)):
        x = _match(row_regret, n)
        y = _match(col_regret, m)
        row_strategy_sum += x
        col_strategy_sum += y

        # Row maximises payoff; col minimises it (so col's "value" is -payoff).
        row_value_per_action = M @ y          # value of each row action vs y
        ev_row = x @ row_value_per_action
        row_regret += row_value_per_action - ev_row

        col_value_per_action = M.T @ x        # row payoff if col plays action j
        ev_col = y @ col_value_per_action
        # col wants to MINIMISE row payoff -> regret is reduction it could force
        col_regret += ev_col - col_value_per_action

    x = row_strategy_sum / row_strategy_sum.sum()
    y = col_strategy_sum / col_strategy_sum.sum()
    value = float(x @ M @ y)

    # Exploitability: how much either player could gain by best-responding.
    row_br = float(np.max(M @ y))             # best the row player can get vs y
    col_br = float(np.min(M.T @ x))           # best (lowest) the col player can force vs x
    exploitability = max(0.0, (row_br - value) + (value - col_br))

    return MetaSolution(x, y, value, exploitability)


def adversarial_weights(payoff: np.ndarray, iters: int = 5000) -> np.ndarray:
    """Opponent (column) mixture that is hardest for our current candidates.

    Use this to re-weight the gauntlet so the objective targets the adversarial
    field (PSRO-lite), instead of a flat average over opponents.
    """
    return solve_zero_sum(payoff, iters=iters).col_strategy
