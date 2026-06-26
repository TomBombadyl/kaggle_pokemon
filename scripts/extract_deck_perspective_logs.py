"""Extract per-deck perspective turn logs from Kaggle replays.

Each deck uses a different rule pilot and 60-card list — analysis must be from
*our seat only* (bench/hand/prize/decisions when yourIndex == our agent).

Kaggle ``agent_logs`` are timing-only; deck learning comes from replay steps.

Usage:
  python scripts/extract_deck_perspective_logs.py --ref 54083197 --deck archaludon \\
    --deck-csv agent_decks/archaludon_ex_cinderace.csv --brain archaludon_rules
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from episode_stats import load_json, parse_replay, team_names_from_replay  # noqa: E402
from mine_episode_replays import _card_names  # noqa: E402

DEFAULT_REPLAYS = ROOT / "report" / "replays"
DEFAULT_STATS = ROOT / "report" / "submission_stats"
DEFAULT_OUT = ROOT / "report" / "deck_logs"


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    h.update(path.read_bytes())
    return h.hexdigest()


def _replay_path(episode_id: str, replays_dir: Path) -> Path | None:
    for p in (replays_dir / f"{episode_id}.json", replays_dir / f"episode-{episode_id}-replay.json"):
        if p.exists():
            return p
    return None


def _load_stats(ref: str, stats_path: Path | None) -> dict[str, dict[str, str]]:
    path = stats_path or (DEFAULT_STATS / f"{ref}_stats.csv")
    if not path.exists():
        return {}
    return {(r.get("episode_id") or "").strip(): r for r in csv.DictReader(path.open(encoding="utf-8")) if r.get("episode_id")}


def _pokemon_summary(card: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(card, dict):
        return None
    return {
        "id": card.get("id"),
        "hp": card.get("hp"),
        "max_hp": card.get("maxHp") or card.get("max_hp"),
        "energy_count": len(card.get("energies") or card.get("energyCards") or []),
        "has_tool": bool(card.get("tools") or card.get("tool")),
    }


def _player_snapshot(player: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(player, dict):
        return {}
    active = player.get("active") or []
    bench = player.get("bench") or []
    return {
        "deck_count": player.get("deckCount"),
        "hand_count": len(player.get("hand") or []),
        "bench_count": len(bench),
        "prize_remaining": len(player.get("prize") or []),
        "discard_count": len(player.get("discard") or []),
        "active": _pokemon_summary(active[0] if active else None),
        "bench_ids": [p.get("id") for p in bench if isinstance(p, dict)],
    }


def _select_summary(select: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(select, dict):
        return {}
    opts = select.get("option") or []
    return {
        "type": select.get("type"),
        "context": select.get("context"),
        "option_count": len(opts) if isinstance(opts, list) else 0,
        "min_count": select.get("minCount"),
        "max_count": select.get("maxCount"),
    }


def _action_summary(action: Any) -> Any:
    if isinstance(action, list):
        return action
    if isinstance(action, dict):
        return {k: action[k] for k in ("type", "index", "attackId", "cardId") if k in action}
    return action


def extract_our_turns(data: dict[str, Any], our_index: int) -> list[dict[str, Any]]:
    """One entry per replay step where our deck is the deciding player."""
    turns: list[dict[str, Any]] = []
    steps = data.get("steps")
    if not isinstance(steps, list):
        return turns

    for step_idx, step in enumerate(steps):
        if not isinstance(step, list):
            continue
        for ps in step:
            if not isinstance(ps, dict):
                continue
            obs = ps.get("observation")
            if not isinstance(obs, dict):
                continue
            cur = obs.get("current") or {}
            if int(cur.get("yourIndex", -1)) != our_index:
                continue
            players = cur.get("players") or []
            our_player = players[our_index] if our_index < len(players) else {}
            opp_player = players[1 - our_index] if len(players) > 1 else {}
            turns.append({
                "step": step_idx,
                "turn": cur.get("turn"),
                "result": cur.get("result"),
                "select": _select_summary(obs.get("select")),
                "action": _action_summary(ps.get("action")),
                "us": _player_snapshot(our_player),
                "opponent_visible": {
                    "bench_count": len(opp_player.get("bench") or []) if isinstance(opp_player, dict) else None,
                    "prize_remaining": len(opp_player.get("prize") or []) if isinstance(opp_player, dict) else None,
                    "active": _pokemon_summary((opp_player.get("active") or [None])[0]) if isinstance(opp_player, dict) else None,
                },
            })
    return turns


def build_episode_log(
    episode_id: str,
    *,
    ref: str,
    deck_name: str,
    brain: str,
    deck_csv: Path,
    replays_dir: Path,
    stats_row: dict[str, str] | None,
    card_names: dict[int, str],
) -> dict[str, Any] | None:
    deck_csv = deck_csv if deck_csv.is_absolute() else (ROOT / deck_csv)
    raw = _replay_path(episode_id, replays_dir)
    if raw is None:
        return None
    data = load_json(raw)
    if not isinstance(data, dict):
        return None

    our_index = int((stats_row or {}).get("agent_index", 0))
    parsed = parse_replay(data, our_agent_index=our_index)
    teams = team_names_from_replay(data)
    our_turns = extract_our_turns(data, our_index)

    # Terminal snapshot from our deck's seat
    terminal = our_turns[-1]["us"] if our_turns else {}
    if parsed and parsed.outcome == "loss" and our_turns:
        terminal = our_turns[-1]["us"]

    deck_ids: list[int] = []
    if deck_csv.exists():
        deck_ids = [int(line.strip()) for line in deck_csv.read_text(encoding="utf-8").splitlines() if line.strip()]

    return {
        "ref": ref,
        "deck": deck_name,
        "brain": brain,
        "deck_csv": str(deck_csv.relative_to(ROOT)),
        "deck_sha1": _sha1(deck_csv) if deck_csv.exists() else None,
        "deck_card_ids": deck_ids,
        "episode_id": episode_id,
        "our_agent_index": our_index,
        "our_team": teams[our_index] if our_index < len(teams) else "",
        "opponent_team": teams[1 - our_index] if len(teams) > 1 else "",
        "outcome": parsed.outcome if parsed else (stats_row or {}).get("outcome"),
        "result_reason": parsed.result_reason if parsed else (stats_row or {}).get("result_reason"),
        "turn_count": parsed.turn_count if parsed else int((stats_row or {}).get("turn_count") or 0),
        "our_decision_count": len(our_turns),
        "terminal_us": terminal,
        "raw_replay": str(raw.relative_to(ROOT)),
        "turns": our_turns,
        "note": "Deck-perspective only: rules+cards for this list, not opponent pilot logic.",
    }


def write_index(deck_name: str, ref: str, brain: str, episodes: list[dict[str, Any]], out_dir: Path) -> None:
    wins = [e for e in episodes if e.get("outcome") == "win"]
    losses = [e for e in episodes if e.get("outcome") == "loss"]
    idx = {
        "deck": deck_name,
        "brain": brain,
        "ref": ref,
        "perspective": "our_seat_only",
        "episodes_total": len(episodes),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(100.0 * len(wins) / (len(wins) + len(losses)), 2) if wins or losses else 0.0,
        "episodes": [
            {
                "episode_id": e["episode_id"],
                "outcome": e["outcome"],
                "result_reason": e["result_reason"],
                "turn_count": e["turn_count"],
                "our_decision_count": e["our_decision_count"],
                "terminal_bench": (e.get("terminal_us") or {}).get("bench_count"),
                "file": f"{e['episode_id']}.json",
            }
            for e in episodes
        ],
    }
    (out_dir / "index.json").write_text(json.dumps(idx, indent=2), encoding="utf-8")
    loss_eps = [e for e in episodes if e.get("outcome") == "loss"]
    (out_dir / "losses.json").write_text(json.dumps({
        "deck": deck_name,
        "brain": brain,
        "ref": ref,
        "count": len(loss_eps),
        "losses": [
            {
                "episode_id": e["episode_id"],
                "result_reason": e["result_reason"],
                "turn_count": e["turn_count"],
                "terminal_bench": (e.get("terminal_us") or {}).get("bench_count"),
                "terminal_hand": (e.get("terminal_us") or {}).get("hand_count"),
                "last_turns": e["turns"][-3:] if e.get("turns") else [],
                "file": f"{e['episode_id']}.json",
            }
            for e in loss_eps
        ],
    }, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--deck", required=True, help="Output folder name, e.g. archaludon")
    ap.add_argument("--deck-csv", type=Path, required=True)
    ap.add_argument("--brain", default="", help="Brain/rules id, e.g. archaludon_rules")
    ap.add_argument("--stats", type=Path, default=None)
    ap.add_argument("--replays", type=Path, default=DEFAULT_REPLAYS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    ref = args.ref.strip()
    deck_name = args.deck.strip()
    brain = args.brain.strip() or deck_name
    out_dir = args.out / deck_name
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = _load_stats(ref, args.stats)
    names = _card_names()

    episodes: list[dict[str, Any]] = []
    missing: list[str] = []
    for ep_id in sorted(stats.keys(), key=lambda x: int(x) if x.isdigit() else x):
        doc = build_episode_log(
            ep_id,
            ref=ref,
            deck_name=deck_name,
            brain=brain,
            deck_csv=args.deck_csv,
            replays_dir=args.replays,
            stats_row=stats.get(ep_id),
            card_names=names,
        )
        if doc is None:
            missing.append(ep_id)
            continue
        episodes.append(doc)
        (out_dir / f"{ep_id}.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")

    if not episodes:
        print(f"ERROR: no deck logs for ref {ref}", file=sys.stderr)
        return 1

    write_index(deck_name, ref, brain, episodes, out_dir)
    print(f"wrote {len(episodes)} deck-perspective log(s) -> {out_dir.relative_to(ROOT)}")
    if missing:
        print(f"  missing replays: {len(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
