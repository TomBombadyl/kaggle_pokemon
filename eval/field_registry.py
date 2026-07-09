"""Load field/registry.json — canonical opponent index."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "field" / "registry.json"


@lru_cache(maxsize=4)
def load_registry(path: Path | None = None) -> dict[str, Any]:
    """Cached per (path) -- every existing caller uses the default path, so this
    is effectively one disk read per process instead of one per call. Safe because
    no caller mutates the returned dict (callers that need a copy already do
    dict(opp) / list(...) at the point of use)."""
    p = path or REGISTRY_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_deck_path(stem: str, registry: dict[str, Any] | None = None) -> Path:
    reg = registry or load_registry()
    opp = reg["opponents"].get(stem)
    if opp is None:
        raise KeyError(f"unknown opponent stem: {stem}")
    return ROOT / opp["deck_path"]


def opponents_for_suite(
    suite: str,
    registry: dict[str, Any] | None = None,
) -> list[str]:
    reg = registry or load_registry()
    if suite not in reg["suites"]:
        raise KeyError(f"unknown suite: {suite}")
    return list(reg["suites"][suite])


def opponent_meta(stem: str, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = registry or load_registry()
    opp = reg["opponents"].get(stem)
    if opp is None:
        raise KeyError(f"unknown opponent stem: {stem}")
    return dict(opp)
