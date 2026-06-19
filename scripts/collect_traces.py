"""Parallel trace collection for behavior cloning."""

from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
TRACE_DIR = ROOT / "data" / "traces"
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(ROOT))

from agent.agent import build_agent  # noqa: E402
from agent.evalfn import board_value  # noqa: E402
from agent.features import FEATURE_VERSION, OPTION_DIM, STATE_DIM, option_features, state_features  # noqa: E402


def _load_deck(path: Path) -> list[int]:
    return [int(x) for x in path.read_text().splitlines() if x.strip()][:60]


def _play_game(deck0, deck1, seed: int, max_steps: int) -> dict | None:
    sys.path.insert(0, str(ENGINE_DIR))
    sys.path.insert(0, str(ROOT))
    from cg import game  # noqa: WPS433
    from cg.sim import Battle, lib  # noqa: WPS433

    agent_a = build_agent(seed=seed)
    agent_b = build_agent(seed=seed + 5000)
    policies = (agent_a, agent_b)

    states, options_mats, actions, rewards = [], [], [], []
    try:
        obs, start = game.battle_start(deck0, deck1)
        if obs is None:
            return None
        outcome = -1
        for _ in range(max_steps):
            cur = obs.get("current")
            if cur is not None and cur.get("result", -1) != -1:
                outcome = int(cur["result"])
                break
            sel = obs.get("select")
            if sel is None:
                outcome = -1
                break
            player = lib.GetBattleData(Battle.battle_ptr).selectPlayer
            policy = policies[player]
            select = obs["select"]
            opts = select.get("option") or []
            if opts:
                states.append(state_features(obs))
                opt_mat = np.stack([option_features(obs, o) for o in opts])
                options_mats.append(opt_mat)
                choice = policy(obs)
                idx = choice[0] if choice else 0
                actions.append(idx)
                rewards.append(board_value(obs))
            obs = game.battle_select(policy(obs))
        else:
            outcome = -1
    except Exception:
        return None
    finally:
        try:
            game.battle_finish()
        except Exception:
            pass

    if not states:
        return None
    return {
        "states": np.stack(states),
        "actions": np.array(actions, dtype=np.int32),
        "rewards": np.array(rewards, dtype=np.float32),
        "outcome": np.array([outcome], dtype=np.int32),
        "feature_version": np.array([FEATURE_VERSION], dtype=np.int32),
        "state_dim": np.array([STATE_DIM], dtype=np.int32),
        "option_dim": np.array([OPTION_DIM], dtype=np.int32),
    }


def _worker(args: tuple) -> str | None:
    shard_id, games, deck_path, max_steps = args
    deck = _load_deck(Path(deck_path))
    opp = deck
    out_path = TRACE_DIR / f"traces_{shard_id:04d}.npz"
    shard_states, shard_actions, shard_rewards, shard_outcomes = [], [], [], []
    for g in range(games):
        data = _play_game(deck, opp, shard_id * 1000 + g, max_steps)
        if data is None:
            continue
        shard_states.append(data["states"])
        shard_actions.append(data["actions"])
        shard_rewards.append(data["rewards"])
        shard_outcomes.append(data["outcome"])
    if not shard_states:
        return None
    np.savez_compressed(
        out_path,
        states=np.concatenate(shard_states),
        actions=np.concatenate(shard_actions),
        rewards=np.concatenate(shard_rewards),
        outcomes=np.concatenate(shard_outcomes),
        feature_version=FEATURE_VERSION,
    )
    return str(out_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--shards", type=int, default=2)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--deck", default=str(ROOT / "agent" / "deck.csv"))
    parser.add_argument("--max-steps", type=int, default=6000)
    args = parser.parse_args(argv)

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    games_per_shard = max(1, args.games // args.shards)
    tasks = [(i, games_per_shard, args.deck, args.max_steps) for i in range(args.shards)]
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=max(1, args.workers)) as pool:
        paths = [p for p in pool.map(_worker, tasks) if p]
    print(f"wrote {len(paths)} trace shard(s) under {TRACE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
