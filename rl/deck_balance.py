"""Deck composition balance for evolutionary deck search.

Real TCG lists follow archetype-specific ratios. Our pilot decks (heavy basics)
run ~29–35 energy / ~12–16 Pokémon / ~11–15 trainers; meta pool decks run
~18–22 energy / ~13–17 Pokémon / ~25–27 trainers (more draw/search).

Profiles are derived from agent_decks/*.csv (see deck_profiles.json).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = ROOT / "rl" / "deck_profiles.json"

CardRole = Literal["energy", "pokemon", "trainer"]


class DeckProfile(str, Enum):
    BASIC_HEAVY = "basic_heavy"  # simple pilot / big basic / kyogre lines
    META_STANDARD = "meta_standard"  # competitive meta-style lists
    AUTO = "auto"


@dataclass(frozen=True)
class Composition:
    energy: int
    pokemon: int
    trainers: int

    @property
    def total(self) -> int:
        return self.energy + self.pokemon + self.trainers

    def as_dict(self) -> dict[str, int]:
        return {"energy": self.energy, "pokemon": self.pokemon, "trainers": self.trainers}


@dataclass(frozen=True)
class ProfileBounds:
    name: str
    energy: tuple[int, int]
    pokemon: tuple[int, int]
    trainers: tuple[int, int]

    def contains(self, comp: Composition) -> bool:
        return (
            self.energy[0] <= comp.energy <= self.energy[1]
            and self.pokemon[0] <= comp.pokemon <= self.pokemon[1]
            and self.trainers[0] <= comp.trainers <= self.trainers[1]
        )

    def distance(self, comp: Composition) -> float:
        """How far outside bounds (0 = inside)."""
        d = 0.0
        for val, bounds in (
            (comp.energy, self.energy),
            (comp.pokemon, self.pokemon),
            (comp.trainers, self.trainers),
        ):
            if val < bounds[0]:
                d += bounds[0] - val
            elif val > bounds[1]:
                d += val - bounds[1]
        return d


def load_profiles() -> dict[str, ProfileBounds]:
    if PROFILES_PATH.exists():
        data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        return {
            name: ProfileBounds(
                name=name,
                energy=tuple(row["energy"]),
                pokemon=tuple(row["pokemon"]),
                trainers=tuple(row["trainers"]),
            )
            for name, row in data.get("profiles", {}).items()
        }
    return {
        "basic_heavy": ProfileBounds("basic_heavy", (27, 37), (10, 18), (10, 18)),
        "meta_standard": ProfileBounds("meta_standard", (16, 24), (12, 20), (22, 30)),
    }


BASIC_HEAVY = ProfileBounds("basic_heavy", (27, 37), (10, 18), (10, 18))
META_STANDARD = ProfileBounds("meta_standard", (16, 24), (12, 20), (22, 30))


def _load_pool():
    import sys

    sys.path.insert(0, str(ROOT))
    from scripts.validate_deck import load_card_pool

    return load_card_pool()


def card_role(pool, card_id: int) -> CardRole:
    info = pool[card_id]
    if info.is_basic_energy:
        return "energy"
    if info.is_basic_pokemon or info.is_evolution:
        return "pokemon"
    return "trainer"


def composition_of(counts: Counter, pool) -> Composition:
    e = p = t = 0
    for cid, n in counts.items():
        if cid not in pool:
            continue
        role = card_role(pool, cid)
        if role == "energy":
            e += n
        elif role == "pokemon":
            p += n
        else:
            t += n
    return Composition(e, p, t)


def infer_profile(counts: Counter, pool) -> ProfileBounds:
    """Pick profile from current energy band (pilot vs meta style)."""
    comp = composition_of(counts, pool)
    profiles = load_profiles()
    basic = profiles.get("basic_heavy", BASIC_HEAVY)
    meta = profiles.get("meta_standard", META_STANDARD)
    if comp.energy >= 26:
        return basic
    if comp.trainers >= 22:
        return meta
    # Mid-range: closer profile by L1 distance to band centers
    def center(pb: ProfileBounds) -> Composition:
        return Composition(
            sum(pb.energy) // 2,
            sum(pb.pokemon) // 2,
            sum(pb.trainers) // 2,
        )

    bc, mc = center(basic), center(meta)
    d_basic = abs(comp.energy - bc.energy) + abs(comp.trainers - bc.trainers)
    d_meta = abs(comp.energy - mc.energy) + abs(comp.trainers - mc.trainers)
    return basic if d_basic <= d_meta else meta


def balance_penalty(counts: Counter, pool, profile: ProfileBounds | None = None) -> float:
    """Soft penalty [0, 1] for decks outside suggested composition."""
    profile = profile or infer_profile(counts, pool)
    comp = composition_of(counts, pool)
    dist = profile.distance(comp)
    return min(1.0, dist / 10.0)


# Minimum expected win rate vs any high-weight benchmark opponent before collapse penalty.
MATCHUP_COLLAPSE_FLOOR = 0.30
# Only opponents at or above this suite weight count toward the min-rate check.
MATCHUP_COLLAPSE_MIN_WEIGHT = 1.0


def matchup_collapse_penalty(
    per_opponent: dict[str, dict],
    *,
    floor: float = MATCHUP_COLLAPSE_FLOOR,
    min_opponent_weight: float = MATCHUP_COLLAPSE_MIN_WEIGHT,
) -> tuple[float, float]:
    """Soft penalty [0, 1] when min win rate vs weighted opponents falls below floor.

    Returns (penalty, min_win_rate). Penalty scales linearly from 0 at floor to 1 at 0%.
    """
    rates: list[float] = []
    for row in per_opponent.values():
        weight = float(row.get("weight", 1.0))
        if weight >= min_opponent_weight:
            rates.append(float(row["rate"]))
    if not rates:
        rates = [float(row["rate"]) for row in per_opponent.values()]
    min_rate = min(rates) if rates else 0.0
    if min_rate >= floor:
        return 0.0, min_rate
    return min(1.0, (floor - min_rate) / max(floor, 1e-9)), min_rate


def _energy_ids(pool) -> set[int]:
    return {cid for cid, info in pool.items() if info.is_basic_energy}


def _cards_by_role(counts: Counter, pool, role: CardRole) -> list[int]:
    return [cid for cid, n in counts.items() if n > 0 and cid in pool and card_role(pool, cid) == role]


def rebalance_counts(
    counts: Counter,
    pool,
    profile: ProfileBounds | None,
    rng,
) -> Counter:
    """Nudge counts toward profile bands without breaking 60-card total."""
    import copy

    profile = profile or infer_profile(counts, pool)
    counts = copy.deepcopy(counts)
    energy_ids = _energy_ids(pool)
    if not energy_ids:
        return counts
    eid = next(iter(energy_ids))

    for _ in range(40):
        comp = composition_of(counts, pool)
        if profile.contains(comp) and sum(counts.values()) == 60:
            break

        total = sum(counts.values())
        if total != 60:
            delta = 60 - total
            counts[eid] = max(0, counts.get(eid, 0) + delta)
            continue

        if comp.energy < profile.energy[0]:
            donors = _cards_by_role(counts, pool, "trainer") + _cards_by_role(counts, pool, "pokemon")
            donors = [c for c in donors if counts[c] > 0 and (card_role(pool, c) != "pokemon" or counts[c] > 1)]
            if donors:
                d = rng.choice(donors)
                counts[d] -= 1
                counts[eid] = counts.get(eid, 0) + 1
            else:
                break
        elif comp.energy > profile.energy[1]:
            receivers = [c for c in _cards_by_role(counts, pool, "trainer") if counts.get(c, 0) < 4]
            if not receivers:
                receivers = [c for c in _cards_by_role(counts, pool, "pokemon") if counts.get(c, 0) < 4]
            if receivers and counts.get(eid, 0) > 0:
                r = rng.choice(receivers)
                counts[eid] -= 1
                counts[r] = counts.get(r, 0) + 1
            else:
                break
        elif comp.trainers < profile.trainers[0]:
            if counts.get(eid, 0) > profile.energy[0]:
                receivers = [c for c in _cards_by_role(counts, pool, "trainer") if counts.get(c, 0) < 4]
                if receivers:
                    r = rng.choice(receivers)
                    counts[eid] -= 1
                    counts[r] = counts.get(r, 0) + 1
                else:
                    break
            else:
                break
        elif comp.trainers > profile.trainers[1]:
            donors = [c for c in _cards_by_role(counts, pool, "trainer") if counts[c] > 1]
            if donors:
                d = rng.choice(donors)
                counts[d] -= 1
                counts[eid] = counts.get(eid, 0) + 1
            else:
                break
        elif comp.pokemon < profile.pokemon[0]:
            if counts.get(eid, 0) > profile.energy[0]:
                receivers = [c for c in _cards_by_role(counts, pool, "pokemon") if counts.get(c, 0) < 4]
                if receivers:
                    r = rng.choice(receivers)
                    counts[eid] -= 1
                    counts[r] = counts.get(r, 0) + 1
                else:
                    break
            else:
                break
        elif comp.pokemon > profile.pokemon[1]:
            donors = [c for c in _cards_by_role(counts, pool, "pokemon") if counts[c] > 1]
            if donors:
                d = rng.choice(donors)
                counts[d] -= 1
                counts[eid] = counts.get(eid, 0) + 1
            else:
                break
        else:
            break

    return counts


def summarize_deck(counts: Counter, pool) -> str:
    comp = composition_of(counts, pool)
    prof = infer_profile(counts, pool)
    return (
        f"{prof.name}: energy={comp.energy} pokemon={comp.pokemon} "
        f"trainers={comp.trainers} (bands E{prof.energy} P{prof.pokemon} T{prof.trainers})"
    )
