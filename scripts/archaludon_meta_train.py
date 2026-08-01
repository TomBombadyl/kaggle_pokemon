#!/usr/bin/env python3
"""High-intensity Archaludon meta gauntlet vs Grimmsnarl / Crustle / Alakazam / Iono / Dragapult.

Runs repeatedly, logs WR, writes best to dist/best_gate.json + recordings/metrics.
Also watches episodes/raw/2026-07-27 for completed zip → unzip + mine.

Does NOT submit. Pair with aggressive_loop for ship decisions.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PY = Path(sys.executable)
LOG = ROOT / "recordings" / "logs" / "archaludon_meta_train.jsonl"
METRICS = ROOT / "recordings" / "metrics"
BEST = ROOT / "dist" / "best_gate.json"
DAY27 = ROOT / "episodes" / "raw" / "2026-07-27"


def log(event: str, **kw) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kw}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{row['ts']}] {event} {json.dumps(kw, ensure_ascii=False) if kw else ''}", flush=True)


def run_gate(suite: str, games: int) -> tuple[int, str, float | None]:
    cmd = [
        str(PY),
        "scripts/gate_archaludon.py",
        "--games",
        str(games),
        "--suite",
        suite,
        "--report",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=7200)
    out = (p.stdout or "") + (p.stderr or "")
    wr = None
    m = re.search(r"OVERALL[^\n]*?([0-9]+(?:\.[0-9]+)?)\s*%", out, re.I)
    if m:
        wr = float(m.group(1))
    return p.returncode, out, wr


def run_gate_opponents(opponents: list[str], games: int) -> tuple[int, str, float | None]:
    cmd = [
        str(PY),
        "scripts/gate_archaludon.py",
        "--games",
        str(games),
        "--opponents",
        *opponents,
        "--report",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=7200)
    out = (p.stdout or "") + (p.stderr or "")
    wr = None
    m = re.search(r"OVERALL[^\n]*?([0-9]+(?:\.[0-9]+)?)\s*%", out, re.I)
    if m:
        wr = float(m.group(1))
    return p.returncode, out, wr


def maybe_process_day27() -> None:
    if not DAY27.exists():
        return
    ready = DAY27 / ".ready"
    if ready.exists():
        return
    zips = list(DAY27.glob("*.zip"))
    # complete if zip ~700MB+ and no .kaggle-partial growing
    partial = list(DAY27.glob("*.kaggle-partial"))
    good = [z for z in zips if z.stat().st_size > 700_000_000]
    if not good:
        return
    if partial and any(p.stat().st_size < 1000 for p in partial):
        # still downloading
        return
    z = max(good, key=lambda p: p.stat().st_size)
    log("day27_unzip_start", zip=z.name, size=z.stat().st_size)
    try:
        with zipfile.ZipFile(z, "r") as zf:
            zf.extractall(DAY27)
    except Exception as e:
        log("day27_unzip_fail", err=str(e))
        return
    n = sum(1 for _ in DAY27.rglob("*.json"))
    ready.write_text(f"n={n}\n", encoding="utf-8")
    log("day27_unzip_done", n_json=n)
    # mine
    for args in (
        [
            "scripts/extract_gauntlet_from_replays.py",
            "--replays",
            str(DAY27),
            "--out",
            "report/deck_rl/mined_decks",
            "--max-decks",
            "80",
        ],
        [
            "scripts/mine_episode_decks.py",
            "--episodes",
            str(DAY27),
            "--out-dir",
            "agent_decks",
            "--leaders",
            "--report",
            "recordings/metrics/mined_decks_2026-07-27.md",
        ],
    ):
        p = subprocess.run([str(PY), *args], cwd=str(ROOT), capture_output=True, text=True, timeout=3600)
        log("day27_mine", cmd=args[0], rc=p.returncode, tail=((p.stdout or "") + (p.stderr or ""))[-400:])
    mined = ROOT / "report" / "deck_rl" / "mined_decks"
    field = ROOT / "field" / "decks" / "mined_top"
    field.mkdir(parents=True, exist_ok=True)
    if mined.exists():
        for csvp in mined.glob("*.csv"):
            shutil.copy2(csvp, field / csvp.name)
    try:
        z.unlink()
    except OSError:
        pass
    log("day27_pipeline_complete", n_json=n)


def save_best(wr: float, suite: str, games: int, tail: str) -> None:
    BEST.parent.mkdir(parents=True, exist_ok=True)
    prev = 0.0
    if BEST.exists():
        try:
            prev = float(json.loads(BEST.read_text(encoding="utf-8")).get("wr") or 0)
        except Exception:
            pass
    if wr >= prev:
        payload = {
            "id": "archaludon",
            "wr": wr,
            "suite": suite,
            "games_per_opp": games,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tail": tail[-600:],
        }
        BEST.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        METRICS.mkdir(parents=True, exist_ok=True)
        (METRICS / "archaludon_best_gate.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        log("best_updated", wr=wr, prev=prev, suite=suite)


def main() -> int:
    log("meta_train_start", focus=["grimmsnarl", "crustle", "alakazam", "iono", "dragapult"])
    cycle = 0
    # Schedule: deep dual, deep meta, deep alakazam, core
    plan = [
        ("dual", 40),
        ("sprint", 48),  # leads with real_iono
        ("meta", 32),
        ("alakazam", 40),
        ("top6", 24),
        ("core", 40),
    ]
    iono_history: list[float] = []
    while True:
        cycle += 1
        maybe_process_day27()
        # Every cycle: deep Iono-only probe (primary bottleneck)
        try:
            irc, iout, iwr = run_gate_opponents(["real_iono"], 50)
            log("iono_probe", cycle=cycle, rc=irc, wr=iwr, tail=iout[-300:])
            if iwr is not None:
                iono_history.append(iwr)
                iono_history = iono_history[-8:]
                avg = sum(iono_history) / len(iono_history)
                (METRICS / "iono_progress.json").write_text(
                    json.dumps(
                        {
                            "latest": iwr,
                            "avg_last_n": avg,
                            "n": len(iono_history),
                            "history": iono_history,
                            "target": 55.0,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                if iwr >= 55.0 and avg >= 55.0:
                    log("iono_breakthrough", wr=iwr, avg=avg)
        except Exception as e:
            log("iono_probe_fail", err=str(e))

        suite, games = plan[(cycle - 1) % len(plan)]
        log("gate_start", cycle=cycle, suite=suite, games=games)
        try:
            rc, out, wr = run_gate(suite, games)
        except Exception as e:
            log("gate_crash", err=str(e))
            time.sleep(30)
            continue
        log("gate_done", cycle=cycle, suite=suite, rc=rc, wr=wr, tail=out[-500:])
        if wr is not None:
            save_best(wr, suite, games, out)
            # Ship only if dual-like overall >=66 AND recent Iono avg >=55
            iono_ok = bool(iono_history) and (sum(iono_history) / len(iono_history) >= 55.0)
            if wr >= 66.0 and iono_ok:
                flag = ROOT / "dist" / "archaludon_ship_signal.json"
                flag.write_text(
                    json.dumps(
                        {
                            "wr": wr,
                            "suite": suite,
                            "games": games,
                            "iono_avg": sum(iono_history) / len(iono_history),
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "note": "Iono stable >=55 and suite WR >=66 — quality slot OK",
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                log("ship_signal", wr=wr, suite=suite, iono_avg=sum(iono_history) / len(iono_history))
        time.sleep(5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
