"""Shared CabtEnv construction for Track B RL training and distillation."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal

ROOT = Path(__file__).resolve().parents[1]

OpponentMode = Literal["benchmark", "pool"]


def resolve_deck_path(deck_path: str | Path | None) -> Path:
    path = Path(deck_path or ROOT / "agent" / "deck.csv")
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"deck not found: {path}")
    return path


def _load_deck_ids(path: Path) -> list[int]:
    return [int(x) for x in path.read_text().splitlines() if x.strip()]


def load_named_opponents(mode: OpponentMode = "benchmark") -> dict[str, list[int]]:
    """Return {name: deck} opponent map (names allow holdout filtering)."""
    if mode == "benchmark":
        from rl.benchmark import load_suite

        return {d.name: d.load() for d in load_suite()}
    if mode == "pool":
        from scripts.arena import pool_decks

        decks = dict(pool_decks())
        if not decks:
            raise FileNotFoundError("no pool_*.csv opponents found under agent_decks/")
        return decks
    raise ValueError(f"unknown opponent mode: {mode}")


def load_opponent_decks(
    mode: OpponentMode = "benchmark",
    exclude: set[str] | None = None,
) -> list[list[int]]:
    """Return opponent deck lists for training rollouts, minus any `exclude` names."""
    named = load_named_opponents(mode)
    exclude = exclude or set()
    decks = [deck for name, deck in named.items() if name not in exclude]
    if not decks:
        raise FileNotFoundError(f"no opponents left after excluding {exclude} from {mode}")
    return decks


def load_named_deck(name_or_path: str, mode: OpponentMode = "benchmark") -> list[int]:
    """Load one opponent deck by suite name (e.g. 'a2_kyogre') or by file path."""
    named = load_named_opponents(mode)
    if name_or_path in named:
        return named[name_or_path]
    path = Path(name_or_path)
    if not path.is_absolute():
        path = ROOT / path
    if path.exists():
        return _load_deck_ids(path)
    raise FileNotFoundError(f"holdout deck not found by name or path: {name_or_path}")


def make_masked_cabt_env(
    deck_path: str | Path,
    *,
    opponents: OpponentMode = "benchmark",
    seed: int = 0,
    exclude: set[str] | None = None,
    opp_decks: list[list[int]] | None = None,
):
    """Return ActionMasker-wrapped CabtEnv for MaskablePPO.

    `exclude` drops opponents by name (held-out generalization probes);
    `opp_decks` overrides the opponent set entirely (e.g. eval vs one deck).
    """
    import numpy as np
    from sb3_contrib.common.wrappers import ActionMasker

    from rl.cabt_env import CabtEnv

    deck = resolve_deck_path(deck_path)
    if opp_decks is None:
        opp_decks = load_opponent_decks(opponents, exclude=exclude)

    def mask_fn(env):
        info = getattr(env.unwrapped, "_last_info", {})
        mask = info.get("action_mask") if isinstance(info, dict) else None
        if mask is None:
            return None
        return np.asarray(mask, dtype=bool)

    class MaskedCabtEnv(CabtEnv):
        def reset(self, *, seed=None, options=None):
            obs, info = super().reset(seed=seed, options=options)
            self._last_info = info
            return obs, info

        def step(self, action):
            obs, reward, terminated, truncated, info = super().step(action)
            self._last_info = info
            return obs, reward, terminated, truncated, info

    env = MaskedCabtEnv(
        deck_path=deck,
        opponent_decks=opp_decks,
        seed=seed,
    )
    return ActionMasker(env, mask_fn)


def make_env_thunk(
    deck_path: str | Path,
    *,
    opponents: OpponentMode = "benchmark",
    seed: int = 0,
    exclude: set[str] | None = None,
) -> Callable[[], object]:
    """SubprocVecEnv factory: each worker gets a distinct seed offset."""

    def _thunk():
        return make_masked_cabt_env(deck_path, opponents=opponents, seed=seed, exclude=exclude)

    return _thunk


def deck_slug(deck_path: str | Path) -> str:
    """Stable short name from deck path (e.g. a2_kyogre_33_energy)."""
    path = resolve_deck_path(deck_path)
    name = path.stem
    for prefix in ("pool_", "a2_", "a3_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.replace("_", "-")[:32].strip("-") or "deck"
