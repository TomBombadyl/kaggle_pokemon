"""Serialize / restore deck GA population for interrupt-safe resume."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from rl.deck_genome import DeckGenome

DECK_GA_PATH = Path(__file__).resolve().parents[1] / "report" / "rl_deck_campaign" / "deck_ga.json"


def genome_to_dict(g: DeckGenome) -> dict:
    return {
        "counts": dict(g.counts),
        "label": g.label,
        "lane": g.lane,
        "fitness": g.fitness,
        "meta": g.meta,
    }


def genome_from_dict(row: dict) -> DeckGenome:
    counts = Counter(
        {int(k): int(v) for k, v in row["counts"].items() if int(v) > 0}
    )
    lane = row.get("lane") or row.get("meta", {}).get("lane", "")
    return DeckGenome(
        counts=counts,
        label=row.get("label", ""),
        lane=lane,
        fitness=float(row.get("fitness", -1.0)),
        meta=row.get("meta", {}),
    )


def save_deck_ga(
    path: Path,
    *,
    generation: int,
    population: list[DeckGenome],
    rng_seed: int,
    cycle: int = 0,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generation": generation,
        "cycle": cycle,
        "rng_seed": rng_seed,
        "population": [genome_to_dict(g) for g in population],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_deck_ga(path: Path | None = None) -> dict | None:
    path = path or DECK_GA_PATH
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
