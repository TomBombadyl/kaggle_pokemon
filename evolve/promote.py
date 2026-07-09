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


def _parse_kv(spec: str) -> dict:
    out: dict = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        k, v = pair.split("=", 1)
        key = k.strip()
        out[key] = float(v) if "." in v else int(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ice-cream-hp-threshold", default="", help="e.g. lucario=260,starmie=205")
    ap.add_argument("--attack-base-dmg", default="", help="e.g. 253=210,965=45")
    args = ap.parse_args()

    if not args.ice_cream_hp_threshold and not args.attack_base_dmg:
        print("Nothing to promote -- pass --ice-cream-hp-threshold and/or --attack-base-dmg.")
        return 1

    if args.ice_cream_hp_threshold:
        print("Paste into agent/archaludon_agent.py, replacing _ICE_CREAM_HP_THRESHOLD:")
        print(_parse_kv(args.ice_cream_hp_threshold))
        print()
    if args.attack_base_dmg:
        print("Paste into agent/archaludon_agent.py, replacing _ATTACK_BASE_DMG:")
        print(_parse_kv(args.attack_base_dmg))
        print()

    print(
        "Next: scripts/gate_archaludon.py --games 30 --suite full --report -> "
        "scripts/check_upload_eligible.py -> confirm with user before any Kaggle upload."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
