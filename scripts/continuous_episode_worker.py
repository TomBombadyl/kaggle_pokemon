#!/usr/bin/env python3
"""Background episode processor — high-value public episodes, never-stop."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
LOG = ROOT / "report" / "aggressive"
LOG.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with (LOG / "episode_worker.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(args: list[str], timeout: int = 1800) -> int:
    try:
        p = subprocess.run(
            [PY, "-u"] + args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        with (LOG / "episode_worker_detail.log").open("a", encoding="utf-8") as f:
            f.write(f"\ncmd={args} rc={p.returncode}\n")
            f.write((p.stdout or "")[-1500:])
            f.write((p.stderr or "")[-800:])
        return p.returncode
    except Exception as e:
        log(f"run fail {args}: {e}")
        return 1


def main() -> int:
    # token
    for p in (
        Path.home() / ".kaggle" / "access_token",
        ROOT / ".kaggle" / "access_token",
    ):
        if p.exists():
            os.environ["KAGGLE_API_TOKEN"] = p.read_text(encoding="utf-8").strip().splitlines()[0]
            break

    log("episode_worker START")
    n = 0
    while True:
        n += 1
        try:
            # Prefer extract top decks refresh (cached replays)
            if (ROOT / "scripts" / "extract_deck_from_episode.py").exists():
                run(
                    [
                        "scripts/extract_deck_from_episode.py",
                        "--top",
                        "6",
                        "--episodes-per-team",
                        "2",
                        "--download",
                        "--out",
                        "recordings/metrics",
                    ],
                    timeout=900,
                )
            # Optional mine if present
            if (ROOT / "scripts" / "mine_episode_decks.py").exists():
                ep_dirs = [
                    ROOT / "recordings" / "metrics" / "replays",
                    ROOT / "data" / "kaggle_ref" / "episodes",
                    ROOT / "episodes" / "raw",
                ]
                for d in ep_dirs:
                    if d.exists() and any(d.glob("*.json")):
                        run(
                            [
                                "scripts/mine_episode_decks.py",
                                "--episodes",
                                str(d),
                                "--out-dir",
                                "agent_decks",
                            ],
                            timeout=600,
                        )
                        break
            log(f"episode cycle {n} done — sleep 600s")
        except Exception:
            log("ERROR " + traceback.format_exc()[-500:])
        time.sleep(600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
