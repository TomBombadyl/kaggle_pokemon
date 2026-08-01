"""INTEL: probe what each extracted candidate returns from Kaggle's deck-selection call.

Kaggle calls `agent(obs)` once per episode with `obs.select is None`; the agent must
return its 60 card ids. Public agents also latch their route / specialist / policy in
that call, so an evaluation harness that skips it (or passes a malformed obs) benches
a *fallback* policy on the *wrong* deck.

This probe imports each candidate in a fresh module (the handshake mutates module
globals, so every obs shape needs its own import) and reports, per obs shape:

  ok60   - returned a 60-int list  (handshake understood)
  raised - the call raised          (harness would silently fall back)
  bad    - returned something else

Shapes tested:
  short = {"select": None}                             <- what intel_delegate_bench used
  full  = {"logs": [], "current": None, "select": None} <- what every package_*.py uses

  python scripts/intel_handshake_probe.py
  python scripts/intel_handshake_probe.py --candidates sample_archaludon_75wr archaludon_metal_gpu_v28
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from scripts.intel_delegate_bench import CAND_DIR, load_candidate  # noqa: E402

SHAPES = {
    "short": lambda: {"select": None},
    "full": lambda: {"logs": [], "current": None, "select": None},
}


def own_deck(name: str) -> list[int] | None:
    p = CAND_DIR / name / "deck.csv"
    if not p.exists():
        return None
    try:
        return [int(x) for x in p.read_text().splitlines() if x.strip()][:60]
    except ValueError:
        return None


def probe_one(name: str, shape: str) -> dict:
    """Fresh import + one handshake call. Returns a verdict row."""
    row: dict = {"candidate": name, "shape": shape}
    try:
        brain = load_candidate(name)
    except Exception as exc:  # noqa: BLE001
        row["verdict"] = "import_failed"
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row
    try:
        got = brain(SHAPES[shape]())
    except BaseException as exc:  # noqa: BLE001 - candidates raise SystemExit too
        row["verdict"] = "raised"
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row
    if isinstance(got, list) and len(got) == 60 and all(isinstance(v, int) for v in got):
        row["verdict"] = "ok60"
        row["head"] = got[:6]
        od = own_deck(name)
        row["matches_own_deck_csv"] = (od is not None and sorted(got) == sorted(od))
    else:
        row["verdict"] = "bad"
        row["got_type"] = type(got).__name__
        row["got_len"] = len(got) if isinstance(got, (list, tuple)) else None
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", nargs="*", default=None,
                    help="default: every dir under extracted_agents/ holding main.py")
    ap.add_argument("--out", default="recordings/intel/handshake_probe.json")
    args = ap.parse_args(argv)

    names = args.candidates or sorted(
        d.name for d in CAND_DIR.iterdir() if d.is_dir() and (d / "main.py").exists()
    )

    rows = []
    for name in names:
        for shape in SHAPES:
            row = probe_one(name, shape)
            rows.append(row)
            extra = row.get("error") or (
                f"head={row.get('head')} own_deck_match={row.get('matches_own_deck_csv')}"
                if row["verdict"] == "ok60" else ""
            )
            print(f"{name:34s} {shape:6s} {row['verdict']:14s} {extra}", flush=True)

    # who is fixed by using the full obs shape?
    by = {(r["candidate"], r["shape"]): r["verdict"] for r in rows}
    fixed = [c for c in names
             if by.get((c, "short")) != "ok60" and by.get((c, "full")) == "ok60"]
    broke = [c for c in names
             if by.get((c, "short")) == "ok60" and by.get((c, "full")) != "ok60"]
    both_ok = [c for c in names if by.get((c, "short")) == by.get((c, "full")) == "ok60"]
    neither = [c for c in names
               if by.get((c, "short")) != "ok60" and by.get((c, "full")) != "ok60"]

    print("\n--- summary ---")
    print(f"ok on both shapes      ({len(both_ok)}): {', '.join(both_ok) or '-'}")
    print(f"FIXED by full shape    ({len(fixed)}): {', '.join(fixed) or '-'}")
    print(f"broken by full shape   ({len(broke)}): {', '.join(broke) or '-'}")
    print(f"no handshake either way({len(neither)}): {', '.join(neither) or '-'}")

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"rows": rows, "fixed_by_full_shape": fixed, "ok_both": both_ok,
         "broken_by_full": broke, "no_handshake": neither},
        indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
