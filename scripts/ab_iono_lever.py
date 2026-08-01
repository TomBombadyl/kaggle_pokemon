#!/usr/bin/env python3
"""Single-lever A/B for Archaludon vs real_iono.

  set ARCH_IONO_LEVER=r14n
  python scripts/ab_iono_lever.py --levers none r14n r14u --games 400

Writes metrics JSON under recordings/metrics/ and prints a table.
Does not touch Crustle logic; optional --guard runs flg/majkel after best lever.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
METRICS = ROOT / "recordings" / "metrics"
LOGS = Path("E:/PTCG_AI_Battle_Challenge/recordings/logs")
if not LOGS.exists():
    LOGS = ROOT / "recordings" / "logs"
METRICS.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)


def run_gate(lever: str, games: int, opponents: list[str]) -> tuple[dict[str, float], str]:
    env = {**os.environ, "ARCH_IONO_LEVER": lever}
    cmd = [
        PY, "-u", str(ROOT / "scripts" / "gate_archaludon.py"),
        "--games", str(games),
        "--opponents", *opponents,
    ]
    p = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=7200
    )
    out = (p.stdout or "") + (p.stderr or "")
    found: dict[str, float] = {}
    for m in re.finditer(
        r"^(\S+)\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%",
        out,
        re.M,
    ):
        found[m.group(1)] = float(m.group(2))
    m = re.search(r"OVERALL \(gated\)\s+([0-9]+(?:\.[0-9]+)?)\s*%", out)
    if m:
        found["OVERALL"] = float(m.group(1))
    return found, out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--levers", nargs="+", default=["none", "r14n"])
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--guard", action="store_true", help="Also gate flg/majkel n=40")
    args = ap.parse_args()

    rows = []
    for lev in args.levers:
        print(f"[ab] lever={lev} n={args.games} …", flush=True)
        wrs, out = run_gate(lev, args.games, ["real_iono"])
        iono = wrs.get("real_iono")
        log_path = LOGS / f"ab_iono_{lev}_n{args.games}.log"
        log_path.write_text(out, encoding="utf-8")
        row = {"lever": lev, "iono_wr": iono, "n": args.games, "wrs": wrs}
        if args.guard:
            gw, _ = run_gate(lev, 40, ["meta_crustle_flg", "meta_crustle_majkel"])
            row["flg_wr"] = gw.get("meta_crustle_flg")
            row["majkel_wr"] = gw.get("meta_crustle_majkel")
        rows.append(row)
        print(f"[ab] {lev}: iono={iono}%", flush=True)

    baseline = next((r["iono_wr"] for r in rows if r["lever"] in ("none", "r14h")), None)
    print("\n=== A/B TABLE ===")
    print(f"{'lever':12} {'iono%':>8} {'delta':>8}")
    for r in rows:
        d = ""
        if baseline is not None and r["iono_wr"] is not None:
            d = f"{r['iono_wr'] - baseline:+.1f}"
        print(f"{r['lever']:12} {r['iono_wr']!s:>8} {d:>8}")

    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "games": args.games,
        "rows": rows,
        "baseline": baseline,
        "target": 55.0,
    }
    out_path = METRICS / "iono_ab_latest.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    hist = METRICS / "iono_ab_history.jsonl"
    with hist.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
