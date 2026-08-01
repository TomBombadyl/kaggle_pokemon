#!/usr/bin/env python3
"""Submission & Evaluation Director — continuous status board + CAP/dayroll watch.

Never submits Dra/Alak. Never burns CAP when floors red.
When CAP full: local-only strengthen signal. On dayroll: recheck ship eligibility
via director_gate (does not auto-submit unless --armed and floors green).

Usage:
  python scripts/director_dashboard.py
  python scripts/director_dashboard.py --once
  python scripts/director_dashboard.py --poll-seconds 120 --armed
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.auto_submit import ensure_token, submits_today, _today  # noqa: E402
from scripts.director_gate import (  # noqa: E402
    BLOCKED_SUBMIT_IDS,
    MAX_SUBMITS_UTC_DAY,
    PRIMARY_ID,
    dayroll_eta_str,
    evaluate_ship,
    load_best_gate_wr,
    load_focus_latest,
    log_decision,
    log_regression,
    seconds_to_utc_dayroll,
    utc_day,
    utc_now,
    write_board,
)

COMP = "pokemon-tcg-ai-battle"
PY = sys.executable
LOG = ROOT / "recordings" / "metrics" / "director_dashboard.jsonl"
PUBLIC_JSON = ROOT / "report" / "meta" / "our_submissions_live.json"
LB_JSON = ROOT / "report" / "meta" / "leaderboard_top_20260730.json"


def log(event: str, **kw) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": utc_now().isoformat(timespec="seconds"), "event": event, **kw}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{row['ts']}] {event} { {k: v for k, v in kw.items() if k != 'tail'} }", flush=True)


def process_health() -> dict[str, str]:
    """Count factory PIDs without killing anything."""
    out: dict[str, str] = {}
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress -Depth 3"
                ),
            ],
            capture_output=True,
            timeout=30,
        )
        raw = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
        if not raw:
            raw = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        if not raw:
            return {"python_scan": "empty"}
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        buckets: dict[str, list[dict]] = {
            "aggressive_loop": [],
            "continuous_focus_gates": [],
            "train_lucario_field_mcts": [],
            "gate_archaludon": [],
            "director_dashboard": [],
            "quota_reset_ship_monitor": [],
            "mainline_supervisor": [],
        }
        by_pid = {p.get("ProcessId"): p for p in data}
        for p in data:
            cmd = str(p.get("CommandLine") or "")
            pid = p.get("ProcessId")
            ppid = p.get("ParentProcessId")
            for key in buckets:
                if key in cmd:
                    venv = ".venv" in cmd
                    buckets[key].append(
                        {"pid": pid, "ppid": ppid, "venv": venv, "cmd": cmd}
                    )
        for k, items in buckets.items():
            if not items:
                out[k] = "DOWN"
                continue
            # Windows venv\python.exe is a launcher; base Python312 child is the
            # real worker. Count launcher+child as ONE logical process.
            logical = 0
            labels: list[str] = []
            child_pids = set()
            for it in items:
                if not it["venv"]:
                    parent = by_pid.get(it["ppid"]) or {}
                    pcmd = str(parent.get("CommandLine") or "")
                    if ".venv" in pcmd and k in pcmd:
                        child_pids.add(it["pid"])
                        continue  # folded into parent launcher
                logical += 1
                tag = "venv" if it["venv"] else "orphan_sys"
                labels.append(f"PID {it['pid']} {tag}")
            if logical <= 1:
                out[k] = f"OK ({', '.join(labels) or 'worker'})"
            else:
                out[k] = f"DUP x{logical} ({', '.join(labels)}) — keep one tree"
        # CAP / dayroll
        out["CAP"] = f"{submits_today()}/{MAX_SUBMITS_UTC_DAY} UTC {_today()}"
        out["dayroll"] = dayroll_eta_str()
    except Exception as e:
        out["error"] = str(e)
    return out


def fetch_our_submissions() -> dict:
    """Pull latest Kaggle submissions for public μ board."""
    if not ensure_token():
        return {"error": "no_token"}
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    try:
        proc = subprocess.run(
            [PY, "-m", "kaggle", "competitions", "submissions", "-c", COMP],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=env,
            timeout=120,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return {"error": str(e)}

    rows = []
    for line in text.splitlines():
        m = re.match(
            r"^\s*(\d{6,})\s+(\S+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}\S*)\s+.*?"
            r"(SubmissionStatus\.\w+)\s+([0-9.]+)?",
            line,
        )
        if not m:
            # looser parse
            m2 = re.match(r"^\s*(\d{6,})\s+(\S+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}\S*)", line)
            if not m2:
                continue
            score_m = re.search(r"(SubmissionStatus\.\w+)\s+([0-9.]+)", line)
            rows.append(
                {
                    "ref": m2.group(1),
                    "file": m2.group(2),
                    "date": m2.group(3),
                    "time": m2.group(4),
                    "status": score_m.group(1) if score_m else "?",
                    "publicScore": float(score_m.group(2)) if score_m else None,
                }
            )
            continue
        rows.append(
            {
                "ref": m.group(1),
                "file": m.group(2),
                "date": m.group(3),
                "time": m.group(4),
                "status": m.group(5),
                "publicScore": float(m.group(6)) if m.group(6) else None,
            }
        )

    today = _today()
    today_rows = [r for r in rows if r.get("date") == today]
    # latest-2 by submission time order (API returns newest first)
    latest2 = []
    for r in rows[:2]:
        if r.get("publicScore") is not None:
            latest2.append(r["publicScore"])
    pin = 1196.1
    top1 = 1198.4
    if LB_JSON.exists():
        try:
            lb = json.loads(LB_JSON.read_text(encoding="utf-8"))
            pin = float(lb.get("our_pin") or pin)
            top = lb.get("top") or []
            if top:
                top1 = float(top[0].get("score") or top1)
        except Exception:
            pass

    payload = {
        "as_of": utc_now().isoformat(timespec="seconds"),
        "utc_day": today,
        "submits_utc_today": len(today_rows) if today_rows else submits_today(),
        "latest2": latest2,
        "live_board": " / ".join(f"{x:.1f}" for x in latest2) if latest2 else "—",
        "today": today_rows[:5],
        "recent": rows[:8],
        "pin": pin,
        "top1": top1,
        "blocked": list(BLOCKED_SUBMIT_IDS),
    }
    PUBLIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def detect_local_regression(snap) -> None:
    """If dual or crustle collapses vs recent focus median — log REGRESS (no code kill)."""
    hist = ROOT / "recordings" / "metrics" / "focus_history.jsonl"
    if not hist.exists() or snap is None:
        return
    duals = []
    crusts = []
    try:
        lines = hist.read_text(encoding="utf-8").strip().splitlines()[-20:]
        for ln in lines:
            r = json.loads(ln)
            if r.get("dual_overall") is not None:
                duals.append(float(r["dual_overall"]))
            flg, maj = r.get("flg_wr"), r.get("majkel_wr")
            vals = [v for v in (flg, maj) if isinstance(v, (int, float))]
            if vals:
                crusts.append(min(vals))
    except Exception:
        return
    if len(duals) < 5 or snap.dual_overall is None:
        return
    med = sorted(duals)[len(duals) // 2]
    if snap.dual_overall < med - 8.0:
        log_regression(
            {
                "kind": "dual_collapse",
                "current": snap.dual_overall,
                "median20": med,
                "action": "HOLD ship; do not package; Iono engineer single-lever only",
            }
        )
        log("regression_dual", current=snap.dual_overall, median=med)
    if crusts and snap.crustle_floor_value() is not None:
        cmed = sorted(crusts)[len(crusts) // 2]
        cur = snap.crustle_floor_value()
        if cur is not None and cur < cmed - 10.0:
            log_regression(
                {
                    "kind": "crustle_collapse",
                    "current": cur,
                    "median20": cmed,
                    "action": "HOLD; reconfirm flg/majkel; no light rewire",
                }
            )
            log("regression_crustle", current=cur, median=cmed)


def cycle(armed: bool) -> dict:
    n = submits_today()
    rem = max(0, MAX_SUBMITS_UTC_DAY - n)
    procs = process_health()
    public = fetch_our_submissions()
    # Prefer API count if higher
    api_n = public.get("submits_utc_today")
    if isinstance(api_n, int) and api_n > n:
        n = api_n
        rem = max(0, MAX_SUBMITS_UTC_DAY - n)

    from scripts.director_gate import GateSnapshot, load_focus_pooled, load_ship_snapshot

    # Ship authority = pooled focus (last N) + loop best_gate Arch WR.
    # Instant focus_latest alone is noise (n=40); do not ship on single spike.
    snap = load_ship_snapshot()
    arch_loop = load_best_gate_wr()
    if snap is None:
        snap = GateSnapshot(ts_utc=utc_now().isoformat(timespec="seconds"), source="empty")
    if arch_loop is not None:
        snap.arch_overall = arch_loop

    # Keep instant for regression display only
    instant = load_focus_latest()
    if instant is not None and snap.raw is not None:
        snap.raw = dict(snap.raw or {})
        snap.raw["instant_iono"] = instant.iono
        snap.raw["instant_crustle_min"] = instant.crustle_floor_value()
        snap.raw["instant_dual"] = instant.dual_overall

    verdict = evaluate_ship(snap, candidate_id=PRIMARY_ID, submits_today=n)

    detect_local_regression(snap)
    log_decision(verdict, source="director_dashboard", remaining=rem)

    decision = ""
    if rem <= 0:
        decision = (
            f"**NO SUBMIT** CAP {n}/{MAX_SUBMITS_UTC_DAY}. "
            f"Dayroll in {dayroll_eta_str()}. "
            f"Local-only: Iono is bottleneck (need ≥55). "
            f"Crustle/dual hold. **Blocked**: Dra/Alak. "
            f"Next ship only if SHIP after dayroll + floors green."
        )
    elif verdict.ship and armed:
        decision = (
            f"**ARMED SHIP** remaining={rem} — would invoke auto_submit Arch only. "
            f"(Dashboard does not auto-fire unless --armed; prefer aggressive_loop packaging.)"
        )
    elif verdict.ship:
        decision = (
            f"**SHIP READY** remaining={rem} — wait for aggressive_loop / quota monitor "
            f"to package Arch. Dashboard holds fire (not --armed)."
        )
    else:
        decision = (
            f"**HOLD** rem={rem} decision={verdict.decision}: "
            f"{'; '.join(verdict.reasons)}. Local strengthen only."
        )

    path = write_board(
        snap=snap,
        verdict=verdict,
        submits=n,
        processes=procs,
        public_mu=public,
        decision_line=decision,
    )
    # Mirror short block into root STATE (append-only; avoid regex on Windows paths)
    try:
        state = ROOT.parent / "STATE.md"
        block = (
            f"\n### Director board {datetime.now().isoformat(timespec='seconds')}\n"
            f"- CAP **{n}/{MAX_SUBMITS_UTC_DAY}** rem={rem} dayroll={dayroll_eta_str()}\n"
            f"- gates: iono={getattr(snap, 'iono', None)} crustle_min="
            f"{snap.crustle_floor_value() if snap else None} dual={getattr(snap, 'dual_overall', None)} "
            f"arch_loop={arch_loop}\n"
            f"- decision: **{verdict.decision}** — {'; '.join(verdict.reasons) or 'green'}\n"
            f"- board: STATUS_BOARD.md\n"
            f"- public latest2: {public.get('live_board')}\n"
        )
        if state.exists():
            text = state.read_text(encoding="utf-8")
            marker = "## Director"
            if marker not in text:
                text = text.rstrip() + f"\n\n{marker}\n"
            # Keep last 12 director blocks only
            parts = text.split(marker, 1)
            head, tail = parts[0], parts[1] if len(parts) > 1 else ""
            # strip old director board bullets to avoid unbounded growth
            if "### Director board" in tail:
                # keep content after last 8 board markers max via simple trim
                chunks = tail.split("### Director board")
                kept = chunks[0] + "".join(
                    "### Director board" + c for c in chunks[-8:] if c
                )
                tail = kept
            state.write_text(head + marker + tail.rstrip() + "\n" + block + "\n", encoding="utf-8")
        else:
            state.write_text(f"# STATE\n\n## Director\n{block}\n", encoding="utf-8")
    except Exception as e:
        log("state_mirror_fail", err=str(e))

    log(
        "cycle",
        submits=n,
        remaining=rem,
        decision=verdict.decision,
        reasons=verdict.reasons,
        dayroll_sec=seconds_to_utc_dayroll(),
        board=str(path),
        live=public.get("live_board"),
    )
    return {
        "submits": n,
        "remaining": rem,
        "decision": verdict.decision,
        "reasons": verdict.reasons,
        "board": str(path),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll-seconds", type=int, default=120)
    ap.add_argument(
        "--armed",
        action="store_true",
        help="Annotate ship-ready as ARMED (still does not call Kaggle unless extended)",
    )
    args = ap.parse_args()
    print("[director] dashboard START", flush=True)
    while True:
        try:
            snap = cycle(armed=args.armed)
            print(f"[director] {snap}", flush=True)
        except Exception as e:
            log("error", err=str(e))
            print(f"[director] ERROR {e}", flush=True)
        if args.once:
            break
        time.sleep(max(30, args.poll_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
