"""Candidate proposer -- the 'propose new mutations' half of the AlphaEvolve loop.

Default implementation: bounded per-field random perturbation, evaluated in small
generations, keeping the top-K survivors each round (not just the single best) --
deliberately not a greedy hill-climb, since RULINGS.md already documents blind
single-point GA collapsing onto local-gate noise instead of real improvement.

`propose()` is the one function to replace with an LLM-driven version (the real
AlphaEvolve API, or an Anthropic API call) later -- evaluator.py and
run_evolution.py only depend on this function's signature, nothing else changes.
"""

from __future__ import annotations

import random

from evolve.targets import EvolveTarget, base_params


def propose(
    target: EvolveTarget,
    survivors: list[dict[str, dict]],
    *,
    population: int,
    rng: random.Random,
    step_frac: float = 0.15,
) -> list[dict[str, dict]]:
    """Generate `population` candidate param sets from the current survivor pool.

    Each candidate perturbs one seed (chosen from survivors, or the target's live
    base values on generation 0) by a bounded fraction of each field's legal range.
    """
    seeds = survivors or [base_params(target)]
    return [_perturb(target, rng.choice(seeds), rng, step_frac) for _ in range(population)]


def _perturb(
    target: EvolveTarget,
    seed: dict[str, dict],
    rng: random.Random,
    step_frac: float,
) -> dict[str, dict]:
    candidate: dict[str, dict] = {}
    for block, fields in seed.items():
        block_bounds = target.bounds.get(block, {})
        new_fields = {}
        for key, value in fields.items():
            bounds = block_bounds.get(key)
            if bounds is None:
                new_fields[key] = value
                continue
            span = bounds.hi - bounds.lo
            delta = rng.uniform(-step_frac, step_frac) * span
            new_value = min(bounds.hi, max(bounds.lo, value + delta))
            new_fields[key] = int(round(new_value)) if bounds.is_int else new_value
        candidate[block] = new_fields
    return candidate
