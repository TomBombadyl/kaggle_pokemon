"""Train a small masked option-scoring MLP on traces; export numpy weights."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TRACE_DIR = ROOT / "data" / "traces"
MODEL_DIR = ROOT / "agent" / "models"
sys.path.insert(0, str(ROOT))

from agent.features import FEATURE_VERSION, OPTION_DIM, STATE_DIM  # noqa: E402


def load_traces(trace_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    for path in sorted(trace_dir.glob("*.npz")):
        data = np.load(path)
        states = data["states"]
        actions = data["actions"]
        if "options" in data:
            opts = data["options"]
            for i in range(len(actions)):
                xs.append(np.concatenate([states[i], opts[i, actions[i]]]))
                ys.append(1.0)
        else:
            # Fallback: state-only labels (weaker supervision)
            for i in range(len(actions)):
                xs.append(states[i])
                ys.append(float(actions[i]))
    if not xs:
        rng = np.random.default_rng(0)
        n = 256
        xs = rng.standard_normal((n, STATE_DIM + OPTION_DIM)).astype(np.float32)
        ys = rng.integers(0, 5, size=n).astype(np.float32)
    x = np.stack(xs).astype(np.float32)
    y = np.array(ys, dtype=np.float32)
    return x, y


def train_mlp(x: np.ndarray, y: np.ndarray, hidden: int = 64, epochs: int = 20) -> dict:
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        return train_numpy(x, y, hidden)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = nn.Sequential(
        nn.Linear(x.shape[1], hidden),
        nn.Tanh(),
        nn.Linear(hidden, 1),
    ).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    xt = torch.tensor(x, device=device)
    yt = torch.tensor(y, device=device).unsqueeze(1)
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        pred = model(xt)
        loss = loss_fn(pred, yt)
        loss.backward()
        opt.step()
    w1 = model[0].weight.detach().cpu().numpy().T.astype(np.float32)
    b1 = model[0].bias.detach().cpu().numpy().astype(np.float32)
    w2 = model[2].weight.detach().cpu().numpy().T.astype(np.float32)
    b2 = model[2].bias.detach().cpu().numpy().astype(np.float32)
    return {"w1": w1, "b1": b1, "w2": w2, "b2": b2}


def train_numpy(x: np.ndarray, y: np.ndarray, hidden: int) -> dict:
    rng = np.random.default_rng(0)
    in_dim = x.shape[1]
    w1 = rng.standard_normal((in_dim, hidden)).astype(np.float32) * 0.05
    b1 = np.zeros(hidden, dtype=np.float32)
    w2 = rng.standard_normal((hidden, 1)).astype(np.float32) * 0.05
    b2 = np.zeros(1, dtype=np.float32)
    lr = 0.01
    for _ in range(50):
        h = np.tanh(x @ w1 + b1)
        pred = (h @ w2 + b2).squeeze()
        err = pred - y
        w2 -= lr * (h.T @ err).reshape(-1, 1) / len(y)
        b2 -= lr * err.mean()
        dh = (err[:, None] * w2.T) * (1 - h ** 2)
        w1 -= lr * (x.T @ dh) / len(y)
        b1 -= lr * dh.mean(axis=0)
    return {"w1": w1, "b1": b1, "w2": w2, "b2": b2.squeeze()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", default=str(TRACE_DIR))
    parser.add_argument("--out", default=str(MODEL_DIR / "bc_v1.npz"))
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args(argv)

    x, y = load_traces(Path(args.trace_dir))
    weights = train_mlp(x, y, epochs=args.epochs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        feature_version=FEATURE_VERSION,
        state_dim=STATE_DIM,
        option_dim=OPTION_DIM,
        **weights,
    )
    print(f"exported BC weights to {out} ({x.shape[0]} samples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
