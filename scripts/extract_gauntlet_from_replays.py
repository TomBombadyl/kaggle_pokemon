#!/usr/bin/env python3
"""Turn downloaded Kaggle episode replays into robust-search gauntlet decks.

The Simulation ladder's real opponents are the truest "field". This reads
episode replay JSON you already downloaded (see report/deck_rl/
episode_dataset_manifest.csv for the daily dataset slugs), extracts the 60-card
decks of *strong* agents, dedups them, and writes them to
report/deck_rl/mined_decks/ where rl/gauntlet.py picks them up automatically.

Download first (on a machine with Kaggle access; datasets are ~3-21 GB/day):

    kaggle datasets download kaggle/pokemon-tcg-ai-battle-episodes-2026-06-19 \
        -p report/replays --unzip

Then extract:

    python scripts/extract_gauntlet_from_replays.py --replays report/replays \
        --min-score 800 --max-decks 60

Reuses the proven parsing in scripts/mine_episode_replays.py. Safe to re-run
(overwrites mined_decks). Never downloads anything itself.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mine_episode_replays import (  # noqa: E402
    _archetype, _card_names, _initial_decks, _iter_json_files, _rewards,
    _safe_load, _team_names,
)

OUT_DIR = ROOT / "report" / "deck_rl" / "mined_decks"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--replays", default=str(ROOT / "report" / "replays"))
    p.add_argument("--out", default=str(OUT_DIR))
    p.add_argument("--min-score", type=float, default=None,
                   help="keep only decks whose agent reward >= this (else keep winners)")
    p.add_argument("--max-decks", type=int, default=80, help="cap distinct mined decks")
    args = p.parse_args(argv)

    replay_dir = Path(args.replays)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = _card_names()

    files = _iter_json_files(replay_dir) if replay_dir.exists() else []
    if not files:
        print(f"No replay JSON under {replay_dir}. Download a daily episodes "
              f"dataset first (see report/deck_rl/episode_dataset_manifest.csv).")
        return 0

    # best score seen per unique deck signature
    best: dict[tuple, dict] = {}
    scanned = 0
    for fp in files:
        data = _safe_load(fp)
        if not isinstance(data, dict):
            continue
        scanned += 1
        decks = _initial_decks(data)
        rewards = _rewards(data)
        teams = _team_names(data)
        for ai, deck in enumerate(decks):
            if not deck or len(deck) != 60:
                continue
            score = float(rewards[ai]) if ai < len(rewards) and _is_num(rewards[ai]) else 0.0
            if args.min_score is not None and score < args.min_score:
                continue
            sig = tuple(sorted(deck))
            if sig not in best or score > best[sig]["score"]:
                best[sig] = {"deck": deck, "score": score,
                             "team": teams[ai] if ai < len(teams) else "",
                             "arch": _archetype(deck, names)}

    if not best:
        print(f"Scanned {scanned} episodes but found no qualifying 60-card decks "
              f"(try lowering --min-score).")
        return 0

    ranked = sorted(best.values(), key=lambda d: d["score"], reverse=True)[: args.max_decks]
    scores = [d["score"] for d in ranked] or [0.0]
    smax, smin = max(scores), min(scores)

    # clear previous mined decks
    for old in out_dir.glob("*.csv"):
        old.unlink()

    for i, d in enumerate(ranked):
        # weight 1.0..2.0 by score percentile (stronger opponents weigh more)
        w = 1.0 + (0.0 if smax == smin else (d["score"] - smin) / (smax - smin))
        safe_arch = "".join(c if c.isalnum() else "_" for c in (d["arch"] or "deck"))[:24]
        fname = f"{i:03d}_{safe_arch}__w{w:.2f}.csv"
        (out_dir / fname).write_text("\n".join(str(c) for c in d["deck"]) + "\n", encoding="utf-8")

    print(f"Scanned {scanned} episodes -> wrote {len(ranked)} mined gauntlet decks to {out_dir}")
    print(f"  score range {smin:.0f}..{smax:.0f}; top archetype: {ranked[0]['arch']}")
    print("rl/gauntlet.py will now include these automatically.")
    return 0


def _is_num(x) -> bool:
    try:
        float(x); return True
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    raise SystemExit(main())
