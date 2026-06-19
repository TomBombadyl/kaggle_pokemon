"""Evaluate multiple local agents/decks against each other.

This is a stronger gate than heuristic-vs-random only. It runs full games through
the downloaded cabt engine, swaps seats each game, and writes a compact Markdown
and CSV summary under report/eval/.

Examples:
    python scripts/eval_matrix.py --games 40
    python scripts/eval_matrix.py --games 100 --agents current,safety,random
    python scripts/eval_matrix.py --deck current=agent/deck.csv
"""
from __future__ import annotations

import argparse
import csv
import importlib
import os
import random
import sys
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
DEFAULT_DECK = ENGINE_DIR / "deck.csv"
OUT_DIR = ROOT / "report" / "eval"

sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(ROOT))

from cg import game  # noqa: E402
from cg.sim import Battle, lib  # noqa: E402
from cg.api import LogType, OptionType, SelectContext, SelectType  # noqa: E402


@dataclass(frozen=True)
class AgentSpec:
    name: str
    kind: str
    module: str | None = None
    deck_path: Path = DEFAULT_DECK


@dataclass
class PlayerTelemetry:
    order: str = "unknown"
    decision_contexts: Counter[str] = field(default_factory=Counter)
    decision_types: Counter[str] = field(default_factory=Counter)
    attacks: Counter[str] = field(default_factory=Counter)
    last_attacker: str = ""
    first_attack_turn: int | None = None
    first_evolve_turn: int | None = None
    evolution_count: int = 0
    attachment_turns: set[int] = field(default_factory=set)
    attachment_opportunity_turns: set[int] = field(default_factory=set)

    @property
    def missed_attachment_turns(self) -> int:
        return len(self.attachment_opportunity_turns - self.attachment_turns)


@dataclass
class GameTelemetry:
    game_index: int
    agent_a: str
    agent_b: str
    seat_to_agent: dict[int, str]
    agent_to_side: dict[str, str]
    players: list[PlayerTelemetry] = field(
        default_factory=lambda: [PlayerTelemetry(), PlayerTelemetry()]
    )
    winner: int = -1
    result_reason: str = "unknown"
    turns: int = 0
    steps: int = 0
    final_deck_counts: list[int] = field(default_factory=lambda: [0, 0])
    final_prizes_left: list[int] = field(default_factory=lambda: [0, 0])

    def observe(self, obs: dict, step: int) -> None:
        current = obs.get("current") or {}
        self.steps = step
        self.turns = int(current.get("turn", self.turns) or 0)
        self._record_first_second(current)
        self._record_decision(obs)
        self._record_logs(obs.get("logs") or [], current)
        self._record_final_state(current)

    def _record_first_second(self, current: dict) -> None:
        first = current.get("firstPlayer")
        if first in (0, 1):
            self.players[first].order = "first"
            self.players[1 - first].order = "second"

    def _record_decision(self, obs: dict) -> None:
        select = obs.get("select")
        current = obs.get("current") or {}
        if select is None:
            return
        player = select_player()
        turn = int(current.get("turn", 0) or 0)
        sel_type = _enum_name(SelectType, select.get("type"))
        context = _enum_name(SelectContext, select.get("context"))
        self.players[player].decision_types[sel_type] += 1
        self.players[player].decision_contexts[context] += 1
        if (
            select.get("type") == int(SelectType.MAIN)
            and not current.get("energyAttached", False)
            and any((opt.get("type") == int(OptionType.ATTACH)) for opt in (select.get("option") or []))
        ):
            self.players[player].attachment_opportunity_turns.add(turn)

    def _record_logs(self, logs: list[dict], current: dict) -> None:
        turn = int(current.get("turn", self.turns) or 0)
        for log in logs:
            log_type = log.get("type")
            player = log.get("playerIndex")
            if log_type == int(LogType.RESULT):
                self.winner = int(log.get("result", self.winner))
                self.result_reason = RESULT_REASONS.get(
                    int(log.get("reason", 0) or 0), f"reason_{log.get('reason')}"
                )
            if player not in (0, 1):
                continue
            if log_type == int(LogType.ATTACH):
                self.players[player].attachment_turns.add(turn)
            elif log_type == int(LogType.EVOLVE):
                pt = self.players[player]
                pt.evolution_count += 1
                if pt.first_evolve_turn is None:
                    pt.first_evolve_turn = turn
            elif log_type == int(LogType.ATTACK):
                pt = self.players[player]
                attacker = str(log.get("cardId", "unknown"))
                pt.attacks[attacker] += 1
                pt.last_attacker = attacker
                if pt.first_attack_turn is None:
                    pt.first_attack_turn = turn

    def _record_final_state(self, current: dict) -> None:
        players = current.get("players") or []
        for i in (0, 1):
            if i >= len(players):
                continue
            player = players[i]
            self.final_deck_counts[i] = int(player.get("deckCount", 0) or 0)
            self.final_prizes_left[i] = len(player.get("prize") or [])
        result = current.get("result", -1)
        if result != -1:
            self.winner = int(result)
            if self.result_reason == "unknown":
                self.result_reason = infer_result_reason(self.winner, players)

    def row_for_agent(self, agent_name: str) -> dict[str, object]:
        seat = self.agent_to_side[agent_name]
        pidx = int(seat[-1])
        opp = 1 - pidx
        pt = self.players[pidx]
        won = self.winner == pidx
        return {
            "game": self.game_index,
            "matchup": f"{self.agent_a}_vs_{self.agent_b}",
            "agent": agent_name,
            "opponent": self.seat_to_agent[opp],
            "seat": pidx,
            "order": pt.order,
            "result": "win" if won else "loss" if self.winner == opp else "draw",
            "winner": self.winner,
            "reason": self.result_reason,
            "turns": self.turns,
            "steps": self.steps,
            "prizes_left": self.final_prizes_left[pidx],
            "opp_prizes_left": self.final_prizes_left[opp],
            "deck_left": self.final_deck_counts[pidx],
            "opp_deck_left": self.final_deck_counts[opp],
            "first_attack_turn": _none_to_blank(pt.first_attack_turn),
            "first_evolve_turn": _none_to_blank(pt.first_evolve_turn),
            "evolution_count": pt.evolution_count,
            "missed_attachment_turns": pt.missed_attachment_turns,
            "attachment_opportunity_turns": len(pt.attachment_opportunity_turns),
            "attachment_turns": len(pt.attachment_turns),
            "last_attacker": pt.last_attacker,
            "top_attackers": _counter_summary(pt.attacks),
            "decision_contexts": _counter_summary(pt.decision_contexts),
            "decision_types": _counter_summary(pt.decision_types),
        }


DEFAULT_AGENTS = {
    "current": AgentSpec("current", "module", "agent.agent"),
    "safety": AgentSpec("safety", "module", "agent_snapshots.v2_safety"),
    "random": AgentSpec("random", "random", None),
}

# Meta pool decks (agent.agent pilots any deck via deck_path).
POOL_DECK_DIR = ROOT / "agent_decks"
for _pool_path in sorted(POOL_DECK_DIR.glob("pool_*.csv")):
    _pool_name = _pool_path.stem  # e.g. pool_dragapult
    DEFAULT_AGENTS[_pool_name] = AgentSpec(
        _pool_name, "deck", "agent.agent", _pool_path,
    )
    # Short alias: deck:pool_dragapult style without prefix
    DEFAULT_AGENTS[f"deck:{_pool_name.replace('pool_', '')}"] = DEFAULT_AGENTS[_pool_name]

RESULT_REASONS = {
    1: "prize",
    2: "deck_out",
    3: "no_active",
    4: "card_effect",
}


def _enum_name(enum_cls, value) -> str:
    try:
        return enum_cls(int(value)).name
    except Exception:
        return f"UNKNOWN_{value}"


def _counter_summary(counter: Counter, limit: int = 8) -> str:
    return ";".join(f"{name}:{count}" for name, count in counter.most_common(limit))


def _none_to_blank(value) -> object:
    return "" if value is None else value


def infer_result_reason(winner: int, players: list[dict]) -> str:
    if winner in (0, 1) and winner < len(players):
        if len(players[winner].get("prize") or []) == 0:
            return "prize"
    loser = 1 - winner if winner in (0, 1) else None
    if loser is not None and loser < len(players):
        if int(players[loser].get("deckCount", 1) or 0) <= 0:
            return "deck_out"
        if not (players[loser].get("active") or []):
            return "no_active"
    return "draw" if winner == 2 else "unknown"


def load_deck(path: Path) -> list[int]:
    return [int(x) for x in path.read_text().splitlines() if x.strip()][:60]


def select_player() -> int:
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


def module_policy(module_name: str, seed: int, deck_path: Path):
    mod = importlib.import_module(module_name)
    if hasattr(mod, "build_agent"):
        return mod.build_agent(seed=seed, deck_path=str(deck_path))
    if hasattr(mod, "agent"):
        return mod.agent
    raise AttributeError(f"{module_name} has no build_agent or agent")


def make_policy(spec: AgentSpec, seed: int):
    if spec.kind == "random":
        return random_policy(seed)
    if spec.kind == "deck":
        if spec.module is None:
            raise ValueError(f"deck agent {spec.name} has no module")
        return module_policy(spec.module, seed, spec.deck_path)
    if spec.module is None:
        raise ValueError(f"module agent {spec.name} has no module")
    return module_policy(spec.module, seed, spec.deck_path)


def run_game(
    deck0: list[int],
    deck1: list[int],
    pol0,
    pol1,
    max_steps: int,
    telemetry: GameTelemetry | None = None,
) -> tuple[int, int]:
    """Return (winner, steps). winner: 0/1, 2 draw, -1 unfinished."""
    obs, start = game.battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(f"battle_start failed: err={start.errorType}")
    policies = (pol0, pol1)
    try:
        for step in range(max_steps):
            if telemetry is not None:
                telemetry.observe(obs, step)
            cur = obs.get("current")
            if cur is not None and cur.get("result", -1) != -1:
                return cur["result"], step
            if obs.get("select") is None:
                return -1, step
            player = select_player()
            obs = game.battle_select(policies[player](obs))
        return -1, max_steps
    finally:
        game.battle_finish()


def play_match(
    a: AgentSpec,
    b: AgentSpec,
    games: int,
    max_steps: int,
    telemetry_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    deck_a = load_deck(a.deck_path)
    deck_b = load_deck(b.deck_path)
    a_wins = b_wins = draws = unfinished = steps_total = 0

    for i in range(games):
        pol_a = make_policy(a, 10000 + i)
        pol_b = make_policy(b, 20000 + i)
        if i % 2 == 0:
            telemetry = GameTelemetry(
                game_index=i,
                agent_a=a.name,
                agent_b=b.name,
                seat_to_agent={0: a.name, 1: b.name},
                agent_to_side={a.name: "p0", b.name: "p1"},
            )
            result, steps = run_game(deck_a, deck_b, pol_a, pol_b, max_steps, telemetry)
            a_win, b_win = result == 0, result == 1
        else:
            telemetry = GameTelemetry(
                game_index=i,
                agent_a=a.name,
                agent_b=b.name,
                seat_to_agent={0: b.name, 1: a.name},
                agent_to_side={a.name: "p1", b.name: "p0"},
            )
            result, steps = run_game(deck_b, deck_a, pol_b, pol_a, max_steps, telemetry)
            a_win, b_win = result == 1, result == 0
        if telemetry_rows is not None:
            telemetry_rows.append(telemetry.row_for_agent(a.name))
            telemetry_rows.append(telemetry.row_for_agent(b.name))
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
    win_rate = 100.0 * a_wins / decided if decided else 0.0
    return {
        "agent_a": a.name,
        "agent_b": b.name,
        "games": games,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": draws,
        "unfinished": unfinished,
        "a_win_rate_decided": round(win_rate, 2),
        "avg_steps": round(steps_total / games, 1) if games else 0.0,
    }


def parse_agents(value: str) -> list[AgentSpec]:
    specs = []
    for raw in value.split(","):
        name = raw.strip()
        if not name:
            continue
        if name.startswith("deck:") and name not in DEFAULT_AGENTS:
            deck_key = name.split(":", 1)[1]
            deck_path = POOL_DECK_DIR / f"pool_{deck_key}.csv"
            if not deck_path.exists():
                deck_path = ROOT / deck_key
            if not deck_path.exists():
                raise ValueError(f"deck agent {name!r}: missing {deck_path}")
            spec = AgentSpec(name.replace(":", "_"), "deck", "agent.agent", deck_path)
            specs.append(spec)
            continue
        if name not in DEFAULT_AGENTS:
            known = ", ".join(sorted(DEFAULT_AGENTS))
            raise ValueError(f"unknown agent '{name}', known: {known}")
        specs.append(DEFAULT_AGENTS[name])
    if len(specs) < 2:
        raise ValueError("need at least two agents")
    return specs


def apply_deck_overrides(specs: list[AgentSpec], values: list[str]) -> list[AgentSpec]:
    overrides: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"--deck expects NAME=PATH, got {value!r}")
        name, path = value.split("=", 1)
        deck_path = Path(path)
        if not deck_path.is_absolute():
            deck_path = ROOT / deck_path
        if not deck_path.exists():
            raise FileNotFoundError(deck_path)
        overrides[name.strip()] = deck_path

    result = []
    for spec in specs:
        result.append(replace(spec, deck_path=overrides.get(spec.name, spec.deck_path)))
    unknown = sorted(set(overrides) - {spec.name for spec in specs})
    if unknown:
        raise ValueError(f"deck override for unknown agent(s): {', '.join(unknown)}")
    return result


def _output_stem(kind: str, games: int, tag: str = "") -> str:
    suffix = f"_{tag}" if tag else ""
    return f"{kind}_{games}{suffix}"


def write_outputs(rows: list[dict[str, object]], games: int, tag: str = "") -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = _output_stem("matrix", games, tag)
    csv_path = OUT_DIR / f"{stem}.csv"
    md_path = OUT_DIR / f"{stem}.md"
    fields = [
        "agent_a", "agent_b", "games", "a_wins", "b_wins", "draws",
        "unfinished", "a_win_rate_decided", "avg_steps",
    ]
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        f"# Evaluation Matrix ({games} games per ordered matchup)",
        "",
        "| A | B | A wins | B wins | Draws | Unfinished | A win % decided | Avg steps |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['agent_a']} | {row['agent_b']} | {row['a_wins']} | "
            f"{row['b_wins']} | {row['draws']} | {row['unfinished']} | "
            f"{row['a_win_rate_decided']} | {row['avg_steps']} |"
        )
    md_path.write_text("\n".join(lines) + "\n")
    return csv_path, md_path


def write_telemetry_outputs(
    rows: list[dict[str, object]], games: int, tag: str = ""
) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = _output_stem("telemetry", games, tag)
    csv_path = OUT_DIR / f"{stem}.csv"
    md_path = OUT_DIR / f"{stem}.md"
    fields = [
        "game", "matchup", "agent", "opponent", "seat", "order", "result",
        "winner", "reason", "turns", "steps", "prizes_left", "opp_prizes_left",
        "deck_left", "opp_deck_left", "first_attack_turn", "first_evolve_turn",
        "evolution_count", "missed_attachment_turns",
        "attachment_opportunity_turns", "attachment_turns", "last_attacker",
        "top_attackers", "decision_contexts", "decision_types",
    ]
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    md_path.write_text(render_telemetry_markdown(rows, games))
    return csv_path, md_path


def render_telemetry_markdown(rows: list[dict[str, object]], games: int) -> str:
    lines = [
        f"# Game Telemetry ({games} games per ordered matchup)",
        "",
        "One row in the CSV is one agent perspective for one game.",
        "",
        "## Results By Agent",
        "",
        "| Agent | Games | Wins | Losses | Draws | Win % | Avg turns | Avg missed attach turns | Avg first evolve turn |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for agent in sorted({str(row["agent"]) for row in rows}):
        subset = [row for row in rows if row["agent"] == agent]
        lines.append(_summary_line(agent, subset))

    lines.extend([
        "",
        "## Results By First/Second",
        "",
        "| Agent | Order | Games | Wins | Losses | Win % | Avg turns | Avg missed attach turns |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ])
    for agent in sorted({str(row["agent"]) for row in rows}):
        for order in ("first", "second", "unknown"):
            subset = [row for row in rows if row["agent"] == agent and row["order"] == order]
            if subset:
                wins = sum(1 for row in subset if row["result"] == "win")
                losses = sum(1 for row in subset if row["result"] == "loss")
                win_pct = 100.0 * wins / (wins + losses) if wins + losses else 0.0
                lines.append(
                    f"| {agent} | {order} | {len(subset)} | {wins} | {losses} | "
                    f"{win_pct:.1f} | {_avg(subset, 'turns'):.1f} | "
                    f"{_avg(subset, 'missed_attachment_turns'):.2f} |"
                )

    lines.extend([
        "",
        "## Loss Reasons",
        "",
        "| Agent | Reason | Losses | Avg turns | Avg deck left | Avg opp prizes left |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for agent in sorted({str(row["agent"]) for row in rows}):
        losses = [row for row in rows if row["agent"] == agent and row["result"] == "loss"]
        for reason, count in Counter(str(row["reason"]) for row in losses).most_common():
            subset = [row for row in losses if row["reason"] == reason]
            lines.append(
                f"| {agent} | {reason} | {count} | {_avg(subset, 'turns'):.1f} | "
                f"{_avg(subset, 'deck_left'):.1f} | {_avg(subset, 'opp_prizes_left'):.1f} |"
            )

    lines.extend([
        "",
        "## Common Decision Contexts In Losses",
        "",
        "| Agent | Context counts |",
        "|---|---|",
    ])
    for agent in sorted({str(row["agent"]) for row in rows}):
        context_counts = Counter()
        for row in rows:
            if row["agent"] == agent and row["result"] == "loss":
                context_counts.update(_parse_counter_summary(str(row["decision_contexts"])))
        lines.append(f"| {agent} | {_counter_summary(context_counts, limit=12)} |")

    lines.extend([
        "",
        "## Active Attackers",
        "",
        "| Agent | Attack counts | Last attacker counts |",
        "|---|---|---|",
    ])
    for agent in sorted({str(row["agent"]) for row in rows}):
        attack_counts = Counter()
        last_counts = Counter()
        for row in rows:
            if row["agent"] != agent:
                continue
            attack_counts.update(_parse_counter_summary(str(row["top_attackers"])))
            if row["last_attacker"]:
                last_counts[str(row["last_attacker"])] += 1
        lines.append(
            f"| {agent} | {_counter_summary(attack_counts, limit=8)} | "
            f"{_counter_summary(last_counts, limit=8)} |"
        )
    return "\n".join(lines) + "\n"


def _summary_line(agent: str, subset: list[dict[str, object]]) -> str:
    wins = sum(1 for row in subset if row["result"] == "win")
    losses = sum(1 for row in subset if row["result"] == "loss")
    draws = sum(1 for row in subset if row["result"] == "draw")
    win_pct = 100.0 * wins / (wins + losses) if wins + losses else 0.0
    evolve_values = [
        float(row["first_evolve_turn"]) for row in subset if row["first_evolve_turn"] != ""
    ]
    avg_evolve = sum(evolve_values) / len(evolve_values) if evolve_values else 0.0
    return (
        f"| {agent} | {len(subset)} | {wins} | {losses} | {draws} | "
        f"{win_pct:.1f} | {_avg(subset, 'turns'):.1f} | "
        f"{_avg(subset, 'missed_attachment_turns'):.2f} | {avg_evolve:.1f} |"
    )


def _avg(rows: list[dict[str, object]], field_name: str) -> float:
    values = [float(row[field_name]) for row in rows if row[field_name] != ""]
    return sum(values) / len(values) if values else 0.0


def _parse_counter_summary(value: str) -> Counter:
    counter = Counter()
    if not value:
        return counter
    for part in value.split(";"):
        if not part or ":" not in part:
            continue
        name, count = part.rsplit(":", 1)
        try:
            counter[name] += int(count)
        except ValueError:
            continue
    return counter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--agents", default="current,safety,random")
    parser.add_argument(
        "--deck", action="append", default=[],
        help="Override an agent deck as NAME=PATH. Can be repeated.",
    )
    parser.add_argument("--max-steps", type=int, default=6000)
    parser.add_argument(
        "--no-telemetry", action="store_true",
        help="Skip per-game telemetry CSV/Markdown output.",
    )
    parser.add_argument(
        "--tag", default="",
        help="Optional safe suffix for output filenames, e.g. a2_big_basic.",
    )
    args = parser.parse_args(argv)

    tag = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in args.tag.strip())
    specs = apply_deck_overrides(parse_agents(args.agents), args.deck)
    rows = []
    telemetry_rows: list[dict[str, object]] = []
    print(f"eval matrix: {args.games} games per ordered matchup")
    for a in specs:
        for b in specs:
            if a.name == b.name:
                continue
            row = play_match(
                a,
                b,
                args.games,
                args.max_steps,
                None if args.no_telemetry else telemetry_rows,
            )
            rows.append(row)
            print(
                f"{a.name:>8} vs {b.name:<8}: "
                f"{row['a_wins']}/{args.games} wins, "
                f"{row['a_win_rate_decided']:.1f}% decided"
            )
    csv_path, md_path = write_outputs(rows, args.games, tag)
    print(f"wrote {csv_path}")
    print(f"wrote {md_path}")
    if not args.no_telemetry:
        tel_csv_path, tel_md_path = write_telemetry_outputs(telemetry_rows, args.games, tag)
        print(f"wrote {tel_csv_path}")
        print(f"wrote {tel_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
