#!/usr/bin/env python3
"""Anti-meta local training director for the Archaludon primary lane.

This is intentionally local-only: it collects/validates Iono data, trains a
schema-v2 fragile-board-weighted prior, writes an audit report, and prints the
pooled gates that must pass before any package can be considered.

It does not edit the runtime agent and it never submits to Kaggle.

Typical use
-----------
  python scripts/anti_meta_train_director.py --mode plan

  python scripts/anti_meta_train_director.py --mode train --device auto \
    --epochs 40 --batch-size 8192

  python scripts/anti_meta_train_director.py --mode full --collect-games 1200 \
    --device auto --epochs 40 --gate
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
METRICS = ROOT / "recordings" / "metrics"
REPORT = ROOT / "report" / "anti_meta_train"
METRICS.mkdir(parents=True, exist_ok=True)
REPORT.mkdir(parents=True, exist_ok=True)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run(cmd: list[str], *, env: dict[str, str] | None = None, timeout: int = 7200) -> dict[str, Any]:
    t0 = time.time()
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        timeout=timeout,
    )
    out = (p.stdout or "") + (p.stderr or "")
    return {
        "cmd": cmd,
        "rc": p.returncode,
        "elapsed_s": round(time.time() - t0, 1),
        "stdout_tail": out[-5000:],
    }


def parse_gate_output(text: str) -> dict[str, float]:
    vals: dict[str, float] = {}
    for m in re.finditer(r"^(\S+)\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%", text, re.M):
        vals[m.group(1)] = float(m.group(2))
    m = re.search(r"OVERALL \(gated\)\s+([0-9]+(?:\.[0-9]+)?)\s*%", text)
    if m:
        vals["OVERALL"] = float(m.group(1))
    return vals


def director_snapshot() -> dict[str, Any]:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from director_gate import evaluate_ship, load_ship_snapshot  # type: ignore
    from auto_submit import submits_today  # type: ignore

    snap = load_ship_snapshot()
    used = submits_today()
    verdict = evaluate_ship(snap, submits_today=used) if snap else None
    return {
        "submits_today": used,
        "snapshot": snap.__dict__ if snap else None,
        "verdict": verdict.__dict__ if verdict else None,
    }


def latest_train_summary(out_dir: Path) -> dict[str, Any] | None:
    files = sorted(out_dir.glob("iono_prior_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        data = json.loads(files[0].read_text(encoding="utf-8"))
        data["_path"] = str(files[0])
        return data
    except Exception:
        return {"_path": str(files[0]), "error": "failed to parse"}


def write_report(payload: dict[str, Any]) -> Path:
    out_json = METRICS / "anti_meta_train_latest.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    hist = METRICS / "anti_meta_train_history.jsonl"
    with hist.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    snap = payload.get("director", {}).get("snapshot") or {}
    verdict = payload.get("director", {}).get("verdict") or {}
    train = payload.get("train_summary") or {}
    loss = payload.get("loss_clusters") or {}

    lines = [
        "# Anti-meta local training director",
        "",
        f"Updated: `{payload['ts_utc']}`",
        "",
        "## Objective",
        "",
        "Build an Archaludon anti-meta/router candidate without burning Kaggle CAP. "
        "Current binding targets: Iono >=55%, Crustle min >=89%, Arch overall >=83%, dual >=90/baseline.",
        "",
        "## Current ship gate",
        "",
        f"- Decision: `{verdict.get('decision', 'unknown')}`",
        f"- Reasons: {', '.join(verdict.get('reasons') or []) or 'none'}",
        f"- Arch: {snap.get('arch_overall')}",
        f"- Iono: {snap.get('iono')}",
        f"- Crustle min: {snap.get('crustle_min')}",
        f"- Dual: {snap.get('dual_overall')}",
        f"- Submits today: {payload.get('director', {}).get('submits_today')}/5",
        "",
        "## Iono failure target",
        "",
        f"- Dataset games: {loss.get('games')}",
        f"- Pooled WR: {loss.get('pooled_wr_pct')}%",
        "- Main cluster: fragile_board_any = incomplete evolved active OR active energy <2 OR empty bench.",
        "",
        "## Latest training artifact",
        "",
        f"- Summary: `{train.get('_path')}`",
        f"- Checkpoint: `{train.get('checkpoint')}`",
        f"- Decisions: {train.get('decisions')}",
        f"- Best win multi-option top1: {train.get('best_val_win_multi_top1')}",
        f"- Fragile decisions: {train.get('fragile_decisions')} "
        f"(loss={train.get('fragile_loss_decisions')}, win={train.get('fragile_win_decisions')})",
        "",
        "## Required KEEP gates before wiring/submission",
        "",
        "```powershell",
        "E:\\PTCG_AI_Battle_Challenge\\fleet\\Shard-Gate.ps1 -Role iono "
        "-Script scripts\\gate_archaludon.py -Games 300 "
        "-Extra @('--opponents','real_iono') "
        "-Env @{ARCH_IONO_LEVER='tomato_bc'} -Label iono_bc_fragile",
        "",
        "E:\\PTCG_AI_Battle_Challenge\\fleet\\Shard-Gate.ps1 -Role crustle "
        "-Script scripts\\gate_archaludon.py -Games 120 "
        "-Extra @('--opponents','meta_crustle_flg','meta_crustle_majkel') "
        "-Env @{ARCH_IONO_LEVER='tomato_bc'} -Label guard_crustle_bc",
        "",
        "E:\\PTCG_AI_Battle_Challenge\\fleet\\Shard-Gate.ps1 -Role director "
        "-Script scripts\\gate_archaludon.py -Games 80 -Suite meta_fast "
        "-Env @{ARCH_IONO_LEVER='tomato_bc'} -Label guard_meta_fast_bc",
        "```",
        "",
        "KEEP only if Iono clears 55% pooled and guard gates do not regress. Otherwise REJECT and keep tomato.",
        "",
    ]
    md = REPORT / "ANTI_META_TRAIN_LATEST.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    return md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("plan", "collect", "train", "full"), default="plan")
    ap.add_argument("--data", default="episodes/iono_bc_v2")
    ap.add_argument("--collect-games", type=int, default=0)
    ap.add_argument("--max-decisions", type=int, default=0)
    ap.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch-size", type=int, default=8192)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--loss-weight", type=float, default=2.0)
    ap.add_argument("--fragile-loss-weight", type=float, default=3.0)
    ap.add_argument("--fragile-win-weight", type=float, default=1.5)
    ap.add_argument("--gate", action="store_true", help="Run quick local guard gates after training")
    ap.add_argument("--gate-games", type=int, default=80)
    args = ap.parse_args()

    payload: dict[str, Any] = {
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": args.mode,
        "args": vars(args),
        "director": director_snapshot(),
        "steps": [],
    }

    if args.mode in ("collect", "full") and args.collect_games > 0:
        payload["steps"].append(run([
            PY, "-u", "scripts/collect_iono_decisions.py",
            "--games", str(args.collect_games),
            "--out", args.data,
            "--opponent", "real_iono",
            *(["--max-decisions", str(args.max_decisions)] if args.max_decisions else []),
        ], env={"ARCH_IONO_LEVER": "tomato"}, timeout=14400))

    loss_path = ROOT / "recordings" / "intel" / "iono_loss_clusters.json"
    if args.mode != "plan":
        payload["steps"].append(run([
            PY, "-u", "scripts/analyze_iono_loss_clusters.py",
            "--data", args.data,
            "--out", "recordings/intel/iono_loss_clusters",
        ], timeout=1800))
    if loss_path.exists():
        payload["loss_clusters"] = json.loads(loss_path.read_text(encoding="utf-8"))

    out_dir = ROOT / "artifacts" / "iono_prior_v2"
    if args.mode in ("train", "full"):
        payload["steps"].append(run([
            PY, "-u", "scripts/train_iono_prior.py",
            "--data", args.data,
            "--out", "artifacts/iono_prior_v2",
            "--device", args.device,
            "--epochs", str(args.epochs),
            "--batch-size", str(args.batch_size),
            "--hidden", str(args.hidden),
            "--objective", "pos",
            "--select-on", "prior",
            "--loss-weight", str(args.loss_weight),
            "--fragile-loss-weight", str(args.fragile_loss_weight),
            "--fragile-win-weight", str(args.fragile_win_weight),
        ], timeout=14400))

    payload["train_summary"] = latest_train_summary(out_dir)

    if args.gate:
        gates = []
        for name, opponents in (
            ("iono", ["real_iono"]),
            ("crustle", ["meta_crustle_flg", "meta_crustle_majkel"]),
            ("meta_fast", []),
        ):
            cmd = [PY, "-u", "scripts/gate_archaludon.py", "--games", str(args.gate_games)]
            if opponents:
                cmd += ["--opponents", *opponents]
            else:
                cmd += ["--suite", "meta_fast"]
            step = run(cmd, env={"ARCH_IONO_LEVER": "tomato"}, timeout=7200)
            step["gate"] = name
            step["wrs"] = parse_gate_output(step["stdout_tail"])
            gates.append(step)
        payload["quick_gates"] = gates

    report = write_report(payload)
    print(json.dumps({
        "mode": args.mode,
        "decision": (payload.get("director", {}).get("verdict") or {}).get("decision"),
        "report": str(report),
        "train_summary": (payload.get("train_summary") or {}).get("_path"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
