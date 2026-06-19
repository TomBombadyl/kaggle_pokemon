"""Time-budgeted search-augmented OptionScorer with heuristic fallback."""

from __future__ import annotations

import json
import time
from typing import Any

from agent.agent import (
    CTX_TO_ACTIVE,
    HeuristicScorer,
    OPT_ATTACK,
    OPT_END,
    OPT_PLAY,
    SEL_ATTACK,
    SEL_MAIN,
    _get,
    _option_type,
)
from agent.evalfn import board_value

SEARCH_BUDGET_MS = 200
HIGH_LEVERAGE_CONTEXTS = {CTX_TO_ACTIVE, 35}  # promotion + ATTACK context


class SearchScorer(HeuristicScorer):
    """Rerank high-leverage decisions with evalfn; optional cg search_* when available."""

    def __init__(self, rng=None, budget_ms: float = SEARCH_BUDGET_MS) -> None:
        super().__init__(rng=rng)
        self._fallback = HeuristicScorer(rng=rng)
        self._budget_ms = budget_ms
        self._lib = None
        self._battle_ptr = None

    def _ensure_engine(self) -> bool:
        if self._lib is not None:
            return True
        try:
            from cg.sim import Battle, lib  # type: ignore

            self._lib = lib
            self._battle_ptr = Battle.battle_ptr
            return self._battle_ptr is not None
        except Exception:
            return False

    def choose(self, obs_dict, select, current, options):
        if not options:
            return []
        try:
            if self._should_search(select, options):
                choice = self._search_choose(obs_dict, select, current, options)
                if choice is not None:
                    return choice
        except Exception:
            pass
        return self._fallback.choose(obs_dict, select, current, options)

    def _should_search(self, select, options) -> bool:
        sel_type = select.get("type")
        context = select.get("context")
        if sel_type == SEL_MAIN and any(_option_type(o) in (OPT_ATTACK, OPT_PLAY) for o in options):
            return True
        if sel_type == SEL_ATTACK:
            return True
        if context in HIGH_LEVERAGE_CONTEXTS:
            return True
        return False

    def _search_choose(self, obs_dict, select, current, options):
        deadline = time.monotonic() + self._budget_ms / 1000.0
        sel_type = select.get("type")

        if sel_type == SEL_MAIN:
            candidates = [
                i for i, opt in enumerate(options)
                if _option_type(opt) in (OPT_ATTACK, OPT_PLAY, OPT_END)
            ]
            if not candidates:
                return None
            return self._evalfn_pick(obs_dict, options, candidates, deadline)

        if sel_type == SEL_ATTACK:
            return self._evalfn_pick(obs_dict, options, list(range(len(options))), deadline)

        if select.get("context") in HIGH_LEVERAGE_CONTEXTS:
            min_count = int(select.get("minCount", 1) or 0)
            if min_count <= 1:
                pick = self._evalfn_pick(obs_dict, options, list(range(len(options))), deadline)
                return pick

        if self._ensure_engine() and time.monotonic() < deadline:
            return self._ctypes_search(obs_dict, options, deadline)
        return None

    def _evalfn_pick(self, obs_dict, options, indices, deadline):
        best_idx = None
        best_val = float("-inf")
        base = board_value(obs_dict)
        for i in indices:
            if time.monotonic() >= deadline:
                break
            opt = options[i]
            bonus = 0.0
            if _option_type(opt) == OPT_ATTACK:
                attack_id = _get(opt, "attackId", 0) or 0
                bonus += self._attack_score(opt, obs_dict.get("current") or {}) / 100.0
                bonus += attack_id * 1e-6
            elif _option_type(opt) == OPT_PLAY:
                bonus += self._play_score(opt, obs_dict.get("current") or {}) / 500.0
            val = base + bonus
            if val > best_val:
                best_val = val
                best_idx = i
        if best_idx is None:
            return None
        return [best_idx]

    def _ctypes_search(self, obs_dict, options, deadline) -> list[int] | None:
        """Best-effort wrapper around cg search_*; returns None on failure."""
        try:
            lib = self._lib
            ptr = self._battle_ptr
            if lib is None or ptr is None:
                return None
            begin_input = obs_dict.get("search_begin_input", "")
            if not begin_input:
                return None
            n_opts = len(options)
            if n_opts <= 0:
                return None
            indices = (ctypes := __import__("ctypes")).c_int * n_opts
            idx_arr = indices(*range(n_opts))
            out_idx = (ctypes.c_int * 1)(0)
            out_score = (ctypes.c_int * 1)(0)
            out_depth = (ctypes.c_int * 1)(0)
            out_nodes = (ctypes.c_int * 1)(0)
            out_time = (ctypes.c_int * 1)(0)
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            search_ptr = lib.SearchBegin(
                ptr,
                begin_input.encode("ascii"),
                remaining_ms,
                idx_arr,
                out_idx,
                out_score,
                out_depth,
                out_nodes,
                out_time,
                n_opts,
            )
            if not search_ptr:
                return None
            handle = int(search_ptr, 16) if isinstance(search_ptr, str) else 0
            try:
                step = lib.SearchStep(ptr, handle, out_idx, 1)
                if step:
                    data = json.loads(step.decode()) if isinstance(step, bytes) else {}
                    pick = data.get("index", out_idx[0])
                    if isinstance(pick, int) and 0 <= pick < n_opts:
                        return [pick]
                if 0 <= out_idx[0] < n_opts:
                    return [out_idx[0]]
            finally:
                lib.SearchEnd(ptr)
                if handle:
                    lib.SearchRelease(ptr, handle)
        except Exception:
            return None
        return None
