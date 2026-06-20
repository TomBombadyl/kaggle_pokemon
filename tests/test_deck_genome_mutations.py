"""Unit tests for role/chain-aware deck mutations (no sim)."""

from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rl.deck_card_registry import get_card_registry
from rl.deck_balance import infer_profile
from rl.deck_genome import DeckGenome, _apply_chain_tune, _apply_support_role_swap


def _load_pool():
    from scripts.validate_deck import load_card_pool

    return load_card_pool()


def test_registry_loads_with_roles_and_chains():
    registry = get_card_registry()
    assert registry is not None
    assert registry.support_roles(1123) == ["switch_trainer"]
    chain = registry.chain_for_card(741)
    assert chain is not None
    assert chain.root_name == "Abra"
    assert len(chain.stages) >= 2


def test_support_role_swap_keeps_switch_role():
    registry = get_card_registry()
    pool = _load_pool()
    rng = random.Random(7)
    counts = Counter({1123: 2, 1182: 2, 5: 56})
    assert _apply_support_role_swap(counts, pool, registry, rng)
    switch_cards = [cid for cid in counts if "switch_trainer" in registry.support_roles(cid)]
    assert switch_cards


def test_chain_tune_stays_legal_on_alakazam_line():
    registry = get_card_registry()
    pool = _load_pool()
    rng = random.Random(11)
    path = ROOT / "agent_decks" / "pool_alakazam_dudunsparce.csv"
    genome = DeckGenome.from_seed_path(path, lane="spread/control")
    counts = Counter(genome.counts)
    profile = infer_profile(counts, pool)
    assert _apply_chain_tune(counts, pool, registry, rng, profile)
    repaired = DeckGenome(counts=counts, label="test", lane="spread/control").repair(
        rng, pool, fallback=genome.counts
    )
    from scripts.validate_deck import validate_deck

    errors, _ = validate_deck(repaired.to_list(rng), pool)
    assert not errors
    assert counts.get(741, 0) + counts.get(742, 0) + counts.get(245, 0) > 0


def test_mutate_stays_legal_on_seed_deck():
    pool = _load_pool()
    rng = random.Random(99)
    path = ROOT / "agent_decks" / "pool_alakazam_dudunsparce.csv"
    base = DeckGenome.from_seed_path(path, lane="spread/control")
    from scripts.validate_deck import validate_deck

    for i in range(12):
        child = base.mutate(random.Random(99 + i), pool)
        errors, _ = validate_deck(child.to_list(rng), pool)
        assert not errors, f"mutate {i} illegal: {errors}"
        assert sum(child.counts.values()) == 60
