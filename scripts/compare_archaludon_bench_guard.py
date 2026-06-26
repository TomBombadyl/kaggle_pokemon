"""A/B compare Archaludon rules (agent scoring) vs + packaged bench guard.

  python scripts/compare_archaludon_bench_guard.py --games 50 --suite full --report

Guard off still uses in-agent ``_empty_bench_basic_score`` (R7b). This compares
``ARCHALUDON_BENCH_GUARD=0`` vs ``1`` on the outer wrapper only.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "data" / "sim" / "sample_submission"
for p in (ENGINE, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from cg import game  # noqa: E402
from eval.field_registry import load_registry, opponents_for_suite, resolve_deck_path  # noqa: E402
from eval.harness import (  # noqa: E402
    DEFAULT_ARCHALUDON_DECK,
    MAX_STEPS,
    _select_player,
    get_opponent_brain,
    load_deck,
    make_archaludon_brain,
)
from scripts.episode_stats import infer_result_reason  # noqa: E402


def _play_series(hero_brain, hero_deck: list[int], opp_name: str, games: int) -> dict:
    opp_brain, _ = get_opponent_brain(opp_name)
    reg = load_registry()
    deck_o = load_deck(resolve_deck_path(opp_name, reg))

    wins = losses = draws = unfinished = 0
    loss_reasons: Counter[str] = Counter()

    for i in range(games):
        seat_swap = i % 2 == 1
        if seat_swap:
            deck_a, deck_b = deck_o, hero_deck
            policies = (opp_brain, hero_brain)
            hero_seat = 1
        else:
            deck_a, deck_b = hero_deck, deck_o
            policies = (hero_brain, opp_brain)
            hero_seat = 0

        obs, _ = game.battle_start(deck_a, deck_b)
        if obs is None:
            unfinished += 1
            continue
        try:
            for _ in range(MAX_STEPS):
                cur = obs["current"]
                if cur is not None and cur.get("result", -1) != -1:
                    r = int(cur["result"])
                    if r == hero_seat:
                        wins += 1
                    elif r == 2:
                        draws += 1
                    else:
                        losses += 1
                        players = cur.get("players") or []
                        loss_reasons[infer_result_reason(r, players)] += 1
                    break
                if obs["select"] is None:
                    break
                p = _select_player()
                obs = game.battle_select(policies[p](obs))
            else:
                unfinished += 1
        finally:
            game.battle_finish()

    n = wins + losses
    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "unfinished": unfinished,
        "wr_pct": 100.0 * wins / n if n else 0.0,
        "loss_reasons": dict(loss_reasons),
        "no_active": loss_reasons.get("no_active", 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=50)
    ap.add_argument("--suite", choices=["core", "full", "lucario", "alakazam", "starmie"], default="full")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    opponents = opponents_for_suite(args.suite)
    hero_deck = load_deck(DEFAULT_ARCHALUDON_DECK)
    brain_off = make_archaludon_brain(bench_guard=False)
    brain_on = make_archaludon_brain(bench_guard=True)

    lines = [
        "# Archaludon: agent scoring vs + packaged bench guard",
        "",
        f"- Games per opponent per variant: **{args.games}**",
        f"- Suite: `{args.suite}`",
        f"- Hero deck: `{DEFAULT_ARCHALUDON_DECK}`",
        f"- Both variants include in-agent `_empty_bench_basic_score` (R7b)",
        "",
        "| Opponent | WR% (guard off) | WR% (+guard) | Δpp | no_active (off) | no_active (on) |",
        "|----------|----------------:|-------------:|----:|----------------:|---------------:|",
    ]

    w_off = w_on = 0
    total_off = total_on = 0
    na_off = na_on = 0

    print(f"Archaludon A/B — {args.games} games/opp — suite={args.suite}\n")
    for opp in opponents:
        off = _play_series(brain_off, hero_deck, opp, args.games)
        on = _play_series(brain_on, hero_deck, opp, args.games)
        delta = on["wr_pct"] - off["wr_pct"]
        total_off += off["wins"] + off["losses"]
        total_on += on["wins"] + on["losses"]
        w_off += off["wins"]
        w_on += on["wins"]
        na_off += off["no_active"]
        na_on += on["no_active"]
        print(
            f"  {opp:32s}  off={off['wr_pct']:5.1f}%  on={on['wr_pct']:5.1f}%  "
            f"d={delta:+5.1f}pp  no_active {off['no_active']}->{on['no_active']}"
        )
        lines.append(
            f"| {opp} | {off['wr_pct']:.1f} | {on['wr_pct']:.1f} | {delta:+.1f} | "
            f"{off['no_active']} | {on['no_active']} |"
        )

    overall_off = 100.0 * w_off / total_off if total_off else 0
    overall_on = 100.0 * w_on / total_on if total_on else 0
    lines.extend(
        [
            "",
            "## Overall",
            "",
            f"- Guard off (agent only): **{overall_off:.1f}%** (n={total_off}), no_active: **{na_off}**",
            f"- + packaged guard: **{overall_on:.1f}%** (n={total_on}), no_active: **{na_on}**",
            f"- Δ: **{overall_on - overall_off:+.1f} pp** vs paired A/B",
            "",
            "**Ladder truth:** ref 54083197 @ 1224.2 μ. Probe only with material delta + upload gate.",
        ]
    )
    print(f"\nOVERALL  off={overall_off:.1f}%  on={overall_on:.1f}%  no_active {na_off}->{na_on}")

    if args.report:
        out = ROOT / "eval" / "archaludon_bench_guard_ab.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nReport: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
