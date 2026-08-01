"""Director-only: wait for UTC dayroll, then ship ONE verified package.

The board keeps only the latest 2 submissions, so a known-good rollback may be
a useful candidate. It is not an exception to the director gates: every ship,
including a rollback/reship, must pass the current pooled floors at execution
time.

Single-shot by design: submits at most once, then exits. Never uses --force.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from auto_submit import submits_today
from director_gate import PRIMARY_ID, evaluate_ship, load_ship_snapshot, log_decision

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def next_dayroll(after: datetime) -> datetime:
    return (after + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="package under dist/candidates")
    ap.add_argument("--message", required=True)
    ap.add_argument("--local-gate", type=float, required=True)
    ap.add_argument("--strength-note", default="")
    ap.add_argument(
        "--grace-seconds",
        type=int,
        default=45,
        help="wait past midnight so Kaggle's own counter has rolled",
    )
    ap.add_argument("--max-wait-seconds", type=int, default=7200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pkg = (ROOT / args.file) if not Path(args.file).is_absolute() else Path(args.file)
    if not pkg.exists():
        print(f"[FATAL] package not found: {pkg}")
        return 2

    start = utc_now()
    target = next_dayroll(start) + timedelta(seconds=args.grace_seconds)
    print(f"[wait] utc_now={start.isoformat()} target={target.isoformat()}")

    while True:
        now = utc_now()
        if now >= target:
            break
        if (now - start).total_seconds() > args.max_wait_seconds:
            print("[FATAL] max wait exceeded without reaching dayroll")
            return 3
        time.sleep(min(20, max(1, (target - now).total_seconds())))

    snap = load_ship_snapshot()
    if snap is None:
        print("[HOLD] no authoritative pooled ship snapshot is available")
        return 4
    verdict = evaluate_ship(
        snap,
        candidate_id=PRIMARY_ID,
        submits_today=submits_today(),
    )
    log_decision(
        verdict,
        source="director_dayroll_ship",
        candidate_id=PRIMARY_ID,
        file=str(pkg),
    )
    if not verdict.ship:
        print(f"[HOLD] director gates are not green: {'; '.join(verdict.reasons)}")
        return 4

    print(f"[dayroll] reached {utc_now().isoformat()} — submitting once")
    cmd = [
        PY,
        "-u",
        str(ROOT / "scripts" / "auto_submit.py"),
        "--file",
        str(pkg),
        "--message",
        args.message,
        "--local-gate",
        str(args.local_gate),
    ]
    if args.strength_note:
        cmd += ["--strength-note", args.strength_note]
    if args.dry_run:
        cmd.append("--dry-run")

    proc = subprocess.run(cmd, cwd=str(ROOT), text=True)
    print(f"[done] auto_submit rc={proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
