"""Unit tests for agent/empty_bench_guard.py (observation + option mask logic)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "data" / "sim" / "sample_submission"
for p in (ENGINE, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from agent.empty_bench_guard import is_basic_pokemon_id  # noqa: E402
from agent.dragapult_bench_guard import _BENCH_PRIORITY as DRG_PRIORITY  # noqa: E402
from agent.alakazam_bench_guard import _BENCH_PRIORITY as ALK_PRIORITY  # noqa: E402
from agent.archaludon_bench_guard import _BENCH_PRIORITY as ARC_PRIORITY  # noqa: E402


@pytest.mark.parametrize("card_id", list(DRG_PRIORITY))
def test_dragapult_priority_ids_are_basics(card_id: int):
    assert is_basic_pokemon_id(card_id), f"{card_id} must be basic for bench guard"


@pytest.mark.parametrize("card_id", list(ALK_PRIORITY))
def test_alakazam_priority_ids_are_basics(card_id: int):
    assert is_basic_pokemon_id(card_id), f"{card_id} must be basic for bench guard"


@pytest.mark.parametrize("card_id", list(ARC_PRIORITY))
def test_archaludon_priority_ids_are_basics(card_id: int):
    assert is_basic_pokemon_id(card_id), f"{card_id} must be basic for bench guard"


def test_kadabra_not_basic():
    assert not is_basic_pokemon_id(742)
