"""Small-n A/B for Lucario MCTS *inference* knobs (frozen checkpoint).

Does not train. Core loop unchanged — only SEARCH_COUNT / DETERMINIZATIONS / PRIOR_BLEND / PUCT.

  python scripts/exp_mcts_infer_ab.py --games 32 --suite core \\
    --model rl_mcts_field/lucarioex_v2/model_best.pth \\
    --variants sc12 sc20 sc20_det2 sc20_prior02
"""

from __future__ import annotations

import argparse
import json
import os
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
    run_suite,
)

VARIANT_SPECS: dict[str, dict] = {
    "sc12": {
        "env": {
            "LUC_SUBMIT_SEARCH_COUNT": "12",
            "LUC_DETERMINIZATIONS": "1",
            "LUC_PRIOR_BLEND": "0",
        },
        "desc": "SEARCH_COUNT=12 (old submit)",
    },
    "sc20": {
        "env": {
            "LUC_SUBMIT_SEARCH_COUNT": "20",
            "LUC_DETERMINIZATIONS": "1",
            "LUC_PRIOR_BLEND": "0",
        },
        "desc": "SEARCH_COUNT=20 (train-aligned)",
    },
    "sc24": {
        "env": {
            "LUC_SUBMIT_SEARCH_COUNT": "24",
            "LUC_DETERMINIZATIONS": "1",
            "LUC_PRIOR_BLEND": "0",
        },
        "desc": "SEARCH_COUNT=24",
    },
    "sc20_det2": {
        "env": {
            "LUC_SUBMIT_SEARCH_COUNT": "20",
            "LUC_DETERMINIZATIONS": "2",
            "LUC_PRIOR_BLEND": "0",
        },
        "desc": "sc20 + 2 determinizations (IS-MCTS-lite)",
    },
    "sc20_prior02": {
        "env": {
            "LUC_SUBMIT_SEARCH_COUNT": "20",
            "LUC_DETERMINIZATIONS": "1",
            "LUC_PRIOR_BLEND": "0.2",
        },
        "desc": "sc20 + LucarioScorer prior blend 0.2",
    },
    "sc16_det2_prior02": {
        "env": {
            "LUC_SUBMIT_SEARCH_COUNT": "16",
            "LUC_DETERMINIZATIONS": "2",
            "LUC_PRIOR_BLEND": "0.2",
        },
        "desc": "balanced: 16 sims × 2 det × prior 0.2",
    },
}


def _apply_env(env: dict[str, str]) -> dict[str, str | None]:
    prev: dict[str, str | None] = {}
    for k, v in env.items():
        prev[k] = os.environ.get(k)
        os.environ[k] = v
    return prev


def _restore_env(prev: dict[str, str | None]) -> None:
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _make_mcts_brain(deck: str, model: str, meta: str | None):
    from agent.agent import build_agent
    from agent.lucario_mcts_policy import LucarioMCTSScorer

    scorer = LucarioMCTSScorer(
        deck_path=deck,
        model_path=model,
        meta_path=meta,
    )
    if not scorer._ready:
        raise RuntimeError(f"MCTS model failed to load (ready=False): {model}")
    return build_agent(deck_path=deck, scorer=scorer).act


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=32)
    ap.add_argument("--suite", choices=["core", "full"], default="core")
    ap.add_argument("--opponents", nargs="*", default=None)
    ap.add_argument("--hero-deck", default=str(DEFAULT_LUCARIO_DECK))
    ap.add_argument(
        "--model",
        default="rl_mcts_field/lucarioex_v2/model_best.pth",
    )
    ap.add_argument("--meta", default="")
    ap.add_argument(
        "--variants",
        nargs="+",
        default=["sc12", "sc20", "sc20_prior02"],
        choices=sorted(VARIANT_SPECS.keys()),
    )
    ap.add_argument("--tag", default="")
    args = ap.parse_args(argv)

    model_path = Path(args.model)
    if not model_path.is_absolute():
        model_path = ROOT / model_path
    if not model_path.is_file():
        print(f"Model not found: {model_path}", file=sys.stderr)
        return 2
    meta_path = args.meta or None
    if meta_path and not Path(meta_path).is_absolute():
        meta_path = str(ROOT / meta_path)

    opponents = args.opponents or opponents_for_suite(args.suite)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = f"_{args.tag}" if args.tag else ""
    out_md = ROOT / "eval" / f"exp_mcts_infer{tag}_{stamp}.md"
    out_json = ROOT / "report" / "exp_search" / f"exp_mcts_infer{tag}_{stamp}.json"

    print(f"Model={model_path}")
    print(f"Suite={args.suite} games/opp={args.games} opps={opponents}")
    rows = []
    for name in args.variants:
        spec = VARIANT_SPECS[name]
        print(f"\n=== {name}: {spec['desc']} ===", flush=True)
        prev = _apply_env(spec["env"])
        t0 = time.time()
        try:
            clear_caches()
            # Fresh scorer so env knobs re-applied in _load_model.
            brain = _make_mcts_brain(args.hero_deck, str(model_path), meta_path)
            result = run_suite(
                brain,
                args.hero_deck,
                opponents,
                games_per_opp=args.games,
                hero_brain_label=f"mcts:{name}",
            )
        finally:
            _restore_env(prev)
        elapsed = time.time() - t0
        row = {
            "variant": name,
            "desc": spec["desc"],
            "env": spec["env"],
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
        rows.append(row)
        print(
            f"  {row['overall_wr_pct']:.1f}% "
            f"[{row['overall_ci'][0]:.1f}, {row['overall_ci'][1]:.1f}] "
            f"({row['overall_wins']}/{row['overall_games']}) {row['elapsed_s']}s",
            flush=True,
        )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# MCTS inference A/B",
        "",
        f"- Model: `{model_path}`",
        f"- Games/opp: {args.games}",
        f"- Suite: {args.suite}",
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
    if len(rows) >= 2:
        base = rows[0]
        lines += ["", "## Δ vs first", "", "| Variant | ΔWR pp |", "|---------|--------|"]
        for r in rows[1:]:
            d = r["overall_wr_pct"] - base["overall_wr_pct"]
            lines.append(f"| {r['variant']} − {base['variant']} | {d:+.1f} |")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReport: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
