"""Resumable nightly orchestrator for the massive-jump plan.

Reads report/nightly_checkpoint.json, runs the next incomplete step, and updates
PROGRESS.md / TASKS.md / .cursor/SESSION.md when a phase completes.

Usage:
    python scripts/nightly.py              # advance one step
    python scripts/nightly.py --run-all    # run until all steps done or blocked
    python scripts/nightly.py --status     # show checkpoint only
    python scripts/nightly.py --reset      # restart from step 0
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "report" / "nightly_checkpoint.json"
PROGRESS = ROOT / "PROGRESS.md"
TASKS = ROOT / "TASKS.md"
SESSION = ROOT / ".cursor" / "SESSION.md"
PYTHON = sys.executable


@dataclass(frozen=True)
class Step:
    id: str
    todo: str
    cmd: list[str]
    cwd: str = str(ROOT)


STEPS: list[Step] = [
    Step("p0_validate", "p0-decks", [PYTHON, "scripts/validate_deck.py"]),
    Step("p0_smoke", "p0-refactor", [PYTHON, "scripts/smoke_test.py"]),
    Step("p0_arena", "p0-arena", [PYTHON, "scripts/arena.py", "--games", "4", "--workers", "2"]),
    Step("p0_ladder", "p0-ladder", [PYTHON, "scripts/track_ladder.py", "--dry-run"]),
    Step("a_deck_search", "a-deck", [PYTHON, "scripts/deck_search.py", "--games", "4"]),
    Step("a_gate", "a-gate", [PYTHON, "scripts/gate_track_a.py", "--games", "4"]),
    Step("b_traces", "b-traces", [PYTHON, "scripts/collect_traces.py", "--games", "8", "--shards", "2"]),
    Step("b_bc", "b-bc", [PYTHON, "scripts/train_bc.py"]),
    Step("b_bc_gate", "b-bc-gate", [PYTHON, "scripts/gate_track_b.py", "--games", "4"]),
    Step("rl_env_smoke", "rl-env", [PYTHON, "-m", "rl.cabt_env"]),
    Step("rl_train", "rl-train", [PYTHON, "rl/train_rl.py", "--timesteps", "512"]),
    Step("rl_league", "rl-train", [PYTHON, "-m", "rl.league"]),
    Step("rl_distill", "rl-distill", [PYTHON, "scripts/distill_policy.py", "--package-dry-run"]),
    Step("package_probe", "finals", [PYTHON, "scripts/package_submission.py", "--name", "nightly_probe"]),
    Step("eval_matrix_pool", "p0-arena", [
        PYTHON, "scripts/eval_matrix.py", "--games", "2",
        "--agents", "current,pool_dragapult", "--no-telemetry",
    ]),
    Step("finals_log", "finals", [PYTHON, "scripts/track_ladder.py", "--dry-run"]),
]


def load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return {"next_index": 0, "completed": [], "last_run": None, "logs": []}


def save_checkpoint(data: dict) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_step(step: Step) -> tuple[int, str]:
    proc = subprocess.run(
        step.cmd,
        cwd=step.cwd,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()[-4000:]


def append_progress(step: Step, rc: int, snippet: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = (
        f"\n### {now} (run 13+ - nightly {step.id})\n"
        f"- **Worked on:** massive-jump plan todo `{step.todo}`\n"
        f"- **Changed:** nightly step `{step.id}` exit={rc}\n"
        f"- **Metrics:** see report/arena, report/track_*_gate.md\n"
        f"- **Blockers:** {'none' if rc == 0 else snippet[:200]}\n"
        f"- **NEXT:** run `python scripts/nightly.py` for next step\n"
    )
    if PROGRESS.exists():
        text = PROGRESS.read_text(encoding="utf-8")
        marker = "## Template (copy for each run)"
        if marker in text:
            head, tail = text.split(marker, 1)
            PROGRESS.write_text(head + block + marker + tail, encoding="utf-8")
        else:
            PROGRESS.write_text(block + text, encoding="utf-8")


def update_session(next_index: int) -> None:
    if not SESSION.exists():
        return
    nxt = STEPS[next_index].id if next_index < len(STEPS) else "all_complete"
    text = SESSION.read_text(encoding="utf-8")
    if "## Current focus" in text:
        parts = text.split("## Current focus", 1)
        rest = parts[1].split("##", 1)
        tail = "##" + rest[1] if len(rest) > 1 else ""
        SESSION.write_text(
            parts[0]
            + "## Current focus\n\n"
            + f"Nightly orchestrator: next step `{nxt}` ({next_index}/{len(STEPS)}).\n\n"
            + tail,
            encoding="utf-8",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resumable nightly plan orchestrator.")
    parser.add_argument("--run-all", action="store_true", help="Run steps until done or failure")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args(argv)

    cp = load_checkpoint()
    if args.reset:
        cp = {"next_index": 0, "completed": [], "last_run": None, "logs": []}
        save_checkpoint(cp)
        print("checkpoint reset")
        return 0

    if args.status:
        print(json.dumps(cp, indent=2))
        print(f"steps: {cp['next_index']}/{len(STEPS)}")
        return 0

    ran = 0
    while cp["next_index"] < len(STEPS):
        idx = cp["next_index"]
        step = STEPS[idx]
        print(f"[nightly] step {idx+1}/{len(STEPS)}: {step.id} ({step.todo})")
        rc, out = run_step(step)
        log_entry = {
            "step": step.id,
            "todo": step.todo,
            "rc": rc,
            "at": datetime.now(timezone.utc).isoformat(),
            "snippet": out[-500:],
        }
        cp["logs"] = (cp.get("logs") or [])[-50:] + [log_entry]
        cp["last_run"] = log_entry["at"]
        if rc != 0:
            print(f"  FAILED rc={rc}\n{out[-800:]}")
            save_checkpoint(cp)
            append_progress(step, rc, out)
            update_session(idx)
            return rc
        cp["completed"] = list(cp.get("completed", [])) + [step.id]
        cp["next_index"] = idx + 1
        save_checkpoint(cp)
        append_progress(step, rc, out)
        print(f"  OK")
        ran += 1
        if not args.run_all:
            break

    update_session(cp["next_index"])
    if cp["next_index"] >= len(STEPS):
        print("all nightly steps complete")
    else:
        print(f"advanced {ran} step(s); next={STEPS[cp['next_index']].id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
