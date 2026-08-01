"""INTEL: measure how much our gates are inflated by `opponent_brain: random`.

Every top-of-leaderboard archetype in the `meta_fast` / `dual` / `top6` suites
(Crustle-Iwapalace, Marnie-Grimmsnarl, Kangaskhan-Ogerpon) has **no** organizer
sample pilot, so `eval/harness.get_opponent_brain` falls back to a uniform-random
action picker (`agent.lucario_mcts_runtime.random_agent`). Those suites therefore
score our hero against decks nobody is actually piloting -- which is exactly the
proxy gating Ruling R2 forbids, and it is the leading candidate explanation for
local 93% vs live mu 648.

This script re-runs the same hero, same decks, same seat-swap, and only swaps the
**opponent pilot**:

  --pilot random    status quo (what the ship floors are measured against)
  --pilot rulecore  agent.rule_core.RuleCoreScorer, the deck-agnostic pilot the
                    harness already ships but never wires up for non-official decks

It is a diagnostic, not a gate: it does not touch any agent brain, ship floor, or
field/registry.json. Prints an `OVERALL (gated)  XX.X%` line so Shard-Gate.ps1 can
pool N independent shards.

  python scripts/intel_pilot_ab.py --suite top6 --pilot random   --games 30
  python scripts/intel_pilot_ab.py --suite top6 --pilot rulecore --games 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from cg.api import to_observation_class  # noqa: E402

from agent.lucario_mcts_runtime import random_agent  # noqa: E402
from eval.field_registry import (  # noqa: E402
    load_registry,
    opponent_meta,
    opponents_for_suite,
    resolve_deck_path,
)
from eval.harness import (  # noqa: E402
    DEFAULT_ARCHALUDON_DECK,
    _wilson_pct,
    get_opponent_brain,
    load_deck,
    make_archaludon_brain,
    official_archetype_for_opponent,
    run_match,
)


def make_rulecore_brain(deck_path: str) -> tuple:
    """Deck-agnostic competent pilot for an arbitrary 60-card list.

    RuleCoreScorer was written for our own archetypes; on an unseen deck
    (Grimmsnarl, Kangaskhan) it can emit an index outside the option mask, and
    `cg.game.battle_select` then raises IndexError and kills the shard. Ruling R7
    says legality comes from the mask, never from card text -- so validate here
    and fall back to a legal random pick. Returns (brain, illegal_counter) so the
    fallback rate is reported instead of silently inflating the arm.
    """
    from agent.agent import build_agent
    from agent.rule_core import RuleCoreScorer

    scorer = RuleCoreScorer(deck_path=deck_path)
    inner = build_agent(deck_path=deck_path, scorer=scorer).act
    stats = {"calls": 0, "fallback": 0}

    def brain(obs_dict: dict) -> list[int]:
        stats["calls"] += 1
        n_opt = len(to_observation_class(obs_dict).select.option)
        max_count = to_observation_class(obs_dict).select.maxCount
        try:
            sel = inner(obs_dict)
        except Exception:
            stats["fallback"] += 1
            return random_agent(obs_dict)
        ok = (
            isinstance(sel, list)
            and len(sel) == max_count
            and len(set(sel)) == len(sel)
            and all(isinstance(i, int) and 0 <= i < n_opt for i in sel)
        )
        if not ok:
            stats["fallback"] += 1
            return random_agent(obs_dict)
        return sel

    return brain, stats


def pilot_for(
    name: str, deck_path: str, deck_o: list[int], reg: dict, mode: str
) -> tuple | None:
    """Resolve the opponent pilot for one entry under the requested mode.

    `as_registry` / `upgrade` reproduce the *real* ship gate's opponent set: they
    keep the native sample pilot wherever `field/registry.json` says `native`, and
    only differ on the `random` entries. That makes them the honest A/B for mixed
    suites like `meta`, where forcing every opponent to one pilot would misstate
    arm A. Returns None for entries `gate_vs_opponent` silently skips (brain=native
    with no official archetype, e.g. meta_kangaskhan_james), so the gated
    denominator matches the gate. (intel, 2026-07-31)
    """
    kind = opponent_meta(name, reg).get("opponent_brain", "native")
    if mode in ("as_registry", "upgrade"):
        if kind == "native":
            if official_archetype_for_opponent(name, deck_o) is None:
                return None
            return get_opponent_brain(name, registry=reg)[0], None
        return pilot_for(
            name, deck_path, deck_o, reg,
            "random" if mode == "as_registry" else "rulecore",
        )
    if mode == "random":
        return random_agent, None
    return make_rulecore_brain(deck_path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite", default="top6")
    ap.add_argument("--opponents", nargs="*", default=None)
    ap.add_argument("--games", type=int, default=30, help="games per opponent")
    ap.add_argument(
        "--pilot",
        choices=["random", "rulecore", "as_registry", "upgrade"],
        default="random",
    )
    args = ap.parse_args()

    reg = load_registry()
    opp_names = args.opponents or opponents_for_suite(args.suite)
    hero_deck = load_deck(DEFAULT_ARCHALUDON_DECK)
    hero_brain = make_archaludon_brain(DEFAULT_ARCHALUDON_DECK)

    print(f"archaludon_agent vs {args.suite} decks, opponent pilot = {args.pilot} "
          f"({args.games} games/opp)\n")

    total_w = total_n = 0
    total_unfinished = 0
    for name in opp_names:
        deck_path = resolve_deck_path(name, reg)
        if not deck_path.exists():
            continue
        deck_o = load_deck(deck_path)
        resolved = pilot_for(name, str(deck_path), deck_o, reg, args.pilot)
        if resolved is None:
            print(f"  {name:32s} ({args.pilot:11s})  SKIPPED (gate returns None)")
            continue
        opp_brain, stats = resolved

        wins = losses = draws = unfinished = 0
        for i in range(args.games):
            # seat-swap on odd games, identical to eval.harness.gate_vs_opponent
            if i % 2 == 1:
                outcome = run_match(deck_o, hero_deck, opp_brain, hero_brain)
                hero_tag, opp_tag = "b", "a"
            else:
                outcome = run_match(hero_deck, deck_o, hero_brain, opp_brain)
                hero_tag, opp_tag = "a", "b"
            if outcome == hero_tag:
                wins += 1
            elif outcome == opp_tag:
                losses += 1
            elif outcome == "draw":
                draws += 1
            else:
                unfinished += 1

        n = wins + losses
        wr, lo, hi = _wilson_pct(wins, n)
        total_w += wins
        total_n += n
        total_unfinished += unfinished
        fb = ""
        if stats and stats["calls"]:
            fb = f"  illegal_fallback={100 * stats['fallback'] / stats['calls']:.1f}%"
        print(f"  {name:32s} ({args.pilot:11s}) {wr:6.1f}%  [{lo:5.1f}, {hi:5.1f}]  "
              f"W{wins}/L{losses}/D{draws}/U{unfinished}{fb}")

    wr, lo, hi = _wilson_pct(total_w, total_n)
    print(f"\n  OVERALL (gated) {' ' * 42} {wr:.1f}%  [{lo:5.1f}, {hi:5.1f}]  "
          f"n={total_n} decided, U{total_unfinished}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
