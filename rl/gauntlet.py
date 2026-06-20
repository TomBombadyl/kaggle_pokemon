"""Opponent gauntlet for robust deck search.

"Good against anything" means good against the *field*. We approximate the real
Simulation-ladder field with every competition-grounded opponent we can get:

  1. benchmark suite        (rl/benchmark.py: 4 anchor + 6 meta proxies)
  2. agent_decks/*.csv       (real archetypes + strong basics shipped in-repo)
  3. mined ladder decks      (report/deck_rl/mined_decks/*.csv, optional) <- the
     real opponents extracted from downloaded episode replays; the strongest
     signal. Absent until you run scripts/extract_gauntlet_from_replays.py.

Self-play elites discovered during the search are added on top by the search
loop (co-evolution), so the field expands and a deck must beat a broadening set.

Pairwise win rates use scripts.arena.play_matchup with a fixed per-opponent seed
so every candidate faces the *same* shuffles vs that opponent (common random
numbers = variance reduction). See report/robust_deck_optimization_design.md §3-4.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINED_DIR = ROOT / "report" / "deck_rl" / "mined_decks"
TMP_DIR = ROOT / "report" / "robust_deck_rl" / "_opp_decks"


@dataclass
class Opponent:
    name: str
    deck: list[int]
    path: str
    weight: float = 1.0
    source: str = "?"


def _read_deck_csv(path: Path) -> list[int]:
    out: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and line.split(",")[0].strip().lstrip("-").isdigit():
            out.append(int(line.split(",")[0]))
    return out[:60]


def signature(deck: list[int]) -> tuple[int, ...]:
    return tuple(sorted(deck))


def materialize_deck(deck: list[int], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(str(c) for c in deck) + "\n", encoding="utf-8")
    return str(path)


def _benchmark_opponents() -> list[Opponent]:
    from rl.benchmark import load_suite

    opps = []
    for o in load_suite():
        try:
            deck = o.load()
        except Exception:
            continue
        if len(deck) == 60:
            opps.append(Opponent(o.name, deck, str(o.path), float(getattr(o, "weight", 1.0)), "benchmark"))
    return opps


def _agent_deck_opponents() -> list[Opponent]:
    opps = []
    deck_dir = ROOT / "agent_decks"
    for p in sorted(deck_dir.glob("*.csv")):
        deck = _read_deck_csv(p)
        if len(deck) == 60:
            opps.append(Opponent(p.stem, deck, str(p), 1.0, "agent_decks"))
    return opps


def _mined_opponents() -> list[Opponent]:
    if not MINED_DIR.is_dir():
        return []
    opps = []
    for p in sorted(MINED_DIR.glob("*.csv")):
        deck = _read_deck_csv(p)
        if len(deck) == 60:
            # filename convention: <name>__w<weight>.csv  -> parse optional weight
            w = 1.5  # mined ladder decks are the realest field -> weight up
            if "__w" in p.stem:
                try:
                    w = float(p.stem.split("__w")[1])
                except ValueError:
                    pass
            opps.append(Opponent(p.stem, deck, str(p), w, "mined"))
    return opps


def load_gauntlet(
    *,
    include_agent_decks: bool = True,
    include_mined: bool = True,
) -> list[Opponent]:
    """Deduplicated opponent field, benchmark first then extra sources."""
    seen: set[tuple[int, ...]] = set()
    out: list[Opponent] = []
    sources = [_benchmark_opponents()]
    if include_agent_decks:
        sources.append(_agent_deck_opponents())
    if include_mined:
        sources.append(_mined_opponents())
    for group in sources:
        for o in group:
            sig = signature(o.deck)
            if sig in seen:
                continue
            seen.add(sig)
            out.append(o)
    return out


def split_train_holdout(
    opponents: list[Opponent],
    *,
    holdout_frac: float = 0.25,
    seed: int = 42,
) -> tuple[list[Opponent], list[Opponent]]:
    """Deterministic train/holdout split (held-out = honest 'vs anything' proxy)."""
    import random

    rng = random.Random(seed)
    ordered = sorted(opponents, key=lambda o: o.name)
    idx = list(range(len(ordered)))
    rng.shuffle(idx)
    n_hold = max(1, int(round(len(ordered) * holdout_frac))) if len(ordered) > 3 else 0
    hold_ids = set(idx[:n_hold])
    train = [ordered[i] for i in idx if i not in hold_ids]
    holdout = [ordered[i] for i in idx if i in hold_ids]
    return train, holdout


def winrate_vs(
    deck: list[int],
    deck_path: str,
    opp: Opponent,
    *,
    games: int = 6,
    workers: int = 2,
    scorer: str | None = "heuristic",
    seed: int = 1234,
) -> tuple[float, int]:
    """Win rate of `deck` vs one opponent (seats swapped). Returns (rate, games_played)."""
    from scripts.arena import play_matchup

    res = play_matchup(
        "cand", deck, opp.name, opp.deck, games, 6000,
        workers=workers, scorer_a=scorer, deck_path_a=deck_path,
        scorer_b=scorer, deck_path_b=opp.path, seed=seed,
    )
    decisive = res["a_wins"] + res["b_wins"]
    rate = res["a_wins"] / decisive if decisive > 0 else 0.5
    return rate, decisive
