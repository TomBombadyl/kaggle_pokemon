"""Numpy-only learned option scorer exported from behavior cloning."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from agent.agent import HeuristicScorer
from agent.features import FEATURE_VERSION, OPTION_DIM, STATE_DIM, option_features, state_features

DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "bc_v1.npz"


class LearnedScorer(HeuristicScorer):
    """Score each legal option with a small MLP; fall back to heuristic on error."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL, rng=None) -> None:
        super().__init__(rng=rng)
        self._fallback = HeuristicScorer(rng=rng)
        self._w1 = self._b1 = self._w2 = self._b2 = None
        self._feature_version = None
        self._load(model_path)

    def _load(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            return
        data = np.load(p)
        self._w1 = data["w1"]
        self._b1 = data["b1"]
        self._w2 = data["w2"]
        self._b2 = data["b2"]
        self._feature_version = int(data.get("feature_version", FEATURE_VERSION))

    @property
    def ready(self) -> bool:
        return self._w1 is not None

    def _score_option(self, obs_dict, option) -> float:
        if not self.ready or self._feature_version != FEATURE_VERSION:
            raise RuntimeError("model not loaded or feature version mismatch")
        state = state_features(obs_dict)
        opt = option_features(obs_dict, option)
        x = np.concatenate([state, opt]).astype(np.float32)
        h = np.tanh(x @ self._w1 + self._b1)
        return float(h @ self._w2 + self._b2)

    def choose(self, obs_dict, select, current, options):
        if not options or not self.ready:
            return self._fallback.choose(obs_dict, select, current, options)
        try:
            scores = [self._score_option(obs_dict, opt) for opt in options]
            sel_type = select.get("type")
            min_count = int(select.get("minCount", 1) or 0)
            max_count = int(select.get("maxCount", len(options)) or len(options))
            if min_count <= 1 and max_count == 1:
                return [int(np.argmax(scores))]
            ranked = sorted(range(len(options)), key=lambda i: scores[i], reverse=True)
            count = min(max(min_count, 1), max_count, len(options))
            return ranked[:count]
        except Exception:
            return self._fallback.choose(obs_dict, select, current, options)
