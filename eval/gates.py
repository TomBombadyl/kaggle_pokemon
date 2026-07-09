"""Gate pyramid L0–L2 over eval/harness (real field only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from agent.matchup_levers import LeverDeltas
from eval.field_registry import load_registry, opponent_meta, opponents_for_suite
from eval.field_weights import archetype_weight, load_weights, opponent_weight
from eval.harness import (
    DEFAULT_ABOMASNOW_DECK,
    DEFAULT_ALAKAZAM_DECK,
    DEFAULT_ARCHALUDON_DECK,
    DEFAULT_DRAGAPULT_DECK,
    DEFAULT_LUCARIO_DECK,
    DEFAULT_STARMIE_DECK,
    HarnessResult,
    clear_caches,
    make_alakazam_brain,
    make_archaludon_brain,
    make_abomasnow_brain,
    make_dragapult_brain,
    make_lucario_brain,
    make_search_brain,
    make_starmie_brain,
    run_suite,
)
from scripts.stats_utils import sprt_test

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"


@dataclass
class SprtVerdict:
    decision: str
    log_ratio: float
    games: int


def gate_l0_import_smoke() -> tuple[bool, str]:
    """L0: imports and registry load without crash."""
    try:
        from eval import harness  # noqa: F401
        from eval.field_registry import load_registry

        reg = load_registry()
        if not reg.get("opponents"):
            return False, "registry has no opponents"
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def gate_matchups(
    suite: str = "full",
    *,
    games_per_opp: int = 20,
    opponents: list[str] | None = None,
    lever_overrides: dict[str, LeverDeltas] | None = None,
    hero_deck: str | Path | None = None,
) -> HarnessResult:
    """L1: per-matchup win-rate vs field registry suite."""
    clear_caches()
    deck = hero_deck or DEFAULT_LUCARIO_DECK
    opp_list = opponents or opponents_for_suite(suite)
    brain = make_lucario_brain(deck, lever_overrides=lever_overrides)
    return run_suite(
        brain,
        deck,
        opp_list,
        games_per_opp=games_per_opp,
        lever_overrides=lever_overrides,
        hero_brain_label="LucarioScorer",
    )


def gate_search_matchups(
    suite: str = "full",
    *,
    games_per_opp: int = 20,
    opponents: list[str] | None = None,
    hero_deck: str | Path | None = None,
) -> HarnessResult:
    """L1: SearchScorer vs native field opponents."""
    clear_caches()
    deck = hero_deck or DEFAULT_LUCARIO_DECK
    opp_list = opponents or opponents_for_suite(suite)
    brain = make_search_brain(deck)
    return run_suite(
        brain,
        deck,
        opp_list,
        games_per_opp=games_per_opp,
        hero_brain_label="SearchScorer",
    )


def gate_sprt_vs_baseline(
    challenger: HarnessResult,
    baseline: HarnessResult,
    *,
    p0: float = 0.50,
    p1: float = 0.55,
) -> SprtVerdict:
    """L2: SPRT on pooled wins (challenger vs baseline overall)."""
    r = sprt_test(
        challenger.overall_wins,
        challenger.overall_games,
        p0=p0,
        p1=p1,
    )
    return SprtVerdict(r.decision, r.log_ratio, r.games)


def format_harness_markdown(result: HarnessResult, *, title: str = "Gate report") -> str:
    lines = [
        f"# {title}",
        "",
        f"- Hero: `{result.hero_brain}` × `{result.hero_deck}`",
        f"- Games per opponent: {result.games_per_opp}",
        f"- Opponents: {', '.join(result.opponents)}",
    ]
    if result.lever_overrides:
        lines.append(f"- Lever overrides: {', '.join(result.lever_overrides.keys())}")
    lines.extend(["", "## Per-matchup", "", "| Opponent | Brain | WR% | 95% CI | Record |", "|----------|-------|-----|--------|--------|"])
    for m in result.matchups:
        lines.append(
            f"| {m.opponent} | {m.brain} | {m.wr_pct:.1f} | [{m.ci_low_pct:.1f}, {m.ci_high_pct:.1f}] | "
            f"W{m.wins}/L{m.losses}/D{m.draws}/U{m.unfinished} |"
        )
    lines.extend([
        "",
        "## Overall",
        "",
        f"- **{result.overall_wr_pct:.1f}%** [{result.overall_ci_low_pct:.1f}, {result.overall_ci_high_pct:.1f}] "
        f"(n={result.overall_games} decided)",
        "",
    ])
    return "\n".join(lines)


def write_gate_report(
    result: HarnessResult,
    *,
    stem: str | None = None,
    title: str | None = None,
) -> Path:
    day = date.today().isoformat()
    name = stem or f"gates_{day}"
    path = EVAL_DIR / f"{name}.md"
    body = format_harness_markdown(result, title=title or f"Gate report — {day}")
    path.write_text(body, encoding="utf-8")
    return path


@dataclass
class WeightedGateSummary:
    expected_win_pct: float
    total_weight: float
    per_opponent: list[dict[str, Any]]


def compute_weighted_summary(result: HarnessResult) -> WeightedGateSummary:
    """E[win] = sum(weight_i * WR_i) / sum(weight_i)."""
    reg = load_registry()
    weights_doc = load_weights()
    rows: list[dict[str, Any]] = []
    weighted_sum = 0.0
    total_w = 0.0
    for m in result.matchups:
        meta = opponent_meta(m.opponent, reg)
        arch = meta.get("archetype", "unknown")
        w = opponent_weight(m.opponent, reg, weights_doc)
        contrib = w * (m.wr_pct / 100.0)
        weighted_sum += contrib
        total_w += w
        rows.append({
            "opponent": m.opponent,
            "archetype": arch,
            "weight": w,
            "wr_pct": m.wr_pct,
            "weighted_contrib": contrib,
        })
    e_win = 100.0 * weighted_sum / total_w if total_w else 0.0
    return WeightedGateSummary(expected_win_pct=e_win, total_weight=total_w, per_opponent=rows)


def gate_dragapult_matchups(
    suite: str = "full",
    *,
    games_per_opp: int = 20,
    opponents: list[str] | None = None,
    lever_overrides: dict | None = None,
    hero_deck: str | Path | None = None,
) -> HarnessResult:
    """L1: Dragapult agent vs native field opponents."""
    clear_caches()
    deck = hero_deck or DEFAULT_DRAGAPULT_DECK
    opp_list = opponents or opponents_for_suite(suite)
    brain = make_dragapult_brain(deck, lever_overrides=lever_overrides)
    return run_suite(
        brain,
        deck,
        opp_list,
        games_per_opp=games_per_opp,
        hero_brain_label="dragapult_agent",
    )


def gate_alakazam_matchups(
    suite: str = "full",
    *,
    games_per_opp: int = 20,
    opponents: list[str] | None = None,
    hero_deck: str | Path | None = None,
) -> HarnessResult:
    """L1: Alakazam best5 agent vs native field opponents."""
    clear_caches()
    deck = hero_deck or DEFAULT_ALAKAZAM_DECK
    opp_list = opponents or opponents_for_suite(suite)
    brain = make_alakazam_brain(deck)
    return run_suite(
        brain,
        deck,
        opp_list,
        games_per_opp=games_per_opp,
        hero_brain_label="alakazam_agent",
    )


def gate_archaludon_matchups(
    suite: str = "full",
    *,
    games_per_opp: int = 20,
    opponents: list[str] | None = None,
    hero_deck: str | Path | None = None,
    param_overrides: dict[str, dict] | None = None,
) -> HarnessResult:
    """L1: Archaludon ex / Cinderace agent vs native field opponents.

    param_overrides (evolve/evaluator.py hook): {'ice_cream_hp_threshold': {...},
    'attack_base_dmg': {...}} merged over the base constants in archaludon_agent.py
    for this gate run only -- reset unconditionally on exit (even on error) so a
    candidate's overrides can never leak into a later, unrelated gate call. See
    agent/archaludon_levers.py.
    """
    clear_caches()
    deck = hero_deck or DEFAULT_ARCHALUDON_DECK
    opp_list = opponents or opponents_for_suite(suite)
    try:
        brain = make_archaludon_brain(deck, param_overrides=param_overrides)
        return run_suite(
            brain,
            deck,
            opp_list,
            games_per_opp=games_per_opp,
            hero_brain_label="archaludon_agent",
        )
    finally:
        if param_overrides is not None:
            from agent.archaludon_levers import set_archaludon_param_overrides

            set_archaludon_param_overrides(None)


def gate_starmie_matchups(
    suite: str = "starmie",
    *,
    games_per_opp: int = 20,
    opponents: list[str] | None = None,
    hero_deck: str | Path | None = None,
) -> HarnessResult:
    """L1: Starmie / Froslass agent vs field suite (default: mirror smoke)."""
    clear_caches()
    deck = hero_deck or DEFAULT_STARMIE_DECK
    opp_list = opponents or opponents_for_suite(suite)
    brain = make_starmie_brain(deck)
    return run_suite(
        brain,
        deck,
        opp_list,
        games_per_opp=games_per_opp,
        hero_brain_label="starmie_agent",
    )


def gate_abomasnow_matchups(
    suite: str = "full",
    *,
    games_per_opp: int = 20,
    opponents: list[str] | None = None,
    hero_deck: str | Path | None = None,
) -> HarnessResult:
    """L1: Official Abomasnow agent vs native field opponents."""
    clear_caches()
    deck = hero_deck or DEFAULT_ABOMASNOW_DECK
    opp_list = opponents or opponents_for_suite(suite)
    brain = make_abomasnow_brain(deck)
    return run_suite(
        brain,
        deck,
        opp_list,
        games_per_opp=games_per_opp,
        hero_brain_label="abomasnow_agent",
    )


def print_weighted_summary(summary: WeightedGateSummary) -> None:
    print(f"\n  WEIGHTED E[win] (field mixture): {summary.expected_win_pct:.1f}%  (weight sum={summary.total_weight:.2f})")
    for row in summary.per_opponent:
        print(
            f"    w={row['weight']:.2f} {row['opponent']:28} ({row['archetype']:18})  "
            f"{row['wr_pct']:5.1f}%  contrib={row['weighted_contrib']:.3f}"
        )


def print_harness_summary(result: HarnessResult, *, weighted: bool = False) -> None:
    print(f"{result.hero_brain} vs field ({result.games_per_opp} games/opp)\n")
    for m in result.matchups:
        flag = " GAP" if m.wr_pct < 30 else " OK" if m.wr_pct >= 50 else ""
        print(
            f"  {m.opponent:32} ({m.brain:22})  {m.wr_pct:5.1f}%  "
            f"[{m.ci_low_pct:4.1f}, {m.ci_high_pct:5.1f}]  "
            f"W{m.wins}/L{m.losses}/D{m.draws}/U{m.unfinished}{flag}",
        )
    if result.overall_games:
        print(
            f"\n  {'OVERALL (gated)':32} {'':22}  {result.overall_wr_pct:5.1f}%  "
            f"[{result.overall_ci_low_pct:4.1f}, {result.overall_ci_high_pct:5.1f}]  "
            f"n={len(result.matchups)} decks"
        )
    if weighted:
        print_weighted_summary(compute_weighted_summary(result))
