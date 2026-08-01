"""Autonomous Kaggle submit director for pokemon-tcg-ai-battle.

Ladder mechanics this encodes (verified 2026-07-31)
---------------------------------------------------
* 5 submissions per UTC day, hard cap.
* Only the **2 most recent** submissions are active on the ladder.
* Leaderboard score = **best** of the active submissions, so a fresh 600 does
  not drag the displayed score down.
* A new submission always evicts the **older** active one; there is no way to
  pin a good agent. Protecting a high roll therefore means: stop submitting.
* Every submission starts at mu=600 and plays roughly 24 games/day, with
  scheduling priority biased toward higher-rated agents.
* Identical agents have been observed converging 400 mu apart. Each upload is
  a lottery ticket; the policy below plays that lottery deliberately.

Policy
------
1. At UTC dayroll, fill both active slots with the top-2 ranked candidates.
2. Poll. Give each submission `--settle-hours` before judging it.
3. If the best active score clears `--protect-at`, STOP for the day: any
   further upload would eventually evict the good roll.
4. Otherwise re-roll the weaker slot while daily budget remains, keeping
   `--reserve` slots unused as insurance.

Usage
-----
    python scripts/ladder_director.py --status
    python scripts/ladder_director.py --plan
    python scripts/ladder_director.py --run           # continuous
    python scripts/ladder_director.py --submit-now arch_v5_r7 --reason "..."
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND_DIR = os.path.join(ROOT, "dist", "candidates")
STATE_PATH = os.path.join(ROOT, "dist", "director_state.json")
LOG_PATH = os.path.join(ROOT, "dist", "director_log.jsonl")
COMP = "pokemon-tcg-ai-battle"
DAILY_CAP = 5
ACTIVE_SLOTS = 2

VENV_KAGGLE = os.path.join(os.path.dirname(ROOT), ".venv", "Scripts", "kaggle.exe")
TOKEN_PATHS = [
    os.path.join(ROOT, ".kaggle", "access_token"),
    os.path.join(os.path.expanduser("~"), ".kaggle", "access_token"),
]

# Ranked candidate queue. Order = submission priority.
# `gauntlet` is the local 8-opponent win rate (n>=1200, 0 errors required).
CANDIDATES = [
    {
        "name": "arch_v5_r7",
        "gauntlet": 55.1,
        "worst_matchup": 14.5,
        "why": "community v5 brain (ref 54083197 = mu 1196.1) + R7 bench guard, zero repo levers",
    },
    {
        "name": "arch_75wr_r7",
        "gauntlet": None,
        "worst_matchup": None,
        "why": "public sample_archaludon_75wr + R7 bench guard; same lineage, refined shell",
    },
    {
        "name": "arch_75wr_raw",
        "gauntlet": None,
        "worst_matchup": None,
        "why": "public 75wr verbatim, no wrapper",
    },
]


def _log(event: str, **fields) -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[{rec['ts']}] {event} " +
          " ".join(f"{k}={v}" for k, v in fields.items()), flush=True)


def _token() -> str:
    tok = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if tok:
        return tok
    for p in TOKEN_PATHS:
        if os.path.exists(p):
            t = open(p, encoding="utf-8").read().strip()
            if t:
                return t
    raise SystemExit("no Kaggle token: set KAGGLE_API_TOKEN or .kaggle/access_token")


def _kaggle(args: list[str], timeout: int = 180) -> tuple[int, str]:
    env = dict(os.environ)
    env["KAGGLE_API_TOKEN"] = _token()
    exe = VENV_KAGGLE if os.path.exists(VENV_KAGGLE) else "kaggle"
    try:
        p = subprocess.run([exe] + args, capture_output=True, text=True,
                           timeout=timeout, env=env, cwd=ROOT)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def fetch_submissions() -> list[dict]:
    """Newest-first list of {ref, file, date, message, status, score}."""
    rc, out = _kaggle(["competitions", "submissions", "-c", COMP, "-v"])
    if rc != 0 and "," not in out:
        raise RuntimeError(f"kaggle submissions failed: {out[:400]}")
    # Real CSV: ref,fileName,date,description,status,publicScore,privateScore
    # Descriptions contain commas and quotes, so parse it properly rather than
    # splitting by hand. Blank separator lines are skipped by csv.reader.
    rows: list[dict] = []
    reader = csv.reader(io.StringIO(out))
    for rec in reader:
        if len(rec) < 6 or not rec[0].strip().isdigit():
            continue
        try:
            score = float(rec[5])
        except (ValueError, IndexError):
            score = None
        rows.append({
            "ref": rec[0].strip(),
            "file": rec[1].strip(),
            "date": rec[2].strip(),
            "message": rec[3].strip(),
            "status": rec[4].replace("SubmissionStatus.", "").strip(),
            "score": score,
        })
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def utc_day(dt_str: str) -> str:
    return dt_str.split(" ")[0].split("T")[0]


def dayroll_remaining() -> timedelta:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - now


def status() -> dict:
    subs = fetch_submissions()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = [s for s in subs if utc_day(s["date"]) == today]
    active = subs[:ACTIVE_SLOTS]
    scored = [s["score"] for s in active if s["score"] is not None]
    return {
        "utc_now": datetime.now(timezone.utc).isoformat(),
        "utc_day": today,
        "used_today": len(used),
        "remaining_today": max(0, DAILY_CAP - len(used)),
        "dayroll_in": str(dayroll_remaining()).split(".")[0],
        "active": active,
        "board_score": max(scored) if scored else None,
        "total_submissions": len(subs),
    }


def print_status(st: dict) -> None:
    print(f"UTC {st['utc_now']}  day={st['utc_day']}  dayroll in {st['dayroll_in']}")
    print(f"CAP {st['used_today']}/{DAILY_CAP}  remaining={st['remaining_today']}")
    print(f"BOARD (best of active) = {st['board_score']}")
    print("active slots (newest first):")
    for s in st["active"]:
        print(f"  {s['ref']:>10s} {str(s['score']):>8s} {s['status']:<10s} "
              f"{s['file']:<28s} {s['date']}")


def candidate_path(name: str) -> str:
    p = os.path.join(CAND_DIR, name + ".tar.gz")
    if not os.path.exists(p):
        raise FileNotFoundError(f"candidate not built: {p}")
    manifest = os.path.join(CAND_DIR, name + ".manifest.json")
    if not os.path.exists(manifest):
        raise FileNotFoundError(f"no manifest (unverified build): {manifest}")
    return p


def submit(name: str, reason: str, dry: bool = False) -> dict:
    path = candidate_path(name)
    manifest = json.load(open(os.path.join(CAND_DIR, name + ".manifest.json")))
    msg = f"{name} | {reason} | sha256={manifest['tarball_sha256'][:12]}"[:480]
    st = status()
    if st["remaining_today"] <= 0:
        _log("submit_blocked", name=name, why="daily cap full",
             used=st["used_today"])
        return {"ok": False, "why": "cap_full"}
    if dry:
        _log("submit_dry_run", name=name, msg=msg, remaining=st["remaining_today"])
        return {"ok": True, "dry": True, "msg": msg}
    rc, out = _kaggle(
        ["competitions", "submit", "-c", COMP, "-f", path, "-m", msg], timeout=900
    )
    ok = rc == 0 and "error" not in out.lower()[:200]
    _log("submit", name=name, ok=ok, rc=rc, msg=msg, out=out.strip()[-300:])
    return {"ok": ok, "out": out, "msg": msg}


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            return json.load(open(STATE_PATH, encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(st: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)


def plan(args) -> dict:
    """Decide the next action without performing it."""
    st = status()
    board = st["board_score"]
    active = st["active"]
    now = datetime.now(timezone.utc)

    def age_hours(sub: dict) -> float:
        try:
            d = datetime.fromisoformat(sub["date"].replace(" ", "T"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return (now - d).total_seconds() / 3600
        except Exception:
            return 999.0

    if st["remaining_today"] <= args.reserve:
        return {"action": "hold", "why": f"budget at reserve ({st['remaining_today']} left)"}

    if board is not None and board >= args.protect_at:
        return {"action": "hold",
                "why": f"board {board} >= protect-at {args.protect_at}; "
                       "another upload would evict the good roll"}

    fresh = [s for s in active if age_hours(s) < args.settle_hours]
    if fresh and not args.force:
        youngest = min(age_hours(s) for s in active)
        return {"action": "wait",
                "why": f"active submission only {youngest:.1f}h old, "
                       f"settle window {args.settle_hours}h"}

    submitted_names = {s["message"].split(" | ")[0] for s in active}
    for cand in CANDIDATES:
        if cand["name"] not in submitted_names:
            return {"action": "submit", "candidate": cand["name"],
                    "why": f"fill slot with untried {cand['name']}: {cand['why']}"}

    weakest = min((s for s in active if s["score"] is not None),
                  key=lambda s: s["score"], default=None)
    if weakest is not None and weakest["score"] < args.reroll_below:
        return {"action": "submit", "candidate": CANDIDATES[0]["name"],
                "why": f"re-roll: weakest active {weakest['ref']} at "
                       f"{weakest['score']} < {args.reroll_below}"}
    return {"action": "hold", "why": "no candidate beats the current board"}


def run_loop(args) -> int:
    _log("director_start", poll=args.poll, protect_at=args.protect_at,
         settle_hours=args.settle_hours, reserve=args.reserve)
    while True:
        try:
            st = status()
            decision = plan(args)
            _log("tick", cap=f"{st['used_today']}/{DAILY_CAP}",
                 board=st["board_score"], dayroll_in=st["dayroll_in"],
                 action=decision["action"], why=decision["why"])
            if decision["action"] == "submit" and not args.dry_run:
                submit(decision["candidate"], decision["why"])
                time.sleep(30)
                continue
        except Exception as exc:
            _log("tick_error", error=f"{type(exc).__name__}: {exc}")
        time.sleep(args.poll)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--submit-now", metavar="NAME")
    ap.add_argument("--reason", default="director auto-submit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--poll", type=int, default=600, help="seconds between ticks")
    ap.add_argument("--protect-at", type=float, default=1000.0,
                    help="stop submitting once the board reaches this")
    ap.add_argument("--reroll-below", type=float, default=750.0)
    ap.add_argument("--settle-hours", type=float, default=6.0)
    ap.add_argument("--reserve", type=int, default=0,
                    help="daily slots to leave unused")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if args.submit_now:
        r = submit(args.submit_now, args.reason, dry=args.dry_run)
        return 0 if r.get("ok") else 1
    if args.run:
        return run_loop(args)
    st = status()
    print_status(st)
    if args.plan:
        d = plan(args)
        print(f"\nPLAN: {d['action']}  -> {d.get('candidate','')}\n  {d['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
