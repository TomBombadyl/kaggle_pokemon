#!/usr/bin/env python3
"""Collect decision-level (state, options, choice, outcome) data for Archaludon vs Iono.

Why this exists
---------------
The Iono matchup is the fleet's #1 bottleneck. Rule levers are exhausted
(``configs/iono_tomato_train.yaml``: rule ceiling ~32%, tomato hybrid ~50% pooled,
floor is 55%). Breaking it needs a *learned* re-ranker, and there was no
Archaludon learning path at all — only the Lucario MCTS trainer, which the iono
config explicitly forbids retraining for this gate.

This script is the data half of that path. It plays real gate games (same engine,
same opponent brain as ``scripts/gate_archaludon.py``) and logs, for every hero
decision, a fixed-width state feature vector plus per-option feature vectors and
which option the current rule agent actually picked. Games are labelled with the
final outcome, so the dump trains either

  * a value head (state -> P(win)), or
  * a decision prior / re-ranker (state+option -> advantage),

which can then be wired in as a new ``ARCH_IONO_LEVER`` branch.

The hero agent is *not* modified: we wrap the brain callable, so collection is
observation-only and cannot change gate behaviour.

Usage
-----
  python scripts/collect_iono_decisions.py --games 200 --opponent real_iono
  python scripts/collect_iono_decisions.py --games 2000 --out episodes/iono_bc

Output: ``<out>/iono_decisions_<tag>.jsonl`` (one JSON object per game) plus a
``.meta.json`` summary. Shard-safe: honours ``PTCG_SHARD`` for the filename.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
for p in (str(ENGINE_DIR), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from cg import game  # noqa: E402
from cg.api import (  # noqa: E402
    AreaType,
    CardType,
    OptionType,
    SelectContext,
    all_card_data,
    to_observation_class,
)
from cg.sim import Battle, lib  # noqa: E402

from eval.field_registry import load_registry, opponent_meta, resolve_deck_path  # noqa: E402
from eval.harness import (  # noqa: E402
    DEFAULT_ARCHALUDON_DECK,
    MAX_STEPS,
    get_opponent_brain,
    load_deck,
    make_archaludon_brain,
)

# Iono-relevant card ids, mirrored from agent/archaludon_agent.py so the feature
# layout stays readable without importing the whole agent module namespace.
DURALUDON = 169
ARCHALUDON_EX = 190
CINDERACE = 666
RELICANTH = 57
IONO_THREATS = {269, 271}  # Bellibolt ex / Kilowattrel

SCHEMA_VERSION = 2
OPTION_TYPES = list(OptionType)
OPTION_TYPE_INDEX = {t: i for i, t in enumerate(OPTION_TYPES)}
CARD_DB = {c.cardId: c for c in all_card_data()}

STATE_FEATURES = [
    "turn", "my_prize", "opp_prize", "hand", "deck", "discard",
    "my_bench", "opp_bench",
    "act_hp", "act_dmg", "act_energy", "act_is_dura", "act_is_arch",
    "act_is_cinder", "act_is_relic", "act_is_none",
    "opp_hp", "opp_dmg", "opp_energy", "opp_is_ex", "opp_is_threat",
    "ctx_main", "ctx_setup", "ctx_switch", "n_options",
]
OPTION_FEATURES = [
    f"type_{t.name.lower()}" for t in OPTION_TYPES
] + ["card_id", "is_pokemon_card", "is_energy_card", "targets_opponent"]


def _i(x, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _pokemon_features(pkm) -> list[float]:
    """[hp_remaining, damage, energy_count] for a board slot (zeros if empty)."""
    if pkm is None:
        return [0.0, 0.0, 0.0]
    hp = _i(getattr(pkm, "hp", 0))
    max_hp = _i(getattr(pkm, "maxHp", hp), hp)
    return [float(hp), float(max(0, max_hp - hp)),
            float(len(getattr(pkm, "energies", None) or []))]


def _side(obs, mine: bool):
    """Return the board side object for hero (mine=True) or opponent."""
    state = getattr(obs, "current", None)
    players = getattr(state, "players", None) or []
    yi = _i(getattr(state, "yourIndex", 0))
    index = yi if mine else 1 - yi
    return players[index] if 0 <= index < len(players) else None


def _active(side):
    active = getattr(side, "active", None) or []
    return active[0] if active else None


def _get_card(obs, area, index, player_index):
    if area is None or index is None or obs.current is None:
        return None
    players = obs.current.players or []
    if not (0 <= player_index < len(players)):
        return None
    ps = players[player_index]
    if area == AreaType.DECK and obs.select and obs.select.deck is not None:
        cards = obs.select.deck
    elif area == AreaType.HAND:
        cards = ps.hand or []
    elif area == AreaType.DISCARD:
        cards = ps.discard or []
    elif area == AreaType.ACTIVE:
        cards = ps.active or []
    elif area == AreaType.BENCH:
        cards = ps.bench or []
    elif area == AreaType.PRIZE:
        cards = ps.prize or []
    elif area == AreaType.STADIUM:
        cards = obs.current.stadium or []
    elif area == AreaType.LOOKING:
        cards = obs.current.looking or []
    else:
        return None
    return cards[index] if 0 <= index < len(cards) else None


def _option_card(obs, opt):
    yi = _i(getattr(obs.current, "yourIndex", 0))
    pi = opt.playerIndex if opt.playerIndex is not None else yi
    if opt.type == OptionType.PLAY:
        return _get_card(obs, AreaType.HAND, opt.index, pi)
    card = _get_card(obs, opt.area, opt.index, pi)
    if card is not None:
        return card
    card_id = _i(getattr(opt, "cardId", 0))
    return type("CardRef", (), {"id": card_id})() if card_id else None


def state_vector(obs) -> list[float]:
    """Fixed-width state features. Never raises; unknown fields become 0."""
    me = _side(obs, True)
    opp = _side(obs, False)

    act = _active(me) if me is not None else None
    oact = _active(opp) if opp is not None else None
    act_hp, act_dmg, act_en = _pokemon_features(act)
    opp_hp, opp_dmg, opp_en = _pokemon_features(oact)

    act_id = _i(getattr(act, "id", 0)) if act is not None else 0
    opp_id = _i(getattr(oact, "id", 0)) if oact is not None else 0

    ctx = getattr(getattr(obs, "select", None), "context", None)
    ctx_value = _i(ctx, -1)
    n_opts = len(getattr(getattr(obs, "select", None), "option", None) or [])

    return [
        float(_i(getattr(getattr(obs, "current", None), "turn", 0))),
        float(len(getattr(me, "prize", None) or [])) if me is not None else 0.0,
        float(len(getattr(opp, "prize", None) or [])) if opp is not None else 0.0,
        float(_i(getattr(me, "handCount", 0))) if me is not None else 0.0,
        float(_i(getattr(me, "deckCount", 0))) if me is not None else 0.0,
        float(len(getattr(me, "discard", None) or [])) if me is not None else 0.0,
        float(len(getattr(me, "bench", None) or [])) if me is not None else 0.0,
        float(len(getattr(opp, "bench", None) or [])) if opp is not None else 0.0,
        act_hp, act_dmg, act_en,
        float(act_id == DURALUDON),
        float(act_id == ARCHALUDON_EX),
        float(act_id == CINDERACE),
        float(act_id == RELICANTH),
        float(act is None),
        opp_hp, opp_dmg, opp_en,
        float(bool(getattr(CARD_DB.get(opp_id), "ex", False) or
                   getattr(CARD_DB.get(opp_id), "megaEx", False))) if oact is not None else 0.0,
        float(opp_id in IONO_THREATS),
        float(ctx_value == int(SelectContext.MAIN)),
        float(ctx_value in (int(SelectContext.SETUP_ACTIVE_POKEMON),
                            int(SelectContext.SETUP_BENCH_POKEMON))),
        float(ctx_value in (int(SelectContext.SWITCH),
                            int(SelectContext.TO_ACTIVE),
                            int(SelectContext.TO_BENCH))),
        float(n_opts),
    ]


def option_vector(obs, opt) -> list[float]:
    """Fixed-width per-option features."""
    vec = [0.0] * len(OPTION_TYPES)
    otype = getattr(opt, "type", None)
    idx = OPTION_TYPE_INDEX.get(otype)
    if idx is not None:
        vec[idx] = 1.0

    card = _option_card(obs, opt)
    card_id = _i(getattr(card, "id", 0)) if card is not None else 0
    card_data = CARD_DB.get(card_id)
    card_type = getattr(card_data, "cardType", None)
    is_pkm = float(card_type == CardType.POKEMON)
    is_energy = float(card_type in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY))

    targets_opp = 0.0
    try:
        yi = _i(getattr(obs.current, "yourIndex", 0))
        targets_opp = float(opt.playerIndex is not None and opt.playerIndex != yi)
    except Exception:
        pass

    return vec + [float(card_id), is_pkm, is_energy, targets_opp]


class _Recorder:
    """Wraps the hero brain and records every decision it makes.

    With ``explore_eps > 0`` the recorder additionally *deviates*: on a fraction
    eps of single-selection decisions that have more than one legal option, the
    rule agent's pick is replaced by a uniformly random legal option and the game
    plays on from there. This is the only way to identify the value of the
    options the rule agent never takes -- chosen-action-only logs observe Q(s,a)
    only at a = pi(s), so no offline model can rank the alternatives (see
    fleet/state/gputrain_STATE.md, round-1 `q` objective REJECT).

    ``explore_eps = 0`` (the default) is byte-identical to observation-only
    collection, so the autopilot's dataset is unaffected.
    """

    def __init__(self, brain, explore_eps: float = 0.0, rng: random.Random | None = None):
        self._brain = brain
        self._eps = float(explore_eps)
        self._rng = rng or random.Random()
        self.decisions: list[dict] = []
        self.n_explored = 0
        self.n_eligible = 0

    def __call__(self, obs_dict):
        picked = self._brain(obs_dict)
        explored = 0
        rule_pick: list = []
        try:
            obs = to_observation_class(obs_dict)
            select = getattr(obs, "select", None)
            options = list(getattr(select, "option", None) or []) if select else []
            if options:
                pick_list = list(picked) if isinstance(picked, list) else []
                # Build the record before deviating, so a feature-extraction
                # failure can never leave an unlogged deviation in the game.
                rec = {
                    "s": [round(v, 3) for v in state_vector(obs)],
                    "o": [[round(v, 3) for v in option_vector(obs, o)] for o in options],
                    "pick": pick_list,
                }
                # Only deviate on single-selection decisions with a real choice.
                # Any single index into the engine's own option list is legal by
                # construction, so the swap cannot produce an illegal action.
                if len(pick_list) == 1 and len(options) > 1:
                    self.n_eligible += 1
                    if self._eps > 0.0 and self._rng.random() < self._eps:
                        alt = self._rng.randrange(len(options))
                        if alt != pick_list[0]:
                            rule_pick = pick_list
                            explored = 1
                            self.n_explored += 1
                            rec["pick"] = [alt]
                            rec["e"] = 1
                            rec["rp"] = rule_pick
                            picked = [alt]
                self.decisions.append(rec)
        except Exception:
            pass  # collection must never perturb the game
        return picked

    def reset(self) -> list[dict]:
        out = self.decisions
        self.decisions = []
        return out


def _select_player() -> int:
    return lib.GetBattleData(Battle.battle_ptr).selectPlayer


def play_one(deck_a, deck_b, brain_a, brain_b) -> str:
    """Copy of eval.harness.run_match — inlined so we own the game boundary."""
    obs, start = game.battle_start(deck_a, deck_b)
    if obs is None:
        raise RuntimeError(f"battle_start failed: err={getattr(start, 'errorType', '?')}")
    policies = (brain_a, brain_b)
    try:
        for _ in range(MAX_STEPS):
            cur = obs["current"]
            if cur is not None and cur.get("result", -1) != -1:
                r = cur["result"]
                return {0: "a", 1: "b", 2: "draw"}.get(r, "unfinished")
            if obs["select"] is None:
                return "unfinished"
            obs = game.battle_select(policies[_select_player()](obs))
        return "unfinished"
    finally:
        game.battle_finish()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--opponent", default="real_iono")
    ap.add_argument("--out", default="episodes/iono_bc_v2")
    ap.add_argument("--hero-deck", default=None)
    ap.add_argument("--losses-only", action="store_true",
                    help="Only keep lost games (oversample the failure mode)")
    ap.add_argument("--max-decisions", type=int, default=0,
                    help="Stop early once this many decisions are logged (0 = no cap)")
    ap.add_argument("--explore-eps", type=float, default=0.0,
                    help="Deviate to a uniformly random legal option on this "
                         "fraction of single-selection decisions (0 = pure "
                         "observation, identical to the legacy collector). "
                         "Needed to identify the value of unchosen options.")
    ap.add_argument("--explore-seed", type=int, default=None,
                    help="Seed for the exploration RNG (default: entropy)")
    args = ap.parse_args()
    if not 0.0 <= args.explore_eps <= 1.0:
        print("ERROR: --explore-eps must be in [0,1]", file=sys.stderr)
        return 1

    shard = os.environ.get("PTCG_SHARD", "0")
    lever = os.environ.get("ARCH_IONO_LEVER", "tomato")

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    eps_tag = f"_eps{args.explore_eps:g}" if args.explore_eps > 0 else ""
    # PID is part of the tag because several shard fleets can start inside the
    # same wall-clock second; without it two concurrent shards with the same
    # PTCG_SHARD open the same path with "w" and silently clobber each other.
    tag = (f"{args.opponent}_{lever}{eps_tag}_s{shard}_"
           f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_p{os.getpid()}")
    out_path = out_dir / f"iono_decisions_{tag}.jsonl"

    hero_deck_path = args.hero_deck or DEFAULT_ARCHALUDON_DECK
    hero_deck = load_deck(hero_deck_path)
    brain = make_archaludon_brain(hero_deck_path)
    seed = args.explore_seed
    if seed is None:
        seed = int.from_bytes(os.urandom(8), "little")
    rec = _Recorder(brain, explore_eps=args.explore_eps, rng=random.Random(seed))

    reg = load_registry()
    opponent_meta(args.opponent, reg)  # fail fast on unknown opponent
    deck_path = resolve_deck_path(args.opponent, reg)
    if not deck_path.exists():
        print(f"ERROR: opponent deck not found: {deck_path}", file=sys.stderr)
        return 1
    deck_o = load_deck(deck_path)
    opp_brain, opp_label = get_opponent_brain(args.opponent, registry=reg)

    wins = losses = other = 0
    n_decisions = 0
    n_games_written = 0
    t0 = time.time()

    with out_path.open("w", encoding="utf-8") as f:
        for i in range(args.games):
            rec.reset()
            # Seat swap on odd games, matching eval.harness.gate_vs_opponent so
            # the collected distribution matches the gate we are measured on.
            hero_first = (i % 2 == 0)
            if hero_first:
                outcome = play_one(hero_deck, deck_o, rec, opp_brain)
                hero_won = outcome == "a"
                hero_lost = outcome == "b"
            else:
                outcome = play_one(deck_o, hero_deck, opp_brain, rec)
                hero_won = outcome == "b"
                hero_lost = outcome == "a"

            if hero_won:
                wins += 1
            elif hero_lost:
                losses += 1
            else:
                other += 1

            decisions = rec.reset()
            if args.losses_only and not hero_lost:
                continue
            if not decisions:
                continue
            g_explored = sum(1 for d in decisions if d.get("e"))
            f.write(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "game": i,
                "hero_first": hero_first,
                "outcome": outcome,
                "label": 1 if hero_won else (0 if hero_lost else -1),
                "n_decisions": len(decisions),
                "n_explored": g_explored,
                "explore_eps": args.explore_eps,
                "decisions": decisions,
            }, ensure_ascii=False) + "\n")
            n_games_written += 1
            n_decisions += len(decisions)

            if i and i % 20 == 0:
                n = wins + losses
                wr = 100.0 * wins / n if n else 0.0
                print(f"[collect] {i}/{args.games} wr={wr:.1f}% "
                      f"decisions={n_decisions} {time.time() - t0:.0f}s", flush=True)
            if args.max_decisions and n_decisions >= args.max_decisions:
                print(f"[collect] decision cap {args.max_decisions} reached at game {i}", flush=True)
                break

    n = wins + losses
    wr = 100.0 * wins / n if n else 0.0
    meta = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "opponent": args.opponent,
        "opponent_brain": opp_label,
        "lever": lever,
        "shard": shard,
        "hero_deck": str(hero_deck_path),
        "games": wins + losses + other,
        "wins": wins, "losses": losses, "other": other,
        "wr_pct": round(wr, 2),
        "games_written": n_games_written,
        "decisions": n_decisions,
        "losses_only": args.losses_only,
        "explore_eps": args.explore_eps,
        "explore_seed": seed,
        "explore_eligible": rec.n_eligible,
        "explore_deviations": rec.n_explored,
        "schema_version": SCHEMA_VERSION,
        "state_features": STATE_FEATURES,
        "option_features": OPTION_FEATURES,
        "elapsed_s": round(time.time() - t0, 1),
        "path": str(out_path),
    }
    (out_path.with_suffix(".meta.json")).write_text(
        json.dumps(meta, indent=2), encoding="utf-8")

    # Shard-Gate.ps1 pools on this line, so a collection run doubles as a gate.
    print(f"\n{args.opponent} (gated) {wr:.1f}%  n={n}")
    print(f"OVERALL (gated) {wr:.1f}%")
    print(f"[collect] wrote {n_games_written} games / {n_decisions} decisions -> {out_path}")
    print(f"[collect] W={wins} L={losses} other={other} "
          f"explore_eps={args.explore_eps:g} eligible={rec.n_eligible} "
          f"deviations={rec.n_explored}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
