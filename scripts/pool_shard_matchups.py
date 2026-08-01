"""Pool per-opponent W/L across the shard logs of one Shard-Gate run.

Shard-Gate.ps1 pools only the OVERALL line, which hides *where* a lever moved.
This reads every shard*.out under a fleet log dir and prints per-opponent
pooled win rate with a binomial stderr, plus an A/B diff when two dirs are given.

  python scripts/pool_shard_matchups.py <log_dir_A> [log_dir_B]

Written by the `arch` fleet worker (2026-07-31); safe for any role to use.
"""

from __future__ import annotations

import collections
import glob
import math
import os
import re
import sys

ROW = re.compile(r"^\s{2}(\S+)\s+\(.*?\)\s+([0-9.]+)%.*?W(\d+)/L(\d+)/D(\d+)/U(\d+)")


def pool(log_dir: str) -> "collections.OrderedDict[str, list[int]]":
    agg: collections.OrderedDict[str, list[int]] = collections.OrderedDict()
    for path in sorted(glob.glob(os.path.join(log_dir, "shard*.out"))):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = ROW.match(line)
                if not m:
                    continue
                cell = agg.setdefault(m.group(1), [0, 0, 0, 0])
                for i, v in enumerate(map(int, m.groups()[2:])):
                    cell[i] += v
    return agg


def wr_se(cell: list[int]) -> tuple[float, float, int]:
    w, l, d, u = cell
    n = w + l + d + u
    if n == 0:
        return 0.0, 0.0, 0
    p = w / n
    return 100.0 * p, 100.0 * math.sqrt(max(p * (1 - p), 1e-9) / n), n


def show(label: str, agg) -> None:
    print(f"== {label}")
    tw = tn = 0
    for name, cell in agg.items():
        wr, se, n = wr_se(cell)
        tw += cell[0]
        tn += n
        print(f"  {name:32s} {wr:5.1f}% +-{se:4.2f}  n={n}")
    if tn:
        p = tw / tn
        print(f"  {'OVERALL(micro)':32s} {100 * p:5.1f}% +-{100 * math.sqrt(p * (1 - p) / tn):4.2f}  n={tn}")
    print()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    a = pool(sys.argv[1])
    show(os.path.basename(sys.argv[1]), a)
    if len(sys.argv) < 3:
        return 0
    b = pool(sys.argv[2])
    show(os.path.basename(sys.argv[2]), b)

    print("== B - A per opponent (diff, 2x stderr of the diff)")
    for name in a:
        if name not in b:
            continue
        wa, sa, na = wr_se(a[name])
        wb, sb, nb = wr_se(b[name])
        if not na or not nb:
            continue
        sd = math.sqrt(sa * sa + sb * sb)
        mark = "SIG" if abs(wb - wa) >= 2 * sd else "   "
        print(f"  {name:32s} {wb - wa:+6.2f}pp  2se={2 * sd:4.2f}  {mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
