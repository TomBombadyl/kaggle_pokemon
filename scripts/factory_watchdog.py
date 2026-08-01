#!/usr/bin/env python3
"""Factory supervisor: keep PTCG train/gate/loop alive; restart every 30s.

Children (E: venv only):
  0 aggressive_loop   — package/ship policy + meta refresh
  1 wait_and_submit   — UTC-day submit window
  2 continuous_focus  — Iono / majkel / flg gate rotation (CPU sim)
  3 train_mcts_cuda   — Lucario/field MCTS on GPU when available
  4 episode_worker    — process high-value episode batches when free
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"E:\PTCG_AI_Battle_Challenge\kaggle_pokemon")
PY = Path(r"E:\PTCG_AI_Battle_Challenge\.venv\Scripts\python.exe")
LOG = ROOT / "report" / "aggressive"
STATE = ROOT / "STATE.md"
POLL = 30

os.chdir(ROOT)
LOG.mkdir(parents=True, exist_ok=True)

# Token
for p in (
    Path.home() / ".kaggle" / "access_token",
    ROOT / ".kaggle" / "access_token",
    ROOT.parent / ".kaggle" / "access_token",
):
    if p.exists():
        os.environ["KAGGLE_API_TOKEN"] = p.read_text(encoding="utf-8").strip().splitlines()[0]
        break

# Prefer CUDA for train
device = "cuda"
try:
    import torch

    if not torch.cuda.is_available():
        device = "cpu"
except Exception:
    device = "cpu"


def _cmd_train() -> list[str]:
    train = ROOT / "scripts" / "train_lucario_field_mcts.py"
    if not train.exists():
        return [str(PY), "-c", "import time; time.sleep(3600)"]
    return [
        str(PY),
        "-u",
        str(train),
        "--device",
        device,
        "--cycles",
        "50",
    ]


def _cmd_focus() -> list[str]:
    return [str(PY), "-u", str(ROOT / "scripts" / "continuous_focus_gates.py")]


def _cmd_episodes() -> list[str]:
    ep = ROOT / "scripts" / "continuous_episode_worker.py"
    if ep.exists():
        return [str(PY), "-u", str(ep)]
    return [str(PY), "-c", "import time; time.sleep(3600)"]


CMDS: list[tuple[str, list[str]]] = [
    ("aggressive_loop", [str(PY), "-u", "scripts/aggressive_loop.py", "--poll-seconds", "60"]),
    ("wait_and_submit", [str(PY), "-u", "scripts/wait_and_submit.py"]),
    ("continuous_focus", _cmd_focus()),
    ("train_mcts", _cmd_train()),
    ("episode_worker", _cmd_episodes()),
    (
        "strategy_intel",
        [str(PY), "-u", str(ROOT / "scripts" / "continuous_strategy_intel.py")],
    ),
]


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with (LOG / "factory_watchdog.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def spawn(name: str, cmd: list[str]) -> tuple[subprocess.Popen, object, object]:
    out = open(LOG / f"wd_{name}.log", "a", encoding="utf-8")
    err = open(LOG / f"wd_{name}.err", "a", encoding="utf-8")
    out.write(f"\n--- spawn {datetime.now(timezone.utc).isoformat()} ---\n")
    out.flush()
    p = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=out,
        stderr=err,
        env=os.environ.copy(),
    )
    log(f"spawned {name} pid={p.pid} cmd={' '.join(cmd[:6])}")
    return p, out, err


def write_state(procs: dict) -> None:
    alive = {n: (p.poll() is None) for n, (p, _, _) in procs.items()}
    metrics = ROOT / "recordings" / "metrics" / "focus_latest.json"
    focus = ""
    if metrics.exists():
        try:
            focus = metrics.read_text(encoding="utf-8")[:800]
        except Exception:
            focus = ""
    body = f"""# STATE — Factory NEVER-STOP

> Auto {datetime.now(timezone.utc).isoformat()} UTC · device={device}

## Processes
| Worker | Alive |
|--------|-------|
""" + "\n".join(f"| {n} | {'YES' if a else 'DEAD→restart'} |" for n, a in alive.items()) + f"""

## Ship policy
- overall ≥72% · deep Crustle ≥70% · Iono ≥55% · no vanity random-gate ships
- primary: Archaludon 75wr shell

## Focus metrics (latest)
```
{focus or '(waiting first focus cycle)'}
```

## Bottleneck
See continuous_focus / aggressive_loop logs under report/aggressive/
"""
    try:
        STATE.write_text(body, encoding="utf-8")
    except Exception as e:
        log(f"state write fail: {e}")


def main() -> int:
    log(f"factory_watchdog START device={device}")
    procs: dict[str, tuple] = {}
    for name, cmd in CMDS:
        # skip missing scripts for optional workers
        if name == "continuous_focus" and not (ROOT / "scripts" / "continuous_focus_gates.py").exists():
            log("skip continuous_focus — script missing")
            continue
        if name == "wait_and_submit" and not (ROOT / "scripts" / "wait_and_submit.py").exists():
            continue
        if name == "aggressive_loop" and not (ROOT / "scripts" / "aggressive_loop.py").exists():
            continue
        procs[name] = spawn(name, cmd)

    while True:
        for name, cmd in CMDS:
            if name not in procs:
                continue
            p, out, err = procs[name]
            if p.poll() is not None:
                log(f"DEAD {name} exit={p.returncode} — restart")
                try:
                    out.close()
                    err.close()
                except Exception:
                    pass
                # refresh train device each respawn
                if name == "train_mcts":
                    cmd = _cmd_train()
                procs[name] = spawn(name, cmd)
        write_state(procs)
        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main())
