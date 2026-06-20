"""The win-rate surrogate must learn a synthetic matchup function (NumPy path)."""

import numpy as np

from rl.winrate_surrogate import WinRateSurrogate, deck_features, pair_features


def _rand_deck(rng, strength_card):
    # 60 cards drawn from a small id space; include `strength_card` copies to vary strength
    base = list(rng.integers(1, 40, size=60 - 4))
    return base + [strength_card] * 4


def _true_winrate(a, b):
    # ground truth: deck with more high-id cards is stronger
    sa, sb = sum(a), sum(b)
    return 1.0 / (1.0 + np.exp(-(sa - sb) / 50.0))


def test_surrogate_learns_matchup_signal():
    rng = np.random.default_rng(0)
    decks = [_rand_deck(rng, int(rng.integers(1, 60))) for _ in range(60)]
    pairs, labels = [], []
    for _ in range(800):
        a = decks[rng.integers(len(decks))]
        b = decks[rng.integers(len(decks))]
        pairs.append((a, b))
        labels.append(_true_winrate(a, b))

    split = 640
    sur = WinRateSurrogate(pool=None, hidden=64, seed=0)
    sur.fit(pairs[:split], labels[:split], epochs=400, lr=0.1)

    preds = [sur.predict_pair(a, b) for a, b in pairs[split:]]
    truth = labels[split:]
    # predictions should correlate strongly with the true win rates
    corr = np.corrcoef(preds, truth)[0, 1]
    assert corr > 0.6, f"surrogate failed to learn (corr={corr:.2f})"
    # and predict the favourite correctly most of the time
    acc = np.mean([(p > 0.5) == (t > 0.5) for p, t in zip(preds, truth)])
    assert acc > 0.7, f"surrogate sign accuracy too low ({acc:.2f})"


def test_predict_matrix_shape():
    rng = np.random.default_rng(1)
    rows = [list(rng.integers(1, 40, size=60)) for _ in range(3)]
    cols = [list(rng.integers(1, 40, size=60)) for _ in range(5)]
    sur = WinRateSurrogate(pool=None)
    M = sur.predict_matrix(rows, cols)
    assert M.shape == (3, 5)
    assert ((M >= 0) & (M <= 1)).all()
