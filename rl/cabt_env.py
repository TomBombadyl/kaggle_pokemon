"""Gymnasium wrapper for the cabt engine with action masking.

Each env instance runs in its own process when vectorized via SubprocVecEnv
(mandatory: cg/sim.py holds a per-process engine singleton).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(ROOT))

from agent.agent import build_agent  # noqa: E402
from agent.evalfn import board_value  # noqa: E402
from agent.features import OPTION_DIM, STATE_DIM, option_features, state_features  # noqa: E402

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:  # pragma: no cover
    gym = None
    spaces = None

MAX_OPTIONS = 64
OBS_DIM = STATE_DIM + MAX_OPTIONS * OPTION_DIM + MAX_OPTIONS  # state + opts + mask


def _load_deck(path: Path) -> list[int]:
    return [int(x) for x in path.read_text().splitlines() if x.strip()][:60]


def flatten_obs(obs_dict: dict) -> tuple[np.ndarray, np.ndarray]:
    """Return (flat_obs, action_mask) for padded option space."""
    state = state_features(obs_dict)
    select = obs_dict.get("select") or {}
    options = select.get("option") or []
    n = min(len(options), MAX_OPTIONS)
    opt_block = np.zeros(MAX_OPTIONS * OPTION_DIM, dtype=np.float32)
    mask = np.zeros(MAX_OPTIONS, dtype=np.float32)
    for i in range(n):
        opt_block[i * OPTION_DIM:(i + 1) * OPTION_DIM] = option_features(obs_dict, options[i])
        mask[i] = 1.0
    flat = np.concatenate([state, opt_block, mask]).astype(np.float32)
    return flat, mask


if gym is not None:

    class CabtEnv(gym.Env):
        """Single-player cabt env: agent is player 0 vs a fixed opponent policy."""

        metadata = {"render_modes": []}

        def __init__(
            self,
            deck_path: str | Path | None = None,
            opp_deck_path: str | Path | None = None,
            seed: int = 0,
            max_steps: int = 6000,
            shaped_reward: bool = True,
        ) -> None:
            super().__init__()
            self._deck = _load_deck(Path(deck_path or ROOT / "agent" / "deck.csv"))
            self._opp_deck = _load_deck(Path(opp_deck_path or ROOT / "agent" / "deck.csv"))
            self._seed = seed
            self._max_steps = max_steps
            self._shaped = shaped_reward
            self._agent = build_agent(seed=seed)
            self._opp = build_agent(seed=seed + 9000)
            self.observation_space = spaces.Box(
                low=-np.inf, high=np.inf, shape=(OBS_DIM,), dtype=np.float32,
            )
            self.action_space = spaces.Discrete(MAX_OPTIONS)
            self._obs: dict | None = None
            self._step_count = 0

        def reset(self, *, seed: int | None = None, options: dict | None = None):
            super().reset(seed=seed)
            from cg import game  # noqa: WPS433
            from cg.sim import Battle, lib  # noqa: WPS433

            self._step_count = 0
            try:
                game.battle_finish()
            except Exception:
                pass
            obs, start = game.battle_start(self._deck, self._opp_deck)
            if obs is None:
                raise RuntimeError(f"battle_start failed: {start.errorType}")
            self._obs = obs
            self._lib = lib
            self._battle_ptr = Battle.battle_ptr
            flat, mask = flatten_obs(obs)
            info = {"action_mask": mask.astype(bool)}
            self._last_info = info
            return flat, info

        def _observe(self) -> np.ndarray:
            flat, _mask = flatten_obs(self._obs)
            return flat

        def _select_player(self) -> int:
            return self._lib.GetBattleData(self._battle_ptr).selectPlayer

        def step(self, action: int):
            from cg import game  # noqa: WPS433

            reward = 0.0
            terminated = truncated = False
            info: dict[str, Any] = {}
            if self._obs is None:
                raise RuntimeError("call reset() first")

            # Advance opponent turns until it is our decision or the game ends.
            for _ in range(32):
                cur = self._obs.get("current")
                if cur is not None and cur.get("result", -1) != -1:
                    terminated = True
                    result = cur["result"]
                    if result == 0:
                        reward += 1.0
                    elif result == 1:
                        reward -= 1.0
                    break
                if self._obs.get("select") is None:
                    truncated = True
                    break
                player = self._select_player()
                if player == 0:
                    break
                try:
                    self._obs = game.battle_select(self._opp(self._obs))
                except (IndexError, ValueError):
                    opts = (self._obs.get("select") or {}).get("option") or []
                    if opts:
                        self._obs = game.battle_select([0])
                    else:
                        truncated = True
                        break

            if not terminated and not truncated and self._obs.get("select") is not None:
                player = self._select_player()
                if player == 0:
                    select = self._obs.get("select") or {}
                    opts = select.get("option") or []
                    n = len(opts)
                    if n:
                        choice = min(int(action) % MAX_OPTIONS, n - 1)
                        prev_val = board_value(self._obs) if self._shaped else 0.0
                        try:
                            self._obs = game.battle_select([choice])
                        except (IndexError, ValueError):
                            try:
                                self._obs = game.battle_select(self._agent(self._obs))
                            except (IndexError, ValueError):
                                truncated = True
                        if self._shaped:
                            reward += 0.01 * (board_value(self._obs) - prev_val)

            self._step_count += 1
            cur = self._obs.get("current")
            if cur is not None and cur.get("result", -1) != -1:
                terminated = True
            if self._step_count >= self._max_steps:
                truncated = True

            flat, mask = flatten_obs(self._obs)
            info["action_mask"] = mask.astype(bool)
            self._last_info = info
            return flat, reward, terminated, truncated, info

        def close(self) -> None:
            try:
                from cg import game  # noqa: WPS433

                game.battle_finish()
            except Exception:
                pass


def make_vec_env(n_envs: int = 4, **kwargs):
    """SubprocVecEnv factory (requires gymnasium + optional sb3)."""
    if gym is None:
        raise ImportError("gymnasium required for CabtEnv")

    def _thunk():
        return CabtEnv(**kwargs)

    try:
        from stable_baselines3.common.vec_env import SubprocVecEnv

        return SubprocVecEnv([_thunk for _ in range(n_envs)])
    except ImportError:
        from gymnasium.vector import SyncVectorEnv

        return SyncVectorEnv([_thunk for _ in range(n_envs)])


if __name__ == "__main__":
    if gym is None:
        print("gymnasium not installed")
        raise SystemExit(1)
    env = CabtEnv()
    obs, _ = env.reset()
    assert obs.shape == (OBS_DIM,)
    print(f"OK: CabtEnv reset obs shape={obs.shape}")
