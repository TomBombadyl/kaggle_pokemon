#!/usr/bin/env python3
"""Manually apply one evolved candidate's params into agent/archaludon_agent.py.

Deliberately not automatic -- this is the one point where evolve/ output touches a
shipped agent file. archaludon_agent.py's own docstring asks for hand-reviewed,
one-lever-at-a-time changes; a promotion is exactly that kind of change, so this
script prints the literal dict-literal replacement rather than editing bytes in
place. After pasting it in, the existing pipeline takes over unchanged: full local
gate (scripts/gate_archaludon.py) -> scripts/check_upload_eligible.py ->
user-confirmed Kaggle upload -> >=2 ladder mu readings (R12).

  python evolve/promote.py \
      --ice-cream-hp-threshold lucario=260,starmie=205 \
      --attack-base-dmg 253=210
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_kv(spec: str, *, key_cast: Callable[[str], object] = str) -> dict:
    """key_cast must match the real dict's key type -- _ATTACK_BASE_DMG is keyed by
    int attack_id, _ICE_CREAM_HP_THRESHOLD by str matchup name. Getting this wrong
    produces a dict that silently never matches on lookup (wrong type, not KeyError)."""
    out: dict = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        k, v = pair.split("=", 1)
        key = key_cast(k.strip())
        out[key] = float(v) if "." in v else int(v)
    return out


def _check_bounds(block: str, values: dict) -> None:
    """Best-effort warning if a hand-typed value falls outside evolve/targets.py's
    declared range for this block. Silently skipped if the cg engine (needed to
    build the target registry) isn't available -- promote.py can still be used to
    format values, just without the sanity check."""
    try:
        from evolve.targets import get_target
    except ImportError:
        return
    try:
        target = get_target("archaludon")
    except Exception:
        return
    block_bounds = target.bounds.get(block, {})
    for key, value in values.items():
        bounds = block_bounds.get(key)
        if bounds is None:
            print(f"  warning: {key!r} has no declared bounds for {block} -- new key?")
        elif not (bounds.lo <= value <= bounds.hi):
            print(f"  warning: {key}={value} outside evolve/targets.py bounds [{bounds.lo}, {bounds.hi}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ice-cream-hp-threshold", default="", help="e.g. lucario=260,starmie=205")
    ap.add_argument("--attack-base-dmg", default="", help="e.g. 253=210,965=45")
    args = ap.parse_args()

    if not args.ice_cream_hp_threshold and not args.attack_base_dmg:
        print("Nothing to promote -- pass --ice-cream-hp-threshold and/or --attack-base-dmg.")
        return 1

    if args.ice_cream_hp_threshold:
        values = _parse_kv(args.ice_cream_hp_threshold, key_cast=str)
        print("Paste into agent/archaludon_agent.py, replacing _ICE_CREAM_HP_THRESHOLD:")
        print(values)
        _check_bounds("ice_cream_hp_threshold", values)
        print()
    if args.attack_base_dmg:
        values = _parse_kv(args.attack_base_dmg, key_cast=int)
        print("Paste into agent/archaludon_agent.py, replacing _ATTACK_BASE_DMG:")
        print(values)
        _check_bounds("attack_base_dmg", values)
        print()

    print(
        "Next: scripts/gate_archaludon.py --games 30 --suite full --report -> "
        "scripts/check_upload_eligible.py -> confirm with user before any Kaggle upload."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
