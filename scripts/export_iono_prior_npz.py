#!/usr/bin/env python3
"""Export an Iono prior .pt checkpoint to a NumPy runtime artifact.

The Kaggle agent must not depend on torch for this lever.  This script converts
the latest schema-v2 checkpoint produced by train_iono_prior.py into a compact
NPZ that agent/archaludon_agent.py can load with numpy only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]


def latest_checkpoint() -> Path:
    summaries = sorted(
        (ROOT / "artifacts" / "iono_prior_v2").glob("iono_prior_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not summaries:
        raise SystemExit("no iono_prior_v2 summaries found")
    data = json.loads(summaries[0].read_text(encoding="utf-8"))
    ckpt = Path(data["checkpoint"])
    if not ckpt.is_absolute():
        ckpt = ROOT / ckpt
    return ckpt


def arr(state: dict, name: str) -> np.ndarray:
    return state[name].detach().cpu().numpy().astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--out", default="agent/models/iono_prior_v2.npz")
    args = ap.parse_args()

    ckpt = Path(args.checkpoint) if args.checkpoint else latest_checkpoint()
    if not ckpt.is_absolute():
        ckpt = ROOT / ckpt
    blob = torch.load(ckpt, map_location="cpu", weights_only=False)
    sd = blob["state_dict"]
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        out,
        state_mean=blob["state_mean"].detach().cpu().numpy().astype(np.float32),
        state_std=blob["state_std"].detach().cpu().numpy().astype(np.float32),
        max_options=np.array([blob.get("max_options", 32)], dtype=np.int32),
        hidden=np.array([blob.get("hidden", 256)], dtype=np.int32),
        state_dim=np.array([blob.get("state_dim", 25)], dtype=np.int32),
        option_dim=np.array([blob.get("option_dim", 17)], dtype=np.int32),
        se0_w=arr(sd, "state_enc.0.weight"),
        se0_b=arr(sd, "state_enc.0.bias"),
        se2_w=arr(sd, "state_enc.2.weight"),
        se2_b=arr(sd, "state_enc.2.bias"),
        oe0_w=arr(sd, "opt_enc.0.weight"),
        oe0_b=arr(sd, "opt_enc.0.bias"),
        sc0_w=arr(sd, "score.0.weight"),
        sc0_b=arr(sd, "score.0.bias"),
        sc2_w=arr(sd, "score.2.weight"),
        sc2_b=arr(sd, "score.2.bias"),
        source_checkpoint=np.array([str(ckpt)]),
    )
    meta = {
        "checkpoint": str(ckpt),
        "out": str(out),
        "bytes": out.stat().st_size,
        "state_dim": int(blob.get("state_dim", 25)),
        "option_dim": int(blob.get("option_dim", 17)),
        "max_options": int(blob.get("max_options", 32)),
    }
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
