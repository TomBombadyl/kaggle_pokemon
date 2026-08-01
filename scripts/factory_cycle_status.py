#!/usr/bin/env python3
"""Factory cycle status table — PID / cycle / gates / bottleneck. Never starts workers."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "aggressive" / "factory_cycle_status.md"
JSONL = ROOT / "recordings" / "metrics" / "factory_status.jsonl"
FOCUS_LATEST = ROOT / "recordings" / "metrics" / "focus_latest.json"
FOCUS_HIST = ROOT / "recordings" / "metrics" / "focus_history.jsonl"
LOOP_LOG = ROOT / "dist" / "loop_log.jsonl"
MCTS_METRICS = ROOT / "rl_mcts_field" / "lucarioex_v2" / "metrics.csv"
BEST_GATE = ROOT / "dist" / "best_gate.json"

PATTERNS = {
    "aggressive_loop": re.compile(r"aggressive_loop\.py"),
    "continuous_focus_gates": re.compile(r"continuous_focus_gates\.py"),
    "train_lucario_MCTS": re.compile(r"train_lucario_field_mcts\.py"),
    "gate_archaludon": re.compile(r"gate_archaludon\.py"),
}


def _procs() -> list[dict]:
    rows = []
    if psutil is None:
        return rows
    for p in psutil.process_iter(["pid", "name", "cmdline", "memory_info", "create_time", "cpu_percent"]):
        try:
            if not p.info["name"] or "python" not in (p.info["name"] or "").lower():
                continue
            cmd = " ".join(p.info.get("cmdline") or [])
            if not cmd:
                continue
            label = None
            for k, pat in PATTERNS.items():
                if pat.search(cmd):
                    label = k
                    break
            if not label:
                continue
            py = "venv" if ".venv" in cmd else ("sys" if "Python312" in cmd else "other")
            mem = (p.info.get("memory_info").rss / (1024 * 1024)) if p.info.get("memory_info") else 0
            rows.append(
                {
                    "label": label,
                    "pid": p.info["pid"],
                    "py": py,
                    "mem_mb": round(mem, 0),
                    "cmd_tail": cmd[-80:],
                }
            )
        except (psutil.Error, TypeError, AttributeError):
            continue
    return rows


def _latest_focus() -> dict:
    if FOCUS_LATEST.exists():
        try:
            return json.loads(FOCUS_LATEST.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _rolling(key: str, n: int = 20) -> dict:
    if not FOCUS_HIST.exists():
        return {}
    vals = []
    for line in FOCUS_HIST.read_text(encoding="utf-8", errors="replace").splitlines()[-n * 2 :]:
        if not line.strip():
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        v = o.get(key)
        if v is not None:
            vals.append(float(v))
    vals = vals[-n:]
    if not vals:
        return {}
    return {
        "n": len(vals),
        "mean": round(sum(vals) / len(vals), 1),
        "min": round(min(vals), 1),
        "max": round(max(vals), 1),
        "last": round(vals[-1], 1),
    }


def _loop_arch() -> dict:
    if not LOOP_LOG.exists():
        return {}
    last = None
    recent = []
    for line in LOOP_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]:
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("event") == "gate" and o.get("id") == "archaludon":
            last = o
            if o.get("wr") is not None:
                recent.append(float(o["wr"]))
        if o.get("event") == "cycle_done":
            last_cycle = o
    out = {"recent_wr": recent[-8:], "mean8": round(sum(recent[-8:]) / len(recent[-8:]), 1) if recent else None}
    if last:
        out["last_wr"] = last.get("wr")
        out["last_ok"] = last.get("ok")
        # parse matchups from tail if present
        tail = last.get("tail") or ""
        for name in ("real_iono", "meta_crustle_flg", "meta_crustle_majkel", "meta_grimmsnarl_dries", "meta_grimmsnarl_luca"):
            m = re.search(rf"{name}\s+\([^)]*\)\s+([0-9.]+)\s*%", tail)
            if m:
                out[name] = float(m.group(1))
    if "last_cycle" in dir():
        pass
    # cycle from latest cycle_done
    for line in reversed(LOOP_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]):
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("event") == "cycle_done":
            st = o.get("status") or {}
            out["loop_cycle"] = st.get("cycle") or o.get("cycle")
            out["submits"] = st.get("submits_today")
            break
    return out


def _bottleneck(focus: dict, loop: dict, roll: dict) -> str:
    parts = []
    iono = focus.get("iono_wr")
    if iono is not None and iono < 55:
        parts.append(f"Iono {iono}% (ship floor 55%, Arch≥85% needs ~55–60%)")
    maj = focus.get("majkel_wr")
    if maj is not None and maj < 89:
        parts.append(f"Crustle majkel {maj}% (<89%)")
    dual = focus.get("dual_overall")
    if dual is not None and dual < 95:
        parts.append(f"dual {dual}% (<95%)")
    arch = loop.get("last_wr")
    if arch is not None and arch < 85:
        parts.append(f"Arch sprint {arch}% (<85%)")
    if not parts:
        return "none — all local bars clear or within noise"
    return "; ".join(parts)


def render() -> dict:
    focus = _latest_focus()
    loop = _loop_arch()
    procs = _procs()
    roll = {
        "iono": _rolling("iono_wr"),
        "majkel": _rolling("majkel_wr"),
        "flg": _rolling("flg_wr"),
        "dual": _rolling("dual_overall"),
    }
    best = {}
    if BEST_GATE.exists():
        try:
            best = json.loads(BEST_GATE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Prefer worker PIDs (sys / high mem) for display
    by_label: dict[str, list] = {}
    for r in procs:
        by_label.setdefault(r["label"], []).append(r)

    ts = datetime.now(timezone.utc).isoformat()
    row = {
        "ts": ts,
        "focus_cycle": focus.get("cycle"),
        "loop_cycle": loop.get("loop_cycle"),
        "iono_wr": focus.get("iono_wr"),
        "majkel_wr": focus.get("majkel_wr"),
        "flg_wr": focus.get("flg_wr"),
        "dual_overall": focus.get("dual_overall"),
        "arch_sprint_wr": loop.get("last_wr"),
        "arch_mean8": loop.get("mean8"),
        "best_gate": best,
        "rolling": roll,
        "procs": procs,
        "bottleneck": _bottleneck(focus, loop, roll),
        "targets": {"arch_sprint": 85.0, "dual": 95.0, "crustle": 89.0, "iono_ship": 55.0},
        "policy": "Arch 75wr + Crustle lever; no auto-submit Dra/Alak; local only",
    }

    # Markdown table
    lines = [
        f"# Factory cycle status",
        f"",
        f"**UTC:** {ts}  ",
        f"**Policy:** Archaludon 75wr shell + Crustle lever · loop + CUDA MCTS · no Dra/Alak submit  ",
        f"**Bottleneck:** {row['bottleneck']}",
        f"",
        f"## Gates (latest)",
        f"",
        f"| Metric | Latest | Rolling20 mean | Target | Gap |",
        f"|--------|-------:|---------------:|-------:|----:|",
    ]

    def gap(val, tgt):
        if val is None:
            return "—"
        d = float(val) - tgt
        return f"{d:+.1f}"

    metrics = [
        ("Arch sprint overall", loop.get("last_wr"), roll.get("dual") and loop.get("mean8"), 85.0),
        ("Iono", focus.get("iono_wr"), (roll.get("iono") or {}).get("mean"), 55.0),
        ("Crustle flg", focus.get("flg_wr"), (roll.get("flg") or {}).get("mean"), 89.0),
        ("Crustle majkel", focus.get("majkel_wr"), (roll.get("majkel") or {}).get("mean"), 89.0),
        ("Dual overall", focus.get("dual_overall"), (roll.get("dual") or {}).get("mean"), 95.0),
    ]
    for name, latest, mean, tgt in metrics:
        lv = f"{latest:.1f}%" if latest is not None else "—"
        mv = f"{mean:.1f}%" if mean is not None else "—"
        lines.append(f"| {name} | {lv} | {mv} | {tgt:.0f}% | {gap(latest, tgt)} |")

    lines += [
        f"",
        f"**Focus cycle:** {focus.get('cycle')} · **Loop cycle:** {loop.get('loop_cycle')} · "
        f"**Submits today:** {loop.get('submits')} · **Arch mean8:** {loop.get('mean8')}",
        f"",
        f"## Processes (do not kill parent/child pairs)",
        f"",
        f"| Role | PID | Py | MemMB |",
        f"|------|----:|----|------:|",
    ]
    for r in sorted(procs, key=lambda x: (x["label"], x["py"] != "sys", x["pid"])):
        lines.append(f"| {r['label']} | {r['pid']} | {r['py']} | {r['mem_mb']:.0f} |")
    if not procs:
        lines.append("| (psutil missing or no workers) | — | — | — |")

    lines += [
        f"",
        f"## Matchup snapshot (last Arch sprint gate)",
        f"",
    ]
    for k in ("real_iono", "meta_crustle_flg", "meta_crustle_majkel", "meta_grimmsnarl_dries", "meta_grimmsnarl_luca"):
        if k in loop:
            lines.append(f"- `{k}`: **{loop[k]}%**")
    lines += [
        f"",
        f"## Next μ action",
        f"",
        f"1. Keep workers healthy (venv launcher + sys worker pairs are normal).",
        f"2. Default Iono lever **r14n**; candidate **r14v** A/B (pre-MD soft engine) — promote only if +3pp @ n≥200 + crustle guard.",
        f"3. Hold Crustle levers; majkel/flg must stay ≥89% rolling (target dual 95%+).",
        f"4. No Dra/Alak auto-submit; Arch only when iono≥55 + arch≥83 + crustle≥89.",
        f"",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    JSONL.parent.mkdir(parents=True, exist_ok=True)
    with JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=90, help="seconds between status writes")
    args = ap.parse_args()
    while True:
        row = render()
        print(
            f"[status] focus={row.get('focus_cycle')} loop={row.get('loop_cycle')} "
            f"iono={row.get('iono_wr')} dual={row.get('dual_overall')} arch={row.get('arch_sprint_wr')} "
            f"| {row.get('bottleneck')}",
            flush=True,
        )
        if args.once:
            return 0
        time.sleep(max(30, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
