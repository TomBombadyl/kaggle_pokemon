"""MaskablePPO training entry point (training-only; needs sb3-contrib + torch)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "report" / "rl" / "ppo_checkpoint"
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=2048)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
        from stable_baselines3.common.vec_env import SubprocVecEnv
    except ImportError:
        print("SKIP: install torch, gymnasium, stable-baselines3, sb3-contrib for RL training")
        CHECKPOINT.mkdir(parents=True, exist_ok=True)
        (CHECKPOINT / "README.txt").write_text(
            "RL training skipped — training deps not installed.\n", encoding="utf-8",
        )
        return 0

    from rl.cabt_env import CabtEnv  # noqa: E402
    from rl.league import League  # noqa: E402

    league = League.default()

    def make_env(seed: int):
        opp = league.sample_opponent()
        def _init():
            return CabtEnv(
                deck_path=str(ROOT / "agent" / "deck.csv"),
                opponent_deck_path=str(opp.deck_path),
                seed=seed,
            )
        return _init

    n_envs = 2
    env = SubprocVecEnv([make_env(i) for i in range(n_envs)])

    model_path = CHECKPOINT / "maskable_ppo.zip"
    if args.resume and model_path.exists():
        model = MaskablePPO.load(model_path, env=env)
    else:
        model = MaskablePPO("MultiInputPolicy", env, verbose=1)

    model.learn(total_timesteps=args.timesteps)
    CHECKPOINT.mkdir(parents=True, exist_ok=True)
    model.save(model_path)
    print(f"saved {model_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
