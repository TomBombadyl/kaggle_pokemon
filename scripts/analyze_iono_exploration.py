#!/usr/bin/env python3
"""Measure how much Archaludon's Iono decisions are actually worth.

Why this exists
---------------
Round 1 of the gputrain lane trained an option-conditioned Q head on
``episodes/iono_bc_v2`` and rejected it: chosen-action-only logs observe the
outcome only at ``a = pi(s)``, so nothing in the data identifies the value of
the options the rule agent never takes. Any re-ranker fitted on that data is
extrapolating.

``collect_iono_decisions.py --explore-eps E`` fixes the identification problem
by *deviating*: on a fraction E of single-selection decisions it plays a
uniformly random legal option instead of the rule pick. Because E is fixed per
run and the deviation coin is independent of the state, comparing whole runs at
different E is a clean randomized experiment.

This script reads the resulting runs and answers two questions:

1. **Dose-response** -- P(win) as a function of E. The slope says how much a
   single random deviation costs, i.e. how much signal the option dimension
   carries at all. A flat curve would mean Iono decisions barely matter and no
   learned re-ranker can help; a steep one means the option axis is where the
   matchup is won or lost.

2. **Where the rule agent is not optimal** -- bucketed by the option type the
   rule agent wanted, the win rate of games whose *first* deviation happened in
   that bucket. Buckets where deviating is cheap (or free) are buckets where
   the rule pick is not clearly the best option, and are the places a learned
   ranker has room to beat it.

Usage
-----
  python scripts/analyze_iono_exploration.py --data episodes/iono_bc_explore
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Mirrors collect_iono_decisions.OPTION_FEATURES: the one-hot block of
# OptionType comes first, then card_id / is_pokemon / is_energy / targets_opp.
N_TAIL_FEATURES = 4


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Point estimate plus Wilson score interval, in percent."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * p, 100 * max(0.0, centre - half), 100 * min(1.0, centre + half)


def binom_se(k: int, n: int) -> float:
    if n == 0:
        return 0.0
    p = k / n
    return 100 * math.sqrt(max(p * (1 - p), 1e-12) / n)


def option_type_names() -> list[str]:
    try:
        sys.path.insert(0, str(ROOT / "data" / "sim" / "sample_submission"))
        from cg.api import OptionType  # noqa: PLC0415
        return [t.name for t in OptionType]
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="episodes/iono_bc_explore")
    ap.add_argument("--json-out", default="recordings/metrics/iono_exploration.json")
    ap.add_argument("--min-bucket", type=int, default=40,
                    help="Suppress first-deviation buckets smaller than this")
    args = ap.parse_args()

    data_dir = ROOT / args.data
    files = sorted(data_dir.glob("iono_decisions_*.jsonl"))
    if not files:
        print(f"ERROR: no jsonl under {data_dir}", file=sys.stderr)
        return 1

    # eps -> [wins, decided_games, other, deviations, eligible_games]
    arms: dict[float, dict[str, int]] = defaultdict(
        lambda: {"w": 0, "n": 0, "other": 0, "dev": 0, "games": 0, "dec": 0})
    # (eps, option_type_index) -> [wins, n] for games whose FIRST deviation
    # replaced a rule pick of that option type
    first_dev: dict[tuple[float, int], list[int]] = defaultdict(lambda: [0, 0])
    # control games (zero deviations) inside a treated arm, for reference
    within: dict[float, dict[str, list[int]]] = defaultdict(
        lambda: {"dev": [0, 0], "nodev": [0, 0]})
    n_types = 0

    for fp in files:
        with fp.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    g = json.loads(line)
                except json.JSONDecodeError:
                    continue
                eps = float(g.get("explore_eps", 0.0) or 0.0)
                a = arms[eps]
                a["games"] += 1
                a["dec"] += int(g.get("n_decisions", 0))
                label = g.get("label", -1)
                won = label == 1
                if label in (0, 1):
                    a["n"] += 1
                    a["w"] += int(won)
                else:
                    a["other"] += 1
                    continue

                decisions = g.get("decisions") or []
                ndev = 0
                first_type = None
                for d in decisions:
                    if not d.get("e"):
                        continue
                    ndev += 1
                    if first_type is None:
                        rp = d.get("rp") or []
                        opts = d.get("o") or []
                        if rp and 0 <= rp[0] < len(opts):
                            vec = opts[rp[0]]
                            head = vec[:-N_TAIL_FEATURES]
                            if head:
                                first_type = max(range(len(head)),
                                                 key=lambda i: head[i])
                a["dev"] += ndev
                if ndev:
                    within[eps]["dev"][0] += int(won)
                    within[eps]["dev"][1] += 1
                    if first_type is not None:
                        n_types = max(n_types, first_type + 1)
                        b = first_dev[(eps, first_type)]
                        b[0] += int(won)
                        b[1] += 1
                else:
                    within[eps]["nodev"][0] += int(won)
                    within[eps]["nodev"][1] += 1

    if not arms:
        print("ERROR: no games parsed", file=sys.stderr)
        return 1

    tnames = option_type_names()

    print("=" * 78)
    print("IONO DECISION SENSITIVITY -- dose-response on random-deviation rate")
    print("=" * 78)
    print(f"{'eps':>6} {'games':>7} {'decided':>8} {'other':>6} {'devs':>7} "
          f"{'dev/game':>9} {'win%':>7} {'se':>5}  ci95")
    ordered = sorted(arms)
    for eps in ordered:
        a = arms[eps]
        wr, lo, hi = wilson(a["w"], a["n"])
        se = binom_se(a["w"], a["n"])
        dpg = a["dev"] / a["games"] if a["games"] else 0.0
        print(f"{eps:>6g} {a['games']:>7} {a['n']:>8} {a['other']:>6} "
              f"{a['dev']:>7} {dpg:>9.2f} {wr:>7.2f} {se:>5.2f}  "
              f"[{lo:.2f},{hi:.2f}]")

    base = arms.get(0.0)
    results = {"arms": {}, "first_deviation": {}, "per_deviation": None}
    for eps in ordered:
        a = arms[eps]
        wr, lo, hi = wilson(a["w"], a["n"])
        results["arms"][f"{eps:g}"] = {
            "games": a["games"], "decided": a["n"], "wins": a["w"],
            "other": a["other"], "deviations": a["dev"],
            "dev_per_game": round(a["dev"] / a["games"], 4) if a["games"] else 0,
            "decisions": a["dec"],
            "win_pct": round(wr, 2), "se": round(binom_se(a["w"], a["n"]), 3),
            "ci95": [round(lo, 2), round(hi, 2)],
        }

    if base and base["n"]:
        p0 = base["w"] / base["n"]
        se0 = binom_se(base["w"], base["n"])
        print()
        print("vs eps=0 control (2*se_diff is the KEEP/REJECT bar):")
        odds_ratios = []
        for eps in ordered:
            if eps == 0.0:
                continue
            a = arms[eps]
            if not a["n"]:
                continue
            p = a["w"] / a["n"]
            se = binom_se(a["w"], a["n"])
            diff = 100 * (p - p0)
            sed = math.sqrt(se * se + se0 * se0)
            verdict = "SIGNIFICANT" if abs(diff) >= 2 * sed else "ns"
            dpg = a["dev"] / a["games"] if a["games"] else 0.0
            # per-deviation win-odds multiplier, assuming independent hits
            r = None
            if 0 < p < 1 and 0 < p0 < 1 and dpg > 0:
                o, o0 = p / (1 - p), p0 / (1 - p0)
                r = (o / o0) ** (1.0 / dpg)
                odds_ratios.append(r)
            rtxt = f"  odds x{r:.3f}/deviation" if r else ""
            print(f"  eps={eps:<5g} diff={diff:+7.2f}pp  2*se_diff={2*sed:5.2f}"
                  f"  {verdict}{rtxt}")
            results["arms"][f"{eps:g}"]["diff_vs_control_pp"] = round(diff, 2)
            results["arms"][f"{eps:g}"]["two_se_diff"] = round(2 * sed, 2)
            results["arms"][f"{eps:g}"]["verdict"] = verdict
            if r:
                results["arms"][f"{eps:g}"]["odds_per_deviation"] = round(r, 4)
        if odds_ratios:
            m = sum(odds_ratios) / len(odds_ratios)
            results["per_deviation"] = round(m, 4)
            print(f"\n  mean win-odds multiplier per random deviation: x{m:.3f}")
            print("  (x1.0 would mean the rule pick is worth nothing over random)")

    if first_dev:
        print()
        print("=" * 78)
        print("WHERE THE RULE PICK IS NOT CLEARLY BEST")
        print("(games bucketed by the option type of the FIRST deviation;")
        print(" a bucket at/above the eps=0 control is a bucket the rule agent")
        print(" is not winning -- that is where a learned ranker has room)")
        print("=" * 78)
        ctrl = 100 * (base["w"] / base["n"]) if base and base["n"] else float("nan")
        agg: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        for (eps, t), (w, n) in first_dev.items():
            agg[t][0] += w
            agg[t][1] += n
        print(f"{'option type':>26} {'games':>7} {'win%':>7} {'se':>6}   "
              f"vs control {ctrl:.2f}%")
        for t in sorted(agg, key=lambda x: -agg[x][1]):
            w, n = agg[t]
            if n < args.min_bucket:
                continue
            wr, lo, hi = wilson(w, n)
            se = binom_se(w, n)
            name = tnames[t] if t < len(tnames) else f"type_{t}"
            flag = ""
            if not math.isnan(ctrl):
                d = wr - ctrl
                flag = f"  {d:+6.2f}pp"
                if d + 2 * se >= 0:
                    flag += "  <== rule pick not clearly best"
            print(f"{name:>26} {n:>7} {wr:>7.2f} {se:>6.2f}{flag}")
            results["first_deviation"][name] = {
                "games": n, "wins": w, "win_pct": round(wr, 2),
                "se": round(se, 2), "ci95": [round(lo, 2), round(hi, 2)],
            }

    out = ROOT / args.json_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
