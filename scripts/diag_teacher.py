"""Diagnostic: measure the MaskablePPO teacher's own win-rate.

Splits the Track B failure into (A) bad teacher [training problem] vs
(B) good teacher lost in distillation [distill problem]. Plays the loaded
teacher policy directly in the env and counts terminal results.

    python scripts/diag_teacher.py --deck report/rl_deck_campaign/best_deck.csv \
        --opponents benchmark --episodes 60
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL = ROOT / "agent" / "models" / "rl_policy.zip"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", required=True)
    parser.add_argument("--opponents", choices=("benchmark", "pool"), default="benchmark")
    parser.add_argument("--episodes", type=int, default=60)
    parser.add_argument("--model", default=str(MODEL))
    parser.add_argument("--deterministic", action="store_true", default=True)
    parser.add_argument("--stochastic", dest="deterministic", action="store_false")
    args = parser.parse_args(argv)

    from sb3_contrib import MaskablePPO

    from rl.env_factory import make_masked_cabt_env, resolve_deck_path

    deck = resolve_deck_path(args.deck)
    env = make_masked_cabt_env(deck, opponents=args.opponents, seed=0)
    model = MaskablePPO.load(str(Path(args.model).with_suffix("")), env=env)

    base = env
    while hasattr(base, "env"):
        base = base.env

    results = Counter()  # "win" / "loss" / "draw_trunc" / "unfinished"
    ep_rewards = []
    for ep in range(args.episodes):
        obs, info = env.reset(seed=10_000 + ep)
        terminated = truncated = False
        total_r = 0.0
        while not (terminated or truncated):
            mask = info.get("action_mask")
            action, _ = model.predict(obs, action_masks=mask, deterministic=args.deterministic)
            obs, reward, terminated, truncated, info = env.step(int(action))
            total_r += reward
        ep_rewards.append(total_r)
        # Read the true terminal result from the engine, NOT the reward sign:
        # reward is shaped (0.01*board_value delta per step), so its sign is
        # unrelated to who actually won.
        cur = (base._obs or {}).get("current") or {}
        result = cur.get("result", -1)
        if result == 0:
            results["win"] += 1
        elif result == 1:
            results["loss"] += 1
        elif result != -1:
            results["draw"] += 1
        else:
            results["unfinished"] += 1
    env.close()

    wins = results["win"]
    losses = results["loss"]
    decided = wins + losses
    wr = wins / decided if decided else float("nan")
    print(f"=== Teacher diagnostic ({args.opponents}, {args.episodes} eps, "
          f"deterministic={args.deterministic}) ===")
    print(f"deck: {deck.name}")
    print(f"results: {dict(results)}")
    print(f"win-rate (decided games): {wins}/{decided} = {wr:.1%}")
    print(f"mean episode reward: {np.mean(ep_rewards):+.3f}  "
          f"(min {np.min(ep_rewards):+.2f}, max {np.max(ep_rewards):+.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
