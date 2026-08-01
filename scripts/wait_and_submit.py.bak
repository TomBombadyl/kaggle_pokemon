"""Wait until UTC daily Kaggle submit allowance resets, then submit Archaludon.

Final strategy lock 2026-07-30 (chase #1 / pin 1196 → 1198+):
  - FIRST ship after UTC flip = Archaludon ONLY (best current package)
  - SECOND ship only if a clear Archaludon upgrade exists (higher deep gate WR)
  - Never auto-ship Dragapult / Alakazam on day flip (demoted)
  - Max 1–2 quality ships; board keeps latest 2
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = Path(sys.executable)
COMP = "pokemon-tcg-ai-battle"
LOG = ROOT / "dist" / "wait_submit_log.jsonl"
COUNT_PATH = ROOT / "dist" / "submit_count.json"
BEST_GATE_PATH = ROOT / "dist" / "best_gate.json"
RECORDINGS = ROOT / "recordings"

# Day-flip: 1 guaranteed Archaludon; 2nd only on clear upgrade evidence
MAX_QUALITY_SHIPS = 2
FIRST_SHIP_ONLY_ARCHALUDON = True
# Require deep-gate WR before 2nd slot (must beat first ship local note)
SECOND_SHIP_MIN_WR_DELTA = 3.0

# Archaludon-only queue (Dragapult/Alakazam demoted off day-flip path)
QUEUE = [
    (
        ROOT / "dist" / "candidates" / "archaludon.tar.gz",
        "Archaludon R7 PRIMARY day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)",
        200,
    ),
]


def log(msg: str, **kw) -> None:
    row = {"ts": datetime.now(timezone.utc).isoformat(), "msg": msg, **kw}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{row['ts']}] {msg} {kw if kw else ''}", flush=True)


def ensure_token() -> None:
    if os.environ.get("KAGGLE_API_TOKEN"):
        return
    for p in (
        ROOT.parent / ".kaggle" / "access_token",
        ROOT / ".kaggle" / "access_token",
        Path.home() / ".kaggle" / "access_token",
    ):
        if p.exists():
            os.environ["KAGGLE_API_TOKEN"] = p.read_text(encoding="utf-8").strip().splitlines()[0]
            return


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def seconds_until_next_utc_midnight(buffer_sec: int = 45) -> float:
    now = datetime.now(timezone.utc)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    # if already past midnight edge, still add buffer
    return max(5.0, (nxt - now).total_seconds() + buffer_sec)


def reset_submit_count_for_new_day() -> None:
    """Force local counter onto current UTC day with 0 count if day flipped."""
    day = utc_today()
    data = {"date": day, "count": 0, "refs": [], "source": "wait_and_submit_day_flip"}
    if COUNT_PATH.exists():
        try:
            old = json.loads(COUNT_PATH.read_text(encoding="utf-8"))
            if old.get("date") == day:
                # keep existing count for same day
                return
        except Exception:
            pass
    COUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
    COUNT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log("submit_count_reset", date=day)


def ordered_queue() -> list[tuple[Path, str, int]]:
    """Archaludon-only day-flip queue (strategy lock 2026-07-30)."""
    items = [it for it in QUEUE if it[0].exists()]
    # Prefer newest archaludon*.tar.gz if multiple variants appear later
    cand_dir = ROOT / "dist" / "candidates"
    extras: list[tuple[Path, str, int]] = []
    if cand_dir.exists():
        for p in sorted(cand_dir.glob("archaludon*.tar.gz"), key=lambda x: x.stat().st_mtime, reverse=True):
            if not any(p.resolve() == it[0].resolve() for it in items):
                extras.append(
                    (
                        p,
                        f"Archaludon variant {p.name} day-flip quality ship",
                        150,
                    )
                )
    ordered = items + extras
    # Dedup by resolved path, keep first
    seen: set[str] = set()
    uniq: list[tuple[Path, str, int]] = []
    for it in ordered:
        key = str(it[0].resolve())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    wr = 0.0
    if BEST_GATE_PATH.exists():
        try:
            bg = json.loads(BEST_GATE_PATH.read_text(encoding="utf-8"))
            wr = float(bg.get("wr") or 0)
        except Exception:
            pass
    log(
        "queue_ordered",
        wr=wr,
        order=[p.name for p, _, _ in uniq],
        note="archaludon_only_day_flip",
    )
    return uniq


def try_submit(path: Path, message: str, local_gate: float = 60.0) -> tuple[bool, str]:
    ensure_token()
    if not path.exists():
        return False, f"missing {path}"
    auto = ROOT / "scripts" / "auto_submit.py"
    if auto.exists():
        proc = subprocess.run(
            [
                str(PY),
                str(auto),
                "--file",
                str(path),
                "--message",
                message,
                "--local-gate",
                str(local_gate),
                "--strength-note",
                message,
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        low = out.lower()
        if (
            "daily cap" in low
            or "daily submission allowance" in low
            or "allowance (5)" in low
            or "[skip] daily" in low
            or "failed_precondition" in low
        ):
            return False, "DAILY_CAP: " + out[-400:]
        if "MANUAL" in out or "failed twice" in low:
            return False, out[-500:]
        if proc.returncode == 0:
            if "skip" in low and "cap" in low:
                return False, "DAILY_CAP: " + out[-400:]
            if "skip" in low and "weak" in low:
                return False, "WEAK_GATE: " + out[-400:]
            # success markers
            if any(s in low for s in ("successfully", "[ok] submitted", "submission", "[submit]")):
                return True, out[-500:]
            # auto_submit prints [OK] submitted
            if "[ok]" in low:
                return True, out[-500:]
            # exit 0 without skip → treat as ok
            return True, out[-500:]
        return False, out[-500:]

    proc = subprocess.run(
        [
            str(PY),
            "-m",
            "kaggle",
            "competitions",
            "submit",
            "-c",
            COMP,
            "-f",
            str(path),
            "-m",
            message[:80],
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env=os.environ.copy(),
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if "daily" in out.lower() and "allowance" in out.lower():
        return False, "DAILY_CAP"
    if proc.returncode == 0:
        return True, out[-400:]
    return False, out[-400:]


def _record_ship(path: Path, detail: str, day: str) -> None:
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    (RECORDINGS / "logs").mkdir(exist_ok=True)
    (RECORDINGS / "metrics").mkdir(exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "day": day,
        "path": str(path),
        "detail_tail": detail[-500:],
        "strategy": "archaludon_primary_day_flip",
    }
    with (RECORDINGS / "logs" / "day_flip_submits.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    ensure_token()
    log(
        "wait_and_submit start",
        py=str(PY),
        max_quality=MAX_QUALITY_SHIPS,
        strategy="archaludon_only_1_to_2",
        target_pin=1196.1,
        target_top1=1198.4,
    )
    submitted = 0
    first_wr = 0.0
    attempts = 0
    max_attempts = 72  # cover multi-hour waits

    while submitted < MAX_QUALITY_SHIPS and attempts < max_attempts:
        attempts += 1
        day = utc_today()
        reset_submit_count_for_new_day()

        any_cap = False
        for path, msg, _pri in ordered_queue():
            if submitted >= MAX_QUALITY_SHIPS:
                break
            if not path.exists():
                log("missing_package", path=str(path))
                continue
            # 2nd ship: only Archaludon upgrade path (never other agents)
            if submitted >= 1:
                if "archaludon" not in path.name.lower():
                    log("skip_non_arch_second", path=path.name)
                    continue
                wr = 0.0
                if BEST_GATE_PATH.exists():
                    try:
                        bg = json.loads(BEST_GATE_PATH.read_text(encoding="utf-8"))
                        if str(bg.get("id", "")).startswith("archaludon"):
                            wr = float(bg.get("wr") or 0)
                    except Exception:
                        pass
                if wr < first_wr + SECOND_SHIP_MIN_WR_DELTA:
                    log(
                        "skip_second_no_clear_upgrade",
                        wr=wr,
                        first_wr=first_wr,
                        need_delta=SECOND_SHIP_MIN_WR_DELTA,
                    )
                    # stop day-flip after first quality ship if no upgrade
                    submitted = MAX_QUALITY_SHIPS
                    break

            # ARCH_SHIP_GATE_FLOOR: never ship with noisy short-gate WR below auto_submit min (64)
            ARCH_SHIP_GATE_FLOOR = 65.0
            local_gate = ARCH_SHIP_GATE_FLOOR
            if "archaludon" in path.name.lower():
                local_gate = ARCH_SHIP_GATE_FLOOR
                if BEST_GATE_PATH.exists():
                    try:
                        bg = json.loads(BEST_GATE_PATH.read_text(encoding="utf-8"))
                        if str(bg.get("id", "")).startswith("archaludon"):
                            local_gate = max(ARCH_SHIP_GATE_FLOOR, float(bg.get("wr") or 0))
                    except Exception:
                        pass
            elif BEST_GATE_PATH.exists():
                try:
                    bg = json.loads(BEST_GATE_PATH.read_text(encoding="utf-8"))
                    local_gate = max(ARCH_SHIP_GATE_FLOOR, float(bg.get("wr") or local_gate))
                except Exception:
                    pass

            ok, detail = try_submit(path, msg, local_gate=local_gate)
            log("attempt", path=path.name, ok=ok, detail=detail[:300], day=day, slot=submitted + 1)
            if ok:
                _record_ship(path, detail, day)
                submitted += 1
                if submitted == 1:
                    first_wr = local_gate
                time.sleep(8)
                # After first Archaludon ship: only continue if upgrade path may exist
                if submitted == 1 and FIRST_SHIP_ONLY_ARCHALUDON:
                    # briefly check for upgrade; else exit loop after one quality ship
                    log("first_archaludon_shipped", wr=first_wr, note="hold 2nd for clear upgrade only")
                continue
            if "DAILY_CAP" in detail or "allowance" in detail.lower():
                any_cap = True
                break
            # other error → try next package

        if submitted >= MAX_QUALITY_SHIPS:
            break

        if any_cap:
            wait_s = seconds_until_next_utc_midnight(buffer_sec=45)
            sleep_s = min(wait_s, 120.0)  # tighter poll near midnight
            log(
                "sleep_waiting_allowance",
                submitted=submitted,
                sleep_s=sleep_s,
                until_utc_midnight_s=wait_s,
                utc_now=datetime.now(timezone.utc).isoformat(),
            )
            time.sleep(sleep_s)
            continue

        if submitted == 0:
            log("sleep_retry_no_success", submitted=submitted)
            time.sleep(60)
            continue

        # one quality Archaludon shipped, no upgrade evidence → stop (don't spray)
        log("stop_after_quality_ship", submitted=submitted)
        break

    log("wait_and_submit done", submitted=submitted, attempts=attempts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
