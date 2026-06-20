"""Benchmark suite for deck fitness and RL league training.

Uses meta pool decks as championship-field proxies until real Worlds lists are
added under agent_decks/benchmark/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "agent_decks" / "benchmark" / "suite.json"


@dataclass(frozen=True)
class BenchmarkDeck:
    name: str
    path: Path
    tag: str
    weight: float

    def load(self) -> list[int]:
        return [int(x) for x in self.path.read_text().splitlines() if x.strip()]


def load_suite(path: Path | None = None) -> list[BenchmarkDeck]:
    path = path or SUITE_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[BenchmarkDeck] = []
    for row in data.get("decks", []):
        p = ROOT / row["path"]
        if not p.exists():
            continue
        out.append(
            BenchmarkDeck(
                name=row["name"],
                path=p,
                tag=row.get("tag", "meta"),
                weight=float(row.get("weight", 1.0)),
            )
        )
    if not out:
        raise FileNotFoundError(f"no benchmark decks found via {path}")
    return out


def evaluate_deck_vs_benchmark(
    deck: list[int],
    *,
    games_per_opponent: int = 8,
    workers: int = 4,
    scorer: str | None = None,
    deck_path: str | None = None,
    seed: int = 42,
) -> dict:
    """Weighted win rate vs the full benchmark suite."""
    import sys
    from concurrent.futures import ProcessPoolExecutor

    sys.path.insert(0, str(ROOT))
    from scripts.arena import _play_game_scored

    suite = load_suite()
    total_w = 0.0
    weighted_wins = 0.0
    weighted_games = 0.0
    per_opponent: dict[str, dict] = {}

    path = deck_path or str(ROOT / "agent" / "deck.csv")
    all_jobs: list[tuple] = []
    job_meta: list[tuple[str, str]] = []  # (opp_name, seat tag a0|a1)

    for opp_idx, opp in enumerate(suite):
        opp_deck = opp.load()
        opp_path = str(opp.path)
        base = seed + opp_idx * 1000
        for i in range(games_per_opponent):
            seed0 = base + 2 * i
            seed1 = base + 2 * i + 1
            if i % 2 == 0:
                all_jobs.append(
                    (
                        deck,
                        opp_deck,
                        seed0,
                        seed1,
                        path,
                        opp_path,
                        6000,
                        scorer,
                        None,
                        None,
                        None,
                    )
                )
                job_meta.append((opp.name, "a0"))
            else:
                all_jobs.append(
                    (
                        opp_deck,
                        deck,
                        seed0,
                        seed1,
                        opp_path,
                        path,
                        6000,
                        None,
                        scorer,
                        None,
                        None,
                    )
                )
                job_meta.append((opp.name, "a1"))

    opp_wins: dict[str, dict[str, int]] = {
        o.name: {"a_wins": 0, "b_wins": 0, "draws": 0, "unfinished": 0} for o in suite
    }
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {pool.submit(_play_game_scored, job): meta for job, meta in zip(all_jobs, job_meta)}
        for fut, (opp_name, tag) in futs.items():
            winner, _ = fut.result()
            row = opp_wins[opp_name]
            a_is_seat0 = tag == "a0"
            if winner == 2:
                row["draws"] += 1
            elif winner == -1:
                row["unfinished"] += 1
            elif (winner == 0) == a_is_seat0:
                row["a_wins"] += 1
            else:
                row["b_wins"] += 1

    for opp in suite:
        row = opp_wins[opp.name]
        wins = row["a_wins"]
        total = row["a_wins"] + row["b_wins"]
        rate = wins / max(1, total)
        per_opponent[opp.name] = {
            "wins": wins,
            "total": total,
            "rate": rate,
            "tag": opp.tag,
            "weight": opp.weight,
        }
        weighted_wins += opp.weight * wins
        weighted_games += opp.weight * total
        total_w += opp.weight

    fitness = weighted_wins / max(1e-9, weighted_games)
    from rl.deck_balance import matchup_collapse_penalty

    collapse_penalty, min_win_rate = matchup_collapse_penalty(per_opponent)
    return {
        "fitness": fitness,
        "weighted_win_rate": fitness,
        "opponents": per_opponent,
        "suite_size": len(suite),
        "min_benchmark_win_rate": min_win_rate,
        "matchup_collapse_penalty": collapse_penalty,
    }


if __name__ == "__main__":
    deck = load_suite()[0].load()
    print(f"benchmark suite: {len(load_suite())} decks")
    print("smoke eval on first opponent deck only — use train_deck_campaign for full run")
