"""Crustle lane diagnostic: why do we lose the flg / majkel wall matchups?

Round-1 established the gap is a *mean* deficit, not variance, and blamed
majkel's 4x Crushing Hammer from a deck diff alone. Three levers built on that
deck-diff theory (latch / hammer_prior / rhsoft) all came back NULL, so this
script stops guessing and reads the terminal state of every game instead.

Per game it records the seat, the RESULT log's `reason` (1 = prizes, 2 = deck
out, 3 = no Active, 4 = card effect), both prize counts, both deck counts and
the turn number, so a loss can be attributed to an actual mechanism.

  python scripts/crustle_loss_profile.py --games 300 \
      --opponents meta_crustle_majkel meta_crustle_flg

Writes recordings/metrics/crustle_loss_profile.json (+ a markdown summary).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval import harness  # noqa: E402
from eval.harness import (  # noqa: E402
    DEFAULT_ARCHALUDON_DECK,
    load_deck,
    load_registry,
    make_archaludon_brain,
    get_opponent_brain,
    opponent_meta,
    resolve_deck_path,
)

CRUSHING_HAMMER = 1120
RESULT_LOG = 23
ATTACK_LOG = 15
RAGING_HAMMER = 224
REASON_NAME = {
    1: "prizes",
    2: "deckout",
    3: "no_active",
    4: "card_effect",
}


def _pstate(cur, idx):
    return cur["players"][idx]


def _live(seq):
    return len([x for x in (seq or []) if x])


def run_match_traced(deck_a, deck_b, brain_a, brain_b, hero_seat, *, max_steps=None):
    """harness.run_match, but returns (outcome, trace) for the hero seat."""
    game = harness.game
    lib = harness.lib
    Battle = harness.Battle
    if max_steps is None:
        max_steps = harness.MAX_STEPS

    trace = {
        "hero_seat": hero_seat,
        "reason": None,
        "turn": None,
        "hero_prize": None,
        "opp_prize": None,
        "hero_deck": None,
        "opp_deck": None,
        "hero_bench": None,
        "opp_bench": None,
        "hero_in_play": None,
        "opp_in_play": None,
        "hero_hand": None,
        "opp_hammers": 0,
        "hero_rh_attacks": 0,
        "hero_attacks": 0,
    }

    obs, start = game.battle_start(deck_a, deck_b)
    if obs is None:
        raise RuntimeError(f"battle_start failed: err={getattr(start, 'errorType', '?')}")
    policies = (brain_a, brain_b)
    outcome = "unfinished"
    try:
        for _ in range(max_steps):
            cur = obs["current"]
            if cur is not None:
                # Snapshot every step: the terminal obs is never handed to a
                # brain, so this is the only place the end state is visible.
                hp = _pstate(cur, hero_seat)
                op = _pstate(cur, 1 - hero_seat)
                trace["turn"] = cur.get("turn")
                # prize entries are None while facedown -> count slots, not cards
                trace["hero_prize"] = len(hp.get("prize") or [])
                trace["opp_prize"] = len(op.get("prize") or [])
                trace["hero_deck"] = hp.get("deckCount")
                trace["opp_deck"] = op.get("deckCount")
                trace["hero_bench"] = _live(hp.get("bench"))
                trace["opp_bench"] = _live(op.get("bench"))
                trace["hero_in_play"] = _live(hp.get("active")) + _live(hp.get("bench"))
                trace["opp_in_play"] = _live(op.get("active")) + _live(op.get("bench"))
                trace["hero_hand"] = hp.get("handCount")
                trace["opp_hammers"] = sum(
                    1 for c in (op.get("discard") or []) if c and c.get("id") == CRUSHING_HAMMER
                )
            for log in obs.get("logs") or []:
                lt = log.get("type")
                if lt == ATTACK_LOG and log.get("playerIndex") == hero_seat:
                    trace["hero_attacks"] += 1
                    if log.get("attackId") == RAGING_HAMMER:
                        trace["hero_rh_attacks"] += 1
                elif lt == RESULT_LOG:
                    trace["reason"] = log.get("reason")
            if cur is not None and cur.get("result", -1) != -1:
                r = cur["result"]
                outcome = {0: "a", 1: "b", 2: "draw"}.get(r, "unfinished")
                break
            if obs["select"] is None:
                break
            p = lib.GetBattleData(Battle.battle_ptr).selectPlayer
            obs = game.battle_select(policies[p](obs))
    finally:
        game.battle_finish()
    return outcome, trace


def profile(opp_name, games, hero_deck, registry, pilot="as_registry"):
    meta = opponent_meta(opp_name, registry)
    deck_path = resolve_deck_path(opp_name, registry)
    if not deck_path.exists():
        raise SystemExit(f"missing opponent deck: {deck_path}")
    deck_o = load_deck(deck_path)
    if pilot == "rulecore":
        # Both crustle floor opponents are opponent_brain=random (intel, R3), so
        # the shipped instrument profiles losses against a pilot nobody plays.
        # Reuse intel's validated deck-agnostic pilot so the loss *composition*
        # can be read under a competent opponent. (crustle, 2026-07-31)
        if str(Path(__file__).resolve().parent) not in sys.path:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
        from intel_pilot_ab import make_rulecore_brain

        opp_brain, _stats = make_rulecore_brain(str(deck_path))
        brain_label = "rulecore"
    else:
        opp_brain, brain_label = get_opponent_brain(opp_name, registry=registry)
    hero_brain = make_archaludon_brain()

    rows = []
    for i in range(games):
        # Mirror harness.gate_vs_opponent seat swapping exactly.
        if i % 2 == 1:
            outcome, tr = run_match_traced(deck_o, hero_deck, opp_brain, hero_brain, 1)
            won = outcome == "b"
            lost = outcome == "a"
        else:
            outcome, tr = run_match_traced(hero_deck, deck_o, hero_brain, opp_brain, 0)
            won = outcome == "a"
            lost = outcome == "b"
        tr["outcome"] = "W" if won else ("L" if lost else outcome)
        tr["going_first"] = tr["hero_seat"] == 0
        rows.append(tr)
    return brain_label, rows


def summarize(opp_name, brain_label, rows):
    w = sum(1 for r in rows if r["outcome"] == "W")
    l = sum(1 for r in rows if r["outcome"] == "L")
    n = w + l
    out = {
        "opponent": opp_name,
        "brain": brain_label,
        "games": len(rows),
        "wins": w,
        "losses": l,
        "wr_pct": round(100.0 * w / n, 2) if n else None,
        "by_seat": {},
        "loss_reasons": {},
        "win_reasons": {},
    }
    for first in (True, False):
        sub = [r for r in rows if r["going_first"] is first]
        sw = sum(1 for r in sub if r["outcome"] == "W")
        sl = sum(1 for r in sub if r["outcome"] == "L")
        key = "first" if first else "second"
        out["by_seat"][key] = {
            "n": sw + sl,
            "wins": sw,
            "wr_pct": round(100.0 * sw / (sw + sl), 2) if (sw + sl) else None,
        }
    losses = [r for r in rows if r["outcome"] == "L"]
    wins = [r for r in rows if r["outcome"] == "W"]
    out["loss_reasons"] = {
        REASON_NAME.get(k, str(k)): v
        for k, v in Counter(r["reason"] for r in losses).most_common()
    }
    out["win_reasons"] = {
        REASON_NAME.get(k, str(k)): v
        for k, v in Counter(r["reason"] for r in wins).most_common()
    }
    def prof(sub):
        k = len(sub)
        return {
            "n": k,
            "opp_prize_left_hist": dict(sorted(Counter(r["opp_prize"] for r in sub).items())),
            "hero_prize_left_hist": dict(sorted(Counter(r["hero_prize"] for r in sub).items())),
            "hero_in_play_hist": dict(sorted(Counter(r["hero_in_play"] for r in sub).items())),
            "mean_turn": round(sum(r["turn"] or 0 for r in sub) / k, 1),
            "mean_hero_deck_left": round(sum(r["hero_deck"] or 0 for r in sub) / k, 1),
            "mean_opp_deck_left": round(sum(r["opp_deck"] or 0 for r in sub) / k, 1),
            "mean_hero_hand": round(sum(r["hero_hand"] or 0 for r in sub) / k, 1),
            "mean_opp_hammers": round(sum(r["opp_hammers"] for r in sub) / k, 2),
            "mean_hero_rh_attacks": round(sum(r["hero_rh_attacks"] for r in sub) / k, 2),
            "mean_hero_attacks": round(sum(r["hero_attacks"] for r in sub) / k, 2),
        }

    if losses:
        out["loss_profile"] = prof(losses)
        out["loss_profile_by_reason"] = {
            REASON_NAME.get(k, str(k)): prof([r for r in losses if r["reason"] == k])
            for k in sorted({r["reason"] for r in losses}, key=lambda x: (x is None, x))
        }
    if wins:
        out["win_profile"] = prof(wins)
    return out


def merge(paths):
    """Pool per-shard raw rows into one summary per opponent."""
    buckets: dict[str, list] = {}
    labels: dict[str, str] = {}
    for p in paths:
        blob = json.loads(Path(p).read_text(encoding="utf-8"))
        for opp in blob.get("opponents", []):
            buckets.setdefault(opp["opponent"], []).extend(opp.get("rows", []))
            labels[opp["opponent"]] = opp.get("brain", "")
    return {
        "shards": len(paths),
        "opponents": [
            summarize(name, labels.get(name, ""), rows) for name, rows in buckets.items()
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument(
        "--opponents",
        nargs="*",
        default=["meta_crustle_majkel", "meta_crustle_flg"],
    )
    ap.add_argument("--hero-deck", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--keep-rows", action="store_true", help="persist per-game rows (for --merge)")
    ap.add_argument("--merge", nargs="*", default=None, help="pool shard JSONs instead of playing")
    ap.add_argument(
        "--pilot",
        choices=["as_registry", "rulecore"],
        default="as_registry",
        help="as_registry = the shipped gate's pilot (random for both crustle "
             "decks); rulecore = intel's competent deck-agnostic pilot",
    )
    args = ap.parse_args()

    if args.merge:
        report = merge(args.merge)
        print(json.dumps(report, indent=2))
        if args.out:
            Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"\nwrote {args.out}")
        return 0

    registry = load_registry()
    hero_deck = load_deck(args.hero_deck or DEFAULT_ARCHALUDON_DECK)

    report = {"games_per_opp": args.games, "pilot": args.pilot, "opponents": []}
    for opp in args.opponents:
        brain_label, rows = profile(opp, args.games, hero_deck, registry, args.pilot)
        s = summarize(opp, brain_label, rows)
        if args.keep_rows:
            s["rows"] = rows
        report["opponents"].append(s)
        print(json.dumps({k: v for k, v in s.items() if k != "rows"}, indent=2))

    out = Path(args.out) if args.out else ROOT / "recordings" / "metrics" / "crustle_loss_profile.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
