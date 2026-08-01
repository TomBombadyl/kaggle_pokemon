#!/usr/bin/env python3
"""Train an Iono option-outcome model from schema-v2 decision logs.

This is the learned path after filtered BC failed in runtime.  It does not try
to imitate tomato's selected action.  Instead it learns:

    P(game win | state, selected legal option)

Only the actually selected option has an observed outcome, so this is still an
observational/off-policy model, not a causal oracle.  The output is research
evidence and a future reranker candidate; it is not wired into the agent by this
script and it never submits.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]


def fragile_board_mask(state: torch.Tensor) -> torch.Tensor:
    if state.shape[1] < 14:
        return torch.zeros(state.shape[0], dtype=torch.bool)
    evolved_active = (state[:, 12] >= 0.5) | (state[:, 13] >= 0.5)
    low_energy = state[:, 10] < 2.0
    empty_bench = state[:, 6] <= 0.0
    return (~evolved_active) | low_energy | empty_bench


def load_dataset(data_dir: Path, max_options: int) -> dict:
    files = sorted(data_dir.glob("iono_decisions_*.jsonl"))
    if not files:
        raise SystemExit(f"no iono_decisions_*.jsonl under {data_dir}")

    states, opts, labels = [], [], []
    skipped = {"schema": 0, "draw": 0, "multi": 0, "wide": 0, "bad": 0}
    for fp in files:
        with fp.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    skipped["bad"] += 1
                    continue
                if rec.get("schema_version") != 2:
                    skipped["schema"] += 1
                    continue
                label = rec.get("label")
                if label not in (0, 1):
                    skipped["draw"] += 1
                    continue
                for d in rec.get("decisions") or []:
                    pick = d.get("pick") or []
                    o = d.get("o") or []
                    if len(pick) != 1:
                        skipped["multi"] += 1
                        continue
                    if not o or pick[0] >= len(o):
                        skipped["bad"] += 1
                        continue
                    if len(o) > max_options:
                        skipped["wide"] += 1
                        continue
                    states.append(d["s"])
                    opts.append(o[int(pick[0])])
                    labels.append(float(label))
    if not states:
        raise SystemExit("empty option-q dataset after filtering")

    ds = {
        "state": torch.tensor(states, dtype=torch.float32),
        "option": torch.tensor(opts, dtype=torch.float32),
        "label": torch.tensor(labels, dtype=torch.float32),
        "skipped": skipped,
        "files": [str(p) for p in files],
    }
    varying_state = int((ds["state"].std(0) > 1e-6).sum())
    card_id_std = float(ds["option"][:, -4].std())
    if varying_state < 8 or card_id_std <= 1e-6:
        raise SystemExit(
            f"degenerate features: varying_state={varying_state} card_id_std={card_id_std}"
        )
    return ds


def normalise(ds: dict) -> dict:
    sm = ds["state"].mean(0)
    ss = ds["state"].std(0).clamp_min(1e-3)
    om = ds["option"].mean(0)
    os = ds["option"].std(0).clamp_min(1e-3)
    # Card id is wide and sparse; match prior path.
    ds["option"][:, -4] = torch.log1p(ds["option"][:, -4]) / 8.0
    om = ds["option"].mean(0)
    os = ds["option"].std(0).clamp_min(1e-3)
    ds["state"] = (ds["state"] - sm) / ss
    ds["option"] = (ds["option"] - om) / os
    return {"state_mean": sm, "state_std": ss, "option_mean": om, "option_std": os}


class OptionQ(nn.Module):
    def __init__(self, state_dim: int, option_dim: int, hidden: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim + option_dim, hidden), nn.SiLU(),
            nn.Dropout(0.05),
            nn.Linear(hidden, hidden), nn.SiLU(),
            nn.Linear(hidden, hidden // 2), nn.SiLU(),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, state, option):
        return self.net(torch.cat([state, option], dim=1)).squeeze(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="episodes/iono_bc_v2")
    ap.add_argument("--out", default="artifacts/iono_q_v2")
    ap.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch-size", type=int, default=8192)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--max-options", type=int, default=32)
    ap.add_argument("--loss-weight", type=float, default=2.0)
    ap.add_argument("--fragile-loss-weight", type=float, default=3.0)
    ap.add_argument("--fragile-win-weight", type=float, default=1.5)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    dev = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if dev == "auto":
        dev = "cpu"
    if dev == "cuda" and not torch.cuda.is_available():
        dev = "cpu"
    device = torch.device(dev)

    ds = load_dataset(ROOT / args.data, args.max_options)
    fragile_raw = fragile_board_mask(ds["state"])
    norm = normalise(ds)

    n = ds["state"].shape[0]
    perm = torch.randperm(n, generator=torch.Generator().manual_seed(args.seed))
    n_val = max(1, int(n * args.val_frac))
    val_idx, tr_idx = perm[:n_val], perm[n_val:]

    for k in ("state", "option", "label"):
        ds[k] = ds[k].to(device)
    fragile = fragile_raw.to(device)

    model = OptionQ(ds["state"].shape[1], ds["option"].shape[1], args.hidden).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, args.epochs))
    amp = dev == "cuda"

    w_all = torch.where(ds["label"] > 0.5, 1.0, args.loss_weight).to(device)
    fmult = torch.where(
        ds["label"] > 0.5,
        torch.tensor(float(args.fragile_win_weight), device=device),
        torch.tensor(float(args.fragile_loss_weight), device=device),
    )
    w_all = torch.where(fragile, w_all * fmult, w_all)

    best_bce = float("inf")
    best_state = None
    history = []
    t0 = time.time()
    for ep in range(args.epochs):
        model.train()
        order = tr_idx[torch.randperm(tr_idx.numel())].to(device)
        total = 0.0
        nb = 0
        for i in range(0, order.numel(), args.batch_size):
            b = order[i:i + args.batch_size]
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                logits = model(ds["state"][b], ds["option"][b])
                loss_vec = F.binary_cross_entropy_with_logits(logits.float(), ds["label"][b], reduction="none")
                loss = (loss_vec * w_all[b]).mean()
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss)
            nb += 1
        sched.step()

        model.eval()
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
            vb = val_idx.to(device)
            logits = model(ds["state"][vb], ds["option"][vb]).float()
            label = ds["label"][vb]
            bce = float(F.binary_cross_entropy_with_logits(logits, label))
            prob = torch.sigmoid(logits)
            acc = float(((prob > 0.5).float() == label).float().mean())
            pos_mean = float(prob[label > 0.5].mean()) if bool((label > 0.5).any()) else None
            neg_mean = float(prob[label < 0.5].mean()) if bool((label < 0.5).any()) else None
        row = {
            "epoch": ep,
            "train_loss": total / max(1, nb),
            "val_bce": bce,
            "val_acc": acc,
            "val_win_prob_mean": pos_mean,
            "val_loss_prob_mean": neg_mean,
            "lr": sched.get_last_lr()[0],
        }
        history.append(row)
        print(
            f"[ep {ep:03d}] train={row['train_loss']:.4f} "
            f"val_bce={bce:.4f} acc={acc:.3f} "
            f"p_win={pos_mean:.3f} p_loss={neg_mean:.3f}",
            flush=True,
        )
        if bce < best_bce:
            best_bce = bce
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ckpt = out_dir / f"iono_option_q_{tag}.pt"
    torch.save({
        "state_dict": best_state or model.state_dict(),
        "state_dim": int(ds["state"].shape[1]),
        "option_dim": int(ds["option"].shape[1]),
        "hidden": args.hidden,
        "normalization": norm,
        "args": vars(args),
    }, ckpt)
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "checkpoint": str(ckpt),
        "decisions": n,
        "wins": int(ds["label"].sum().item()),
        "losses": int((1 - ds["label"]).sum().item()),
        "fragile_decisions": int(fragile.sum().item()),
        "best_val_bce": best_bce,
        "best_val_acc": max(h["val_acc"] for h in history),
        "final": history[-1],
        "history": history,
        "elapsed_s": round(time.time() - t0, 1),
        "device": str(device),
        "skipped": ds["skipped"],
    }
    ckpt.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("checkpoint", "decisions", "best_val_bce", "best_val_acc", "device")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
