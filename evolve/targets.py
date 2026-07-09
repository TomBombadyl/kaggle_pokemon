"""Registry of evolvable parameter blocks (AlphaEvolve-style search, Pillar support).

Each target names the parameter blocks living in a seed program (base values stay
the single source of truth in the agent file itself — nothing here copies them
permanently, just reads them live), the legal range each field may be perturbed
within, and the eval.gates function that scores a candidate. A target's gate_fn
must accept a `param_overrides` kwarg shaped like `param_blocks` (see
eval.gates.gate_archaludon_matchups + agent/archaludon_levers.py for the pattern).

Start with exactly one target — Archaludon, the only unpaused primary track
(ROADMAP.md Sec 0: "Refine archaludon_rules x archaludon_ex_cinderace only. All
other agents paused."). Extend to other decks/levers only after the pilot proves
the loop surfaces a real (CI-separated) improvement, not local-gate noise.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldBounds:
    lo: float
    hi: float
    is_int: bool = True


@dataclass(frozen=True)
class EvolveTarget:
    name: str
    param_blocks: dict[str, dict]
    bounds: dict[str, dict]
    gate_fn: str  # dotted path, e.g. "eval.gates.gate_archaludon_matchups"


def base_params(target: EvolveTarget) -> dict[str, dict]:
    """Live snapshot of a target's current (production) parameter values."""
    return {block: dict(values) for block, values in target.param_blocks.items()}


def _archaludon_target() -> EvolveTarget:
    from agent.archaludon_agent import _ATTACK_BASE_DMG, _ICE_CREAM_HP_THRESHOLD

    return EvolveTarget(
        name="archaludon",
        param_blocks={
            "ice_cream_hp_threshold": dict(_ICE_CREAM_HP_THRESHOLD),
            "attack_base_dmg": dict(_ATTACK_BASE_DMG),
        },
        bounds={
            "ice_cream_hp_threshold": {
                k: FieldBounds(lo=max(0, v - 100), hi=v + 100)
                for k, v in _ICE_CREAM_HP_THRESHOLD.items()
            },
            "attack_base_dmg": {
                k: FieldBounds(lo=max(0, v - 60), hi=v + 60)
                for k, v in _ATTACK_BASE_DMG.items()
            },
        },
        gate_fn="eval.gates.gate_archaludon_matchups",
    )


_TARGET_BUILDERS = {"archaludon": _archaludon_target}
_target_cache: dict[str, EvolveTarget] = {}


def available_targets() -> list[str]:
    return sorted(_TARGET_BUILDERS)


def get_target(name: str) -> EvolveTarget:
    """Build (and cache) a target on first use -- keeps import of this module free

    of the cg-engine dependency chain that building an EvolveTarget requires, so
    evolve.proposer and the search algorithm itself stay importable/testable
    without the real game engine.
    """
    if name not in _target_cache:
        if name not in _TARGET_BUILDERS:
            raise KeyError(f"unknown evolve target: {name!r} (available: {available_targets()})")
        _target_cache[name] = _TARGET_BUILDERS[name]()
    return _target_cache[name]
