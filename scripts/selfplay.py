"""T4/T5: self-play harness over the real cabt engine (libcg.so / cg.dll).

Runs full games by driving cg.game.battle_start/battle_select directly — no
kaggle_environments needed, so it works on Python 3.10+ on Linux or Windows
(sim.py auto-selects libcg.so vs cg.dll by OS).

Policies:
  - random_policy   : legal random (the sample agent's behaviour) — baseline.
  - heuristic_policy : agent/agent.py Agent (MAIN priority + safe fallback).

Win-rate is measured with sides swapped each game to cancel first-player
advantage. The engine's own RNG (shuffles, coin flips) is not seedable from
Python, so results carry variance — run enough games (>=100) and report n.

Run:  python3 scripts/selfplay.py [n_games]
"""
from __future__ import annotations

import os
import random
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(PROJ, "data", "sim", "sample_submission")
sys.path.insert(0, ENGINE_DIR)          # for `import cg`
sys.path.insert(0, PROJ)                # for `import agent.agent`

from cg import game            # noqa: E402
from cg.sim import lib, Battle  # noqa: E402
from agent.agent import Agent   # noqa: E402

DECK_PATH = os.path.join(ENGINE_DIR, "deck.csv")


def load_deck(path=DECK_PATH):
    return [int(x) for x in open(path).read().split("\n") if x.strip()][:60]


def _select_player():
    """Index (0/1) of the player the engine is currently asking to choose."""
    return lib.GetBattleData(Battle.battle_ptr).selectPlayer


def random_policy(rng):
    def pol(obs):
        sel = obs["select"]
        opts = sel["option"]
        k = max(int(sel.get("minCount", 1) or 0), 1)
        k = min(k, sel["maxCount"], len(opts))
        return rng.sample(range(len(opts)), k)
    return pol


def heuristic_policy(seed=0):
    ag = Agent(seed=seed)
    return lambda obs: ag.act(obs)


def run_game(pol0, pol1, max_steps=6000):
    """Return winner index (0/1), 2=draw, or -1 if it hit the step cap."""
    deck = load_deck()
    obs, start = game.battle_start(deck, deck)
    if obs is None:
        raise RuntimeError(f"battle_start failed: err={start.errorType}")
    policies = (pol0, pol1)
    try:
        for _ in range(max_steps):
            cur = obs["current"]
            if cur is not None and cur.get("result", -1) != -1:
                return cur["result"]
            if obs["select"] is None:
                return -1
            p = _select_player()
            choice = policies[p](obs)
            obs = game.battle_select(choice)
        return -1
    finally:
        game.battle_finish()


def match(make_a, make_b, n, label):
    """Play n games; A and B swap seats each game. Report A's win-rate."""
    a_wins = b_wins = draws = unfinished = 0
    for i in range(n):
        pa, pb = make_a(i), make_b(i)
        if i % 2 == 0:
            res = run_game(pa, pb)          # A is player 0
            a_win = (res == 0)
            b_win = (res == 1)
        else:
            res = run_game(pb, pa)          # A is player 1
            a_win = (res == 1)
            b_win = (res == 0)
        if res == 2:
            draws += 1
        elif res == -1:
            unfinished += 1
        elif a_win:
            a_wins += 1
        elif b_win:
            b_wins += 1
    decided = a_wins + b_wins
    wr = 100.0 * a_wins / decided if decided else 0.0
    print(f"{label}: A {a_wins}/{n} wins ({wr:.1f}% of decided), "
          f"B {b_wins}, draws {draws}, unfinished {unfinished}")
    return wr


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print(f"cabt self-play — {n} games per matchup (sides swapped each game)\n")
    # T5 sanity: random vs random should be ~50%.
    match(lambda i: random_policy(random.Random(1000 + i)),
          lambda i: random_policy(random.Random(9000 + i)),
          n, "random vs random ")
    # Heuristic agent vs random baseline.
    match(lambda i: heuristic_policy(seed=i),
          lambda i: random_policy(random.Random(7000 + i)),
          n, "heuristic vs random")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
