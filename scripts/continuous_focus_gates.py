#!/usr/bin/env python3
"""Never-stop focus gates: Iono 鈫?majkel 鈫?flg 鈫?dual sample; write metrics.

Runs forever; failures logged and loop continues.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
LOG = ROOT / "report" / "aggressive"
METRICS = ROOT / "recordings" / "metrics"
METRICS.mkdir(parents=True, exist_ok=True)
LOG.mkdir(parents=True, exist_ok=True)

# Ensure meta crustle random brains
def _fix_registry() -> None:
    reg_path = ROOT / "field" / "registry.json"
    try:
        r = json.loads(reg_path.read_text(encoding="utf-8"))
        for k, v in r.get("opponents", {}).items():
            if "crustle" in k or k.startswith("top_lb_") or "grimmsnarl" in k:
                if "alakazam" not in k:
                    v["opponent_brain"] = "random"
        # sprint/dual include iono for ship floor
        r.setdefault("suites", {})["dual"] = [
            "meta_crustle_flg",
            "meta_crustle_majkel",
            "meta_grimmsnarl_dries",
            "meta_grimmsnarl_luca",
            "meta_grimmsnarl_liamk",
        ]
        r["suites"]["sprint"] = [
            "real_iono",
            "meta_crustle_flg",
            "meta_crustle_majkel",
            "meta_grimmsnarl_dries",
            "meta_grimmsnarl_luca",
        ]
        if "meta_grimmsnarl_liamk" not in r["opponents"] and "meta_grimmsnarl_liamak" in r["opponents"]:
            r["opponents"]["meta_grimmsnarl_liamk"] = dict(r["opponents"]["meta_grimmsnarl_liamak"])
            r["opponents"]["meta_grimmsnarl_liamk"]["opponent_brain"] = "random"
        reg_path.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[warn] registry fix: {e}", flush=True)


def run_gate(args: list[str], timeout: int = 3600) -> tuple[int, str]:
    cmd = [PY, "-u", str(ROOT / "scripts" / "gate_archaludon.py")] + args
    try:
        env = {**dict(**{k: v for k, v in __import__("os").environ.items()})}
        # Iono KEEP lever (2026-07-31): tomato matchup-gated sample_75wr delegate
        env["ARCH_IONO_LEVER"] = __import__("os").environ.get("FOCUS_IONO_LEVER") or "tomato"
        p = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or "") + (e.stderr or "") + "\nTIMEOUT"
    except Exception as e:
        return 1, str(e)


def parse_wr(out: str, opp_key: str) -> float | None:
    import re

    # line like: real_iono (iono) 52.5% ...
    m = re.search(
        rf"{re.escape(opp_key)}\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%",
        out,
    )
    if m:
        return float(m.group(1))
    m = re.search(r"OVERALL \(gated\)\s+([0-9]+(?:\.[0-9]+)?)\s*%", out)
    if m:
        return float(m.group(1))
    return None


def parse_all_opp_wr(out: str) -> dict[str, float]:
    import re

    found = {}
    for m in re.finditer(
        r"^(\S+)\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%",
        out,
        re.M,
    ):
        found[m.group(1)] = float(m.group(2))
    m = re.search(r"OVERALL \(gated\)\s+([0-9]+(?:\.[0-9]+)?)\s*%", out)
    if m:
        found["OVERALL"] = float(m.group(1))
    return found


def append_metrics(row: dict) -> None:
    path = METRICS / "focus_history.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    latest = METRICS / "focus_latest.json"
    latest.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
    # Director ship floors on every focus cycle (no submit from here)
    try:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from director_gate import (  # type: ignore
            evaluate_ship,
            load_ship_snapshot,
            log_decision,
            maybe_raise_baseline,
            snapshot_from_focus_row,
        )

        # Instant row for history; ship authority = pooled N + loop Arch WR.
        instant = snapshot_from_focus_row(row)
        snap = load_ship_snapshot() or instant
        # submits=0 so decision reflects gate floors only (focus never ships)
        verdict = evaluate_ship(snap, submits_today=0)
        row["ship_ready"] = bool(verdict.ship)
        row["ship_decision"] = verdict.decision
        row["ship_reasons"] = verdict.reasons
        row["ship_source"] = getattr(snap, "source", "")
        row["ship_iono_pool"] = snap.iono
        row["ship_crustle_pool"] = snap.crustle_floor_value()
        row["ship_dual_pool"] = snap.dual_overall
        row["ship_arch"] = snap.arch_overall
        latest.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
        log_decision(verdict, source="continuous_focus_gates", cycle=row.get("cycle"))
        if verdict.ship:
            maybe_raise_baseline(snap)
            print(
                f"[focus] SHIP_READY cycle={row.get('cycle')} "
                f"pool_iono={snap.iono} crust={snap.crustle_floor_value()} dual={snap.dual_overall}",
                flush=True,
            )
        else:
            print(
                f"[focus] HOLD cycle={row.get('cycle')} decision={verdict.decision} "
                f"reasons={verdict.reasons} instant_iono={row.get('iono_wr')}",
                flush=True,
            )
    except Exception as e:
        print(f"[focus] director_gate skip: {e}", flush=True)


def cycle(n: int) -> dict:
    _fix_registry()
    row: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cycle": n,
        "iono_wr": None,
        "majkel_wr": None,
        "flg_wr": None,
        "dual_overall": None,
        "ok": True,
    }
    jobs = [
        ("iono", ["--games", "40", "--opponents", "real_iono"], "real_iono", "iono_wr"),
        ("majkel", ["--games", "60", "--opponents", "meta_crustle_majkel"], "meta_crustle_majkel", "majkel_wr"),
        ("flg", ["--games", "40", "--opponents", "meta_crustle_flg"], "meta_crustle_flg", "flg_wr"),
        (
            "dual",
            [
                "--games",
                "24",
                "--opponents",
                "meta_crustle_flg",
                "meta_crustle_majkel",
                "meta_grimmsnarl_dries",
                "meta_grimmsnarl_luca",
                "meta_grimmsnarl_liamk",
            ],
            "OVERALL",
            "dual_overall",
        ),
    ]
    for name, args, key, field in jobs:
        print(f"[focus] cycle={n} job={name} ...", flush=True)
        code, out = run_gate(args)
        wrs = parse_all_opp_wr(out)
        wr = wrs.get(key) if key != "OVERALL" else wrs.get("OVERALL")
        if wr is None:
            wr = parse_wr(out, key)
        row[field] = wr
        row[f"{name}_rc"] = code
        # log tail
        with (LOG / f"focus_{name}.log").open("a", encoding="utf-8") as f:
            f.write(f"\n=== cycle {n} rc={code} wr={wr} ===\n")
            f.write(out[-2500:])
        print(f"[focus] {name} wr={wr} rc={code}", flush=True)
        if code != 0 and wr is None:
            row["ok"] = False
    append_metrics(row)
    return row


def main() -> int:
    print("[focus] continuous_focus_gates START", flush=True)
    n = 0
    while True:
        n += 1
        try:
            row = cycle(n)
            print(f"[focus] cycle_done {row}", flush=True)
        except Exception:
            print("[focus] ERROR\n" + traceback.format_exc(), flush=True)
            with (LOG / "focus_errors.log").open("a", encoding="utf-8") as f:
                f.write(traceback.format_exc() + "\n")
        time.sleep(5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

