"""End-to-end Track B pipeline for one deck: train → distill → gate → package.

Track B is the primary submission path (LearnedScorer). Each deck needs its
own policy train + distill; do not reuse distilled weights across archetypes.

Example:
    python scripts/train_track_b_deck.py \\
      --deck agent_decks/a2_kyogre_33_energy.csv \\
      --timesteps 100000 --gate-games 40 --package

No Kaggle upload unless --submit is passed (blocked by default).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODELS = ROOT / "agent" / "models"
REPORT_DIR = ROOT / "report" / "track_b_runs"


def _run(cmd: list[str], label: str) -> subprocess.CompletedProcess:
    print(f"\n=== {label} ===")
    print(" ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"{label} failed (exit {proc.returncode})")
    return proc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--deck", required=True, help="Player deck CSV (fixed for this policy)")
    parser.add_argument("--slug", default=None, help="Artifact slug (default: derived from deck path)")
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--n-envs", type=int, default=None)
    parser.add_argument("--opponents", choices=("benchmark", "pool"), default="benchmark")
    parser.add_argument(
        "--holdout",
        default="",
        help="Comma-separated opponent names excluded from policy training as "
             "held-out generalization probes (e.g. 'a2_kyogre'). Passed to train_rl.",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--distill-episodes", type=int, default=100)
    parser.add_argument("--distill-epochs", type=int, default=30)
    parser.add_argument("--gate-games", type=int, default=40)
    parser.add_argument("--package", action="store_true", help="Package tarball if gate passes")
    parser.add_argument("--promote", action="store_true", help="Copy distilled npz to agent/models/distilled_v1.npz")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-distill", action="store_true")
    parser.add_argument("--skip-gate", action="store_true")
    args = parser.parse_args(argv)

    from rl.env_factory import deck_slug, resolve_deck_path

    deck = resolve_deck_path(args.deck)
    slug = args.slug or deck_slug(deck)
    policy_zip = MODELS / "rl_policy.zip"
    distilled = MODELS / f"distilled_{slug}_v1.npz"
    package_name = f"track_b_learned_{slug.replace('-', '_')}"
    report_path = REPORT_DIR / f"{slug}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

    py = sys.executable
    summary: dict = {
        "started": datetime.now(timezone.utc).isoformat(),
        "deck": str(deck),
        "slug": slug,
        "opponents": args.opponents,
        "timesteps": args.timesteps,
        "distilled": str(distilled),
        "package_name": package_name,
    }

    try:
        if not args.skip_train:
            train_cmd = [
                py, str(ROOT / "rl" / "train_rl.py"),
                "--timesteps", str(args.timesteps),
                "--deck", str(deck),
                "--opponents", args.opponents,
            ]
            if args.resume:
                train_cmd.append("--resume")
            if args.n_envs is not None:
                train_cmd.extend(["--n-envs", str(args.n_envs)])
            if args.holdout:
                train_cmd.extend(["--holdout", args.holdout])
            _run(train_cmd, "RL train")
            ckpt = json.loads((ROOT / "report" / "rl_train" / "checkpoint.json").read_text(encoding="utf-8"))
            summary["train"] = ckpt
            if ckpt.get("status") != "ok":
                raise RuntimeError(f"train status: {ckpt}")

        if not args.skip_distill:
            _run([
                py, str(ROOT / "scripts" / "distill_policy.py"),
                "--src", str(MODELS / "rl_policy.pt"),
                "--out", str(distilled),
                "--deck", str(deck),
                "--opponents", args.opponents,
                "--episodes", str(args.distill_episodes),
                "--epochs", str(args.distill_epochs),
            ], "Distill")
            if not distilled.exists():
                raise RuntimeError(f"missing {distilled}")

        if args.promote:
            promoted = MODELS / "distilled_v1.npz"
            shutil.copy2(distilled, promoted)
            summary["promoted"] = str(promoted)

        gate_passed = None
        if not args.skip_gate:
            gate_cmd = [
                py, str(ROOT / "scripts" / "gate_track_b.py"),
                "--games", str(args.gate_games),
                "--deck", str(deck),
                "--model", str(distilled),
                "--name", package_name,
            ]
            if not args.package:
                gate_cmd.append("--no-package")
            proc = subprocess.run(gate_cmd, cwd=str(ROOT))
            gate_passed = proc.returncode == 0
            summary["gate_passed"] = gate_passed
            summary["gate_report"] = str(ROOT / "report" / "track_b_gates" / f"{package_name}_gate.md")

        summary["status"] = "ok"
        summary["finished"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        summary["status"] = "error"
        summary["error"] = str(exc)
        summary["finished"] = datetime.now(timezone.utc).isoformat()
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 1

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nRun log: {report_path}")
    if args.package and gate_passed:
        print(f"Package: dist/candidates/{package_name}.tar.gz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
