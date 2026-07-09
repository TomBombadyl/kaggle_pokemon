"""Load field mixture weights for weighted eval gates (R3)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_PATH = ROOT / "field" / "weights.json"


@lru_cache(maxsize=4)
def load_weights(path: Path | None = None) -> dict[str, Any]:
    """Cached per (path) -- see load_registry's docstring in field_registry.py for
    why this is safe. scripts/build_field_weights.py, which rewrites weights.json,
    always runs as a separate process (see evolve/run_evolution.py
    --refresh-episodes), so a stale in-process cache is not a concern here."""
    p = path or WEIGHTS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def archetype_weight(archetype: str, weights: dict[str, Any] | None = None) -> float:
    w = weights or load_weights()
    table = w.get("opponent_archetype_weights") or {}
    return float(table.get(archetype, 0.05))


def opponent_weight(stem: str, registry: dict[str, Any], weights: dict[str, Any] | None = None) -> float:
    from eval.field_registry import opponent_meta

    meta = opponent_meta(stem, registry)
    return archetype_weight(meta.get("archetype", "unknown"), weights)
