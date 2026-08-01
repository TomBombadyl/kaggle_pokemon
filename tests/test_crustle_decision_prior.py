"""Offline unit tests for Crustle decision prior (no cg engine required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.crustle_levers import (
    BOSS_ID,
    CRUSTLE_ID,
    DWEBBLE_ID,
    KANGASKHAN_ID,
    OGERPON_ID,
    active_choice_score,
    boss_target_score,
    decision_prior_card_score,
    decision_prior_energy_home,
    energy_attach_priority,
    is_crustle_pilot_deck,
)


def test_is_crustle_pilot_deck():
    assert is_crustle_pilot_deck([344, 345, 117, 756] + [1] * 56)
    assert not is_crustle_pilot_deck([344, 1, 2, 3])


def test_energy_priority_order():
    assert energy_attach_priority(CRUSTLE_ID) > energy_attach_priority(OGERPON_ID)
    assert energy_attach_priority(OGERPON_ID) > energy_attach_priority(KANGASKHAN_ID)
    assert energy_attach_priority(KANGASKHAN_ID) > energy_attach_priority(DWEBBLE_ID)
    assert decision_prior_energy_home(CRUSTLE_ID) == energy_attach_priority(CRUSTLE_ID)


def test_boss_prefers_non_ex_wall_breaker():
    non_ex_no_ability = boss_target_score(9999, is_ex=False, has_ability=False)
    non_ex_ability = boss_target_score(117, is_ex=False, has_ability=True)
    pure_ex = boss_target_score(756, is_ex=True, has_ability=True)
    assert non_ex_no_ability > non_ex_ability > pure_ex


def test_promote_crustle_vs_ex():
    vs_ex = active_choice_score(CRUSTLE_ID, opp_active_is_ex=True)
    vs_non = active_choice_score(CRUSTLE_ID, opp_active_is_ex=False)
    assert vs_ex > vs_non
    # Kangaskhan early setup still strong when not forced wall.
    kang_setup = active_choice_score(
        KANGASKHAN_ID, turn=1, select_context="setup_active",
    )
    assert kang_setup > active_choice_score(DWEBBLE_ID, turn=1, select_context="setup_active")


def test_ogerpon_vs_ability_single():
    oger = active_choice_score(
        OGERPON_ID,
        opp_active_has_ability=True,
        opp_active_is_single_prize=True,
        opp_active_is_ex=False,
    )
    # ex Active is multi-prize → Stance less relevant; score drops to "vs ex" branch.
    oger_vs_ex = active_choice_score(
        OGERPON_ID,
        opp_active_is_ex=True,
        opp_active_has_ability=True,
        opp_active_is_single_prize=False,
    )
    assert oger > oger_vs_ex


def test_decision_prior_card_score_roles():
    ours = decision_prior_card_score(CRUSTLE_ID, side="ours", turn=2)
    boss = decision_prior_card_score(1, side="opp", is_ex=False, has_ability=False)
    energy = decision_prior_card_score(CRUSTLE_ID, side="energy")
    assert ours > 0
    assert boss > decision_prior_card_score(1, side="opp", is_ex=True, has_ability=True)
    assert energy == energy_attach_priority(CRUSTLE_ID)
    assert BOSS_ID == 1182


def test_crustle_search_scorer_imports():
    """Scorer class must import even without cg at construction time.

    Construction may pull RuleCore; engine only needed at choose().
    """
    from agent.search_policy import CrustleSearchScorer, CRUSTLE_SEARCH_CONTEXTS

    assert CRUSTLE_ID == 345
    assert len(CRUSTLE_SEARCH_CONTEXTS) >= 3
    # Instantiation without deck path still constructs.
    scorer = CrustleSearchScorer(budget_ms=200.0, guard_top_k=2)
    assert scorer._budget_ms == 200.0
    assert scorer._guard_top_k == 2
