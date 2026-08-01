#!/usr/bin/env python3
"""Train a learned Iono decision prior + value head on the RTX 4080 (gputrain lane).

Input: the jsonl dumps from ``scripts/collect_iono_decisions.py``.
Output: ``artifacts/iono_prior_<tag>.pt`` containing weights, feature layout and
normalisation stats, plus a ``.json`` sidecar with training metrics.

Objective (advantage-weighted regression, two heads sharing an encoder):

  value head   : state -> P(hero wins)        [BCE against the game outcome]
  prior head   : (state, option) -> logit     [cross-entropy toward the option the
                 rule agent actually picked, weighted by the game advantage
                 ``label - value_baseline``]

Advantage weighting is what makes this more than plain behaviour cloning: decisions
from won games are pulled toward, decisions from lost games pushed away. Loss games
are additionally oversampled (``--loss-weight``), which is the "Iono oversample"
the director asked for — the loss mode (board wipe / no_active) is the 4pp gap
between tomato's ~51% and the 55% floor.

Usage
-----
  python scripts/train_iono_prior.py --device cuda --epochs 30
  python scripts/train_iono_prior.py --data episodes/iono_bc --batch-size 16384

For the 2026-07-31 anti-meta path, use the schema-v2 collector plus fragile-board
weights:

  python scripts/train_iono_prior.py --data episodes/iono_bc_v2 --out artifacts/iono_prior_v2 \
    --device auto --epochs 40 --objective pos --select-on prior \
    --loss-weight 2.0 --fragile-loss-weight 3.0 --fragile-win-weight 1.5

This script only writes under ``artifacts/``. It never touches agent code or gates;
wiring the prior into a new ``ARCH_IONO_LEVER`` branch is a separate, gated step.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]


# ── data ────────────────────────────────────────────────────────────────────

def load_dataset(data_dir: Path, max_options: int) -> dict:
    """Flatten every jsonl dump into padded tensors.

    Returns dict of tensors:
      state   [N, S]
      options [N, K, O]     (zero-padded)
      mask    [N, K]        (1 = real option)
      pick    [N]           index of the chosen option
      label   [N]           1 = hero won that game, 0 = lost
    """
    files = sorted(data_dir.glob("iono_decisions_*.jsonl"))
    if not files:
        raise SystemExit(f"no iono_decisions_*.jsonl under {data_dir} — run collect_iono_decisions.py first")

    states: list[list[float]] = []
    opts: list[list[list[float]]] = []
    masks: list[list[float]] = []
    picks: list[int] = []
    labels: list[float] = []
    skipped_multi = skipped_wide = skipped_draw = skipped_schema = 0

    for fp in files:
        with fp.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("schema_version") != 2:
                    skipped_schema += 1
                    continue
                label = rec.get("label", -1)
                if label not in (0, 1):
                    skipped_draw += 1
                    continue
                for d in rec.get("decisions", ()):
                    pick = d.get("pick") or []
                    if len(pick) != 1:
                        skipped_multi += 1
                        continue
                    o = d.get("o") or []
                    if not o or pick[0] >= len(o):
                        continue
                    if len(o) > max_options:
                        skipped_wide += 1
                        continue
                    o_dim = len(o[0])
                    padded = list(o) + [[0.0] * o_dim] * (max_options - len(o))
                    states.append(d["s"])
                    opts.append(padded)
                    masks.append([1.0] * len(o) + [0.0] * (max_options - len(o)))
                    picks.append(int(pick[0]))
                    labels.append(float(label))

    if not states:
        raise SystemExit("dataset is empty after filtering")

    ds = {
        "state": torch.tensor(states, dtype=torch.float32),
        "options": torch.tensor(opts, dtype=torch.float32),
        "mask": torch.tensor(masks, dtype=torch.float32),
        "pick": torch.tensor(picks, dtype=torch.long),
        "label": torch.tensor(labels, dtype=torch.float32),
    }
    print(f"[data] {len(files)} files -> {ds['state'].shape[0]} decisions "
          f"(state_dim={ds['state'].shape[1]} option_dim={ds['options'].shape[2]} K={max_options})")
    print(f"[data] win-decisions={int(ds['label'].sum())} "
          f"loss-decisions={int((1 - ds['label']).sum())} "
          f"skipped: schema={skipped_schema} multi={skipped_multi} "
          f"wide={skipped_wide} draw_games={skipped_draw}")
    varying_state = int((ds["state"].std(0) > 1e-6).sum())
    card_id_col = ds["options"][..., -4]
    if varying_state < 8 or float(card_id_col.std()) <= 1e-6:
        raise SystemExit(
            "degenerate Iono features: collector schema/field mapping is invalid "
            f"(varying_state={varying_state}, option_card_id_std={float(card_id_col.std()):.6g})"
        )
    return ds


def fragile_board_mask(state: torch.Tensor) -> torch.Tensor:
    """Decision-level version of recordings/intel/iono_loss_clusters.

    State layout comes from collect_iono_decisions.py::STATE_FEATURES:
      6  = my_bench
      10 = active energy
      12 = active is Archaludon ex
      13 = active is Cinderace

    The loss report found this cluster in 40.33% of losses vs 5.50% of wins:
    incomplete evolved active OR active energy < 2 OR empty bench.  We weight
    this cluster during training instead of adding another brittle hand rule.
    """
    if state.shape[1] < 14:
        return torch.zeros(state.shape[0], dtype=torch.bool, device=state.device)
    evolved_active = (state[:, 12] >= 0.5) | (state[:, 13] >= 0.5)
    low_energy = state[:, 10] < 2.0
    empty_bench = state[:, 6] <= 0.0
    return (~evolved_active) | low_energy | empty_bench


def normalise(ds: dict) -> tuple[torch.Tensor, torch.Tensor]:
    """Per-feature mean/std over the state block (options are mostly one-hot)."""
    mean = ds["state"].mean(0)
    std = ds["state"].std(0).clamp_min(1e-3)
    ds["state"] = (ds["state"] - mean) / std
    # card_id is the only wide option feature; log-compress it in place.
    ds["options"][..., -4] = torch.log1p(ds["options"][..., -4]) / 8.0
    return mean, std


# ── model ───────────────────────────────────────────────────────────────────

class IonoPrior(nn.Module):
    def __init__(self, state_dim: int, option_dim: int, hidden: int = 256):
        super().__init__()
        self.state_enc = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.SiLU(),
            nn.Linear(hidden, hidden), nn.SiLU(),
        )
        self.opt_enc = nn.Sequential(
            nn.Linear(option_dim, hidden), nn.SiLU(),
        )
        self.score = nn.Sequential(
            nn.Linear(hidden * 2, hidden), nn.SiLU(),
            nn.Linear(hidden, 1),
        )
        self.value = nn.Sequential(
            nn.Linear(hidden, hidden // 2), nn.SiLU(),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, state, options, mask):
        s = self.state_enc(state)                      # [B, H]
        o = self.opt_enc(options)                      # [B, K, H]
        s_exp = s.unsqueeze(1).expand(-1, o.shape[1], -1)
        logits = self.score(torch.cat([s_exp, o], dim=-1)).squeeze(-1)  # [B, K]
        logits = logits.masked_fill(mask < 0.5, float("-inf"))
        return logits, self.value(s).squeeze(-1)


# ── train ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="episodes/iono_bc_v2")
    ap.add_argument("--out", default="artifacts")
    ap.add_argument("--device", default="cuda", choices=("cuda", "cpu", "auto"))
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=8192)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--max-options", type=int, default=32)
    ap.add_argument("--loss-weight", type=float, default=2.0,
                    help="Oversample factor for decisions from lost games")
    ap.add_argument("--fragile-loss-weight", type=float, default=1.0,
                    help="Extra multiplier for fragile-board decisions from lost games")
    ap.add_argument("--fragile-win-weight", type=float, default=1.0,
                    help="Extra multiplier for fragile-board decisions from won games")
    ap.add_argument("--objective", default="pos", choices=("signed", "pos", "exp"),
                    help="Prior-head weighting. 'signed' is the original "
                         "advantage*CE (unbounded below -> diverges). 'pos' clamps "
                         "the advantage to >=0 (filtered BC). 'exp' uses AWR "
                         "exp(adv/beta) weights.")
    ap.add_argument("--beta", type=float, default=0.5, help="AWR temperature for --objective exp")
    ap.add_argument("--select-on", default="prior", choices=("value", "prior"),
                    help="Which holdout metric picks the saved checkpoint.")
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True

    dev = args.device
    if dev == "auto":
        dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cuda" and not torch.cuda.is_available():
        print("[warn] cuda requested but unavailable -> cpu", flush=True)
        dev = "cpu"
    device = torch.device(dev)
    print(f"[env] torch={torch.__version__} device={device} "
          f"{torch.cuda.get_device_name(0) if dev == 'cuda' else ''}", flush=True)

    ds = load_dataset(ROOT / args.data, args.max_options)
    # Compute evidence flags on the raw feature scale.  normalise() rewrites the
    # state tensor in place, so doing this afterwards would turn thresholds like
    # "active energy < 2" into nonsense.
    fragile_raw = fragile_board_mask(ds["state"])
    mean, std = normalise(ds)

    n = ds["state"].shape[0]
    perm = torch.randperm(n, generator=torch.Generator().manual_seed(args.seed))
    n_val = max(1, int(n * args.val_frac))
    val_idx, tr_idx = perm[:n_val], perm[n_val:]

    # Whole dataset lives on the GPU: even 1e6 decisions is well under 1GB, so the
    # loop is pure compute with no host transfer. This is what keeps util high.
    for k in ds:
        ds[k] = ds[k].to(device)

    state_dim = ds["state"].shape[1]
    option_dim = ds["options"].shape[2]
    model = IonoPrior(state_dim, option_dim, args.hidden).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, args.epochs))
    amp = (dev == "cuda")

    # Per-decision sample weight: lost games count more (the oversample), and
    # fragile-board states count even more because they are the measured Iono
    # failure mode.  This keeps the optimization target tied to the evidence in
    # recordings/intel/iono_loss_clusters.json instead of vibes.
    fragile = fragile_raw.to(device)
    w_all = torch.where(ds["label"] > 0.5, 1.0, args.loss_weight).to(device)
    fragile_mult = torch.where(
        ds["label"] > 0.5,
        torch.tensor(float(args.fragile_win_weight), device=device),
        torch.tensor(float(args.fragile_loss_weight), device=device),
    )
    w_all = torch.where(fragile, w_all * fragile_mult, w_all)
    fragile_total = int(fragile.sum().item())
    fragile_loss = int((fragile & (ds["label"] < 0.5)).sum().item())
    fragile_win = int((fragile & (ds["label"] > 0.5)).sum().item())
    print(
        f"[weights] loss_weight={args.loss_weight} "
        f"fragile_loss_weight={args.fragile_loss_weight} "
        f"fragile_win_weight={args.fragile_win_weight} "
        f"fragile_decisions={fragile_total} "
        f"(loss={fragile_loss}, win={fragile_win})",
        flush=True,
    )

    history = []
    best_val = math.inf
    best_state = None
    t0 = time.time()
    for epoch in range(args.epochs):
        model.train()
        ep = tr_idx[torch.randperm(tr_idx.numel())].to(device)
        tot = tot_p = tot_v = 0.0
        nb = 0
        for i in range(0, ep.numel(), args.batch_size):
            b = ep[i:i + args.batch_size]
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                logits, value = model(ds["state"][b], ds["options"][b], ds["mask"][b])
                label = ds["label"][b]
                v_loss = F.binary_cross_entropy_with_logits(value.float(), label)
                # advantage = outcome - detached value baseline
                adv = (label - torch.sigmoid(value.detach().float())).clamp(-1.0, 1.0)
                ce = F.cross_entropy(logits.float(), ds["pick"][b], reduction="none")
                if args.objective == "signed":
                    a_w = adv
                elif args.objective == "pos":
                    # Filtered BC: only imitate decisions that beat the value
                    # baseline. A negative weight makes the CE term unbounded
                    # below, which drives the score net to +/-inf and kills the
                    # prior head (observed: train_prior -> -3.46, top1 frozen).
                    a_w = adv.clamp_min(0.0)
                else:
                    a_w = torch.exp(adv / max(1e-3, args.beta)).clamp_max(20.0)
                p_loss = (ce * a_w * w_all[b]).mean()
                loss = p_loss + v_loss
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tot += float(loss); tot_p += float(p_loss); tot_v += float(v_loss); nb += 1
        sched.step()

        model.eval()
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
            vb = val_idx.to(device)
            logits, value = model(ds["state"][vb], ds["options"][vb], ds["mask"][vb])
            label = ds["label"][vb]
            v_loss = float(F.binary_cross_entropy_with_logits(value.float(), label))
            v_acc = float(((torch.sigmoid(value.float()) > 0.5).float() == label).float().mean())
            lg = logits.float()
            lg = torch.nan_to_num(lg, nan=-1e9, posinf=-1e9)
            hit = (lg.argmax(-1) == ds["pick"][vb]).float()
            top1 = float(hit.mean())
            # The shippable target: agreement with the pick on decisions that came
            # from a WON game. Overall top1 mixes in losses we do not want to copy.
            won = label > 0.5
            win_top1 = float(hit[won].mean()) if bool(won.any()) else float("nan")
            # Multi-option decisions only; forced 1-option states inflate top1.
            multi = ds["mask"][vb].sum(-1) > 1.5
            sel = won & multi
            win_multi_top1 = float(hit[sel].mean()) if bool(sel.any()) else float("nan")
        row = {
            "epoch": epoch, "train_loss": tot / max(1, nb),
            "train_prior": tot_p / max(1, nb), "train_value": tot_v / max(1, nb),
            "val_value_bce": v_loss, "val_value_acc": v_acc, "val_prior_top1": top1,
            "val_win_top1": win_top1, "val_win_multi_top1": win_multi_top1,
            "lr": sched.get_last_lr()[0],
        }
        history.append(row)
        print(f"[ep {epoch:3d}] loss={row['train_loss']:.4f} "
              f"prior={row['train_prior']:+.4f} value={row['train_value']:.4f} | "
              f"val_bce={v_loss:.4f} val_acc={v_acc:.3f} agree_top1={top1:.3f} "
              f"win_multi_top1={win_multi_top1:.3f}", flush=True)
        # Lower is better for both criteria, so the prior criterion is negated.
        crit = v_loss if args.select_on == "value" else -(
            win_multi_top1 if win_multi_top1 == win_multi_top1 else -1.0)
        if crit < best_val:
            best_val = crit
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    tag = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = out_dir / f"iono_prior_{tag}.pt"
    torch.save({
        "state_dict": best_state or model.state_dict(),
        "state_dim": state_dim, "option_dim": option_dim, "hidden": args.hidden,
        "max_options": args.max_options,
        "state_mean": mean, "state_std": std,
        "args": vars(args),
    }, ckpt_path)
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "checkpoint": str(ckpt_path),
        "decisions": n, "val_decisions": n_val,
        "objective": args.objective, "select_on": args.select_on,
        "loss_weight": args.loss_weight,
        "fragile_loss_weight": args.fragile_loss_weight,
        "fragile_win_weight": args.fragile_win_weight,
        "fragile_decisions": fragile_total,
        "fragile_loss_decisions": fragile_loss,
        "fragile_win_decisions": fragile_win,
        "best_criterion": best_val,
        "best_val_win_multi_top1": max(
            (h["val_win_multi_top1"] for h in history
             if h["val_win_multi_top1"] == h["val_win_multi_top1"]), default=None),
        "final": history[-1] if history else None,
        "elapsed_s": round(time.time() - t0, 1),
        "device": str(device),
        "history": history,
    }
    (ckpt_path.with_suffix(".json")).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[done] {time.time() - t0:.0f}s  best_val_bce={best_val:.4f}  -> {ckpt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
