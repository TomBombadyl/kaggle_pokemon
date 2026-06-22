"""Verify cg engine loads and one battle step works (CPU smoke)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import lucario_mcts_runtime as rt  # noqa: E402


def main() -> int:
    deck = rt.LUCARIO_DECK
    obs, start = rt.battle_start(deck, deck)
    if start.errorPlayer >= 0:
        print(f"FAIL deck error type={start.errorType}")
        return 1
    sel = rt.random_agent(obs)
    obs2 = rt.battle_select(sel)
    rt.battle_finish()
    print(f"OK cg engine; first select len={len(sel)} result_pending={obs2['current']['result']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
