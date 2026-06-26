"""Index downloaded Kaggle replay/log JSON for Deck RL and BC/RL/IL planning.

This script does not call Kaggle. It only scans local replay/log files that were
already downloaded with the Kaggle CLI and writes lightweight indexes for later
benchmark refresh and behavior-cloning work.

Run:
  python scripts/mine_episode_replays.py
  python scripts/mine_episode_replays.py --replays report/replays --logs report/agent_logs
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPLAYS = ROOT / "report" / "replays"
DEFAULT_LOGS = ROOT / "report" / "agent_logs"
DEFAULT_OUT = ROOT / "report" / "deck_rl" / "replay_index.csv"
DEFAULT_MD = ROOT / "report" / "deck_rl" / "mined_archetypes.md"


def _safe_load(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _episode_id(path: Path, data: Any) -> str:
    if isinstance(data, dict):
        for key in ("episodeId", "episode_id", "id"):
            val = data.get(key)
            if val is not None:
                return str(val)
    return path.stem


def _team_names(data: dict[str, Any]) -> list[str]:
    info = data.get("info") or {}
    names = info.get("TeamNames") or info.get("teamNames") or info.get("teams") or []
    if isinstance(names, list):
        return [str(n) for n in names]
    return []


def _rewards(data: dict[str, Any]) -> list[Any]:
    rewards = data.get("rewards")
    return rewards if isinstance(rewards, list) else []


def _turn_count(data: dict[str, Any]) -> int:
    steps = data.get("steps")
    if isinstance(steps, list):
        return len(steps)
    return 0


def _winner(rewards: list[Any]) -> int | None:
    numeric = []
    for i, reward in enumerate(rewards):
        try:
            numeric.append((i, float(reward)))
        except (TypeError, ValueError):
            pass
    if not numeric:
        return None
    best = max(numeric, key=lambda x: x[1])
    if sum(1 for _i, reward in numeric if reward == best[1]) > 1:
        return None
    return best[0]


def _initial_decks(data: dict[str, Any]) -> list[list[int]]:
    """Return visible 60-card decks when the replay exposes them."""
    try:
        action = data["steps"][0][0]["visualize"][0]["action"]
    except (KeyError, IndexError, TypeError):
        return []
    decks = []
    if isinstance(action, list):
        for deck in action:
            if isinstance(deck, list) and len(deck) == 60:
                try:
                    decks.append([int(c) for c in deck])
                except (TypeError, ValueError):
                    decks.append([])
    return decks


def _selected_context_counts(data: dict[str, Any]) -> Counter:
    """Best-effort count of replay contexts containing selected actions/options."""
    counts: Counter = Counter()
    steps = data.get("steps")
    if not isinstance(steps, list):
        return counts
    for step in steps:
        if not isinstance(step, list):
            continue
        for player_state in step:
            if not isinstance(player_state, dict):
                continue
            for key in ("action", "selected", "selection", "select"):
                if key in player_state:
                    counts[key] += 1
            obs = player_state.get("observation")
            if isinstance(obs, dict):
                select = obs.get("select")
                if isinstance(select, dict):
                    ctx = select.get("type") or select.get("context") or "select"
                    counts[f"obs:{ctx}"] += 1
    return counts


def _deck_signature(deck: list[int]) -> str:
    if len(deck) != 60:
        return ""
    counts = Counter(deck)
    return " ".join(f"{cid}:{n}" for cid, n in sorted(counts.items()))


def _card_names() -> dict[int, str]:
    path = ROOT / "data" / "EN_Card_Data.csv"
    if not path.exists():
        return {}
    names: dict[int, str] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                names[int(row["Card ID"])] = row["Card Name"]
            except (KeyError, ValueError):
                pass
    return names


def _archetype(deck: list[int], names: dict[int, str]) -> str:
    deck_names = " ".join(names.get(cid, "").lower() for cid in set(deck))
    if "kyogre" in deck_names:
        return "kyogre"
    if "dragapult" in deck_names:
        return "dragapult"
    if "greninja" in deck_names:
        return "greninja"
    if "alakazam" in deck_names:
        return "alakazam"
    if "bellibolt" in deck_names:
        return "bellibolt"
    if "lucario" in deck_names:
        return "lucario"
    if "abomasnow" in deck_names:
        return "abomasnow"
    if "archaludon" in deck_names or "duraludon" in deck_names:
        return "archaludon"
    if "starmie" in deck_names or "froslass" in deck_names:
        return "starmie"
    return "unknown"


def _iter_json_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.json") if p.is_file())


def build_index(replay_dir: Path, log_dir: Path) -> tuple[list[dict[str, str]], Counter]:
    names = _card_names()
    rows: list[dict[str, str]] = []
    archetypes: Counter = Counter()
    log_files = {p.stem for p in _iter_json_files(log_dir)}

    for path in _iter_json_files(replay_dir):
        data = _safe_load(path)
        if not isinstance(data, dict):
            continue
        rewards = _rewards(data)
        winner = _winner(rewards)
        teams = _team_names(data)
        decks = _initial_decks(data)
        contexts = _selected_context_counts(data)
        episode_id = _episode_id(path, data)
        for agent_index in range(max(len(teams), len(rewards), len(decks), 2)):
            deck = decks[agent_index] if agent_index < len(decks) else []
            arch = _archetype(deck, names) if deck else "unknown"
            if deck:
                archetypes[arch] += 1
            rows.append(
                {
                    "episode_id": episode_id,
                    "source_file": str(path.relative_to(ROOT)),
                    "agent_index": str(agent_index),
                    "team_name": teams[agent_index] if agent_index < len(teams) else "",
                    "reward": str(rewards[agent_index]) if agent_index < len(rewards) else "",
                    "winner": "1" if winner == agent_index else "0" if winner is not None else "",
                    "turn_count": str(_turn_count(data)),
                    "deck_archetype": arch,
                    "deck_signature": _deck_signature(deck),
                    "selected_context_counts": json.dumps(dict(contexts), sort_keys=True),
                    "has_downloaded_log": "1" if episode_id in log_files or path.stem in log_files else "0",
                }
            )
    return rows, archetypes


def write_outputs(rows: list[dict[str, str]], archetypes: Counter, out_csv: Path, out_md: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "episode_id",
        "source_file",
        "agent_index",
        "team_name",
        "reward",
        "winner",
        "turn_count",
        "deck_archetype",
        "deck_signature",
        "selected_context_counts",
        "has_downloaded_log",
    ]
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Mined Archetypes",
        "",
        "Generated from local downloaded replay/log JSON only. No Kaggle API calls were made.",
        "",
        f"Replay agent rows indexed: {len(rows)}",
        "",
        "| Archetype | Deck rows |",
        "|---|---:|",
    ]
    for arch, count in archetypes.most_common():
        lines.append(f"| {arch} | {count} |")
    if not archetypes:
        lines.append("| none | 0 |")
    lines.extend(
        [
            "",
            "Next use: reconstruct repeated winning archetypes as `agent_decks/benchmark/live_*.csv`, then validate with `scripts/validate_deck.py` before adding them to `agent_decks/benchmark/suite.json`.",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replays", default=str(DEFAULT_REPLAYS))
    parser.add_argument("--logs", default=str(DEFAULT_LOGS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--markdown", default=str(DEFAULT_MD))
    args = parser.parse_args(argv)

    rows, archetypes = build_index(Path(args.replays), Path(args.logs))
    write_outputs(rows, archetypes, Path(args.out), Path(args.markdown))
    print(f"wrote {args.out} rows={len(rows)}")
    print(f"wrote {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
