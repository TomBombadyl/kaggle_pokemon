"""Small-n A/B for SearchScorer / Lucario / Crustle hybrid (n=32–48).

Does NOT retrain MCTS. Measures local field gate only — ladder is truth.

Examples:

  # Baseline SearchScorer @ 200ms vs 400ms budget, n=40/opp, core suite
  python scripts/exp_search_hybrid_ab.py --games 40 --suite core --variants budget200 budget400

  # LucarioSearch guard-k and budget
  python scripts/exp_search_hybrid_ab.py --games 32 --suite core \\
      --variants lucario200 lucario400 lucario400_k3

  # Crustle mainline: RuleCore floor vs CrustleSearch @ 200/400ms
  python scripts/exp_search_hybrid_ab.py --games 32 --suite core \\
      --hero-deck agent_decks/crustle_MissingNo_rank1.csv \\
      --variants crustle_rules crustle200 crustle400 --tag crustle_s0

  # Heuristic blend probe
  python scripts/exp_search_hybrid_ab.py --games 32 --suite core \\
      --variants budget400 budget400_blend015

Reports: eval/exp_search_hybrid_*.md + JSON under report/exp_search/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.field_registry import opponents_for_suite  # noqa: E402
from eval.harness import (  # noqa: E402
    DEFAULT_LUCARIO_DECK,
    clear_caches,
    make_lucario_brain,
    run_suite,
)

# Named variants → constructor knobs (no importlib.reload).
# Keep defaults = current production so A is the bar.
VARIANT_SPECS: dict[str, dict] = {
    "rules": {
        "brain": "lucario_rules",
        "kwargs": {},
        "desc": "LucarioScorer only (no cg search)",
    },
    "budget200": {
        "brain": "search",
        "kwargs": {"budget_ms": 200.0, "heuristic_blend": 0.0},
        "desc": "SearchScorer budget=200ms (prod baseline)",
    },
    "budget400": {
        "brain": "search",
        "kwargs": {"budget_ms": 400.0, "heuristic_blend": 0.0},
        "desc": "SearchScorer budget=400ms",
    },
    "budget600": {
        "brain": "search",
        "kwargs": {"budget_ms": 600.0, "heuristic_blend": 0.0},
        "desc": "SearchScorer budget=600ms",
    },
    "budget400_blend015": {
        "brain": "search",
        "kwargs": {"budget_ms": 400.0, "heuristic_blend": 0.15},
        "desc": "SearchScorer 400ms + heuristic blend 0.15",
    },
    "lucario200": {
        "brain": "lucario_search",
        "kwargs": {"budget_ms": 200.0, "guard_top_k": 2, "heuristic_blend": 0.0},
        "desc": "LucarioSearchScorer 200ms guard_k=2",
    },
    "lucario400": {
        "brain": "lucario_search",
        "kwargs": {"budget_ms": 400.0, "guard_top_k": 2, "heuristic_blend": 0.0},
        "desc": "LucarioSearchScorer 400ms guard_k=2",
    },
    "lucario400_k3": {
        "brain": "lucario_search",
        "kwargs": {"budget_ms": 400.0, "guard_top_k": 3, "heuristic_blend": 0.0},
        "desc": "LucarioSearchScorer 400ms guard_k=3 (looser)",
    },
    "lucario400_blend02": {
        "brain": "lucario_search",
        "kwargs": {"budget_ms": 400.0, "guard_top_k": 2, "heuristic_blend": 0.2},
        "desc": "LucarioSearch 400ms + Lucario-rank blend 0.2",
    },
    # --- Crustle MissingNo mainline (RuleCore floor + decision prior guard) ---
    "crustle_rules": {
        "brain": "rulecore",
        "kwargs": {},
        "desc": "RuleCoreScorer only (Crustle decision prior, no cg search)",
    },
    "crustle200": {
        "brain": "crustle_search",
        "kwargs": {"budget_ms": 200.0, "guard_top_k": 2, "heuristic_blend": 0.0},
        "desc": "CrustleSearchScorer 200ms guard_k=2",
    },
    "crustle400": {
        "brain": "crustle_search",
        "kwargs": {"budget_ms": 400.0, "guard_top_k": 2, "heuristic_blend": 0.0},
        "desc": "CrustleSearchScorer 400ms guard_k=2",
    },
    "crustle400_k3": {
        "brain": "crustle_search",
        "kwargs": {"budget_ms": 400.0, "guard_top_k": 3, "heuristic_blend": 0.0},
        "desc": "CrustleSearchScorer 400ms guard_k=3 (looser)",
    },
    "crustle400_blend015": {
        "brain": "crustle_search",
        "kwargs": {"budget_ms": 400.0, "guard_top_k": 2, "heuristic_blend": 0.15},
        "desc": "CrustleSearch 400ms + decision-prior blend 0.15",
    },
}


def _make_brain(kind: str, deck_path: str, kwargs: dict):
    if kind == "lucario_rules":
        return make_lucario_brain(deck_path)
    if kind == "search":
        from agent.agent import build_agent
        from agent.search_policy import SearchScorer

        return build_agent(
            deck_path=deck_path,
            scorer=SearchScorer(deck_path=deck_path, **kwargs),
        ).act
    if kind == "lucario_search":
        from agent.agent import build_agent
        from agent.search_policy import LucarioSearchScorer

        return build_agent(
            deck_path=deck_path,
            scorer=LucarioSearchScorer(deck_path=deck_path, **kwargs),
        ).act
    if kind == "rulecore":
        from agent.agent import build_agent
        from agent.rule_core import RuleCoreScorer

        return build_agent(
            deck_path=deck_path,
            scorer=RuleCoreScorer(deck_path=deck_path),
        ).act
    if kind == "crustle_search":
        from agent.agent import build_agent
        from agent.search_policy import CrustleSearchScorer

        return build_agent(
            deck_path=deck_path,
            scorer=CrustleSearchScorer(deck_path=deck_path, **kwargs),
        ).act
    raise ValueError(f"unknown brain kind: {kind}")


def run_variant(
    name: str,
    *,
    games: int,
    suite: str,
    opponents: list[str],
    hero_deck: str,
) -> dict:
    spec = VARIANT_SPECS[name]
    t0 = time.time()
    clear_caches()
    brain = _make_brain(spec["brain"], hero_deck, spec.get("kwargs") or {})
    result = run_suite(
        brain,
        hero_deck,
        opponents,
        games_per_opp=games,
        hero_brain_label=f"{name}:{spec['brain']}",
    )
    elapsed = time.time() - t0
    return {
        "variant": name,
        "desc": spec["desc"],
        "kwargs": spec.get("kwargs") or {},
        "brain": spec["brain"],
        "games_per_opp": games,
        "suite": suite,
        "opponents": opponents,
        "overall_wr_pct": result.overall_wr_pct,
        "overall_ci": [result.overall_ci_low_pct, result.overall_ci_high_pct],
        "overall_wins": result.overall_wins,
        "overall_games": result.overall_games,
        "matchups": [
            {
                "opponent": m.opponent,
                "wr_pct": m.wr_pct,
                "wins": m.wins,
                "losses": m.losses,
                "draws": m.draws,
            }
            for m in result.matchups
        ],
        "elapsed_s": round(elapsed, 1),
    }


def write_report(rows: list[dict], out_md: Path, out_json: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# Search hybrid A/B experiment",
        "",
        f"- UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Variants: {', '.join(r['variant'] for r in rows)}",
        "",
        "## Overall",
        "",
        "| Variant | WR% | 95% CI | W/G | Elapsed | Desc |",
        "|---------|-----|--------|-----|---------|------|",
    ]
    for r in rows:
        ci = r["overall_ci"]
        lines.append(
            f"| {r['variant']} | **{r['overall_wr_pct']:.1f}** | "
            f"[{ci[0]:.1f}, {ci[1]:.1f}] | "
            f"{r['overall_wins']}/{r['overall_games']} | "
            f"{r['elapsed_s']}s | {r['desc']} |"
        )
    lines += ["", "## Per-matchup", ""]
    for r in rows:
        lines.append(f"### {r['variant']}")
        lines.append("")
        lines.append("| Opponent | WR% | W-L-D |")
        lines.append("|----------|-----|-------|")
        for m in r["matchups"]:
            lines.append(
                f"| {m['opponent']} | {m['wr_pct']:.1f} | "
                f"{m['wins']}-{m['losses']}-{m['draws']} |"
            )
        lines.append("")
    # Delta vs first variant
    if len(rows) >= 2:
        base = rows[0]
        lines += ["## Deltas vs first variant", ""]
        lines.append("| Variant | ΔWR pp |")
        lines.append("|---------|--------|")
        for r in rows[1:]:
            d = r["overall_wr_pct"] - base["overall_wr_pct"]
            lines.append(f"| {r['variant']} − {base['variant']} | {d:+.1f} |")
        lines.append("")
        lines.append(
            "Note: local gate WR does **not** sort ladder μ (RULINGS). "
            "Use n≥32 as filter; promote only if ΔWR ≥ +2pp with non-overlapping CI or SPRT."
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=40, help="Games per opponent (32–48 recommended)")
    ap.add_argument("--suite", choices=["core", "full", "alakazam"], default="core")
    ap.add_argument("--opponents", nargs="*", default=None)
    ap.add_argument("--hero-deck", default=str(DEFAULT_LUCARIO_DECK))
    ap.add_argument(
        "--variants",
        nargs="+",
        default=["budget200", "budget400", "lucario400"],
        choices=sorted(VARIANT_SPECS.keys()),
    )
    ap.add_argument(
        "--tag",
        default="",
        help="Optional suffix for report filenames",
    )
    args = ap.parse_args(argv)

    opponents = args.opponents or opponents_for_suite(args.suite)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = f"_{args.tag}" if args.tag else ""
    out_md = ROOT / "eval" / f"exp_search_hybrid{tag}_{stamp}.md"
    out_json = ROOT / "report" / "exp_search" / f"exp_search_hybrid{tag}_{stamp}.json"

    print(f"Suite={args.suite} games/opp={args.games} opponents={opponents}")
    print(f"Variants: {args.variants}")
    rows = []
    for name in args.variants:
        print(f"\n=== {name}: {VARIANT_SPECS[name]['desc']} ===", flush=True)
        row = run_variant(
            name,
            games=args.games,
            suite=args.suite,
            opponents=opponents,
            hero_deck=args.hero_deck,
        )
        rows.append(row)
        print(
            f"  overall {row['overall_wr_pct']:.1f}% "
            f"[{row['overall_ci'][0]:.1f}, {row['overall_ci'][1]:.1f}] "
            f"({row['overall_wins']}/{row['overall_games']}) "
            f"in {row['elapsed_s']}s",
            flush=True,
        )

    write_report(rows, out_md, out_json)
    print(f"\nReport: {out_md}")
    print(f"JSON:   {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
