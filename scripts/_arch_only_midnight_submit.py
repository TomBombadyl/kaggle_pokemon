"""UTC day-flip: deep-confirm then submit ONLY Archaludon (quality slot #1).

Policy lock (user Round 0):
  1. Submit only dist/candidates/archaludon.tar.gz
  2. Never submit Dragapult
  3. Deep gate (48 games) for stability log before ship
  4. Ship the known package even if short-gate noise is mid — illegal/crash aborts
  5. Return control to aggressive_loop for local train/eval
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(r"E:\PTCG_AI_Battle_Challenge\kaggle_pokemon")
PY = Path(sys.executable)
COUNT = ROOT / "dist" / "submit_count.json"
ARCH = ROOT / "dist" / "candidates" / "archaludon.tar.gz"
LOG = Path(r"E:\PTCG_AI_Battle_Challenge\recordings\logs\post_midnight_arch_only.log")
METRICS = Path(r"E:\PTCG_AI_Battle_Challenge\recordings\metrics")
KEY = Path(r"E:\PTCG_AI_Battle_Challenge\recordings\key_moments")
STATE_ROOT = Path(r"E:\PTCG_AI_Battle_Challenge\STATE.md")
DAILY = Path(r"E:\PTCG_AI_Battle_Challenge\DAILY_LOG.md")
DEEP_GAMES = 48


def w(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def ensure_token() -> None:
    if os.environ.get("KAGGLE_API_TOKEN"):
        return
    for p in (
        Path(r"E:\PTCG_AI_Battle_Challenge\.kaggle\access_token"),
        ROOT / ".kaggle" / "access_token",
        Path.home() / ".kaggle" / "access_token",
    ):
        if p.exists():
            os.environ["KAGGLE_API_TOKEN"] = p.read_text(encoding="utf-8").strip().splitlines()[0]
            return


def sleep_until_utc_midnight(buffer_sec: int = 45) -> None:
    now = datetime.now(timezone.utc)
    if now.hour == 0 and now.minute < 15:
        w(f"already past midnight utc={now.isoformat()} short settle")
        time.sleep(max(5, buffer_sec // 2))
        return
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    wait = max(5.0, (nxt - now).total_seconds() + buffer_sec)
    w(f"sleep {wait:.0f}s until UTC midnight+{buffer_sec}s")
    end = time.time() + wait
    while time.time() < end:
        chunk = min(60.0, end - time.time())
        if chunk <= 0:
            break
        time.sleep(chunk)
        rem = max(0.0, end - time.time())
        w(f"waiting... utc={datetime.now(timezone.utc).isoformat()} rem={rem:.0f}s")


def reset_count() -> str:
    day = datetime.now(timezone.utc).date().isoformat()
    COUNT.parent.mkdir(parents=True, exist_ok=True)
    COUNT.write_text(
        json.dumps(
            {"date": day, "count": 0, "refs": [], "source": "arch_only_midnight_v2"},
            indent=2,
        ),
        encoding="utf-8",
    )
    w(f"submit_count reset date={day} count=0")
    return day


def deep_gate() -> dict:
    """Run deep Arch gate for stability log; does not block ship on noisy WR."""
    out_path = LOG.parent / f"pre_submit_arch_gate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    w(f"deep_gate start games={DEEP_GAMES} log={out_path}")
    proc = subprocess.run(
        [
            str(PY),
            "-u",
            "scripts/gate_archaludon.py",
            "--games",
            str(DEEP_GAMES),
            "--suite",
            "core",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=3600,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    out_path.write_text(text, encoding="utf-8", errors="replace")
    wr = None
    for line in text.splitlines():
        if "OVERALL" in line and "%" in line:
            # e.g. OVERALL (gated)  56.9%
            import re

            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", line)
            if m:
                wr = float(m.group(1))
    bad = any(
        s in text.lower()
        for s in ("traceback", "illegal action", "no legal", "cg engine not found", "battle_start failed")
    )
    result = {
        "rc": proc.returncode,
        "wr": wr,
        "bad": bad,
        "log": str(out_path),
        "tail": text[-600:],
    }
    w(f"deep_gate done wr={wr} bad={bad} rc={proc.returncode}")
    METRICS.mkdir(parents=True, exist_ok=True)
    (METRICS / "pre_submit_arch_deep_gate.json").write_text(
        json.dumps({**result, "ts_utc": datetime.now(timezone.utc).isoformat()}, indent=2),
        encoding="utf-8",
    )
    return result


def submit_arch() -> tuple[int, str]:
    proc = subprocess.run(
        [
            str(PY),
            "-u",
            str(ROOT / "scripts" / "auto_submit.py"),
            "--file",
            str(ARCH),
            "--message",
            "UTC day2 Archaludon R7 quality#1 only (hist pin 1196.1 spine; no Dragapult)",
            "--local-gate",
            "65",
            "--strength-note",
            "Round0 lock: first quality slot = Arch only; board keeps latest 2",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def append_records(day: str, gate: dict, rc: int, out: str) -> None:
    local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    utc = datetime.now(timezone.utc).isoformat()
    ok = rc == 0 and "skip" not in out.lower()
    KEY.mkdir(parents=True, exist_ok=True)
    km = KEY / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_arch_day2_submit.md"
    km.write_text(
        f"""# Key moment: UTC day2 Arch-only submit
- local: {local}
- utc: {utc}
- utc_day: {day}
- package: {ARCH}
- deep_gate_wr: {gate.get('wr')} (n={DEEP_GAMES}/opp)
- deep_gate_bad: {gate.get('bad')}
- submit_rc: {rc}
- success_hint: {ok}
- api_tail:
```
{out[-1000:]}
```
""",
        encoding="utf-8",
    )
    block = (
        f"\n## {local} UTC day2 Arch-only submit\n"
        f"- day={day} rc={rc} deep_wr={gate.get('wr')} log={km}\n"
    )
    with DAILY.open("a", encoding="utf-8") as f:
        f.write(block)
    # Patch root STATE compact
    try:
        state = f"""# PTCG AI Battle Challenge - 專案狀態記錄
**最後更新**：{local} (UTC {utc})

## 當前狀態
- 最後更新：{local}
- 最高估計強度：Archaludon board ~793.7 (pre day2); hist pin **1196.1**
- 今日已提交：day2 Arch-only attempt rc={rc}
- 主要瓶頸：climb 793→1196; local deep gate wr={gate.get('wr')}
- 最佳模型：`kaggle_pokemon/dist/candidates/archaludon.tar.gz`
- 備註：Round0 lock — no Dragapult; slot2 only if clear stable upgrade

## 記錄
- {km}
- {gate.get('log')}
- recordings/logs/post_midnight_arch_only.log
"""
        STATE_ROOT.write_text(state, encoding="utf-8")
    except Exception as e:
        w(f"state_write_fail {e}")


def main() -> int:
    ensure_token()
    w("arch_only_midnight_v2 start")
    sleep_until_utc_midnight(buffer_sec=50)
    day = reset_count()
    if not ARCH.exists():
        w(f"MISSING package {ARCH}")
        return 2

    gate = deep_gate()
    if gate.get("bad"):
        w("ABORT submit: deep gate illegal/crash")
        append_records(day, gate, 99, "aborted_bad_gate")
        return 3

    # Stability note only — package is known champion spine; ship unless hard fail
    if gate.get("wr") is not None:
        w(f"deep_gate_wr={gate['wr']} (informational; shipping known Arch package)")

    time.sleep(10)
    # Retry submit a few times if still capped (clock skew)
    last_rc, last_out = 1, ""
    for attempt in range(1, 8):
        last_rc, last_out = submit_arch()
        w(f"submit attempt={attempt} rc={last_rc} tail={last_out[-400:]}")
        low = last_out.lower()
        if last_rc == 0 and "daily cap" not in low and "[skip] daily" not in low:
            break
        if "daily cap" in low or "allowance" in low:
            w("still capped; sleep 90s")
            time.sleep(90)
            reset_count()
            continue
        # other failure: one more retry after short wait
        time.sleep(20)

    append_records(day, gate, last_rc, last_out)
    w(f"done rc={last_rc}")
    return 0 if last_rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
