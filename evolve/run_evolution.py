#!/usr/bin/env python3
"""Evolutionary search over an agent's evolvable parameter blocks (AlphaEvolve-style).

  python evolve/run_evolution.py --target archaludon --generations 3 --population 6 --games 20 --report

  # Pull fresh daily Kaggle episodes first and rebuild field/weights.json, so the
  # weighted E[win] column reflects the current meta (needs Kaggle creds + egress
  # -- run on the dev machine, not this sandbox):
  python evolve/run_evolution.py --target archaludon --refresh-episodes 50 --report

Never edits agent/*.py. Writes a session report to eval/evolve_<target>_gen<N>.md;
promoting a winning candidate into the real agent file is a separate, manual step
(evolve/promote.py) that still goes through scripts/check_upload_eligible.py before
anything reaches Kaggle (R12).
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolve.evaluator import EvalResult, evaluate  # noqa: E402
from evolve.proposer import propose  # noqa: E402
from evolve.targets import TARGETS, base_params  # noqa: E402

EVAL_DIR = ROOT / "eval"


def _refresh_episode_weights(per_band: int) -> None:
    """Pull fresh daily episodes per mu band and rebuild field/weights.json (Phase C)."""
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "analyze_meta_by_mu_band.py"),
         "--download-per-band", str(per_band)],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_field_weights.py")],
        check=True,
    )


def run(
    target_name: str,
    *,
    generations: int,
    population: int,
    games_per_opp: int,
    suite: str,
    seed: int,
) -> list[EvalResult]:
    target = TARGETS[target_name]
    rng = random.Random(seed)

    baseline = evaluate(target, base_params(target), games_per_opp=games_per_opp, suite=suite)
    print(
        f"gen0 baseline: {baseline.wr_pct:.1f}% [{baseline.ci_low_pct:.1f}, {baseline.ci_high_pct:.1f}] "
        f"(n={baseline.games})"
    )

    survivors = [base_params(target)]
    keep_k = max(2, population // 3)
    history = [baseline]

    for gen in range(1, generations + 1):
        candidates = propose(target, survivors, population=population, rng=rng)
        results = [
            evaluate(target, c, games_per_opp=games_per_opp, suite=suite) for c in candidates
        ]
        results.sort(key=lambda r: r.wr_pct, reverse=True)
        history.extend(results)
        survivors = [r.params for r in results[:keep_k]]
        best = results[0]
        print(
            f"gen{gen}: best {best.wr_pct:.1f}% [{best.ci_low_pct:.1f}, {best.ci_high_pct:.1f}] "
            f"(n={best.games}) vs baseline {baseline.wr_pct:.1f}%"
        )

    return history


def write_report(target_name: str, generation: int, history: list[EvalResult]) -> Path:
    baseline, *rest = history
    rest_sorted = sorted(rest, key=lambda r: r.wr_pct, reverse=True)
    lines = [
        f"# evolve run -- {target_name} (gen{generation})",
        "",
        f"- Baseline: **{baseline.wr_pct:.1f}%** [{baseline.ci_low_pct:.1f}, {baseline.ci_high_pct:.1f}] "
        f"(n={baseline.games}, {baseline.hero_brain} x {baseline.hero_deck})",
        f"- Candidates evaluated: {len(rest)}",
        "",
        "## Top candidates",
        "",
        "| Rank | WR% | 95% CI | n | Weighted E[win]% | Beats baseline CI? | Params |",
        "|------|-----|--------|---|-------------------|---------------------|--------|",
    ]
    for i, r in enumerate(rest_sorted[:10], start=1):
        beats = "yes" if r.ci_low_pct > baseline.ci_high_pct else "no"
        weighted = f"{r.weighted_e_win_pct:.1f}" if r.weighted_e_win_pct is not None else "n/a"
        lines.append(
            f"| {i} | {r.wr_pct:.1f} | [{r.ci_low_pct:.1f}, {r.ci_high_pct:.1f}] | {r.games} | "
            f"{weighted} | {beats} | `{r.params}` |"
        )
    lines.append("")
    lines.append(
        "Ranking above is by raw win-rate + Wilson CI only (Ruling R2/R8) -- weighted E[win] "
        "(field/weights.json, refresh via `--refresh-episodes`) is informational context, not a "
        "selection criterion, per AGENTS.md (\"weighted gates: filter only\") and Ruling R11 "
        "(\"rules before mixture\")."
    )
    lines.append("")
    lines.append(
        "Promotion is manual (`evolve/promote.py`) -- only promote a row whose CI does not "
        "overlap the baseline's, then re-run the full local gate + "
        "`scripts/check_upload_eligible.py` before any Kaggle upload (R12)."
    )
    path = EVAL_DIR / f"evolve_{target_name}_gen{generation}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", choices=sorted(TARGETS), required=True)
    ap.add_argument("--generations", type=int, default=3)
    ap.add_argument("--population", type=int, default=6)
    ap.add_argument("--games", type=int, default=20, dest="games_per_opp")
    ap.add_argument("--suite", default="full")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--report", action="store_true")
    ap.add_argument(
        "--refresh-episodes",
        type=int,
        default=0,
        metavar="N",
        help="Pull N fresh episodes/mu-band and rebuild field/weights.json before running "
        "(needs Kaggle creds + egress -- not available in this sandbox).",
    )
    args = ap.parse_args()

    if args.refresh_episodes:
        _refresh_episode_weights(args.refresh_episodes)

    history = run(
        args.target,
        generations=args.generations,
        population=args.population,
        games_per_opp=args.games_per_opp,
        suite=args.suite,
        seed=args.seed,
    )
    if args.report:
        path = write_report(args.target, args.generations, history)
        print(f"\nReport: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
