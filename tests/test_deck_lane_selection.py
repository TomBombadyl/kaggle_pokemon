"""Unit tests for per-lane GA selection in train_deck_campaign (no sim)."""

from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rl.deck_genome import DeckGenome
from rl.deck_lane_registry import CANONICAL_LANES, LaneRegistry
from rl.train_deck_campaign import (
    _breed_next_generation,
    _ensure_lane_coverage,
    _inject_lane_seed,
    _select_survivors_by_lane,
    _survivor_target,
)


def _mock_genome(label: str, lane: str, fitness: float) -> DeckGenome:
    return DeckGenome(
        counts=Counter({1: 60}),
        label=label,
        lane=lane,
        fitness=fitness,
        meta={},
    )


def test_survivor_target_floors_at_num_lanes():
    assert _survivor_target(8, 4) == 4
    assert _survivor_target(12, 4) == 6
    assert _survivor_target(6, 4) == 4


def test_mini_tournament_beats_global():
    lanes = list(CANONICAL_LANES)
    pop = [
        _mock_genome("fb1", "fast-basic", 0.90),
        _mock_genome("fb2", "fast-basic", 0.85),
        _mock_genome("fb3", "fast-basic", 0.80),
        _mock_genome("fb4", "fast-basic", 0.75),
        _mock_genome("ak1", "anti-Kyogre", 0.50),
        _mock_genome("sc1", "spread/control", 0.40),
        _mock_genome("rg1", "resilient-generalist", 0.30),
        _mock_genome("fb5", "fast-basic", 0.25),
    ]
    rng = random.Random(0)
    target = _survivor_target(8, len(lanes))
    survivors = _select_survivors_by_lane(pop, lanes, target, rng)

    global_top4 = {g.lane for g in sorted(pop, key=lambda x: x.fitness, reverse=True)[:4]}
    assert global_top4 == {"fast-basic"}

    survivor_lanes = {g.lane for g in survivors}
    assert survivor_lanes == set(lanes)
    assert len(survivors) == target


def test_round_robin_breeding_preserves_lanes():
    lanes = list(CANONICAL_LANES)
    survivors = [_mock_genome(f"s_{lane}", lane, 0.7) for lane in lanes]
    rng = random.Random(42)
    registry = LaneRegistry.load(ROOT / "report" / "deck_rl" / "candidate_registry.csv")
    pool = None  # breed uses parent genomes; inject not needed when all lanes covered

    from rl.train_deck_campaign import _load_pool_for_balance

    pool = _load_pool_for_balance()
    next_pop = _breed_next_generation(survivors, population=8, lanes=lanes, rng=rng, pool=pool, registry=registry)

    assert len(next_pop) == 8
    pop_lanes = {g.lane for g in next_pop}
    assert pop_lanes == set(lanes)
    offspring = next_pop[len(survivors):]
    for i, child in enumerate(offspring):
        expected_lane = lanes[(len(survivors) + i) % len(lanes)]
        assert child.lane == expected_lane


def test_inject_extinct_lane():
    lanes = list(CANONICAL_LANES)
    survivors = [
        _mock_genome("ak", "anti-Kyogre", 0.8),
        _mock_genome("fb", "fast-basic", 0.7),
        _mock_genome("sc", "spread/control", 0.6),
    ]
    rng = random.Random(7)
    registry = LaneRegistry.load(ROOT / "report" / "deck_rl" / "candidate_registry.csv")
    from rl.train_deck_campaign import _load_pool_for_balance

    pool = _load_pool_for_balance()
    covered = _ensure_lane_coverage(survivors, lanes, registry, rng, pool)

    assert {g.lane for g in covered} == set(lanes)
    injected = [g for g in covered if g.lane == "resilient-generalist"]
    assert len(injected) == 1
    assert injected[0].lane == "resilient-generalist"


def test_inject_lane_seed_from_registry():
    rng = random.Random(3)
    registry = LaneRegistry.load(ROOT / "report" / "deck_rl" / "candidate_registry.csv")
    from rl.train_deck_campaign import _load_pool_for_balance

    pool = _load_pool_for_balance()
    g = _inject_lane_seed(registry, "spread/control", rng, pool)
    assert g.lane == "spread/control"
    assert sum(g.counts.values()) == 60
