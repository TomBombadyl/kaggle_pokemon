"""Run a packaged submission archive through local cabt games.

This validates the artifact we would upload, not just the working-tree agent.

Example:
    python scripts/verify_archive.py dist/candidates/a1_current_963.tar.gz --games 300
"""

from __future__ import annotations

import argparse
import importlib.util
import random
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_submission(archive: Path):
    tmp = tempfile.TemporaryDirectory(
        prefix="pokemon_archive_verify_",
        ignore_cleanup_errors=True,
    )
    tmp_path = Path(tmp.name)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(tmp_path, filter="data")

    required = ["main.py", "deck.csv", "cg/game.py", "cg/sim.py"]
    missing = [name for name in required if not (tmp_path / name).exists()]
    if missing:
        tmp.cleanup()
        raise RuntimeError(f"archive missing required files: {missing}")

    sys.path.insert(0, str(tmp_path))
    try:
        spec = importlib.util.spec_from_file_location("submission_main", tmp_path / "main.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load main.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from cg import game
        from cg.sim import Battle, lib
    except Exception:
        sys.path.remove(str(tmp_path))
        tmp.cleanup()
        raise

    deck = [int(x) for x in (tmp_path / "deck.csv").read_text().splitlines() if x.strip()][:60]
    if len(deck) != 60:
        tmp.cleanup()
        raise RuntimeError(f"deck.csv must contain 60 card IDs, got {len(deck)}")
    return tmp, module.agent, deck, game, Battle, lib


def select_player(Battle, lib) -> int:
    return lib.GetBattleData(Battle.battle_ptr).selectPlayer


def random_policy(seed: int):
    rng = random.Random(seed)

    def policy(obs):
        sel = obs["select"]
        opts = sel.get("option") or []
        if not opts:
            return []
        min_count = int(sel.get("minCount", 1) or 0)
        max_count = int(sel.get("maxCount", len(opts)) or len(opts))
        if min_count <= 0:
            return []
        count = min(max(min_count, 1), max_count, len(opts))
        return rng.sample(range(len(opts)), count)

    return policy


def run_game(game, Battle, lib, deck0, deck1, pol0, pol1, max_steps: int) -> tuple[int, int]:
    obs, start = game.battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(f"battle_start failed: err={start.errorType}")
    policies = (pol0, pol1)
    try:
        for step in range(max_steps):
            cur = obs.get("current")
            if cur is not None and cur.get("result", -1) != -1:
                return int(cur["result"]), step
            if obs.get("select") is None:
                return -1, step
            player = select_player(Battle, lib)
            obs = game.battle_select(policies[player](obs))
        return -1, max_steps
    finally:
        game.battle_finish()


def load_deck(path: Path) -> list[int]:
    deck = [int(x) for x in path.read_text().splitlines() if x.strip()][:60]
    if len(deck) != 60:
        raise RuntimeError(f"{path} must contain 60 card IDs, got {len(deck)}")
    return deck


def verify_vs_random(
    archive: Path,
    games: int,
    max_steps: int,
    opponent_deck_path: Path | None = None,
) -> dict[str, int | float]:
    tmp, agent, deck, game, Battle, lib = load_submission(archive)
    opponent_deck = load_deck(opponent_deck_path) if opponent_deck_path else deck
    try:
        agent_wins = random_wins = draws = unfinished = steps_total = 0
        for i in range(games):
            rand = random_policy(7000 + i)
            if i % 2 == 0:
                result, steps = run_game(
                    game, Battle, lib, deck, opponent_deck, agent, rand, max_steps
                )
                agent_win = result == 0
                random_win = result == 1
            else:
                result, steps = run_game(
                    game, Battle, lib, opponent_deck, deck, rand, agent, max_steps
                )
                agent_win = result == 1
                random_win = result == 0
            steps_total += steps
            if result == 2:
                draws += 1
            elif result == -1:
                unfinished += 1
            elif agent_win:
                agent_wins += 1
            elif random_win:
                random_wins += 1
        decided = agent_wins + random_wins
        win_rate = 100.0 * agent_wins / decided if decided else 0.0
        return {
            "games": games,
            "agent_wins": agent_wins,
            "random_wins": random_wins,
            "draws": draws,
            "unfinished": unfinished,
            "win_rate_decided": round(win_rate, 2),
            "avg_steps": round(steps_total / games, 1) if games else 0.0,
        }
    finally:
        tmp.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--max-steps", type=int, default=6000)
    parser.add_argument(
        "--opponent-deck",
        type=Path,
        help="Optional opponent deck CSV. Defaults to the archive deck for mirror checks.",
    )
    args = parser.parse_args(argv)

    archive = args.archive if args.archive.is_absolute() else ROOT / args.archive
    opponent_deck = None
    if args.opponent_deck:
        opponent_deck = (
            args.opponent_deck if args.opponent_deck.is_absolute()
            else ROOT / args.opponent_deck
        )
    row = verify_vs_random(archive, args.games, args.max_steps, opponent_deck)
    print(
        f"{archive}: {row['agent_wins']}/{row['games']} wins, "
        f"{row['win_rate_decided']:.2f}% decided; random {row['random_wins']}, "
        f"draws {row['draws']}, unfinished {row['unfinished']}, "
        f"avg_steps {row['avg_steps']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
