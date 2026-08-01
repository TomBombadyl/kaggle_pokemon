"""Director self-check: is the arch ship authority a provably default-config run?

Prints the pooled row that currently carries arch ship authority, every fresh pooled
`meta` row that was REJECTED for missing/non-default config provenance, and the
resulting ship verdict. Run this after any change to director_gate's pooled-authority
rules -- a silent switch of authority row is exactly the failure mode being guarded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import director_gate as dg  # noqa: E402


def main() -> int:
    pooled = dg.load_pooled_arch_overall()
    print("== pooled arch authority ==")
    print(json.dumps(pooled, indent=2, default=str))

    snap = dg.load_ship_snapshot()
    if snap is None:
        print("NO SNAPSHOT")
        return 1
    print("\n== snapshot ==")
    print(f"arch_overall = {snap.arch_overall}")
    print(f"arch_source  = {snap.raw.get('arch_source')}")
    print(f"iono         = {snap.iono}")
    print(f"crustle_min  = {snap.crustle_min} ({snap.raw.get('crustle_min_estimator')})")
    print(f"dual_overall = {snap.dual_overall}")
    rej = snap.raw.get("arch_pooled_rejected") or []
    for r in rej:
        print(f"  REJECTED {r.get('label')} mean={r.get('mean')} -> {r.get('why')}")

    verdict = dg.evaluate_ship(snap, submits_today=2)
    print("\n== verdict ==")
    print(f"decision={verdict.decision} ship={verdict.ship}")
    for r in verdict.reasons:
        print(f"  reason: {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
