"""Distill torch RL/BC policy to numpy submission format."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.features import FEATURE_VERSION, OPTION_DIM, STATE_DIM, option_features, state_features  # noqa: E402
from agent.learned_policy import LearnedScorer  # noqa: E402

TORCH_MODEL = ROOT / "agent" / "models" / "rl_policy.pt"
BC_MODEL = ROOT / "agent" / "models" / "bc_v1.npz"
OUT_MODEL = ROOT / "agent" / "models" / "distilled_v1.npz"
REPORT = ROOT / "report" / "distill_gate.md"


def load_torch_weights(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        import torch
    except ImportError:
        return None
    try:
        from stable_baselines3 import PPO
    except ImportError:
        return None
    try:
        model = PPO.load(str(path.with_suffix("")))
        state_dict = model.policy.state_dict()
        # Best-effort: extract first two linear layers if shapes match
        keys = list(state_dict.keys())
        w_keys = [k for k in keys if k.endswith("weight")]
        b_keys = [k for k in keys if k.endswith("bias")]
        if len(w_keys) < 2:
            return None
        w1 = state_dict[w_keys[0]].detach().cpu().numpy().T.astype(np.float32)
        b1 = state_dict[b_keys[0]].detach().cpu().numpy().astype(np.float32)
        w2 = state_dict[w_keys[1]].detach().cpu().numpy().T.astype(np.float32)
        b2 = state_dict[b_keys[1]].detach().cpu().numpy().astype(np.float32)
        in_dim = STATE_DIM + OPTION_DIM
        if w1.shape[0] != in_dim:
            return None
        return {"w1": w1, "b1": b1, "w2": w2.squeeze(), "b2": b2}
    except Exception:
        return None


def latency_check(scorer: LearnedScorer, n: int = 200) -> float:
    obs = {
        "logs": [],
        "current": {"turn": 5, "yourIndex": 0, "players": [{}, {}]},
        "select": {
            "type": 0, "context": 0, "minCount": 1, "maxCount": 1,
            "option": [{"type": 14}, {"type": 7, "index": 0}, {"type": 13, "attackId": 1}],
        },
    }
    start = time.perf_counter()
    for _ in range(n):
        scorer.choose(obs, obs["select"], obs["current"], obs["select"]["option"])
    return (time.perf_counter() - start) / n * 1000.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(TORCH_MODEL))
    parser.add_argument("--fallback", default=str(BC_MODEL))
    parser.add_argument("--out", default=str(OUT_MODEL))
    parser.add_argument("--package-dry-run", action="store_true")
    args = parser.parse_args(argv)

    weights = load_torch_weights(Path(args.src))
    source = "torch"
    if weights is None and Path(args.fallback).exists():
        data = np.load(args.fallback)
        weights = {k: data[k] for k in ("w1", "b1", "w2", "b2")}
        source = "bc_fallback"

    if weights is None:
        print("no torch or BC weights found")
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        feature_version=FEATURE_VERSION,
        state_dim=STATE_DIM,
        option_dim=OPTION_DIM,
        **weights,
    )

    scorer = LearnedScorer(model_path=out)
    ms_per_move = latency_check(scorer)
    gate_ok = ms_per_move < 50.0 and scorer.ready

    lines = [
        "# Distill policy gate",
        "",
        f"- Source: {source}",
        f"- Output: `{out}`",
        f"- Latency: {ms_per_move:.2f} ms/move (budget <50 ms)",
        f"- Gate: **{'PASS' if gate_ok else 'FAIL'}**",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.package_dry_run:
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "package_submission.py"),
             "--name", "distilled_probe"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        lines.append(f"- Package dry-run: {'OK' if proc.returncode == 0 else proc.stderr}")
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"distilled to {out}; latency={ms_per_move:.2f}ms gate={gate_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
