#!/usr/bin/env python3
"""Unattended local-compute autopilot for climbing toward first place.

Scope:
  - local data collection / training / gates only
  - no Kaggle submission
  - no ship-floor changes

The loop spends spare compute on the current blockers:
  1. expand schema-v2 Iono data,
  2. train option-outcome Q and prior candidates,
  3. run Iono smoke gates plus Crustle guard gates for safe rule candidates,
  4. rank candidates by ship-floor safety,
  5. write an always-readable dashboard.
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


def ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(cmd: list[str], *, env: dict[str, str] | None = None, timeout: int = 14400) -> dict[str, Any]:
    start = time.time()
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
        "env": env or {},
        "rc": p.returncode,
        "elapsed_s": round(time.time() - start, 1),
        "tail": out[-6000:],
    }


def parse_wr(out: str) -> dict[str, float]:
    vals: dict[str, float] = {}
    for m in re.finditer(r"^\s*(\S+)\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%", out, re.M):
        vals[m.group(1)] = float(m.group(2))
    m = re.search(r"^\s*OVERALL \(gated\)\s+([0-9]+(?:\.[0-9]+)?)\s*%", out, re.M)
    if m:
        vals["OVERALL"] = float(m.group(1))
    return vals


def ranked_candidates(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for gate in gates:
        name = str(gate.get("name") or "unknown")
        entry = by_name.setdefault(name, {"name": name, "iono": None, "crustle_min": None, "overall": None, "rc_ok": True})
        wrs = gate.get("wrs") or {}
        entry["rc_ok"] = bool(entry["rc_ok"] and gate.get("rc") == 0)
        if gate.get("kind") == "iono":
            entry["iono"] = wrs.get("real_iono") or wrs.get("OVERALL")
        elif gate.get("kind") == "crustle":
            flg = wrs.get("meta_crustle_flg")
            majkel = wrs.get("meta_crustle_majkel")
            if flg is not None and majkel is not None:
                entry["crustle_min"] = min(float(flg), float(majkel))
            entry["crustle_flg"] = flg
            entry["crustle_majkel"] = majkel
            entry["overall"] = wrs.get("OVERALL")

    ranked: list[dict[str, Any]] = []
    for entry in by_name.values():
        iono = entry.get("iono")
        crustle_min = entry.get("crustle_min")
        safety = -999.0
        if iono is not None and crustle_min is not None:
            # Hard floors remain in director_gate.py. This score is only a smoke-rank:
            # prioritize the weaker required matchup, then reward Iono headroom.
            safety = min(float(iono) - 55.0, float(crustle_min) - 89.0) + 0.01 * float(iono)
        entry["smoke_rank_score"] = round(safety, 4)
        entry["smoke_green"] = bool(entry.get("rc_ok") and iono is not None and crustle_min is not None and iono >= 55.0 and crustle_min >= 89.0)
        ranked.append(entry)
    ranked.sort(key=lambda x: (bool(x.get("smoke_green")), float(x.get("smoke_rank_score") or -999.0)), reverse=True)
    for i, entry in enumerate(ranked, 1):
        entry["rank"] = i
    return ranked


def latest_json(pattern: str) -> dict[str, Any] | None:
    files = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        data = json.loads(files[0].read_text(encoding="utf-8"))
        data["_path"] = str(files[0])
        return data
    except Exception as e:
        return {"_path": str(files[0]), "error": str(e)}


def director_snapshot() -> dict[str, Any]:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
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
    except Exception as e:
        return {"error": str(e)}


def write_dashboard(payload: dict[str, Any]) -> None:
    latest = METRICS / "anti_meta_autopilot_latest.json"
    latest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with (METRICS / "anti_meta_autopilot_history.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    d = payload.get("director", {})
    snap = d.get("snapshot") or {}
    verdict = d.get("verdict") or {}
    q = payload.get("latest_q") or {}
    prior = payload.get("latest_prior") or {}
    gates = payload.get("smoke_gates") or []
    ranking = payload.get("candidate_ranking") or []
    lines = [
        "# Anti-meta autopilot",
        "",
        f"Updated: `{payload['ts_utc']}`",
        f"Cycle: `{payload['cycle']}`",
        "",
        "## Ship status",
        "",
        f"- Decision: `{verdict.get('decision', 'unknown')}`",
        f"- Reasons: {', '.join(verdict.get('reasons') or []) or 'none'}",
        f"- Iono: {snap.get('iono')}",
        f"- Crustle min: {snap.get('crustle_min')}",
        f"- Arch: {snap.get('arch_overall')}",
        f"- Dual: {snap.get('dual_overall')}",
        f"- Submits today: {d.get('submits_today')}/5",
        "",
        "## Latest learned artifacts",
        "",
        f"- Option-Q: `{q.get('_path')}` best_bce={q.get('best_val_bce')} acc={q.get('best_val_acc')}",
        f"- Prior/BC: `{prior.get('_path')}` win_multi_top1={q.get('best_val_win_multi_top1') or prior.get('best_val_win_multi_top1')}",
        "",
        "## Candidate ranking",
        "",
        "| rank | candidate | smoke green | iono | crustle min | flg | majkel | score |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ranking:
        lines.append(
            f"| {row.get('rank')} | {row.get('name')} | {row.get('smoke_green')} | "
            f"{row.get('iono')} | {row.get('crustle_min')} | {row.get('crustle_flg')} | "
            f"{row.get('crustle_majkel')} | {row.get('smoke_rank_score')} |"
        )
    lines += [
        "",
        "## Raw smoke gates",
        "",
        "| candidate | kind | rc | real_iono | flg | majkel | overall |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for g in gates:
        wr = g.get("wrs") or {}
        lines.append(
            f"| {g.get('name')} | {g.get('kind')} | {g.get('rc')} | {wr.get('real_iono')} | "
            f"{wr.get('meta_crustle_flg')} | {wr.get('meta_crustle_majkel')} | {wr.get('OVERALL')} |"
        )
    lines += [
        "",
        "Autopilot is local-only. It never submits to Kaggle.",
        "",
    ]
    (REPORT / "ANTI_META_AUTOPILOT.md").write_text("\n".join(lines), encoding="utf-8")


def gate_candidate(name: str, env: dict[str, str], games: int, opponents: list[str], kind: str) -> dict[str, Any]:
    step = run(
        [PY, "-u", "scripts/gate_archaludon.py", "--games", str(games), "--opponents", *opponents],
        env=env,
        timeout=7200,
    )
    step["name"] = name
    step["kind"] = kind
    step["wrs"] = parse_wr(step["tail"])
    return step


def one_cycle(args: argparse.Namespace, cycle: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ts_utc": ts(),
        "cycle": cycle,
        "args": vars(args),
        "director": director_snapshot(),
        "steps": [],
    }

    if args.collect_games > 0:
        payload["steps"].append(run([
            PY, "-u", "scripts/collect_iono_decisions.py",
            "--games", str(args.collect_games),
            "--out", args.data,
            "--opponent", "real_iono",
        ], env={"ARCH_IONO_LEVER": "tomato"}, timeout=14400))

    payload["steps"].append(run([
        PY, "-u", "scripts/analyze_iono_loss_clusters.py",
        "--data", args.data,
        "--out", "recordings/intel/iono_loss_clusters",
    ], timeout=1800))

    payload["steps"].append(run([
        PY, "-u", "scripts/train_iono_option_q.py",
        "--data", args.data,
        "--out", "artifacts/iono_q_v2",
        "--device", args.device,
        "--epochs", str(args.q_epochs),
        "--batch-size", str(args.batch_size),
        "--loss-weight", "2.0",
        "--fragile-loss-weight", "3.0",
        "--fragile-win-weight", "1.5",
    ], timeout=14400))

    if args.train_prior:
        payload["steps"].append(run([
            PY, "-u", "scripts/train_iono_prior.py",
            "--data", args.data,
            "--out", "artifacts/iono_prior_v2",
            "--device", args.device,
            "--epochs", str(args.prior_epochs),
            "--batch-size", str(args.batch_size),
            "--objective", "pos",
            "--select-on", "prior",
            "--loss-weight", "2.0",
            "--fragile-loss-weight", "3.0",
            "--fragile-win-weight", "1.5",
        ], timeout=14400))

    candidates = [
        ("tomato", {"ARCH_IONO_LEVER": "tomato"}),
        ("tomato_fork_floor2", {
            "ARCH_IONO_LEVER": "tomato_fork",
            "ARCH_IONO_FORK_FLOOR": "2",
        }),
        ("tomato_fork_floor3", {
            "ARCH_IONO_LEVER": "tomato_fork",
            "ARCH_IONO_FORK_FLOOR": "3",
        }),
    ]
    gates: list[dict[str, Any]] = []
    for name, env in candidates:
        gates.append(gate_candidate(name, env, args.gate_games, ["real_iono"], "iono"))
        gates.append(gate_candidate(name, env, args.crustle_gate_games, ["meta_crustle_flg", "meta_crustle_majkel"], "crustle"))
    payload["smoke_gates"] = gates
    payload["candidate_ranking"] = ranked_candidates(gates)
    payload["latest_q"] = latest_json("artifacts/iono_q_v2/iono_option_q_*.json")
    payload["latest_prior"] = latest_json("artifacts/iono_prior_v2/iono_prior_*.json")
    write_dashboard(payload)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="episodes/iono_bc_v2")
    ap.add_argument("--collect-games", type=int, default=1200)
    ap.add_argument("--gate-games", type=int, default=80)
    ap.add_argument("--crustle-gate-games", type=int, default=60)
    ap.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    ap.add_argument("--batch-size", type=int, default=8192)
    ap.add_argument("--q-epochs", type=int, default=40)
    ap.add_argument("--prior-epochs", type=int, default=20)
    ap.add_argument("--train-prior", action="store_true")
    ap.add_argument("--cycles", type=int, default=0, help="0 = forever")
    ap.add_argument("--sleep-sec", type=int, default=60)
    args = ap.parse_args()

    cycle = 0
    while True:
        cycle += 1
        payload = one_cycle(args, cycle)
        print(json.dumps({
            "cycle": cycle,
            "decision": (payload.get("director", {}).get("verdict") or {}).get("decision"),
            "dashboard": str(REPORT / "ANTI_META_AUTOPILOT.md"),
            "latest": str(METRICS / "anti_meta_autopilot_latest.json"),
        }, ensure_ascii=False), flush=True)
        if args.cycles and cycle >= args.cycles:
            return 0
        time.sleep(max(1, args.sleep_sec))


if __name__ == "__main__":
    raise SystemExit(main())
