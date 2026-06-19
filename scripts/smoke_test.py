"""Offline contract tests for agent.py — no engine/Kaggle token needed.

Validates the cabt agent contract against synthetic observations:
  1. Always returns a list[int].
  2. Count is within [minCount, maxCount] and indices are in range + distinct.
  3. MAIN selections follow T7 setup priority (evolve/play/attach before attack).
  4. Deck-selection phase returns a list (60 IDs when deck.csv is valid).
  5. Never raises, even on malformed/empty option lists.

Run:  python3 scripts/smoke_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.agent import (  # noqa: E402
    agent,
    OPT_ATTACK, OPT_EVOLVE, OPT_ATTACH, OPT_ABILITY, OPT_PLAY, OPT_END,
    OPT_YES, OPT_NO, OPT_CARD, OPT_NUMBER,
    SEL_MAIN, SEL_CARD, SEL_YES_NO, SEL_ATTACK, SEL_COUNT,
    CTX_SETUP_BENCH_POKEMON, CTX_DRAW_COUNT, CTX_TO_HAND, CTX_ATTACH_TO,
    CARD_MEGA_ABOMASNOW_EX, CARD_WATER_ENERGY,
)

PASS, FAIL = 0, 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


def legal(out, select) -> bool:
    """True iff `out` is a valid selection for `select`."""
    if not isinstance(out, list) or not all(isinstance(i, int) for i in out):
        return False
    n = len(select["option"])
    if len(set(out)) != len(out):
        return False
    if any(i < 0 or i >= n for i in out):
        return False
    return select["minCount"] <= len(out) <= select["maxCount"]


def sel(stype, options, mn=1, mx=1, context=0):
    return {"type": stype, "context": context, "minCount": mn,
            "maxCount": mx, "option": options}


print("cabt agent contract tests")

# 1. MAIN priority: setup action chosen over attack.
s = sel(SEL_MAIN, [{"type": OPT_END}, {"type": OPT_PLAY}, {"type": OPT_ATTACK}])
o = agent({"logs": [], "current": {}, "select": s})
check("MAIN develops before ATTACK", o == [1] and legal(o, s))

# 2. MAIN with no attack: evolve > attach > ability > play.
s = sel(SEL_MAIN, [{"type": OPT_END}, {"type": OPT_PLAY}, {"type": OPT_ATTACH},
                   {"type": OPT_EVOLVE}])
o = agent({"logs": [], "current": {}, "select": s})
check("MAIN picks EVOLVE when no attack", o == [3] and legal(o, s))

# 3. MAIN only END available.
s = sel(SEL_MAIN, [{"type": OPT_END}])
o = agent({"logs": [], "current": {}, "select": s})
check("MAIN with only END returns [0]", o == [0] and legal(o, s))

# 4. Forced YES/NO (minCount=1): returns exactly one of YES/NO.
s = sel(SEL_YES_NO, [{"type": OPT_YES}, {"type": OPT_NO}], mn=1, mx=1)
o = agent({"logs": [], "current": {}, "select": s})
check("forced YES_NO returns one index", legal(o, s))

# 5. Optional YES/NO (minCount=0): declines (NO) — still legal.
s = sel(SEL_YES_NO, [{"type": OPT_YES}, {"type": OPT_NO}], mn=0, mx=1)
o = agent({"logs": [], "current": {}, "select": s})
check("optional YES_NO is legal", legal(o, s))

# 6. Multi-select card (minCount=2, maxCount=3): legal count.
opts = [{"type": OPT_CARD, "index": i} for i in range(5)]
s = sel(SEL_CARD, opts, mn=2, mx=3)
o = agent({"logs": [], "current": {}, "select": s})
check("multi-select returns 2..3 distinct in-range", legal(o, s))

# 6b. Optional setup bench should fill legal slots instead of declining.
opts = [{"type": OPT_CARD, "index": i} for i in range(3)]
s = sel(SEL_CARD, opts, mn=0, mx=3, context=CTX_SETUP_BENCH_POKEMON)
o = agent({"logs": [], "current": {}, "select": s})
check("optional setup bench fills slots", len(o) == 3 and legal(o, s))

# 6c. Draw-count prompts should choose the largest available number.
opts = [{"type": OPT_NUMBER, "number": n} for n in [0, 1, 2]]
s = sel(SEL_COUNT, opts, mn=1, mx=1, context=CTX_DRAW_COUNT)
o = agent({"logs": [], "current": {}, "select": s})
check("draw count picks max", o == [2] and legal(o, s))

# 6d. Optional TO_HAND should take a visible high-value card instead of declining.
opts = [{"type": OPT_CARD, "area": 12, "index": 0},
        {"type": OPT_CARD, "area": 12, "index": 1}]
s = sel(SEL_CARD, opts, mn=0, mx=1, context=CTX_TO_HAND)
cur = {"looking": [{"id": CARD_WATER_ENERGY}, {"id": CARD_MEGA_ABOMASNOW_EX}]}
o = agent({"logs": [], "current": cur, "select": s})
check("optional TO_HAND takes best visible card", o == [1] and legal(o, s))

# 6e. Optional ATTACH_TO should take visible Energy instead of declining.
opts = [{"type": OPT_CARD, "area": 12, "index": 0}]
s = sel(SEL_CARD, opts, mn=0, mx=1, context=CTX_ATTACH_TO)
cur = {"looking": [{"id": CARD_WATER_ENERGY}], "energyAttached": False}
o = agent({"logs": [], "current": cur, "select": s})
check("optional ATTACH_TO takes energy", o == [0] and legal(o, s))

# 7. Single attack selection.
opts = [{"type": OPT_ATTACK, "attackId": 1}, {"type": OPT_ATTACK, "attackId": 2}]
s = sel(SEL_ATTACK, opts, mn=1, mx=1)
o = agent({"logs": [], "current": {}, "select": s})
check("attack select returns one index", legal(o, s))

# 8. Empty option list must not crash.
s = sel(SEL_CARD, [], mn=0, mx=0)
try:
    o = agent({"logs": [], "current": {}, "select": s})
    check("empty options returns [] without crashing", o == [])
except Exception as e:  # pragma: no cover
    check(f"empty options without crash (raised {e})", False)

# 9. Deck-selection phase returns a list.
o = agent({"logs": [], "current": None, "select": None})
check("deck phase returns a list", isinstance(o, list))

# 10. Malformed option (missing 'type') must not crash.
s = sel(SEL_MAIN, [{"foo": 1}, {"type": OPT_END}], mn=1, mx=1)
try:
    o = agent({"logs": [], "current": {}, "select": s})
    check("malformed option handled", legal(o, s))
except Exception as e:  # pragma: no cover
    check(f"malformed option handled (raised {e})", False)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
