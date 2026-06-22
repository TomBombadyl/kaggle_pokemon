"""Parallel, variance-aware arena for cabt (Phase 0 foundation).

Round-robins our ``agent.agent.Agent`` piloting different decks against each
other and reports a local rating plus per-matchup Wilson 95% confidence
intervals. Also exposes an SPRT helper ("is B better than A?") with early
stopping.

WHY MULTIPROCESS (NOT THREADS): the cabt engine (cg/sim.py) calls
GameInitialize() at import and keeps a single global Battle.battle_ptr, so it is
a per-process ctypes singleton. Two concurrent games in one process would
corrupt each other. We therefore run **one game per worker process** via
``concurrent.futures.ProcessPoolExecutor`` (spawn on Windows -> a fresh engine
per worker). The engine is imported lazily inside the worker, never at module
import, so the parent process and spawn re-imports stay cheap.

Engine RNG (shuffles, coin flips) is NOT seedable from Python, so every win rate
is noisy: results carry sampling variance regardless of the Python seed. That is
exactly why we report Wilson CIs and offer SPRT.

Examples:
    # Tiny smoke run (proves multiprocessing + CI output end to end):
    python scripts/arena.py --games 4 --decks current=agent/deck.csv,dragapult=agent_decks/pool_dragapult.csv

    # Round-robin the whole meta pool plus the current deck:
    python scripts/arena.py --games 30 --pool --decks current=agent/deck.csv --workers 6

    # A/B two decks with SPRT early stopping:
    python scripts/arena.py --sprt A=agent/deck.csv B=agent_decks/pool_dragapult.csv --max-games 200
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
DECK_DIR = ROOT / "agent_decks"
DEFAULT_MAX_STEPS = 6000


# --------------------------------------------------------------------------- #
# Worker (runs in a separate process: its own engine singleton).
# --------------------------------------------------------------------------- #
def _play_game(job: tuple) -> tuple[int, int]:
    """Play ONE game in this process. Returns (winner, steps).

    winner: 0 (seat-0 wins), 1 (seat-1 wins), 2 (draw), -1 (unfinished).
    ``job`` = (deck0, deck1, seed0, seed1, path0, path1, max_steps).
    All imports are local so this is safe under spawn and never touches the
    parent's interpreter state.
    """
    deck0, deck1, seed0, seed1, path0, path1, max_steps = job
    if str(ENGINE_DIR) not in sys.path:
        sys.path.insert(0, str(ENGINE_DIR))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from cg import game
    from cg.sim import Battle, lib
    from agent.agent import Agent

    pol0 = Agent(seed=seed0, deck_path=path0)
    pol1 = Agent(seed=seed1, deck_path=path1)
    policies = (pol0, pol1)

    obs, start = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        return -1, 0
    try:
        for step in range(max_steps):
            cur = obs.get("current")
            if cur is not None and cur.get("result", -1) != -1:
                return int(cur["result"]), step
            if obs.get("select") is None:
                return -1, step
            player = lib.GetBattleData(Battle.battle_ptr).selectPlayer
            obs = game.battle_select(policies[player](obs))
        return -1, max_steps
    finally:
        game.battle_finish()


# --------------------------------------------------------------------------- #
# Statistics: Wilson CI, SPRT, Elo.
# --------------------------------------------------------------------------- #
def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score interval for a binomial proportion.

    Returns (low, center, high) as win-rate fractions in [0, 1]. With n == 0
    returns (0.0, 0.0, 1.0) to signal "unknown".
    """
    if n <= 0:
        return 0.0, 0.0, 1.0
    p = wins / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)) / denom
    return max(0.0, center - margin), p, min(1.0, center + margin)


def sprt_llr(wins: int, losses: int, p0: float, p1: float) -> float:
    """Log-likelihood ratio of H1 (win prob p1) vs H0 (win prob p0).

    Draws/unfinished should be excluded by the caller (decided games only).
    """
    p0 = min(max(p0, 1e-9), 1 - 1e-9)
    p1 = min(max(p1, 1e-9), 1 - 1e-9)
    return (
        wins * math.log(p1 / p0)
        + losses * math.log((1 - p1) / (1 - p0))
    )


def sprt_decision(
    wins: int,
    losses: int,
    p0: float = 0.5,
    p1: float = 0.55,
    alpha: float = 0.05,
    beta: float = 0.05,
) -> tuple[str, float, float, float]:
    """Sequential Probability Ratio Test on decided games.

    H0: win prob == p0 (B is not better).  H1: win prob == p1 (B is better).
    Returns (decision, llr, lower_bound, upper_bound) where decision is one of
    "accept_h1", "accept_h0", "continue".
    """
    upper = math.log((1 - beta) / alpha)   # cross above -> accept H1
    lower = math.log(beta / (1 - alpha))   # cross below -> accept H0
    llr = sprt_llr(wins, losses, p0, p1)
    if llr >= upper:
        return "accept_h1", llr, lower, upper
    if llr <= lower:
        return "accept_h0", llr, lower, upper
    return "continue", llr, lower, upper


def compute_elo(
    names: list[str],
    games: list[tuple[str, str, int]],
    k: float = 24.0,
    epochs: int = 40,
    base: float = 1500.0,
) -> dict[str, float]:
    """Approximate Elo from decided games.

    ``games`` is a list of (winner_name, loser_name, _) for decided games. We
    iterate over a reshuffled game list for several epochs so the rating does
    not depend on game order (a cheap stand-in for Bradley-Terry).
    """
    rating = {n: base for n in names}
    rng = random.Random(12345)
    order = list(games)
    for epoch in range(epochs):
        rng.shuffle(order)
        kk = k * (1.0 - 0.5 * epoch / max(1, epochs))  # anneal step size
        for winner, loser, _ in order:
            ra, rb = rating[winner], rating[loser]
            ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
            rating[winner] = ra + kk * (1.0 - ea)
            rating[loser] = rb + kk * (0.0 - (1.0 - ea))
    return rating


# --------------------------------------------------------------------------- #
# Bookkeeping.
# --------------------------------------------------------------------------- #
@dataclass
class PairRecord:
    a: str
    b: str
    a_wins: int = 0
    b_wins: int = 0
    draws: int = 0
    unfinished: int = 0

    @property
    def decided(self) -> int:
        return self.a_wins + self.b_wins


@dataclass
class Competitor:
    name: str
    deck_path: Path
    deck: list[int] = field(default_factory=list)


def load_deck(path: Path) -> list[int]:
    return [int(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()][:60]


def parse_decks(values: list[str]) -> list[Competitor]:
    """Parse repeated --decks name=path[,name=path...] into competitors."""
    competitors: dict[str, Competitor] = {}
    for value in values:
        for item in value.split(","):
            item = item.strip()
            if not item:
                continue
            if "=" not in item:
                raise ValueError(f"--decks expects NAME=PATH, got {item!r}")
            name, raw = item.split("=", 1)
            name = name.strip()
            path = Path(raw)
            if not path.is_absolute():
                path = ROOT / path
            if not path.exists():
                raise FileNotFoundError(path)
            competitors[name] = Competitor(name, path)
    return list(competitors.values())


def add_pool(competitors: list[Competitor]) -> list[Competitor]:
    existing = {c.name for c in competitors}
    for path in sorted(DECK_DIR.glob("pool_*.csv")):
        if path.stem not in existing:
            competitors.append(Competitor(path.stem, path))
    return competitors


def pool_decks() -> dict[str, list[int]]:
    """Meta pool decks as name -> card-id list (for gate/deck_search helpers)."""
    return {p.stem: load_deck(p) for p in sorted(DECK_DIR.glob("pool_*.csv"))}


def _play_game_scored(job: tuple) -> tuple[int, int]:
    """Like ``_play_game`` but allows per-seat scorer names (search/learned/None)."""
    (
        deck0, deck1, seed0, seed1, path0, path1, max_steps,
        scorer0, scorer1, model0, model1,
    ) = job
    if str(ENGINE_DIR) not in sys.path:
        sys.path.insert(0, str(ENGINE_DIR))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from cg import game
    from cg.sim import Battle, lib
    from agent.agent import Agent

    def _agent(seed: int, path: str, scorer_name: str | None, model_path: str | None):
        if scorer_name == "search":
            from agent.search_policy import SearchScorer
            return Agent(seed=seed, deck_path=path, scorer=SearchScorer())
        if scorer_name == "lucario":
            from agent.lucario_policy import LucarioScorer
            return Agent(seed=seed, deck_path=path, scorer=LucarioScorer(deck_path=path))
        if scorer_name == "lucario_search":
            from agent.search_policy import LucarioSearchScorer
            return Agent(seed=seed, deck_path=path, scorer=LucarioSearchScorer(deck_path=path))
        if scorer_name == "rulecore":
            from agent.rule_core import RuleCoreScorer
            return Agent(seed=seed, deck_path=path, scorer=RuleCoreScorer(deck_path=path))
        # 'learned' scorer retired in the Session-44 reset (see RULINGS.md R3).
        return Agent(seed=seed, deck_path=path)

    pol0 = _agent(seed0, path0, scorer0, model0)
    pol1 = _agent(seed1, path1, scorer1, model1)
    policies = (pol0, pol1)

    obs, start = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        return -1, 0
    try:
        for step in range(max_steps):
            cur = obs.get("current")
            if cur is not None and cur.get("result", -1) != -1:
                return int(cur["result"]), step
            if obs.get("select") is None:
                return -1, step
            player = lib.GetBattleData(Battle.battle_ptr).selectPlayer
            obs = game.battle_select(policies[player](obs))
        return -1, max_steps
    finally:
        game.battle_finish()


def play_matchup(
    name_a: str,
    deck_a: list[int],
    name_b: str,
    deck_b: list[int],
    games: int,
    max_steps: int,
    *,
    workers: int = 1,
    scorer_a: str | None = None,
    deck_path_a: str | None = None,
    model_path_a: str | None = None,
    scorer_b: str | None = None,
    deck_path_b: str | None = None,
    model_path_b: str | None = None,
    seed: int = 42,
) -> dict[str, int]:
    """Play ``games`` A-vs-B games (seats swapped); return win tallies for side A."""
    path_a = deck_path_a or str(ROOT / "agent" / "deck.csv")
    path_b = deck_path_b or str(DECK_DIR / f"{name_b}.csv")
    a_wins = b_wins = draws = unfinished = 0
    jobs = []
    for i in range(games):
        seed0 = seed + 2 * i
        seed1 = seed + 2 * i + 1
        if i % 2 == 0:
            jobs.append((deck_a, deck_b, seed0, seed1, path_a, path_b,
                         max_steps, scorer_a, scorer_b, model_path_a, model_path_b, "a0"))
        else:
            jobs.append((deck_b, deck_a, seed0, seed1, path_b, path_a,
                         max_steps, scorer_b, scorer_a, model_path_b, model_path_a, "a1"))
    if workers <= 1:
        results = [(_play_game_scored(j[:11]), j[11]) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
            futs = {pool.submit(_play_game_scored, j[:11]): j[11] for j in jobs}
            results = [(fut.result(), tag) for fut, tag in futs.items()]
    for (winner, _), tag in results:
        a_is_seat0 = tag == "a0"
        if winner == 2:
            draws += 1
        elif winner == -1:
            unfinished += 1
        elif (winner == 0) == a_is_seat0:
            a_wins += 1
        else:
            b_wins += 1
    return {"a_wins": a_wins, "b_wins": b_wins, "draws": draws, "unfinished": unfinished}


# --------------------------------------------------------------------------- #
# Match scheduling.
# --------------------------------------------------------------------------- #
def _build_jobs(
    a: Competitor, b: Competitor, games: int, max_steps: int, seed_base: int
) -> list[tuple]:
    """Build ``games`` jobs for an A/B match, swapping seats each game."""
    jobs = []
    for i in range(games):
        seed0 = seed_base + 2 * i
        seed1 = seed_base + 2 * i + 1
        if i % 2 == 0:  # A is seat 0
            jobs.append((a.deck, b.deck, seed0, seed1,
                         str(a.deck_path), str(b.deck_path), max_steps, "a0"))
        else:           # A is seat 1
            jobs.append((b.deck, a.deck, seed0, seed1,
                         str(b.deck_path), str(a.deck_path), max_steps, "a1"))
    return jobs


def _tally(record: PairRecord, winner: int, a_is_seat0: bool) -> None:
    if winner == 2:
        record.draws += 1
        return
    if winner == -1:
        record.unfinished += 1
        return
    a_seat = 0 if a_is_seat0 else 1
    if winner == a_seat:
        record.a_wins += 1
    else:
        record.b_wins += 1


def run_round_robin(
    competitors: list[Competitor],
    games: int,
    workers: int,
    max_steps: int,
    seed: int,
) -> tuple[list[PairRecord], dict[str, float]]:
    """Play every unordered pair ``games`` times (seats swapped); parallelised."""
    pairs: list[tuple[int, int]] = [
        (i, j) for i in range(len(competitors)) for j in range(i + 1, len(competitors))
    ]
    records: dict[tuple[int, int], PairRecord] = {}
    futures = {}
    elo_games: list[tuple[str, str, int]] = []

    with ProcessPoolExecutor(max_workers=workers) as pool:
        for pi, (i, j) in enumerate(pairs):
            a, b = competitors[i], competitors[j]
            records[(i, j)] = PairRecord(a.name, b.name)
            jobs = _build_jobs(a, b, games, max_steps, seed + pi * 100000)
            for job in jobs:
                fut = pool.submit(_play_game, job[:7])
                futures[fut] = (i, j, job[7])
        for fut in as_completed(futures):
            i, j, tag = futures[fut]
            winner, _steps = fut.result()
            rec = records[(i, j)]
            _tally(rec, winner, a_is_seat0=(tag == "a0"))

    out_records = [records[p] for p in pairs]
    for rec in out_records:
        for _ in range(rec.a_wins):
            elo_games.append((rec.a, rec.b, 1))
        for _ in range(rec.b_wins):
            elo_games.append((rec.b, rec.a, 1))
    elo = compute_elo([c.name for c in competitors], elo_games)
    return out_records, elo


def sprt_ab(
    a: Competitor,
    b: Competitor,
    workers: int,
    max_games: int,
    batch: int,
    max_steps: int,
    seed: int,
    p0: float = 0.5,
    p1: float = 0.55,
    alpha: float = 0.05,
    beta: float = 0.05,
) -> dict:
    """Play A vs B in parallel batches until SPRT decides or max_games reached.

    Tests "is B better than A?" from B's perspective (B win prob). Returns a
    summary dict. Early stops as soon as the LLR crosses a boundary.
    """
    b_wins = a_wins = draws = unfinished = played = 0
    decision = "continue"
    llr = lower = upper = 0.0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        while played < max_games and decision == "continue":
            n = min(batch, max_games - played)
            jobs = []
            for i in range(n):
                gi = played + i
                seed0 = seed + 2 * gi
                seed1 = seed + 2 * gi + 1
                if gi % 2 == 0:  # B is seat 0
                    jobs.append(((b.deck, a.deck, seed0, seed1,
                                  str(b.deck_path), str(a.deck_path), max_steps), True))
                else:            # B is seat 1
                    jobs.append(((a.deck, b.deck, seed0, seed1,
                                  str(a.deck_path), str(b.deck_path), max_steps), False))
            futs = {pool.submit(_play_game, job): b_seat0 for job, b_seat0 in jobs}
            for fut in as_completed(futs):
                b_seat0 = futs[fut]
                winner, _ = fut.result()
                played += 1
                if winner == 2:
                    draws += 1
                elif winner == -1:
                    unfinished += 1
                else:
                    b_seat = 0 if b_seat0 else 1
                    if winner == b_seat:
                        b_wins += 1
                    else:
                        a_wins += 1
            decision, llr, lower, upper = sprt_decision(
                b_wins, a_wins, p0, p1, alpha, beta
            )
    low, center, high = wilson_interval(b_wins, b_wins + a_wins)
    return {
        "a": a.name, "b": b.name,
        "b_wins": b_wins, "a_wins": a_wins, "draws": draws,
        "unfinished": unfinished, "played": played,
        "decision": decision, "llr": llr, "lower": lower, "upper": upper,
        "b_winrate": center, "ci_low": low, "ci_high": high,
        "p0": p0, "p1": p1,
    }


# --------------------------------------------------------------------------- #
# Reporting.
# --------------------------------------------------------------------------- #
def print_round_robin(records: list[PairRecord], elo: dict[str, float]) -> None:
    print("\nPer-matchup results (A vs B, seats swapped, Wilson 95% CI on A win rate)")
    print(f"{'A':<22}{'B':<22}{'A-B-D-U':>14}{'A win%':>9}{'  95% CI':>16}")
    for rec in records:
        low, center, high = wilson_interval(rec.a_wins, rec.decided)
        tally = f"{rec.a_wins}-{rec.b_wins}-{rec.draws}-{rec.unfinished}"
        ci = f"[{low*100:4.1f},{high*100:5.1f}]"
        print(f"{rec.a:<22}{rec.b:<22}{tally:>14}{center*100:8.1f}%{ci:>16}")

    print("\nLocal Elo (approx, anneal; engine RNG unseedable so treat as noisy):")
    for name, rating in sorted(elo.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {name:<28}{rating:7.1f}")


def print_sprt(result: dict) -> None:
    print("\nSPRT: is B better than A?")
    print(f"  A = {result['a']}   B = {result['b']}")
    print(f"  H0: B win prob = {result['p0']:.2f}   "
          f"H1: B win prob = {result['p1']:.2f}")
    print(f"  decided games: {result['b_wins'] + result['a_wins']} "
          f"(B {result['b_wins']} / A {result['a_wins']}), "
          f"draws {result['draws']}, unfinished {result['unfinished']}")
    print(f"  B win rate: {result['b_winrate']*100:.1f}% "
          f"(95% CI [{result['ci_low']*100:.1f}, {result['ci_high']*100:.1f}])")
    print(f"  LLR {result['llr']:.3f}  (bounds [{result['lower']:.3f}, "
          f"{result['upper']:.3f}])")
    verdict = {
        "accept_h1": "ACCEPT H1: B is better",
        "accept_h0": "ACCEPT H0: B is not better",
        "continue": "INCONCLUSIVE (hit max_games before a boundary)",
    }[result["decision"]]
    print(f"  decision: {verdict}")


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--decks", action="append", default=[],
        help="Competitors as NAME=PATH[,NAME=PATH...]. Repeatable.",
    )
    parser.add_argument(
        "--pool", action="store_true",
        help="Also add every agent_decks/pool_*.csv as a competitor.",
    )
    parser.add_argument("--games", type=int, default=10,
                        help="Games per pairing (seats swapped each game).")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                        help="Parallel worker processes (one game per process).")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--sprt", nargs=2, metavar=("A=PATH", "B=PATH"), default=None,
        help="Run an SPRT A/B test instead of a round-robin.",
    )
    parser.add_argument("--max-games", type=int, default=200,
                        help="SPRT cap on decided+undecided games.")
    parser.add_argument("--batch", type=int, default=8, help="SPRT parallel batch size.")
    parser.add_argument("--p0", type=float, default=0.5, help="SPRT H0 win prob.")
    parser.add_argument("--p1", type=float, default=0.55, help="SPRT H1 win prob.")
    args = parser.parse_args(argv)

    if args.sprt is not None:
        competitors = parse_decks([args.sprt[0], args.sprt[1]])
        if len(competitors) != 2:
            print("SPRT needs exactly two distinct competitors")
            return 2
        for c in competitors:
            c.deck = load_deck(c.deck_path)
        a, b = competitors[0], competitors[1]
        print(f"arena SPRT: {a.name} vs {b.name} "
              f"(workers={args.workers}, max_games={args.max_games})")
        result = sprt_ab(
            a, b, args.workers, args.max_games, args.batch, args.max_steps,
            args.seed, args.p0, args.p1,
        )
        print_sprt(result)
        return 0

    competitors = parse_decks(args.decks)
    if args.pool:
        competitors = add_pool(competitors)
    if len(competitors) < 2:
        print("need at least two competitors (use --decks and/or --pool)")
        return 2
    for c in competitors:
        c.deck = load_deck(c.deck_path)

    total = len(competitors) * (len(competitors) - 1) // 2 * args.games
    print(f"arena round-robin: {len(competitors)} decks, {args.games} games/pair, "
          f"{total} games total, workers={args.workers}")
    print("competitors: " + ", ".join(c.name for c in competitors))
    records, elo = run_round_robin(
        competitors, args.games, args.workers, args.max_steps, args.seed
    )
    print_round_robin(records, elo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
