#!/usr/bin/env python3
"""Robust deck search CLI (PSRO-lite, maximin/CVaR objective).

Finds a 60-card deck that maximises win rate vs the whole opponent field.
Self-contained: writes to report/robust_deck_rl/ and never touches the
existing deck campaign checkpoint.

    python scripts/robust_deck_search.py --generations 20 --population 12 --games 6
    python scripts/robust_deck_search.py --smoke      # tiny CPU sanity run

Outputs:
    report/robust_deck_rl/best_deck.csv   <- the robust deck
    report/robust_deck_rl/metrics.csv     <- per-gen robust/mean/maximin + holdout
    report/robust_deck_rl/state.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--generations", type=int, default=20)
    p.add_argument("--population", type=int, default=12)
    p.add_argument("--games", type=int, default=6, help="games per candidate-vs-opponent")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--scorer", default="heuristic", choices=("heuristic", "search", "learned"))
    p.add_argument("--alpha", type=float, default=0.5, help="0=pure worst-case, 1=pure mean")
    p.add_argument("--cvar-q", type=float, default=0.3, help="worst-fraction tail for CVaR")
    p.add_argument("--holdout-frac", type=float, default=0.25)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-meta-solver", action="store_true", help="disable adversarial reweighting")
    p.add_argument("--surrogate", action="store_true", help="GPU win-rate surrogate prunes confident matchups")
    p.add_argument("--surrogate-margin", type=float, default=0.2, help="skip-sim if |p-0.5| exceeds this")
    p.add_argument("--no-mined", action="store_true", help="ignore report/deck_rl/mined_decks/")
    p.add_argument("--out-dir", default=None, help="Output directory for this run")
    p.add_argument("--smoke", action="store_true", help="tiny run for a quick sanity check")
    args = p.parse_args(argv)

    from rl.robust_search import run_robust_search

    if args.smoke:
        args.generations, args.population, args.games, args.workers = 1, 4, 2, 2

    kwargs = {}
    if args.out_dir:
        kwargs["out_dir"] = Path(args.out_dir)
    result = run_robust_search(
        generations=args.generations, population=args.population, games_eval=args.games,
        workers=args.workers, scorer=args.scorer, alpha=args.alpha, cvar_q=args.cvar_q,
        holdout_frac=args.holdout_frac, seed=args.seed,
        use_meta_solver=not args.no_meta_solver, include_mined=not args.no_mined,
        use_surrogate=args.surrogate, surrogate_margin=args.surrogate_margin,
        **kwargs,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
