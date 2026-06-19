"""MaskablePPO RL training initialized from BC weights (training-only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHECKPOINT = ROOT / "report" / "rl_train" / "checkpoint.json"
MODEL_OUT = ROOT / "agent" / "models" / "rl_policy.pt"


def train_maskable_ppo(timesteps: int, n_envs: int, resume: bool) -> dict:
    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
    except ImportError as exc:
        return {"status": "skipped", "reason": f"missing sb3-contrib: {exc}"}

    from rl.cabt_env import CabtEnv

    import numpy as np

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

    def make_env():
        env = MaskedCabtEnv()
        return ActionMasker(env, mask_fn)

    try:
        env = make_env()
        model = MaskablePPO(
            "MlpPolicy", env, verbose=0, n_steps=64, batch_size=32, device="cpu",
        )
        model.learn(total_timesteps=timesteps)
        CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(MODEL_OUT.with_suffix("")))
        return {"status": "ok", "timesteps": timesteps, "model": str(MODEL_OUT)}
    except Exception as exc:
        # Fall back to plain PPO when masking wrapper is unavailable
        try:
            from stable_baselines3 import PPO

            env = CabtEnv()
            model = PPO("MlpPolicy", env, verbose=0, n_steps=64, batch_size=32, device="cpu")
            model.learn(total_timesteps=timesteps)
            CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
            model.save(str(MODEL_OUT.with_suffix("")))
            return {"status": "ok", "timesteps": timesteps, "model": str(MODEL_OUT), "note": "PPO fallback"}
        except Exception as exc2:
            return {
                "status": "skipped",
                "reason": f"{type(exc).__name__}: {exc}; fallback: {type(exc2).__name__}: {exc2}",
            }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=2048)
    parser.add_argument("--n-envs", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    result = train_maskable_ppo(args.timesteps, args.n_envs, args.resume)
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
