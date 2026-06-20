"""Unit tests for matchup-collapse penalty in deck GA fitness (no sim)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rl.deck_balance import (
    MATCHUP_COLLAPSE_FLOOR,
    matchup_collapse_penalty,
)


def _opp(rate: float, weight: float = 1.0) -> dict:
    return {"rate": rate, "weight": weight, "wins": 0, "total": 1}


def test_no_penalty_when_min_rate_above_floor():
    opponents = {
        "a": _opp(0.75, 1.2),
        "b": _opp(0.50, 1.0),
        "c": _opp(0.40, 1.1),
    }
    penalty, min_wr = matchup_collapse_penalty(opponents)
    assert min_wr == 0.40
    assert penalty == 0.0


def test_full_penalty_at_zero_min_rate():
    opponents = {
        "strong": _opp(0.80, 1.2),
        "weak": _opp(0.0, 1.0),
    }
    penalty, min_wr = matchup_collapse_penalty(opponents)
    assert min_wr == 0.0
    assert penalty == 1.0


def test_partial_penalty_scales_linearly():
    opponents = {"only": _opp(0.15, 1.0)}
    penalty, min_wr = matchup_collapse_penalty(opponents, floor=0.30)
    assert min_wr == 0.15
    assert abs(penalty - 0.5) < 1e-9


def test_ignores_low_weight_opponents_for_min_rate():
    opponents = {
        "meta": _opp(0.60, 1.2),
        "baseline": _opp(0.0, 0.5),
    }
    penalty, min_wr = matchup_collapse_penalty(opponents, floor=MATCHUP_COLLAPSE_FLOOR)
    assert min_wr == 0.60
    assert penalty == 0.0


def test_falls_back_to_all_opponents_when_none_high_weight():
    opponents = {
        "low_a": _opp(0.20, 0.5),
        "low_b": _opp(0.10, 0.9),
    }
    penalty, min_wr = matchup_collapse_penalty(opponents, min_opponent_weight=1.0, floor=0.30)
    assert min_wr == 0.10
    assert abs(penalty - (0.30 - 0.10) / 0.30) < 1e-9
