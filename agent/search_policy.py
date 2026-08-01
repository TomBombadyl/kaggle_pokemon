"""Time-budgeted search-augmented OptionScorer with heuristic fallback.

Track A design: keep the full heuristic policy as the default brain and only
layer shallow search on high-leverage card picks (promotion / switch). The prior
evalfn rerank on MAIN skipped EVOLVE/ATTACH and regressed badly vs heuristic.

LucarioSearchScorer merges SearchScorer's cg search_* layer with LucarioScorer
MAIN/meta (668 mu search + SmartBench mirror gains).
"""

from __future__ import annotations

import json
import os
import time

from agent.agent import (
    CTX_SETUP_ACTIVE_POKEMON,
    CTX_SETUP_BENCH_POKEMON,
    CTX_SWITCH,
    CTX_TO_ACTIVE,
    CTX_TO_HAND,
    CTX_TO_DECK,
    CTX_TO_DECK_BOTTOM,
    CTX_ATTACH_FROM,
    HeuristicScorer,
    SEL_CARD,
    load_deck,
)
from agent.prize_tracker import PrizeTracker

# Env knobs for small A/B gates (no core-loop rewrite).
# SEARCH_BUDGET_MS: cg SearchBegin wall budget on high-leverage card picks.
# SEARCH_GUARD_TOP_K: LucarioSearchScorer accepts search only if pick ∈ Lucario top-k.
# SEARCH_HEURISTIC_BLEND: after search, if 0<blend≤1, re-rank search pick vs heuristic
#   soft scores (0=pure search, 1=pure heuristic on the candidate set). Default 0.
def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


SEARCH_BUDGET_MS = _env_float("SEARCH_BUDGET_MS", 200.0)
HIGH_LEVERAGE_CONTEXTS = {
    CTX_TO_ACTIVE,
    CTX_SWITCH,
    CTX_SETUP_ACTIVE_POKEMON,
    CTX_SETUP_BENCH_POKEMON,
}
# Lucario hybrid: search on promote/switch/setup-active (SETUP_BENCH is bench_guard → Lucario).
# Search picks must land in Lucario top-2 or we keep LucarioScorer (mirror guard).
LUCARIO_SEARCH_CONTEXTS = {
    CTX_TO_ACTIVE,
    CTX_SWITCH,
    CTX_SETUP_ACTIVE_POKEMON,
}
SEARCH_GUARD_TOP_K = max(1, _env_int("SEARCH_GUARD_TOP_K", 2))
SEARCH_HEURISTIC_BLEND = max(0.0, min(1.0, _env_float("SEARCH_HEURISTIC_BLEND", 0.0)))
PRIZE_DECK_CONTEXTS = {
    CTX_TO_HAND,
    CTX_TO_DECK,
    CTX_TO_DECK_BOTTOM,
    CTX_ATTACH_FROM,
}


class _PrizeTrackerMixin:
    """Update PrizeTracker and penalize prized cards in deck search picks."""

    def _init_prize_tracker(self, deck_path: str | None = None) -> None:
        path = deck_path or os.path.join(
            os.path.dirname(__file__), "deck.csv"
        )
        try:
            deck_ids = load_deck(path)
            self._prize_tracker = PrizeTracker(deck_ids) if len(deck_ids) == 60 else None
        except Exception:
            self._prize_tracker = None

    def _update_prize_tracker(self, obs_dict) -> None:
        if self._prize_tracker is None:
            return
        try:
            from cg.api import to_observation_class

            obs = to_observation_class(obs_dict)
            self._prize_tracker.update(obs, obs_dict)
        except Exception:
            pass

    def _prize_adjust_card_score(self, score: float, card_id: int, select) -> float:
        if self._prize_tracker is None or select is None:
            return score
        context = select.get("context")
        if context not in PRIZE_DECK_CONTEXTS:
            return score
        prized = self._prize_tracker.is_prized(card_id)
        if prized is True:
            return score - 1e9
        return score


class _CgSearchMixin:
    """Shared cg search_* wrapper for high-leverage card picks."""

    def _init_search(
        self,
        budget_ms: float = SEARCH_BUDGET_MS,
        *,
        search_contexts: set | None = None,
    ) -> None:
        self._budget_ms = budget_ms
        self._search_contexts = search_contexts or HIGH_LEVERAGE_CONTEXTS
        self._lib = None
        self._battle_ptr = None

    def _audit_search(self, event: str, **payload) -> None:
        path = os.environ.get("SEARCH_AUDIT_LOG")
        if not path:
            return
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"event": event, **payload}, sort_keys=True) + "\n")
        except Exception:
            pass

    def _try_search(self, obs_dict, select, options) -> list[int] | None:
        if not options:
            return None
        try:
            context = select.get("context")
            eligible = (
                select.get("type") == SEL_CARD
                and context in self._search_contexts
                and int(select.get("minCount", 1) or 0) <= 1
            )
            self._audit_search(
                "try_search",
                context=context,
                eligible=eligible,
                has_begin=bool(obs_dict.get("search_begin_input")),
                options=len(options),
                select_type=select.get("type"),
            )
            if eligible:
                deadline = time.monotonic() + self._budget_ms / 1000.0
                return self._ctypes_search(obs_dict, options, deadline)
        except Exception:
            pass
        return None

    def _ensure_engine(self) -> bool:
        try:
            from cg.sim import Battle, lib  # type: ignore

            self._lib = lib
            # battle_ptr changes every battle_start — never cache across games.
            self._battle_ptr = Battle.battle_ptr
            return self._battle_ptr is not None
        except Exception:
            self._lib = None
            self._battle_ptr = None
            return False

    def _ctypes_search(self, obs_dict, options, deadline) -> list[int] | None:
        """Best-effort wrapper around cg search_*; returns None on failure."""
        if time.monotonic() >= deadline:
            self._audit_search("search_result", fired=False, reason="engine_or_budget")
            return None
        if not self._ensure_engine():
            self._audit_search("search_result", fired=False, reason="engine_or_budget")
            return None
        try:
            lib = self._lib
            ptr = self._battle_ptr
            if lib is None or ptr is None:
                self._audit_search("search_result", fired=False, reason="missing_engine_ptr")
                return None
            begin_input = obs_dict.get("search_begin_input", "")
            if not begin_input:
                self._audit_search("search_result", fired=False, reason="missing_begin_input")
                return None
            n_opts = len(options)
            if n_opts <= 0:
                self._audit_search("search_result", fired=False, reason="no_options")
                return None
            ctypes = __import__("ctypes")
            idx_arr = (ctypes.c_int * n_opts)(*range(n_opts))
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
                self._audit_search("search_result", fired=False, reason="search_begin_failed")
                return None
            handle = int(search_ptr, 16) if isinstance(search_ptr, str) else 0
            try:
                step = lib.SearchStep(ptr, handle, out_idx, 1)
                if step:
                    data = json.loads(step.decode()) if isinstance(step, bytes) else {}
                    pick = data.get("index", out_idx[0])
                    if isinstance(pick, int) and 0 <= pick < n_opts:
                        self._audit_search("search_result", fired=True, pick=pick, source="json")
                        return [pick]
                if 0 <= out_idx[0] < n_opts:
                    self._audit_search("search_result", fired=True, pick=out_idx[0], source="out_idx")
                    return [out_idx[0]]
            finally:
                lib.SearchEnd(ptr)
                if handle:
                    lib.SearchRelease(ptr, handle)
        except Exception:
            self._audit_search("search_result", fired=False, reason="exception")
            return None
        self._audit_search("search_result", fired=False, reason="no_pick")
        return None


def _blend_search_with_heuristic(
    search_pick: list[int],
    options: list,
    score_fn,
    blend: float,
) -> list[int]:
    """Soft-merge cg search pick with heuristic scores (AlphaZero-style prior mix).

    score_fn(option_index) -> float. Higher is better. blend=0 keeps search;
    blend=1 follows pure heuristic argmax among {search_pick, top heuristic}.
    """
    if blend <= 0.0 or not search_pick or len(search_pick) != 1:
        return search_pick
    n = len(options)
    if n <= 1:
        return search_pick
    s_idx = int(search_pick[0])
    if not (0 <= s_idx < n):
        return search_pick
    scores = [float(score_fn(i)) for i in range(n)]
    h_idx = max(range(n), key=lambda i: scores[i])
    if h_idx == s_idx:
        return search_pick
    # Map scores to [0,1] on the two candidates only; pick higher blended mass.
    s_sc, h_sc = scores[s_idx], scores[h_idx]
    lo, hi = min(s_sc, h_sc), max(s_sc, h_sc)
    span = (hi - lo) if hi > lo else 1.0
    s_n = (s_sc - lo) / span
    h_n = (h_sc - lo) / span
    # Search gets (1-blend) mass at its pick; heuristic contributes blend * softmax-ish.
    mass_s = (1.0 - blend) + blend * s_n
    mass_h = blend * h_n
    return [h_idx if mass_h > mass_s else s_idx]


class SearchScorer(_CgSearchMixin, _PrizeTrackerMixin, HeuristicScorer):
    """Heuristic baseline + optional cg search_* on promotion/switch picks."""

    def __init__(
        self,
        rng=None,
        budget_ms: float | None = None,
        deck_path: str | None = None,
        heuristic_blend: float | None = None,
    ) -> None:
        super().__init__(rng=rng)
        self._init_search(SEARCH_BUDGET_MS if budget_ms is None else budget_ms)
        self._init_prize_tracker(deck_path)
        self._active_select = None
        self._heuristic_blend = (
            SEARCH_HEURISTIC_BLEND if heuristic_blend is None else max(0.0, min(1.0, heuristic_blend))
        )

    def choose(self, obs_dict, select, current, options):
        self._update_prize_tracker(obs_dict)
        self._active_select = select
        if not options:
            return []
        picked = self._try_search(obs_dict, select, options)
        if picked is not None:
            if self._heuristic_blend > 0.0:
                def _score(i: int) -> float:
                    # Prefer card-id score when option is a card; else 0.
                    opt = options[i]
                    if isinstance(opt, dict) and "card" in opt:
                        cid = opt.get("card", {}).get("id") if isinstance(opt.get("card"), dict) else opt.get("id")
                        if cid is not None:
                            return float(self._card_id_score(int(cid), current))
                    return 0.0

                blended = _blend_search_with_heuristic(
                    picked, options, _score, self._heuristic_blend,
                )
                self._audit_search(
                    "heuristic_blend",
                    search=picked,
                    blended=blended,
                    blend=self._heuristic_blend,
                )
                return blended
            return picked
        return super().choose(obs_dict, select, current, options)

    def _card_id_score(self, card_id, current):
        base = super()._card_id_score(card_id, current)
        return self._prize_adjust_card_score(base, card_id, self._active_select)


class LucarioSearchScorer(_CgSearchMixin, _PrizeTrackerMixin):
    """Lucario meta MAIN + cg search_* on setup/switch/to-active picks."""

    def __init__(
        self,
        rng=None,
        deck_path: str | None = None,
        budget_ms: float | None = None,
        guard_top_k: int | None = None,
        heuristic_blend: float | None = None,
    ) -> None:
        from agent.lucario_policy import LucarioScorer

        path = deck_path
        self._lucario = LucarioScorer(rng=rng, deck_path=path)
        self._init_search(
            SEARCH_BUDGET_MS if budget_ms is None else budget_ms,
            search_contexts=LUCARIO_SEARCH_CONTEXTS,
        )
        self._init_prize_tracker(path)
        self._active_select = None
        self._guard_top_k = max(1, SEARCH_GUARD_TOP_K if guard_top_k is None else int(guard_top_k))
        self._heuristic_blend = (
            SEARCH_HEURISTIC_BLEND if heuristic_blend is None else max(0.0, min(1.0, heuristic_blend))
        )

    def choose(self, obs_dict, select, current, options):
        self._update_prize_tracker(obs_dict)
        self._active_select = select
        if not options:
            return []
        lucario_pick = self._lucario.choose(obs_dict, select, current, options)
        picked = self._try_search(obs_dict, select, options)
        if picked is None or len(picked) != 1:
            return lucario_pick
        ranked = self._lucario.rank_options(obs_dict, select, current, options)
        if not ranked:
            return lucario_pick
        if self._heuristic_blend > 0.0 and ranked:
            # Prior = Lucario rank (higher rank index penalty).
            rank_pos = {idx: pos for pos, idx in enumerate(ranked)}

            def _score(i: int) -> float:
                return -float(rank_pos.get(i, len(ranked)))

            picked = _blend_search_with_heuristic(
                picked, options, _score, self._heuristic_blend,
            )
        top_k = set(ranked[: min(self._guard_top_k, len(ranked))])
        if picked[0] in top_k:
            self._audit_search(
                "lucario_guard",
                accepted=True,
                pick=picked[0],
                top_k=sorted(top_k),
                guard_k=self._guard_top_k,
            )
            return picked
        self._audit_search(
            "lucario_guard",
            accepted=False,
            pick=picked[0],
            top_k=sorted(top_k),
            guard_k=self._guard_top_k,
        )
        return lucario_pick


# Crustle hybrid: RuleCore floor (decision prior already baked in) + shallow
# cg search on promote/switch/setup-active. Search accepted only if pick ∈
# Crustle decision-prior top-k (vs-ex wall, Boss non-ex, energy homes).
CRUSTLE_SEARCH_CONTEXTS = {
    CTX_TO_ACTIVE,
    CTX_SWITCH,
    CTX_SETUP_ACTIVE_POKEMON,
}


def _option_card_id(opt) -> int | None:
    """Best-effort card id from a select option (dict or engine object)."""
    if opt is None:
        return None
    try:
        if isinstance(opt, dict):
            card = opt.get("card")
            if isinstance(card, dict) and card.get("id") is not None:
                return int(card["id"])
            if opt.get("id") is not None and "card" not in opt:
                # Some payloads put card id at top level.
                try:
                    return int(opt["id"])
                except (TypeError, ValueError):
                    pass
            if opt.get("cardId") is not None:
                return int(opt["cardId"])
            return None
        card = getattr(opt, "card", None)
        if card is not None and getattr(card, "id", None) is not None:
            return int(card.id)
        cid = getattr(opt, "id", None)
        if cid is not None:
            return int(cid)
    except Exception:
        return None
    return None


def _option_is_opponent(opt, my_index: int | None) -> bool:
    if my_index is None:
        return False
    try:
        if isinstance(opt, dict):
            pidx = opt.get("playerIndex")
            if pidx is None:
                pidx = opt.get("player")
            return pidx is not None and int(pidx) != int(my_index)
        pidx = getattr(opt, "playerIndex", None)
        return pidx is not None and int(pidx) != int(my_index)
    except Exception:
        return False


class CrustleSearchScorer(_CgSearchMixin, _PrizeTrackerMixin):
    """RuleCore (Crustle levers) floor + cg search_* guarded by decision prior.

    Design (AlphaZero-style prior + shallow search, no core-loop rewrite):
      1. RuleCore always owns MAIN / energy / evolve (decision prior there).
      2. On TO_ACTIVE / SWITCH / SETUP_ACTIVE, run cg SearchBegin if available.
      3. Accept search only if pick is in Crustle decision-prior top-k
         (promote Crustle vs ex, Boss non-ex wall-breakers, etc.).
      4. Optional prior blend soft-merges search vs prior before the guard.
    """

    def __init__(
        self,
        rng=None,
        deck_path: str | None = None,
        budget_ms: float | None = None,
        guard_top_k: int | None = None,
        heuristic_blend: float | None = None,
    ) -> None:
        from agent.rule_core import RuleCoreScorer

        path = deck_path
        self._rule = RuleCoreScorer(rng=rng, deck_path=path)
        self._init_search(
            SEARCH_BUDGET_MS if budget_ms is None else budget_ms,
            search_contexts=CRUSTLE_SEARCH_CONTEXTS,
        )
        self._init_prize_tracker(path)
        self._active_select = None
        self._guard_top_k = max(1, SEARCH_GUARD_TOP_K if guard_top_k is None else int(guard_top_k))
        self._heuristic_blend = (
            SEARCH_HEURISTIC_BLEND if heuristic_blend is None else max(0.0, min(1.0, heuristic_blend))
        )
        self._deck_path = path

    def choose(self, obs_dict, select, current, options):
        self._update_prize_tracker(obs_dict)
        self._active_select = select
        if not options:
            return []
        rule_pick = self._rule.choose(obs_dict, select, current, options)
        picked = self._try_search(obs_dict, select, options)
        if picked is None or len(picked) != 1:
            return rule_pick
        ranked, scores = self._rank_by_decision_prior(obs_dict, select, current, options)
        if not ranked:
            return rule_pick
        if self._heuristic_blend > 0.0:
            score_map = {idx: sc for idx, sc in zip(ranked, scores)} if scores else {}

            def _score(i: int) -> float:
                if i in score_map:
                    return float(score_map[i])
                # Unknown → bottom.
                return -1e12

            picked = _blend_search_with_heuristic(
                picked, options, _score, self._heuristic_blend,
            )
        top_k = set(ranked[: min(self._guard_top_k, len(ranked))])
        if picked[0] in top_k:
            self._audit_search(
                "crustle_guard",
                accepted=True,
                pick=picked[0],
                top_k=sorted(top_k),
                guard_k=self._guard_top_k,
            )
            return picked
        self._audit_search(
            "crustle_guard",
            accepted=False,
            pick=picked[0],
            top_k=sorted(top_k),
            guard_k=self._guard_top_k,
        )
        return rule_pick

    def _rank_by_decision_prior(
        self, obs_dict, select, current, options,
    ) -> tuple[list[int], list[float]]:
        """Rank option indices by Crustle decision prior (high = better).

        Returns (indices_desc, scores_aligned_to_indices). Never raises.
        """
        try:
            from agent.crustle_levers import (
                decision_prior_card_score,
                decision_prior_boss_target,
                card_has_ability,
            )
        except Exception:
            return list(range(len(options))), [0.0] * len(options)

        context = ""
        if isinstance(select, dict):
            context = str(select.get("context") or "")
        else:
            context = str(getattr(select, "context", "") or "")
        ctx_l = context.lower()
        if "setup" in ctx_l:
            sel_ctx = "setup_active"
        elif "to_active" in ctx_l or ctx_l == "toactive":
            sel_ctx = "to_active"
        else:
            sel_ctx = "switch"

        turn = 1
        my_index = None
        try:
            if isinstance(current, dict):
                turn = int(current.get("turn") or 1)
                my_index = current.get("yourIndex")
                if my_index is None:
                    my_index = current.get("your_index")
            elif current is not None:
                turn = int(getattr(current, "turn", 1) or 1)
                my_index = getattr(current, "yourIndex", None)
        except Exception:
            turn = 1

        # Prefer typed obs for promote_score (ex flags); fall back to raw dict.
        obs_for_prior = obs_dict
        try:
            from cg.api import to_observation_class  # type: ignore

            obs_for_prior = to_observation_class(obs_dict)
        except Exception:
            obs_for_prior = obs_dict

        scored: list[tuple[int, float]] = []
        for i, opt in enumerate(options):
            cid = _option_card_id(opt)
            if cid is None:
                scored.append((i, -1e9))
                continue
            is_opp = _option_is_opponent(opt, my_index)
            try:
                if is_opp:
                    # Boss / gust: prefer non-ex wall-breakers.
                    is_ex = None
                    try:
                        if isinstance(opt, dict):
                            card = opt.get("card") or {}
                            if isinstance(card, dict):
                                is_ex = bool(card.get("ex") or card.get("megaEx"))
                        else:
                            card = getattr(opt, "card", None)
                            if card is not None:
                                is_ex = bool(
                                    getattr(card, "ex", False)
                                    or getattr(card, "megaEx", False)
                                )
                    except Exception:
                        is_ex = None
                    sc = decision_prior_boss_target(
                        cid,
                        is_ex=is_ex,
                        has_ability=card_has_ability(cid),
                    )
                else:
                    energies = 0
                    hp = 0
                    try:
                        if isinstance(opt, dict):
                            card = opt.get("card") or {}
                            if isinstance(card, dict):
                                energies = len(card.get("energies") or [])
                                hp = int(card.get("hp") or 0)
                        else:
                            card = getattr(opt, "card", None)
                            if card is not None:
                                energies = len(getattr(card, "energies", None) or [])
                                hp = int(getattr(card, "hp", 0) or 0)
                    except Exception:
                        energies, hp = 0, 0
                    sc = decision_prior_card_score(
                        cid,
                        obs_for_prior,
                        side="ours",
                        turn=turn,
                        select_context=sel_ctx,
                        energies=energies,
                        hp=hp,
                    )
            except Exception:
                sc = 0.0
            # Prize-deck safety (shared with SearchScorer).
            sc = self._prize_adjust_card_score(sc, cid, select if isinstance(select, dict) else self._active_select)
            scored.append((i, float(sc)))

        scored.sort(key=lambda t: t[1], reverse=True)
        indices = [i for i, _ in scored]
        scores = [s for _, s in scored]
        return indices, scores
