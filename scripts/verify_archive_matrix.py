"""Compare packaged submission archives against each other.

This uses each archive's packaged `main.py` and `deck.csv`, then runs local cabt
games with side swapping. It is a stronger pre-submit check than source-only
matrix runs because it exercises the packaged entry points.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import random
import shutil
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
OUT_DIR = ROOT / "report" / "eval"

sys.path.insert(0, str(ENGINE_DIR))
from cg import game  # noqa: E402
from cg.sim import Battle, lib  # noqa: E402


@dataclass
class PackagedAgent:
    name: str
    tmp: tempfile.TemporaryDirectory
    agent: object
    deck: list[int]


def _clear_submission_modules() -> None:
    prefixes = ("agent", "agent_snapshots")
    for name in list(sys.modules):
        if name in prefixes or any(name.startswith(f"{prefix}.") for prefix in prefixes):
            del sys.modules[name]


def load_packaged_agent(name: str, archive: Path) -> PackagedAgent:
    tmp = tempfile.TemporaryDirectory(
        prefix=f"pokemon_{name}_",
        ignore_cleanup_errors=True,
    )
    tmp_path = Path(tmp.name)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(tmp_path, filter="data")
    for required in ("main.py", "deck.csv"):
        if not (tmp_path / required).exists():
            tmp.cleanup()
            raise RuntimeError(f"{archive} missing {required}")
    deck = [int(x) for x in (tmp_path / "deck.csv").read_text().splitlines() if x.strip()][:60]
    if len(deck) != 60:
        tmp.cleanup()
        raise RuntimeError(f"{archive} deck has {len(deck)} cards")

    _clear_submission_modules()
    sys.path.insert(0, str(tmp_path))
    try:
        spec = importlib.util.spec_from_file_location(f"submission_{name}", tmp_path / "main.py")
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not import {archive}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return PackagedAgent(name=name, tmp=tmp, agent=module.agent, deck=deck)
    finally:
        sys.path.remove(str(tmp_path))


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


def select_player() -> int:
    return lib.GetBattleData(Battle.battle_ptr).selectPlayer


def run_game(deck0, deck1, pol0, pol1, max_steps: int) -> tuple[int, int]:
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
            obs = game.battle_select(policies[select_player()](obs))
        return -1, max_steps
    finally:
        game.battle_finish()


def play_match(a: PackagedAgent, b: PackagedAgent, games: int, max_steps: int) -> dict[str, object]:
    a_wins = b_wins = draws = unfinished = steps_total = 0
    for i in range(games):
        if i % 2 == 0:
            result, steps = run_game(a.deck, b.deck, a.agent, b.agent, max_steps)
            a_win = result == 0
            b_win = result == 1
        else:
            result, steps = run_game(b.deck, a.deck, b.agent, a.agent, max_steps)
            a_win = result == 1
            b_win = result == 0
        steps_total += steps
        if result == 2:
            draws += 1
        elif result == -1:
            unfinished += 1
        elif a_win:
            a_wins += 1
        elif b_win:
            b_wins += 1
    decided = a_wins + b_wins
    return {
        "a": a.name,
        "b": b.name,
        "games": games,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": draws,
        "unfinished": unfinished,
        "a_win_pct": round(100.0 * a_wins / decided, 2) if decided else 0.0,
        "avg_steps": round(steps_total / games, 1) if games else 0.0,
    }


def parse_candidate(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise ValueError("candidate must be NAME=ARCHIVE")
    name, archive = raw.split("=", 1)
    path = Path(archive)
    return name, path if path.is_absolute() else ROOT / path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", action="append", required=True, help="NAME=archive.tar.gz")
    parser.add_argument("--games", type=int, default=60)
    parser.add_argument("--max-steps", type=int, default=6000)
    parser.add_argument("--tag", default="archive_matrix")
    args = parser.parse_args(argv)

    agents = []
    rows = []
    try:
        for raw in args.candidate:
            name, archive = parse_candidate(raw)
            agents.append(load_packaged_agent(name, archive))

        print(f"packaged archive matrix: {args.games} games per ordered pair")
        for a in agents:
            for b in agents:
                if a.name == b.name:
                    continue
                row = play_match(a, b, args.games, args.max_steps)
                rows.append(row)
                print(
                    f"{row['a']:>12} vs {row['b']:<12}: "
                    f"{row['a_wins']}/{row['games']} wins, "
                    f"{row['a_win_pct']:.1f}% decided; "
                    f"draws {row['draws']}, unfinished {row['unfinished']}"
                )
        write_outputs(rows, args.games, args.tag)
    finally:
        for agent in agents:
            agent.tmp.cleanup()
    return 0


def safe_tag(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value.strip())


def write_outputs(rows: list[dict[str, object]], games: int, tag: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"archive_matrix_{games}_{safe_tag(tag)}"
    csv_path = OUT_DIR / f"{stem}.csv"
    md_path = OUT_DIR / f"{stem}.md"
    fields = [
        "a", "b", "games", "a_wins", "b_wins", "draws",
        "unfinished", "a_win_pct", "avg_steps",
    ]
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        f"# Packaged Archive Matrix ({games} games per ordered pair)",
        "",
        "| A | B | A wins | B wins | Draws | Unfinished | A win % decided | Avg steps |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['a']} | {row['b']} | {row['a_wins']} | {row['b_wins']} | "
            f"{row['draws']} | {row['unfinished']} | {row['a_win_pct']} | "
            f"{row['avg_steps']} |"
        )
    md_path.write_text("\n".join(lines) + "\n")
    print(f"wrote {csv_path}")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    raise SystemExit(main())
