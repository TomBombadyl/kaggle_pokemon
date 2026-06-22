"""Remove stale RL+MCTS artifacts so only the fresh local trainer remains.

  python scripts/cleanup_old_rl_artifacts.py

Keeps: official reference notebooks at repo root, agent_decks/*.csv,
       reinforcement-learning-and-mcts-sample-code.ipynb,
       a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REMOVE_DIRS = [
    ROOT / "notebooks" / "rl_mcts_field_train",
    ROOT / "rl_mcts_basic",
    ROOT / "rl_mcts_field" / "lucarioex_field_smoke",
]

REMOVE_FILES = [
    ROOT / "notebooks" / "kernel-metadata.json",  # stale Track B kernel meta
]


def main() -> int:
    for d in REMOVE_DIRS:
        if d.exists():
            shutil.rmtree(d)
            print(f"removed dir {d}")
    for f in REMOVE_FILES:
        if f.exists():
            f.unlink()
            print(f"removed file {f}")
    print("cleanup done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
