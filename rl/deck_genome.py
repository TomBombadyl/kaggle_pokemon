"""Evolutionary deck representation with legality + composition balance repair.

Mutations stay within archetype bands (energy / Pokémon / trainer counts) derived
from our pilot and meta pool decks — see rl/deck_profiles.json.
"""

from __future__ import annotations

import copy
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from rl.deck_balance import (
    card_role,
    composition_of,
    infer_profile,
    rebalance_counts,
    summarize_deck,
)
from rl.deck_card_registry import CardRegistry, EvoChain, get_card_registry
from rl.deck_lane_registry import CANONICAL_LANES, LaneRegistry

ROOT = Path(__file__).resolve().parents[1]


def _load_pool():
    import sys

    sys.path.insert(0, str(ROOT))
    from scripts.validate_deck import load_card_pool

    return load_card_pool()


def _validate(ids: list[int], pool) -> tuple[bool, list[str]]:
    import sys

    sys.path.insert(0, str(ROOT))
    from scripts.validate_deck import validate_deck

    errors, _ = validate_deck(ids, pool)
    return not errors, errors


def _ace_spec_ids(pool) -> set[int]:
    return {cid for cid, info in pool.items() if info.is_ace_spec}


def _energy_ids(pool) -> set[int]:
    return {cid for cid, info in pool.items() if info.is_basic_energy}


def _enforce_ace_spec(counts: Counter, pool, rng: random.Random) -> None:
    """At most one ACE SPEC card in the whole deck."""
    ace_pool = _ace_spec_ids(pool)
    present = [cid for cid in counts if cid in ace_pool and counts[cid] > 0]
    if len(present) <= 1 and all(counts[cid] <= 1 for cid in present):
        return
    keep = rng.choice(present) if present else None
    for cid in present:
        if cid == keep:
            counts[cid] = 1
        else:
            del counts[cid]


def _by_role(counts: Counter, pool, role: str) -> list[int]:
    return [cid for cid, n in counts.items() if n > 0 and cid in pool and card_role(pool, cid) == role]


def _donor_cards(counts: Counter, pool, *, min_energy: int = 0) -> list[int]:
    donors = [c for c in _by_role(counts, pool, "trainer") if counts[c] > 1]
    donors += [c for c in _by_role(counts, pool, "pokemon") if counts[c] > 1]
    energy_ids = _energy_ids(pool)
    if energy_ids:
        eid = next(iter(energy_ids))
        if counts.get(eid, 0) > min_energy:
            donors.append(eid)
    return donors


def _pick_present(counts: Counter, stage: tuple[int, ...]) -> int | None:
    present = [cid for cid in stage if counts.get(cid, 0) > 0]
    if not present:
        return None
    return present[0]


def _apply_support_role_swap(
    counts: Counter,
    pool,
    registry: CardRegistry,
    rng: random.Random,
) -> bool:
    trainers = [
        cid
        for cid in _by_role(counts, pool, "trainer")
        if counts[cid] > 0 and registry.support_roles(cid)
    ]
    if not trainers:
        return False
    out_cid = rng.choice(trainers)
    role = rng.choice(registry.support_roles(out_cid))
    replacements = [
        cid
        for cid in registry.cards_with_role(role)
        if cid != out_cid
        and cid in pool
        and counts.get(cid, 0) < 4
        and not registry.is_ace_spec(cid)
    ]
    if not replacements:
        return False
    in_cid = rng.choice(replacements)
    counts[out_cid] -= 1
    if counts[out_cid] <= 0:
        del counts[out_cid]
    counts[in_cid] = counts.get(in_cid, 0) + 1
    return True


def _apply_chain_tune(
    counts: Counter,
    pool,
    registry: CardRegistry,
    rng: random.Random,
    profile,
) -> bool:
    chains = registry.chains_in_deck(counts)
    if not chains:
        return False
    chain = rng.choice(chains)
    if rng.random() < 0.5:
        return _chain_thicken(counts, pool, chain, rng, profile)
    return _chain_thin(counts, pool, chain, rng)


def _chain_thicken(
    counts: Counter,
    pool,
    chain: EvoChain,
    rng: random.Random,
    profile,
) -> bool:
    pairs = [
        (chain.stages[i], chain.stages[i + 1])
        for i in range(len(chain.stages) - 1)
        if any(counts.get(c, 0) > 0 for c in chain.stages[i])
    ]
    if not pairs:
        return False
    lower, upper = rng.choice(pairs)
    lower_cid = _pick_present(counts, lower) or rng.choice(lower)
    upper_cid = _pick_present(counts, upper) or rng.choice(upper)
    if counts.get(lower_cid, 0) >= 4 or counts.get(upper_cid, 0) >= 4:
        return False
    donors = _donor_cards(counts, pool, min_energy=profile.energy[0])
    if len(donors) < 2:
        return False
    for _ in range(2):
        d = rng.choice([c for c in donors if counts.get(c, 0) > 0])
        counts[d] -= 1
        if counts[d] <= 0:
            del counts[d]
    counts[lower_cid] = counts.get(lower_cid, 0) + 1
    counts[upper_cid] = counts.get(upper_cid, 0) + 1
    return True


def _chain_thin(counts: Counter, pool, chain: EvoChain, rng: random.Random) -> bool:
    for upper in reversed(chain.stages):
        upper_present = [cid for cid in upper if counts.get(cid, 0) > 0]
        if not upper_present:
            continue
        upper_cid = rng.choice(upper_present)
        upper_idx = chain.stages.index(upper)
        lower = chain.stages[upper_idx - 1] if upper_idx > 0 else None
        lower_cid = _pick_present(counts, lower) if lower else None
        if lower_cid is None:
            continue
        counts[upper_cid] -= 1
        if counts[upper_cid] <= 0:
            del counts[upper_cid]
        counts[lower_cid] -= 1
        if counts[lower_cid] <= 0:
            del counts[lower_cid]
        energy_ids = _energy_ids(pool)
        if energy_ids:
            eid = next(iter(energy_ids))
            counts[eid] = counts.get(eid, 0) + 2
        return True
    return False


@dataclass
class DeckGenome:
    """Deck as multiset of card IDs (60 total when valid)."""

    counts: Counter
    label: str = ""
    lane: str = ""
    fitness: float = -1.0
    meta: dict = field(default_factory=dict)

    def _with_lane_meta(self) -> None:
        if self.lane:
            self.meta["lane"] = self.lane

    @classmethod
    def from_deck(cls, deck: list[int], label: str = "", *, lane: str = "") -> "DeckGenome":
        g = cls(counts=Counter(deck), label=label, lane=lane)
        g._with_lane_meta()
        return g

    @classmethod
    def from_seed_path(cls, path: Path, lane: str = "") -> "DeckGenome":
        deck = [int(x) for x in path.read_text().splitlines() if x.strip()]
        return cls.from_deck(deck, label=path.stem, lane=lane)

    @classmethod
    def seed_population(
        cls,
        seed_paths: list[Path],
        size: int,
        rng: random.Random,
        *,
        registry: LaneRegistry | None = None,
    ) -> list["DeckGenome"]:
        pop: list[DeckGenome] = []
        for path in seed_paths:
            lane = registry.lane_for_path(path) if registry else ""
            pop.append(cls.from_seed_path(path, lane=lane))
        while len(pop) < size:
            base = rng.choice(pop[: max(1, len(seed_paths))])
            child = base.mutate(rng)
            pop.append(child)
        return pop[:size]

    @classmethod
    def seed_population_balanced(
        cls,
        registry: LaneRegistry,
        size: int,
        rng: random.Random,
        *,
        lanes: tuple[str, ...] | list[str] | None = None,
    ) -> list["DeckGenome"]:
        wanted = list(lanes or CANONICAL_LANES)
        by_lane_paths: dict[str, list[Path]] = {
            lane: list(registry.lane_to_paths.get(lane, [])) for lane in wanted
        }
        pop: list[DeckGenome] = []

        for lane in wanted:
            paths = by_lane_paths.get(lane, [])
            if paths:
                pop.append(cls.from_seed_path(paths[0], lane=lane))

        if not pop:
            return cls.seed_population(registry.seed_paths(wanted), size, rng, registry=registry)

        next_idx = {lane: 1 for lane in wanted}
        while len(pop) < size:
            added = False
            for lane in wanted:
                paths = by_lane_paths.get(lane, [])
                idx = next_idx.get(lane, 0)
                if idx < len(paths):
                    pop.append(cls.from_seed_path(paths[idx], lane=lane))
                    next_idx[lane] = idx + 1
                    added = True
                    if len(pop) >= size:
                        break
            if not added:
                break

        lane_pop: dict[str, list[DeckGenome]] = {
            lane: [g for g in pop if g.lane == lane] for lane in wanted
        }
        while len(pop) < size:
            lane = wanted[len(pop) % len(wanted)]
            candidates = lane_pop.get(lane) or pop
            base = rng.choice(candidates)
            child = base.mutate(rng)
            pop.append(child)
            lane_pop.setdefault(lane, []).append(child)
        return pop[:size]

    def to_list(self, rng: random.Random | None = None) -> list[int]:
        rng = rng or random.Random(0)
        cards: list[int] = []
        for cid, n in self.counts.items():
            cards.extend([cid] * n)
        rng.shuffle(cards)
        return cards[:60]

    def mutate(self, rng: random.Random, pool=None) -> "DeckGenome":
        pool = pool or _load_pool()
        profile = infer_profile(self.counts, pool)
        energy_ids = _energy_ids(pool)
        counts = copy.deepcopy(self.counts)
        comp = composition_of(counts, pool)

        # Balance-aware ops: energy bands, registry role swaps, evolution chains.
        registry = get_card_registry()
        ops = ["energy_tune", "pokemon_swap", "energy_trainer_trade"]
        if registry is not None:
            ops.extend(["support_role_swap", "chain_tune"])
        op = rng.choice(ops)

        eid = next(iter(energy_ids)) if energy_ids else None

        if op == "support_role_swap" and registry is not None:
            if not _apply_support_role_swap(counts, pool, registry, rng):
                op = "trainer_swap"

        if op == "chain_tune" and registry is not None:
            if not _apply_chain_tune(counts, pool, registry, rng, profile):
                op = "energy_tune"

        if op == "energy_tune" and eid is not None:
            delta = rng.choice([-2, -1, 1, 2])
            new_e = comp.energy + delta
            if profile.energy[0] <= new_e <= profile.energy[1]:
                if delta > 0:
                    donors = _by_role(counts, pool, "trainer") + [
                        c for c in _by_role(counts, pool, "pokemon") if counts[c] > 1
                    ]
                    if donors:
                        for _ in range(delta):
                            d = rng.choice([c for c in donors if counts[c] > 0])
                            counts[d] -= 1
                            counts[eid] = counts.get(eid, 0) + 1
                else:
                    receivers = [c for c in _by_role(counts, pool, "trainer") if counts.get(c, 0) < 4]
                    if receivers:
                        for _ in range(-delta):
                            if counts.get(eid, 0) <= 0:
                                break
                            counts[eid] -= 1
                            r = rng.choice(receivers)
                            counts[r] = counts.get(r, 0) + 1

        elif op == "trainer_swap":
            trainers = _by_role(counts, pool, "trainer")
            if len(trainers) >= 2:
                a, b = rng.sample(trainers, 2)
                if counts[a] > 0 and counts.get(b, 0) < 4:
                    counts[a] -= 1
                    counts[b] = counts.get(b, 0) + 1

        elif op == "pokemon_swap":
            mons = _by_role(counts, pool, "pokemon")
            if len(mons) >= 2:
                a, b = rng.sample(mons, 2)
                if counts[a] > 0 and counts.get(b, 0) < 4:
                    counts[a] -= 1
                    counts[b] = counts.get(b, 0) + 1

        elif op == "energy_trainer_trade" and eid is not None:
            comp = composition_of(counts, pool)
            trainers = [c for c in _by_role(counts, pool, "trainer") if counts.get(c, 0) < 4]
            if comp.energy > profile.energy[0] and trainers:
                counts[eid] -= 1
                t = rng.choice(trainers)
                counts[t] = counts.get(t, 0) + 1
            elif comp.energy < profile.energy[1]:
                donors = [c for c in _by_role(counts, pool, "trainer") if counts[c] > 1]
                if donors:
                    d = rng.choice(donors)
                    counts[d] -= 1
                    counts[eid] = counts.get(eid, 0) + 1

        g = DeckGenome(counts=counts, label=f"mut_{self.label}", lane=self.lane)
        g._with_lane_meta()
        return g.repair(rng, pool, fallback=copy.deepcopy(self.counts))

    def repair(
        self,
        rng: random.Random,
        pool=None,
        *,
        fallback: Counter | None = None,
    ) -> "DeckGenome":
        pool = pool or _load_pool()
        profile = infer_profile(self.counts, pool)
        counts = copy.deepcopy(self.counts)

        for cid in list(counts.keys()):
            if cid not in pool:
                del counts[cid]
            elif counts[cid] <= 0:
                del counts[cid]
            elif not pool[cid].is_basic_energy and counts[cid] > 4:
                counts[cid] = 4

        _enforce_ace_spec(counts, pool, rng)
        counts = rebalance_counts(counts, pool, profile, rng)
        _enforce_ace_spec(counts, pool, rng)

        total = sum(counts.values())
        eid = next(iter(_energy_ids(pool)), None)
        if eid is not None and total != 60:
            counts[eid] = counts.get(eid, 0) + (60 - total)

        g = DeckGenome(counts=counts, label=self.label, lane=self.lane)
        g._with_lane_meta()
        ok, _ = _validate(g.to_list(rng), pool)
        if ok:
            return g

        if fallback is not None:
            fb = DeckGenome(counts=Counter(fallback), label=self.label, lane=self.lane)
            fb._with_lane_meta()
            return fb
        fb = DeckGenome(counts=Counter(self.counts), label=self.label, lane=self.lane)
        fb._with_lane_meta()
        return fb

    @staticmethod
    def crossover(a: "DeckGenome", b: "DeckGenome", rng: random.Random) -> "DeckGenome":
        pool = _load_pool()
        # Crossover only within matching archetype to avoid illegal composition mashups.
        prof_a = infer_profile(a.counts, pool)
        prof_b = infer_profile(b.counts, pool)
        if a.lane and b.lane and a.lane != b.lane:
            parent = a if rng.random() < 0.5 else b
            return parent.mutate(rng, pool)
        if prof_a.name != prof_b.name:
            parent = a if rng.random() < 0.5 else b
            return parent.mutate(rng, pool)

        keys = set(a.counts.keys()) | set(b.counts.keys())
        counts: Counter = Counter()
        for k in keys:
            counts[k] = a.counts[k] if rng.random() < 0.5 else b.counts[k]
        child_lane = a.lane or b.lane
        child = DeckGenome(counts=counts, label=f"x_{a.label}_{b.label}", lane=child_lane)
        child._with_lane_meta()
        parent = a if rng.random() < 0.5 else b
        return child.repair(rng, pool, fallback=copy.deepcopy(parent.counts))

    def composition_summary(self, pool=None) -> str:
        return summarize_deck(self.counts, pool or _load_pool())
