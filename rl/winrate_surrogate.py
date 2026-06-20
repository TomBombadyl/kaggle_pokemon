"""Win-rate surrogate: predict P(deck A beats deck B) without simulating.

Why: ranking D decks vs D opponents at fine resolution costs O(D^2 * G) games
(the wall in report/robust_deck_optimization_design.md §2). A surrogate learns
the matchup function from the games we *do* simulate, predicts the rest, and
lets the search **simulate only the uncertain/high-impact matchups**. This is
the highest-leverage GPU use here: the cabt engine is CPU-only, but the
surrogate trains and predicts on GPU.

Design:
- Deck -> feature vector: composition (energy/pokemon/trainer), distinct count,
  basic/evolution counts, and a hashed bag-of-cards (captures archetype).
- Pairwise input: [feat_A, feat_B, feat_A - feat_B].
- Model: small MLP. Uses **PyTorch (CUDA if available)** when torch is
  installed; otherwise a dependency-free NumPy MLP (same math) so the pipeline
  and tests run anywhere. Identical interface either way.

This module is an *accelerator*: the search is correct without it; with it, it
needs far fewer real games. Predictions must never be the final word on a
close/important matchup — always confirm those with real games.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HASH_DIM = 128


# --------------------------------------------------------------------------- #
# Features
# --------------------------------------------------------------------------- #
def deck_features(deck: list[int], pool=None) -> np.ndarray:
    """Fixed-length feature vector for a 60-card deck. Pool optional (roles)."""
    from collections import Counter

    counts = Counter(deck)
    energy = pokemon = trainer = 0
    evo = basic = 0
    if pool is not None:
        from scripts.validate_deck import CardInfo  # noqa: F401
        for cid, n in counts.items():
            info = pool.get(cid)
            if info is None:
                trainer += n
                continue
            if info.is_basic_energy:
                energy += n
            elif info.is_basic_pokemon:
                pokemon += n
                basic += n
            elif info.is_evolution:
                pokemon += n
                evo += n
            else:
                trainer += n
    comp = np.array([
        energy / 60.0, pokemon / 60.0, trainer / 60.0,
        len(counts) / 60.0, basic / 60.0, evo / 60.0,
    ], dtype=np.float64)

    bag = np.zeros(HASH_DIM, dtype=np.float64)
    for cid, n in counts.items():
        bag[hash(("c", int(cid))) % HASH_DIM] += n / 4.0
    return np.concatenate([comp, bag])


def feature_dim(pool=None) -> int:
    return 6 + HASH_DIM


def pair_features(fa: np.ndarray, fb: np.ndarray) -> np.ndarray:
    return np.concatenate([fa, fb, fa - fb])


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class _NumpyMLP:
    """One-hidden-layer MLP, sigmoid output, BCE loss. Pure NumPy."""

    def __init__(self, in_dim: int, hidden: int = 64, seed: int = 0):
        rng = np.random.default_rng(seed)
        s1 = np.sqrt(2.0 / in_dim)
        self.W1 = rng.normal(0, s1, (in_dim, hidden))
        self.b1 = np.zeros(hidden)
        self.W2 = rng.normal(0, np.sqrt(2.0 / hidden), (hidden, 1))
        self.b2 = np.zeros(1)

    def forward(self, X):
        self.Z1 = X @ self.W1 + self.b1
        self.A1 = np.maximum(0.0, self.Z1)
        self.Z2 = self.A1 @ self.W2 + self.b2
        return _sigmoid(self.Z2).ravel()

    def fit(self, X, y, epochs=300, lr=0.05, l2=1e-4):
        n = len(y)
        y = y.reshape(-1, 1)
        for _ in range(epochs):
            p = self.forward(X).reshape(-1, 1)
            dZ2 = (p - y) / n
            dW2 = self.A1.T @ dZ2 + l2 * self.W2
            db2 = dZ2.sum(0)
            dA1 = dZ2 @ self.W2.T
            dZ1 = dA1 * (self.Z1 > 0)
            dW1 = X.T @ dZ1 + l2 * self.W1
            db1 = dZ1.sum(0)
            self.W2 -= lr * dW2; self.b2 -= lr * db2
            self.W1 -= lr * dW1; self.b1 -= lr * db1
        return self

    def predict(self, X):
        return self.forward(X)


class WinRateSurrogate:
    """Predicts P(A beats B). GPU (torch) if available, else NumPy."""

    def __init__(self, pool=None, hidden: int = 64, seed: int = 0, prefer_gpu: bool = True):
        self.pool = pool
        self.hidden = hidden
        self.seed = seed
        self.in_dim = 3 * feature_dim(pool)
        self.backend = "numpy"
        self._torch = None
        if prefer_gpu:
            try:
                import torch  # noqa: F401
                self._torch = torch
                self.backend = "torch-cuda" if torch.cuda.is_available() else "torch-cpu"
            except Exception:
                self._torch = None
        self._init_model()

    def _init_model(self):
        if self._torch is not None:
            t = self._torch
            self.device = t.device("cuda" if t.cuda.is_available() else "cpu")
            t.manual_seed(self.seed)
            self.net = t.nn.Sequential(
                t.nn.Linear(self.in_dim, self.hidden), t.nn.ReLU(),
                t.nn.Linear(self.hidden, 1),
            ).to(self.device)
        else:
            self.net = _NumpyMLP(self.in_dim, self.hidden, self.seed)

    def _pair_matrix(self, pairs):
        return np.stack([pair_features(deck_features(a, self.pool),
                                       deck_features(b, self.pool)) for a, b in pairs])

    def fit(self, pairs, win_rates, epochs: int = 300, lr: float = 0.05):
        X = self._pair_matrix(pairs)
        y = np.asarray(win_rates, dtype=np.float64)
        if self._torch is not None:
            t = self._torch
            Xt = t.tensor(X, dtype=t.float32, device=self.device)
            yt = t.tensor(y, dtype=t.float32, device=self.device).view(-1, 1)
            opt = t.optim.Adam(self.net.parameters(), lr=1e-3)
            loss_fn = t.nn.BCEWithLogitsLoss()
            self.net.train()
            for _ in range(max(epochs, 400)):
                opt.zero_grad()
                loss = loss_fn(self.net(Xt), yt)
                loss.backward(); opt.step()
        else:
            self.net.fit(X, y, epochs=epochs, lr=lr)
        return self

    def predict_pair(self, deck_a, deck_b) -> float:
        X = self._pair_matrix([(deck_a, deck_b)])
        return float(self.predict_batch_X(X)[0])

    def predict_batch_X(self, X):
        if self._torch is not None:
            t = self._torch
            self.net.eval()
            with t.no_grad():
                z = self.net(t.tensor(X, dtype=t.float32, device=self.device))
                return t.sigmoid(z).view(-1).cpu().numpy()
        return self.net.predict(X)

    def predict_matrix(self, row_decks, col_decks) -> np.ndarray:
        """Full predicted payoff matrix P(row beats col) for cheap pruning."""
        rf = [deck_features(d, self.pool) for d in row_decks]
        cf = [deck_features(d, self.pool) for d in col_decks]
        X = np.stack([pair_features(a, b) for a in rf for b in cf])
        preds = self.predict_batch_X(X)
        return preds.reshape(len(row_decks), len(col_decks))
