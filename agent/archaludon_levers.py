"""Evolvable parameter overrides for archaludon_agent.

Mirrors agent/dragapult_levers.py's override pattern. Base values stay the single
source of truth in agent/archaludon_agent.py (_ICE_CREAM_HP_THRESHOLD,
_ATTACK_BASE_DMG) — this module only lets eval/gate code inject a candidate value
set for one gate run without editing the primary iteration file. Consumed by
evolve/evaluator.py via eval.gates.gate_archaludon_matchups(param_overrides=...).
"""

from __future__ import annotations

_active_overrides: dict[str, dict] | None = None


def set_archaludon_param_overrides(overrides: dict[str, dict] | None) -> None:
    """overrides keys: 'ice_cream_hp_threshold', 'attack_base_dmg' -> dict merged over base."""
    global _active_overrides
    _active_overrides = overrides


def merged_ice_cream_hp_threshold(base: dict[str, int]) -> dict[str, int]:
    if not _active_overrides or "ice_cream_hp_threshold" not in _active_overrides:
        return base
    return {**base, **_active_overrides["ice_cream_hp_threshold"]}


def merged_attack_base_dmg(base: dict[int, int]) -> dict[int, int]:
    if not _active_overrides or "attack_base_dmg" not in _active_overrides:
        return base
    return {**base, **_active_overrides["attack_base_dmg"]}
