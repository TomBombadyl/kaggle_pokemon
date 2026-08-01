"""ARCH: static audit of `detect_matchup` routing vs. the deck's real archetype.

`_should_use_tomato` keys entirely off `detect_matchup(obs)`. Three of the four
delegate KEEPs (alakazam, dragapult, grimmsnarl) only pay out when the router
actually names that matchup, and the router is ordered:

    crustle (CRUSTLE_LINE | FLG_WALL_SHELL | Spiky) -> grimmsnarl -> alakazam
    -> iono -> dragapult -> hop -> starmie -> lucario -> generic

`FLG_WALL_SHELL` contains Cornerstone Ogerpon ex (117) and Mega Kangaskhan ex
(756), both splashable, and the Spiky-Energy branch fires on *any* board without
a Grimmsnarl-line mon in play. So a deck whose real archetype is grimmsnarl can
be routed to `crustle` -- which is still in `_TOMATO_EXCLUDE_MATCHUPS` -- and
silently fall back to our own scorer, the one measured at 74.0% vs the delegate's
91.1%. marnie_grimmsnarl_ex is 65.7% of the live top-band field, so a misroute
there is the difference between the R4 KEEP paying out live and not.

This is a static check: it does not run games and does not touch any brain.
For each deck it reports what the router returns for the *whole* Pokemon set
(late-game board) and, separately, for each single Pokemon alone (any of which
can be the turn-1 board), then flags decks where a delegated archetype can be
captured by an excluded one.

    python scripts/arch_matchup_routing_audit.py
    python scripts/arch_matchup_routing_audit.py --json report/arch_routing_audit.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from agent import archaludon_agent as AA  # noqa: E402
from eval.field_registry import load_registry, resolve_deck_path  # noqa: E402
from eval.harness import load_deck  # noqa: E402

# Router order, replicated as pure set logic so we can ask "what would
# detect_matchup say for this id set" without building an Observation.
TOMATO_OWNED = {"alakazam", "dragapult", "grimmsnarl", "generic"}


def route(ids: set[int], spiky: bool = False) -> str:
    """Pure-set replica of archaludon_agent.detect_matchup's Pokemon branches.

    Energy/stadium branches (Lightning -> iono, Levincia -> iono) are not
    reachable from a decklist alone and are reported separately by the caller.
    """
    if ids & AA.CRUSTLE_LINE or ids & AA.FLG_WALL_SHELL:
        return "crustle"
    if spiky and not (ids & AA.GRIMMSNARL_LINE):
        return "crustle"
    if ids & AA.GRIMMSNARL_LINE or ids & AA.MUNKIDORI_IDS:
        return "grimmsnarl"
    if ids & AA.ALAKAZAM_LINE:
        return "alakazam"
    if ids & AA.IONO_LINE:
        return "iono"
    if ids & AA.DRAGAPULT_LINE:
        return "dragapult"
    if ids & AA.HOP_LINE:
        return "hop"
    if ids & AA.STARMIE_LINE:
        return "starmie"
    if ids & AA.LUCARIO_LINE:
        return "lucario"
    return "generic"


def deck_pokemon_ids(deck: list[int]) -> set[int]:
    """Ids in the list that the router can ever see, i.e. Pokemon on board."""
    tagged = set()
    for cid in set(deck):
        for line in (
            AA.CRUSTLE_LINE, AA.FLG_WALL_SHELL, AA.GRIMMSNARL_LINE,
            AA.MUNKIDORI_IDS, AA.ALAKAZAM_LINE, AA.IONO_LINE,
            AA.DRAGAPULT_LINE, AA.HOP_LINE, AA.STARMIE_LINE, AA.LUCARIO_LINE,
        ):
            if cid in line:
                tagged.add(cid)
    return tagged


def expected_archetype(name: str) -> str:
    n = name.lower()
    for key, arch in (
        ("grimmsnarl", "grimmsnarl"), ("crustle", "crustle"), ("alakazam", "alakazam"),
        ("dragapult", "dragapult"), ("iono", "iono"), ("starmie", "starmie"),
        ("lucario", "lucario"), ("kangaskhan", "crustle"), ("flg", "crustle"),
        ("dries", "grimmsnarl"), ("luca", "grimmsnarl"), ("liamk", "grimmsnarl"),
        ("majkel", "crustle"), ("james", "crustle"), ("abomasnow", "generic"),
        ("archaludon", "generic"),
    ):
        if key in n:
            return arch
    return "?"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None)
    ap.add_argument("--suites", nargs="*", default=None,
                    help="restrict to decks appearing in these suites")
    args = ap.parse_args()

    reg = load_registry()
    names = sorted(reg.get("opponents", {}))
    if args.suites:
        keep = set()
        for s in args.suites:
            keep |= set(reg.get("suites", {}).get(s, []))
        names = [n for n in names if n in keep]

    rows = []
    print(f"{'deck':34s} {'expect':11s} {'full-board':11s} {'solo-routes (turn-1 risk)'}")
    print("-" * 108)
    for name in names:
        path = resolve_deck_path(name, reg)
        if not path.exists():
            continue
        deck = load_deck(path)
        ids = deck_pokemon_ids(deck)
        full = route(ids)
        solo = {}
        for cid in sorted(ids):
            solo.setdefault(route({cid}), []).append(cid)
        exp = expected_archetype(name)

        # A misroute that costs us money: the deck's real archetype is one the
        # tomato delegate owns, but some reachable board routes to an excluded
        # matchup and hands the turn back to our scorer.
        hijack = {r for r in solo if r not in TOMATO_OWNED}
        if full not in TOMATO_OWNED:
            hijack.add(full)
        flag = ""
        if exp in ("grimmsnarl", "alakazam", "dragapult") and hijack:
            flag = "  <== MISROUTE " + ",".join(sorted(hijack))
        elif exp != "?" and full != exp and not (exp == "crustle" and full == "crustle"):
            flag = f"  (full-board says {full})"

        solo_s = " ".join(f"{r}:{v}" for r, v in sorted(solo.items()))
        print(f"{name:34s} {exp:11s} {full:11s} {solo_s}{flag}")
        rows.append({
            "deck": name, "expected": exp, "full_board_route": full,
            "solo_routes": {k: v for k, v in solo.items()},
            "tomato_owns_full_board": full in TOMATO_OWNED,
            "hijack_routes": sorted(hijack),
            "misroute": bool(flag.startswith("  <==")),
        })

    print("\nFLG_WALL_SHELL =", sorted(AA.FLG_WALL_SHELL))
    print("GRIMMSNARL_LINE =", sorted(AA.GRIMMSNARL_LINE), " MUNKIDORI =", sorted(AA.MUNKIDORI_IDS))
    bad = [r for r in rows if r["misroute"]]
    print(f"\nMISROUTED decks (delegated archetype reachable-routed to an excluded "
          f"matchup): {len(bad)} / {len(rows)}")
    for r in bad:
        print(f"  {r['deck']:34s} -> {r['hijack_routes']}")

    if args.json:
        out = ROOT / args.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
