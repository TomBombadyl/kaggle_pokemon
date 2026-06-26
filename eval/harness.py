"""Single game loop and suite runner for real-field evaluation (Pillar 0.4)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
DECKS_DIR = ROOT / "agent_decks"

if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cg import game  # noqa: E402
from cg.sim import Battle, lib  # noqa: E402

from agent.lucario_mcts_runtime import random_agent  # noqa: E402
from agent.matchup_levers import LeverDeltas  # noqa: E402
from agent.native_opponent import make_opponent_brain  # noqa: E402
from agent.official_registry import official_archetype_for_opponent  # noqa: E402
from eval.field_registry import load_registry, opponent_meta, resolve_deck_path  # noqa: E402
from scripts.stats_utils import wilson_ci  # noqa: E402

DEFAULT_LUCARIO_DECK = DECKS_DIR / "real_mega_lucario_ex.csv"
DEFAULT_DRAGAPULT_DECK = DECKS_DIR / "dragapult_ex_sample.csv"
DEFAULT_ALAKAZAM_DECK = DECKS_DIR / "ryotasueyoshi_alakazam_best5.csv"
DEFAULT_ARCHALUDON_DECK = DECKS_DIR / "archaludon_ex_cinderace.csv"
DEFAULT_STARMIE_DECK = DECKS_DIR / "starmie_froslass_ashleysandlin.csv"
DEFAULT_ABOMASNOW_DECK = DECKS_DIR / "real_mega_abomasnow_ex.csv"
MAX_STEPS = 8000

_opp_cache: dict[str, tuple[Callable[[dict], list[int]], str]] = {}


def load_deck(path: Path | str) -> list[int]:
    return [int(x) for x in Path(path).read_text().splitlines() if x.strip()][:60]


def _select_player() -> int:
    return lib.GetBattleData(Battle.battle_ptr).selectPlayer


def run_match(
    deck_a: list[int],
    deck_b: list[int],
    brain_a: Callable[[dict], list[int]],
    brain_b: Callable[[dict], list[int]],
    *,
    max_steps: int = MAX_STEPS,
) -> str:
    """Play one game. Returns 'a', 'b', 'draw', or 'unfinished'."""
    obs, start = game.battle_start(deck_a, deck_b)
    if obs is None:
        raise RuntimeError(f"battle_start failed: err={getattr(start, 'errorType', '?')}")
    policies = (brain_a, brain_b)
    try:
        for _ in range(max_steps):
            cur = obs["current"]
            if cur is not None and cur.get("result", -1) != -1:
                r = cur["result"]
                if r == 0:
                    return "a"
                if r == 1:
                    return "b"
                if r == 2:
                    return "draw"
                return "unfinished"
            if obs["select"] is None:
                return "unfinished"
            p = _select_player()
            obs = game.battle_select(policies[p](obs))
        return "unfinished"
    finally:
        game.battle_finish()


@dataclass
class MatchupResult:
    opponent: str
    brain: str
    wins: int
    losses: int
    draws: int
    unfinished: int
    wr_pct: float
    ci_low_pct: float
    ci_high_pct: float
    games: int
    seeds: list[int] = field(default_factory=list)


@dataclass
class HarnessResult:
    hero_deck: str
    hero_brain: str
    games_per_opp: int
    opponents: list[str]
    lever_overrides: dict[str, LeverDeltas] | None
    matchups: list[MatchupResult]
    overall_wins: int = 0
    overall_games: int = 0
    overall_wr_pct: float = 0.0
    overall_ci_low_pct: float = 0.0
    overall_ci_high_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hero_deck": self.hero_deck,
            "hero_brain": self.hero_brain,
            "games_per_opp": self.games_per_opp,
            "opponents": self.opponents,
            "lever_overrides": list(self.lever_overrides.keys()) if self.lever_overrides else [],
            "matchups": [
                {
                    "opponent": m.opponent,
                    "brain": m.brain,
                    "wins": m.wins,
                    "losses": m.losses,
                    "draws": m.draws,
                    "unfinished": m.unfinished,
                    "wr_pct": m.wr_pct,
                    "ci_low_pct": m.ci_low_pct,
                    "ci_high_pct": m.ci_high_pct,
                    "games": m.games,
                }
                for m in self.matchups
            ],
            "overall": {
                "wins": self.overall_wins,
                "games": self.overall_games,
                "wr_pct": self.overall_wr_pct,
                "ci_low_pct": self.overall_ci_low_pct,
                "ci_high_pct": self.overall_ci_high_pct,
            },
        }


def _wilson_pct(wins: int, n: int) -> tuple[float, float, float]:
    if n <= 0:
        return 0.0, 0.0, 0.0
    lo, hi = wilson_ci(wins, n)
    return 100.0 * wins / n, 100.0 * lo, 100.0 * hi


def make_lucario_brain(
    deck_path: str | Path | None = None,
    *,
    lever_overrides: dict[str, LeverDeltas] | None = None,
) -> Callable[[dict], list[int]]:
    from agent.agent import build_agent
    from agent.lucario_policy import LucarioScorer

    path = str(deck_path or DEFAULT_LUCARIO_DECK)
    scorer = LucarioScorer(deck_path=path, lever_overrides=lever_overrides)
    agent = build_agent(deck_path=path, scorer=scorer)
    return agent.act


def make_search_brain(
    deck_path: str | Path | None = None,
) -> Callable[[dict], list[int]]:
    from agent.agent import build_agent
    from agent.search_policy import SearchScorer

    path = str(deck_path or DEFAULT_LUCARIO_DECK)
    agent = build_agent(deck_path=path, scorer=SearchScorer(deck_path=path))
    return agent.act


def make_dragapult_brain(
    deck_path: str | Path | None = None,
    *,
    lever_overrides: dict | None = None,
    bench_guard: bool = True,
) -> Callable[[dict], list[int]]:
    import os

    from agent import dragapult_levers

    path = str(deck_path or DEFAULT_DRAGAPULT_DECK)
    os.environ["DRAGAPULT_DECK"] = path
    os.environ["DRAGAPULT_BENCH_GUARD"] = "1" if bench_guard else "0"
    if lever_overrides is not None:
        dragapult_levers.set_dragapult_lever_overrides(lever_overrides)
    else:
        dragapult_levers.set_dragapult_lever_overrides(None)

    from agent.dragapult_agent import agent as dragapult_act

    return dragapult_act


def make_alakazam_brain(
    deck_path: str | Path | None = None,
    *,
    bench_guard: bool = False,
) -> Callable[[dict], list[int]]:
    import os

    path = str(deck_path or DEFAULT_ALAKAZAM_DECK)
    os.environ["ALAKAZAM_DECK"] = path
    os.environ["ALAKAZAM_BENCH_GUARD"] = "1" if bench_guard else "0"
    from agent.alakazam_agent import agent as alakazam_act

    return alakazam_act


def make_archaludon_brain(
    deck_path: str | Path | None = None,
    *,
    bench_guard: bool = True,
) -> Callable[[dict], list[int]]:
    import os

    path = str(deck_path or DEFAULT_ARCHALUDON_DECK)
    os.environ["ARCHALUDON_DECK"] = path
    os.environ["ARCHALUDON_BENCH_GUARD"] = "1" if bench_guard else "0"
    from agent.archaludon_agent import agent as archaludon_act

    return archaludon_act


def make_starmie_brain(
    deck_path: str | Path | None = None,
) -> Callable[[dict], list[int]]:
    import os

    path = str(deck_path or DEFAULT_STARMIE_DECK)
    os.environ["STARMIE_DECK"] = path
    from agent.starmie_agent import agent as starmie_act

    return starmie_act


def make_abomasnow_brain(
    deck_path: str | Path | None = None,
) -> Callable[[dict], list[int]]:
    import os

    path = str(deck_path or DEFAULT_ABOMASNOW_DECK)
    os.environ["ABOMASNOW_DECK"] = path
    from agent.abomasnow_agent import agent as abomasnow_act

    return abomasnow_act


def get_opponent_brain(
    opp_name: str,
    *,
    registry: dict[str, Any] | None = None,
) -> tuple[Callable[[dict], list[int]], str]:
    reg = registry or load_registry()
    meta = opponent_meta(opp_name, reg)
    deck_path = str(resolve_deck_path(opp_name, reg))
    deck_o = load_deck(deck_path)
    brain_kind = meta.get("opponent_brain", "native")
    cache_key = f"{opp_name}:{brain_kind}"
    if cache_key in _opp_cache:
        return _opp_cache[cache_key]

    if brain_kind == "native":
        arch = official_archetype_for_opponent(opp_name, deck_o)
        if arch is None:
            raise ValueError(f"no official sample for {opp_name}")
        act, label = make_opponent_brain("native", deck_path, deck_o, opp_name=opp_name)
    elif brain_kind == "random":
        act, label = make_opponent_brain(
            "non_official",
            deck_path,
            deck_o,
            opp_name=opp_name,
            random_agent=random_agent,
            non_official_brain="random",
        )
    else:
        raise ValueError(f"unknown opponent_brain: {brain_kind}")

    _opp_cache[cache_key] = (act, label)
    return act, label


def gate_vs_opponent(
    hero_brain: Callable[[dict], list[int]],
    hero_deck: list[int],
    opp_name: str,
    games: int,
    *,
    seat_swap: bool = True,
    registry: dict[str, Any] | None = None,
) -> MatchupResult | None:
    reg = registry or load_registry()
    meta = opponent_meta(opp_name, reg)
    deck_path = resolve_deck_path(opp_name, reg)
    if not deck_path.exists():
        return None

    deck_o = load_deck(deck_path)
    brain_kind = meta.get("opponent_brain", "native")
    if brain_kind == "native" and official_archetype_for_opponent(opp_name, deck_o) is None:
        return None

    try:
        opp_brain, brain_label = get_opponent_brain(opp_name, registry=reg)
    except (FileNotFoundError, ModuleNotFoundError, ValueError):
        return None

    wins = losses = draws = unfinished = 0
    for i in range(games):
        if seat_swap and i % 2 == 1:
            outcome = run_match(deck_o, hero_deck, opp_brain, hero_brain)
            if outcome == "b":
                wins += 1
            elif outcome == "a":
                losses += 1
            elif outcome == "draw":
                draws += 1
            else:
                unfinished += 1
        else:
            outcome = run_match(hero_deck, deck_o, hero_brain, opp_brain)
            if outcome == "a":
                wins += 1
            elif outcome == "b":
                losses += 1
            elif outcome == "draw":
                draws += 1
            else:
                unfinished += 1

    n = wins + losses
    wr, lo, hi = _wilson_pct(wins, n)
    return MatchupResult(
        opponent=opp_name,
        brain=brain_label,
        wins=wins,
        losses=losses,
        draws=draws,
        unfinished=unfinished,
        wr_pct=wr,
        ci_low_pct=lo,
        ci_high_pct=hi,
        games=games,
    )


def run_suite(
    hero_brain: Callable[[dict], list[int]],
    hero_deck: list[int] | str | Path,
    opponents: list[str],
    *,
    games_per_opp: int = 20,
    seat_swap: bool = True,
    lever_overrides: dict[str, LeverDeltas] | None = None,
    hero_brain_label: str = "lucario_rules",
    registry: dict[str, Any] | None = None,
) -> HarnessResult:
    if isinstance(hero_deck, (str, Path)):
        deck_list = load_deck(hero_deck)
        deck_label = str(hero_deck)
    else:
        deck_list = hero_deck
        deck_label = str(DEFAULT_LUCARIO_DECK)

    if lever_overrides is not None:
        hero_brain = make_lucario_brain(deck_label, lever_overrides=lever_overrides)

    reg = registry or load_registry()
    matchups: list[MatchupResult] = []
    total_w = total_n = 0

    for name in opponents:
        result = gate_vs_opponent(
            hero_brain,
            deck_list,
            name,
            games_per_opp,
            seat_swap=seat_swap,
            registry=reg,
        )
        if result is not None:
            matchups.append(result)
            total_w += result.wins
            total_n += result.wins + result.losses

    wr, lo, hi = _wilson_pct(total_w, total_n)
    return HarnessResult(
        hero_deck=deck_label,
        hero_brain=hero_brain_label,
        games_per_opp=games_per_opp,
        opponents=opponents,
        lever_overrides=lever_overrides,
        matchups=matchups,
        overall_wins=total_w,
        overall_games=total_n,
        overall_wr_pct=wr,
        overall_ci_low_pct=lo,
        overall_ci_high_pct=hi,
    )


def clear_caches() -> None:
    """Reset opponent brain cache (for tests / variant sweeps)."""
    _opp_cache.clear()
    try:
        from agent import dragapult_levers

        dragapult_levers.set_dragapult_lever_overrides(None)
    except ImportError:
        pass
