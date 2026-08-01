#!/usr/bin/env python3
"""Background: watch Kaggle daily submit quota reset + ship only if gate quality holds.

Ship conditions (user 2026-07-30):
  - overall WR ≥ 72%
  - deep Crustle ≥ 70% (meta_crustle_flg / meta_crustle_majkel or crustle matchups)
  - Iono ≥ 45% preferred (ideal ≥55%); hard floor configurable
  - competitive vs flg / majkel (crustle lists)
  - package exists: dist/candidates/archaludon.tar.gz
  - remaining daily slots > 0 (UTC day, max 5)

Usage:
  python scripts/quota_reset_ship_monitor.py
  python scripts/quota_reset_ship_monitor.py --once
  python scripts/quota_reset_ship_monitor.py --poll-seconds 120 --recheck-gate
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

from scripts.auto_submit import (  # noqa: E402
    MAX_PER_DAY,
    ensure_token,
    record_submit,
    run_submit,
    submits_today,
    _today,
)

COMP = "pokemon-tcg-ai-battle"
PACKAGE = ROOT / "dist" / "candidates" / "archaludon.tar.gz"
GATE_CACHE = ROOT / "dist" / "gate_ship_status.json"
MONITOR_LOG = ROOT / "recordings" / "metrics" / "quota_ship_monitor.jsonl"
ROOT_STATE = ROOT.parent / "STATE.md"
REPO_STATE = ROOT / "STATE.md"
PY = sys.executable

# Ship thresholds — Director lock 2026-07-31 (Iono≥55 / Arch≥83 / Crustle≥89)
try:
    from scripts.director_gate import (  # noqa: E402
        SHIP_ARCH_OVERALL,
        SHIP_CRUSTLE_MIN,
        SHIP_IONO,
    )

    SHIP_OVERALL = SHIP_ARCH_OVERALL
    SHIP_CRUSTLE = SHIP_CRUSTLE_MIN
    SHIP_IONO_MIN = SHIP_IONO
    SHIP_IONO_IDEAL = SHIP_IONO
except Exception:
    SHIP_OVERALL = 83.0
    SHIP_CRUSTLE = 89.0
    SHIP_IONO_MIN = 55.0
    SHIP_IONO_IDEAL = 55.0


def log(event: str, **kw) -> None:
    MONITOR_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **kw}
    with MONITOR_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{row['ts']}] {event} { {k: v for k, v in kw.items() if k != 'tail'} }", flush=True)


def kaggle_env() -> dict:
    env = os.environ.copy()
    ensure_token()
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "data" / "sim" / "sample_submission")
    return env


def count_submits_utc_today_via_api() -> tuple[int, str]:
    """Return (count, detail) of submissions created on UTC calendar day."""
    if not ensure_token():
        return -1, "no_token"
    env = kaggle_env()
    try:
        proc = subprocess.run(
            [PY, "-m", "kaggle", "competitions", "submissions", "-c", COMP],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=env,
            timeout=120,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return -1, str(e)

    today = _today()  # UTC date string YYYY-MM-DD
    n = 0
    # rows like: 55095587  archaludon.tar.gz  2026-07-30 01:00:05.970000  ...
    for line in out.splitlines():
        m = re.search(r"\b(20\d{2}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}", line)
        if not m:
            continue
        if m.group(1) == today and re.match(r"^\s*\d{6,}", line):
            n += 1
    # fallback: local count if API parse fails empty
    local = submits_today()
    if n == 0 and local > 0:
        # API table may be truncated/header-only; trust max(local, n)
        n = local
    return n, f"api_count={n} local_count={local} utc_day={today}"


def remaining_slots() -> tuple[int, str]:
    used, detail = count_submits_utc_today_via_api()
    if used < 0:
        return -1, detail
    rem = max(0, MAX_PER_DAY - used)
    return rem, detail


def parse_gate_output(text: str) -> dict:
    overall = None
    m = re.search(r"OVERALL[^\n]*?([0-9]+(?:\.[0-9]+)?)\s*%", text, re.I)
    if m:
        overall = float(m.group(1))
    matchups: dict[str, float] = {}
    for line in text.splitlines():
        mm = re.search(
            r"^\s*(\S+)\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%",
            line,
        )
        if mm:
            matchups[mm.group(1)] = float(mm.group(2))
    # crustle deep = min of flg/majkel if present else any crustle key
    crustle_keys = [k for k in matchups if "crustle" in k.lower() or "flg" in k.lower() or "majkel" in k.lower()]
    crustle_vals = [matchups[k] for k in crustle_keys]
    crustle = min(crustle_vals) if crustle_vals else None
    iono_keys = [k for k in matchups if "iono" in k.lower()]
    iono = matchups[iono_keys[0]] if iono_keys else None
    return {
        "overall": overall,
        "matchups": matchups,
        "crustle_min": crustle,
        "iono": iono,
        "flg": matchups.get("meta_crustle_flg"),
        "majkel": matchups.get("meta_crustle_majkel"),
    }


def run_gate(suite: str, games: int, opponents: list[str] | None = None) -> dict:
    args = [PY, "scripts/gate_archaludon.py", "--games", str(games), "--suite", suite]
    if opponents:
        args += ["--opponents", *opponents]
    env = kaggle_env()
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=env,
            timeout=max(600, games * 90),
        )
        text = (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return {"ok": False, "error": str(e)}
    parsed = parse_gate_output(text)
    parsed["ok"] = proc.returncode == 0 and parsed.get("overall") is not None
    parsed["rc"] = proc.returncode
    parsed["suite"] = suite
    parsed["games"] = games
    parsed["tail"] = text[-600:]
    return parsed


def evaluate_ship(recheck: bool) -> dict:
    """Load or refresh gate metrics; return ship decision."""
    status: dict = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "package_exists": PACKAGE.exists() and PACKAGE.stat().st_size > 1000,
        "package": str(PACKAGE.relative_to(ROOT)),
    }
    if not status["package_exists"]:
        status["ship"] = False
        status["reason"] = "no_package"
        return status

    cached = {}
    if GATE_CACHE.exists() and not recheck:
        try:
            cached = json.loads(GATE_CACHE.read_text(encoding="utf-8"))
        except Exception:
            cached = {}

    # Prefer fresh dual gate when recheck or cache missing/stale (>2h)
    stale = True
    if cached.get("checked_at"):
        try:
            t0 = datetime.fromisoformat(cached["checked_at"].replace("Z", "+00:00"))
            stale = (datetime.now(timezone.utc) - t0).total_seconds() > 7200
        except Exception:
            stale = True

    if recheck or stale or not cached.get("overall"):
        log("gate_refresh_start")
        # Ship panel: baseline-style overall + crustle deep + iono
        # 1) pure core n=30 for overall/iono/draga
        core = run_gate("core", 30, ["dragapult_ex_sample", "real_mega_abomasnow_ex", "real_iono"])
        # 2) crustle deep: flg + majkel n=30
        crust = run_gate(
            "meta_fast",
            30,
            ["meta_crustle_flg", "meta_crustle_majkel"],
        )
        # Combine overall: weighted by games if both ok
        overall = core.get("overall")
        iono = core.get("iono") or core.get("matchups", {}).get("real_iono")
        crustle_min = crust.get("crustle_min")
        if crustle_min is None and crust.get("matchups"):
            vals = list(crust["matchups"].values())
            crustle_min = min(vals) if vals else None
        flg = crust.get("matchups", {}).get("meta_crustle_flg")
        majkel = crust.get("matchups", {}).get("meta_crustle_majkel")
        # Competitive flg/majkel: both ≥ 55 or mean ≥ 60
        flg_ok = flg is not None and flg >= 55.0
        maj_ok = majkel is not None and majkel >= 55.0
        competitive = (flg_ok and maj_ok) or (
            flg is not None and majkel is not None and (flg + majkel) / 2 >= 60.0
        )
        status.update(
            {
                "overall": overall,
                "iono": iono,
                "crustle_min": crustle_min,
                "flg": flg,
                "majkel": majkel,
                "competitive_flg_majkel": competitive,
                "core_gate": {k: v for k, v in core.items() if k != "tail"},
                "crust_gate": {k: v for k, v in crust.items() if k != "tail"},
            }
        )
        GATE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        GATE_CACHE.write_text(json.dumps(status, indent=2), encoding="utf-8")
        log(
            "gate_refresh_done",
            overall=overall,
            iono=iono,
            crustle_min=crustle_min,
            flg=flg,
            majkel=majkel,
        )
    else:
        status.update(cached)
        status["package_exists"] = PACKAGE.exists()
        status["from_cache"] = True

    overall = status.get("overall")
    iono = status.get("iono")
    crustle = status.get("crustle_min")
    competitive = status.get("competitive_flg_majkel")

    reasons = []
    if overall is None or overall < SHIP_OVERALL:
        reasons.append(f"overall {overall} < {SHIP_OVERALL}")
    if crustle is None or crustle < SHIP_CRUSTLE:
        reasons.append(f"crustle_min {crustle} < {SHIP_CRUSTLE}")
    if iono is None or iono < SHIP_IONO_MIN:
        reasons.append(f"iono {iono} < {SHIP_IONO_MIN}")
    if not competitive:
        reasons.append(f"flg/majkel not competitive flg={status.get('flg')} majkel={status.get('majkel')}")

    status["ship"] = len(reasons) == 0
    status["reason"] = "ok" if status["ship"] else "; ".join(reasons)
    status["thresholds"] = {
        "overall": SHIP_OVERALL,
        "crustle": SHIP_CRUSTLE,
        "iono_min": SHIP_IONO_MIN,
        "iono_ideal": SHIP_IONO_IDEAL,
    }
    return status


def append_root_state(msg: str) -> None:
    block = f"\n### Quota monitor {datetime.now().isoformat(timespec='seconds')}\n{msg}\n"
    for path in (ROOT_STATE, REPO_STATE):
        try:
            if path.exists():
                text = path.read_text(encoding="utf-8")
                marker = "## Quota reset ship monitor"
                if marker in text:
                    # append under marker
                    text = text.replace(marker, marker + block, 1)
                else:
                    text = text.rstrip() + f"\n\n---\n\n{marker}\n" + block
                path.write_text(text, encoding="utf-8")
            else:
                path.write_text(f"# STATE\n\n## Quota reset ship monitor\n{block}", encoding="utf-8")
        except Exception as e:
            log("state_write_fail", path=str(path), err=str(e))


def try_ship(status: dict, rem: int) -> bool:
    if rem <= 0:
        log("ship_skip", reason="no_quota")
        return False
    if not status.get("ship"):
        log("ship_skip", reason=status.get("reason"), remaining=rem)
        append_root_state(
            f"- **配額已恢復** remaining={rem}/5，但本地未達標：`{status.get('reason')}`\n"
            f"- overall={status.get('overall')} crustle={status.get('crustle_min')} "
            f"iono={status.get('iono')} flg={status.get('flg')} majkel={status.get('majkel')}\n"
            f"- **未提交**\n"
        )
        return False
    if not PACKAGE.exists():
        log("ship_skip", reason="package_missing")
        return False

    msg = (
        f"Archaludon auto-submit after reset overall={status.get('overall')} "
        f"crustle={status.get('crustle_min')} iono={status.get('iono')}"
    )[:100]
    # Use auto_submit path for count bookkeeping + retry
    env = kaggle_env()
    proc = subprocess.run(
        [
            PY,
            "scripts/auto_submit.py",
            "--file",
            str(PACKAGE),
            "--message",
            msg,
            "--local-gate",
            str(status.get("overall") or 0),
            "--strength-note",
            status.get("reason", "ship"),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        timeout=300,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0 and ("Successfully" in out or "success" in out.lower())
    log("ship_attempt", ok=ok, rc=proc.returncode, tail=out[-400:])
    entry = {
        "status": "OK" if ok else "FAIL",
        "file": str(PACKAGE),
        "message": msg,
        "local_gate": status.get("overall"),
        "strength_note": json.dumps(
            {k: status.get(k) for k in ("iono", "crustle_min", "flg", "majkel", "reason")},
            ensure_ascii=False,
        ),
        "submitted_at_utc": datetime.now(timezone.utc).isoformat(),
        "api_rc": proc.returncode,
        "api_output": out[-500:],
        "submits_today_after": submits_today(),
        "source": "quota_reset_ship_monitor",
    }
    # auto_submit already records on success; still write monitor log + STATE
    append_root_state(
        f"- **AUTO SUBMIT** status={'OK' if ok else 'FAIL'} remaining_before={rem}\n"
        f"- overall={status.get('overall')} crustle={status.get('crustle_min')} iono={status.get('iono')}\n"
        f"- api: ```{out[-300:]}```\n"
    )
    rec_path = ROOT / "recordings" / "metrics" / "quota_ship_events.jsonl"
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    with rec_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return ok


def cycle(recheck_gate: bool) -> dict:
    rem, detail = remaining_slots()
    log("quota_check", remaining=rem, detail=detail, local_used=submits_today())
    snap = {
        "remaining": rem,
        "detail": detail,
        "local_used": submits_today(),
        "utc_day": _today(),
    }
    if rem < 0:
        snap["action"] = "quota_unknown"
        return snap
    if rem == 0:
        snap["action"] = "quota_exhausted"
        return snap

    # Quota available
    status = evaluate_ship(recheck=recheck_gate)
    snap["gate"] = {k: v for k, v in status.items() if k not in ("core_gate", "crust_gate")}
    if status.get("ship"):
        ok = try_ship(status, rem)
        snap["action"] = "submitted" if ok else "submit_failed"
    else:
        snap["action"] = "quota_ready_waiting_local"
        append_root_state(
            f"- 配額可用 remaining=**{rem}/5**，本地未達標 → 等待升級\n"
            f"- reason: `{status.get('reason')}`\n"
            f"- overall={status.get('overall')} crustle={status.get('crustle_min')} "
            f"iono={status.get('iono')} flg={status.get('flg')} majkel={status.get('majkel')}\n"
        )
        log("waiting_local", remaining=rem, reason=status.get("reason"))
    return snap


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll-seconds", type=int, default=180)
    ap.add_argument(
        "--recheck-gate",
        action="store_true",
        help="Always re-run gates when quota > 0 (slower)",
    )
    ap.add_argument(
        "--recheck-every",
        type=int,
        default=3,
        help="When quota>0, re-run gates every N cycles (default 3)",
    )
    args = ap.parse_args()

    log(
        "monitor_start",
        ship_overall=SHIP_OVERALL,
        ship_crustle=SHIP_CRUSTLE,
        ship_iono=SHIP_IONO_MIN,
        package=str(PACKAGE),
    )
    append_root_state(
        f"- **Quota ship monitor STARTED** thresholds: overall≥{SHIP_OVERALL} "
        f"crustle≥{SHIP_CRUSTLE} iono≥{SHIP_IONO_MIN}\n"
        f"- package: `{PACKAGE}`\n"
    )

    cycle_i = 0
    while True:
        cycle_i += 1
        recheck = args.recheck_gate or (cycle_i % max(1, args.recheck_every) == 1)
        try:
            snap = cycle(recheck_gate=recheck)
            log("cycle_done", cycle=cycle_i, **{k: snap.get(k) for k in ("action", "remaining", "local_used")})
        except Exception as e:
            log("cycle_error", err=str(e))
        if args.once:
            break
        time.sleep(args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
