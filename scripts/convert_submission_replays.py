"""Convert raw Kaggle replay JSON into compact analysis-friendly JSON.

Raw replays (report/replays/{episode_id}.json) are multi-MB gymnasium traces.
This script writes one small JSON per episode under report/submission_replays/<name>/
plus index.json and losses.json for quick review.

Usage:
  python scripts/convert_submission_replays.py --ref 54083197 --name archaludon
  python scripts/convert_submission_replays.py --ref 54083197 --name archaludon --stats report/submission_stats/54083197_stats.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from episode_stats import load_json, parse_replay, team_names_from_replay  # noqa: E402
from mine_episode_replays import (  # noqa: E402
    _archetype,
    _card_names,
    _deck_signature,
    _initial_decks,
    _selected_context_counts,
)

DEFAULT_REPLAYS = ROOT / "report" / "replays"
DEFAULT_STATS = ROOT / "report" / "submission_stats"
DEFAULT_OUT = ROOT / "report" / "submission_replays"


def _deck_entries(deck: list[int], names: dict[int, str]) -> list[dict[str, Any]]:
    counts = Counter(deck)
    return [
        {"id": cid, "name": names.get(cid, f"card_{cid}"), "count": n}
        for cid, n in sorted(counts.items())
    ]


def _replay_path(episode_id: str, replays_dir: Path) -> Path | None:
    for candidate in (
        replays_dir / f"{episode_id}.json",
        replays_dir / f"episode-{episode_id}-replay.json",
    ):
        if candidate.exists():
            return candidate
    return None


def _load_stats(stats_path: Path | None, ref: str) -> dict[str, dict[str, str]]:
    path = stats_path or (DEFAULT_STATS / f"{ref}_stats.csv")
    if not path.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            ep = (row.get("episode_id") or "").strip()
            if ep:
                out[ep] = row
    return out


def convert_episode(
    episode_id: str,
    *,
    ref: str,
    package_name: str,
    replays_dir: Path,
    stats_row: dict[str, str] | None,
    names: dict[int, str],
) -> dict[str, Any] | None:
    raw_path = _replay_path(episode_id, replays_dir)
    if raw_path is None:
        return None
    data = load_json(raw_path)
    if not isinstance(data, dict):
        return None

    our_index = int((stats_row or {}).get("agent_index", 0))
    if stats_row and stats_row.get("agent_index") not in (None, ""):
        our_index = int(stats_row["agent_index"])

    parsed = parse_replay(data, our_agent_index=our_index)
    teams = team_names_from_replay(data)
    rewards = data.get("rewards") or []
    decks = _initial_decks(data)
    contexts = _selected_context_counts(data)

    agents: list[dict[str, Any]] = []
    for idx in range(max(len(teams), len(rewards), len(decks), 2)):
        deck = decks[idx] if idx < len(decks) else []
        agents.append({
            "index": idx,
            "team": teams[idx] if idx < len(teams) else "",
            "reward": rewards[idx] if idx < len(rewards) else None,
            "deck_card_ids": deck,
            "deck_cards": _deck_entries(deck, names) if deck else [],
            "deck_archetype": _archetype(deck, names) if deck else "unknown",
            "deck_signature": _deck_signature(deck),
            "is_us": idx == our_index,
        })

    opp_index = 1 - our_index
    opp = agents[opp_index] if opp_index < len(agents) else {}

    doc: dict[str, Any] = {
        "ref": ref,
        "package": package_name,
        "episode_id": episode_id,
        "episode_type": (stats_row or {}).get("episode_type", ""),
        "raw_replay": str(raw_path.relative_to(ROOT)),
        "our_agent_index": our_index,
        "our_team": teams[our_index] if our_index < len(teams) else "",
        "opponent_team": opp.get("team", ""),
        "outcome": parsed.outcome if parsed else (stats_row or {}).get("outcome", "unknown"),
        "result_reason": parsed.result_reason if parsed else (stats_row or {}).get("result_reason", ""),
        "turn_count": parsed.turn_count if parsed else int((stats_row or {}).get("turn_count") or 0),
        "reward": parsed.reward if parsed else float((stats_row or {}).get("reward") or 0),
        "rewards": rewards,
        "opponent_archetype": opp.get("deck_archetype", "unknown"),
        "opponent_deck_signature": opp.get("deck_signature", ""),
        "our_deck_archetype": agents[our_index].get("deck_archetype", "unknown") if our_index < len(agents) else "unknown",
        "selected_context_counts": dict(contexts),
        "agents": agents,
    }
    return doc


def write_outputs(
    ref: str,
    package_name: str,
    episodes: list[dict[str, Any]],
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for ep in episodes:
        ep_id = ep["episode_id"]
        dest = out_dir / f"{ep_id}.json"
        dest.write_text(json.dumps(ep, indent=2), encoding="utf-8")

    index = {
        "ref": ref,
        "package": package_name,
        "episodes_total": len(episodes),
        "wins": sum(1 for e in episodes if e.get("outcome") == "win"),
        "losses": sum(1 for e in episodes if e.get("outcome") == "loss"),
        "draws": sum(1 for e in episodes if e.get("outcome") == "draw"),
        "episodes": [
            {
                "episode_id": e["episode_id"],
                "outcome": e["outcome"],
                "result_reason": e["result_reason"],
                "turn_count": e["turn_count"],
                "opponent_team": e["opponent_team"],
                "opponent_archetype": e["opponent_archetype"],
                "file": f"{e['episode_id']}.json",
            }
            for e in episodes
        ],
    }
    decided = index["wins"] + index["losses"]
    index["win_rate_pct"] = round(100.0 * index["wins"] / decided, 2) if decided else 0.0
    index["loss_reasons"] = dict(Counter(
        e["result_reason"] for e in episodes if e.get("outcome") == "loss"
    ))
    index["opponent_archetypes"] = dict(Counter(e["opponent_archetype"] for e in episodes))

    (out_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

    losses = [e for e in episodes if e.get("outcome") == "loss"]
    (out_dir / "losses.json").write_text(json.dumps({
        "ref": ref,
        "package": package_name,
        "count": len(losses),
        "losses": [
            {
                "episode_id": e["episode_id"],
                "result_reason": e["result_reason"],
                "turn_count": e["turn_count"],
                "opponent_team": e["opponent_team"],
                "opponent_archetype": e["opponent_archetype"],
                "file": f"{e['episode_id']}.json",
            }
            for e in losses
        ],
    }, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", required=True, help="Kaggle submission ref")
    parser.add_argument("--name", default=None, help="Output folder name (default: ref)")
    parser.add_argument("--stats", type=Path, default=None, help="Per-episode stats CSV")
    parser.add_argument("--replays", type=Path, default=DEFAULT_REPLAYS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    ref = args.ref.strip()
    package_name = (args.name or ref).strip()
    out_dir = args.out / package_name
    stats = _load_stats(args.stats, ref)
    if not stats:
        print(f"WARNING: no stats CSV for ref {ref}; agent_index may default to 0", file=sys.stderr)

    names = _card_names()
    converted: list[dict[str, Any]] = []
    missing: list[str] = []
    for ep_id in sorted(stats.keys(), key=lambda x: int(x) if x.isdigit() else x):
        doc = convert_episode(
            ep_id,
            ref=ref,
            package_name=package_name,
            replays_dir=args.replays,
            stats_row=stats.get(ep_id),
            names=names,
        )
        if doc is None:
            missing.append(ep_id)
            continue
        converted.append(doc)

    if not converted:
        print(f"ERROR: no episodes converted for ref {ref}", file=sys.stderr)
        return 1

    write_outputs(ref, package_name, converted, out_dir)
    print(f"converted {len(converted)} episode(s) -> {out_dir.relative_to(ROOT)}")
    print(f"  index.json  losses.json  + {len(converted)} x {{episode_id}}.json")
    if missing:
        print(f"  missing raw replays: {len(missing)} ({', '.join(missing[:5])}{'...' if len(missing)>5 else ''})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
