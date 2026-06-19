"""Numpy feature extractor for the cabt PTCG observation interface.

Pure numpy + stdlib ONLY. This module is on the *submission* code path (a future
learned policy reads these features at inference time), so it must never import
torch or any non-stdlib package beyond numpy. All field access mirrors the
defensive `_get` style in agent.py: missing/None fields degrade to neutral
zeros, never raise.

Two extractors:

    state_features(obs_dict)          -> np.ndarray, shape (STATE_DIM,)
    option_features(obs_dict, option) -> np.ndarray, shape (OPTION_DIM,)

`state_features` summarizes the whole board from *our* perspective. It is
constant-length regardless of how many Pokemon are in play (bench slots are
aggregated). `option_features` produces one fixed-length vector per legal
option, so a pointer-style policy can score each option independently and a
variable number of options is handled natively (mask-friendly: build the matrix
by stacking option_features over select["option"]).

All values are floats. Counts/HP are scaled to roughly O(1) so that an unscaled
linear/MLP head behaves reasonably; the exact scales are part of FEATURE_VERSION
and must not change without bumping it (and any trained weights).

================================ STATE LAYOUT ================================
Index : meaning (all from our perspective unless noted)
  0  : turn count            / 20
  1  : we are first player    (1.0 / 0.0; 0.5 if unknown)
  2  : we are second player   (1.0 / 0.0; 0.5 if unknown)
  3  : our prize remaining    / 6
  4  : opp prize remaining    / 6
  5  : prize differential (opp - our) / 6   (positive = we are ahead)
  6  : our deck count          / 60
  7  : opp deck count          / 60
  8  : our hand count          / 10
  9  : opp hand count          / 10
 10  : our bench count         / 5
 11  : opp bench count         / 5
 12  : supporter already used this turn (1/0)
 13  : energy already attached this turn (1/0)
 -- our active --
 14  : has active Pokemon (1/0)
 15  : active HP fraction (hp / maxHp)
 16  : active HP             / 350
 17  : active energy count   / 4
 18  : active is ex/megaEx role (1/0, best-effort from card data)
 19  : active any status condition (poison/burn/sleep/paralyze/confuse) (1/0)
 -- opp active --
 20  : opp has active Pokemon (1/0)
 21  : opp active HP fraction
 22  : opp active HP         / 350
 23  : opp active energy count / 4
 24  : opp active is ex/megaEx role (1/0)
 25  : opp active any status condition (1/0)
 -- our bench aggregate --
 26  : our bench total energy / 10
 27  : our bench max HP fraction (healthiest benched mon)
 28  : our bench count of ex/megaEx / 5
 -- opp bench aggregate --
 29  : opp bench total energy / 10
 30  : opp bench max HP fraction
 31  : opp bench count of ex/megaEx / 5
STATE_DIM = 32

================================ OPTION LAYOUT ==============================
Index 0..N_OPT_TYPES-1 : one-hot of OptionType (NUMBER..SPECIAL_CONDITION, 17)
Then:
  +0 : has a target area (1/0)
  +1 : target is our ACTIVE area (1/0)
  +2 : target is BENCH area (1/0)
  +3 : target is HAND area (1/0)
  +4 : target is DECK area (1/0)
  +5 : target is DISCARD area (1/0)
  +6 : target is opponent-owned (1/0; best-effort via playerIndex)
  +7 : target Pokemon HP fraction (0 if not a Pokemon target)
  +8 : target Pokemon HP            / 350
  +9 : target Pokemon energy count  / 4
 +10 : target is ex/megaEx role (1/0)
 +11 : option attack damage         / 300 (ATTACK options; else 0)
 +12 : attack would KO opp active (1/0, best-effort)
 +13 : NUMBER option value          / 10 (COUNT options; else 0)
 +14 : energy fit: remainEnergyCost satisfied / progressed (0..1; ENERGY ctx)
 +15 : option references a card with known role bonus (normalized 0..1)
OPTION_DIM = N_OPT_TYPES + 16 = 33
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Bump whenever the vector layout, scales, or semantics change. Any trained
# weights are tied to a specific FEATURE_VERSION.
FEATURE_VERSION = 1

# --- OptionType IDs (mirrors agent.agent; kept local to avoid import cycles) --
OPT_NUMBER, OPT_YES, OPT_NO, OPT_CARD = 0, 1, 2, 3
OPT_TOOL_CARD, OPT_ENERGY_CARD, OPT_ENERGY = 4, 5, 6
OPT_PLAY, OPT_ATTACH, OPT_EVOLVE, OPT_ABILITY = 7, 8, 9, 10
OPT_DISCARD, OPT_RETREAT, OPT_ATTACK, OPT_END = 11, 12, 13, 14
OPT_SKILL, OPT_SPECIAL_CONDITION = 15, 16
N_OPT_TYPES = 17  # OptionType ids 0..16 inclusive

# AreaType IDs (see data/CABT_API.md).
AREA_DECK, AREA_HAND, AREA_DISCARD = 1, 2, 3
AREA_ACTIVE, AREA_BENCH, AREA_PRIZE = 4, 5, 6
AREA_LOOKING = 12

STATE_DIM = 32
OPTION_DIM = N_OPT_TYPES + 16  # 33

# Normalization scales (part of FEATURE_VERSION).
_HP_SCALE = 350.0
_DMG_SCALE = 300.0
_ENERGY_SLOTS = 4.0
_BENCH_MAX = 5.0
_DECK_SCALE = 60.0
_HAND_SCALE = 10.0
_PRIZE_SCALE = 6.0
_TURN_SCALE = 20.0
_BENCH_ENERGY_SCALE = 10.0
_NUMBER_SCALE = 10.0

_STATUS_FLAGS = ("poisoned", "burned", "asleep", "paralyzed", "confused")


def _get(obj: Any, key: str, default=None):
    """Defensive accessor tolerating dict or attribute-style objects (or None)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _num(value, default=0.0) -> float:
    """Coerce to float, mapping None/garbage to a default rather than raising."""
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


# Optional card-data lookups. These are best-effort: in the Kaggle submission the
# cg engine is importable and gives ex/megaEx flags; offline they simply return
# None and the corresponding features stay 0. We cache like agent.agent does.
_CARD_DATA: "dict[int, Any] | None" = None


def _card_data(card_id):
    global _CARD_DATA
    if _CARD_DATA is None:
        _CARD_DATA = {}
        try:
            from cg.api import all_card_data  # type: ignore

            _CARD_DATA = {c.cardId: c for c in all_card_data()}
        except Exception:
            _CARD_DATA = {}
    return _CARD_DATA.get(card_id)


def _is_ex_role(card_id) -> float:
    """1.0 if the card is an ex/megaEx (best-effort), else 0.0."""
    if not card_id:
        return 0.0
    card = _card_data(card_id)
    if card is None:
        return 0.0
    if bool(_get(card, "megaEx", False)) or bool(_get(card, "ex", False)):
        return 1.0
    return 0.0


def _energy_count(pokemon) -> float:
    energies = _get(pokemon, "energies", []) or []
    try:
        return float(len(energies))
    except TypeError:
        return 0.0


def _has_status(pokemon) -> float:
    for flag in _STATUS_FLAGS:
        if bool(_get(pokemon, flag, False)):
            return 1.0
    return 0.0


def _hp_fraction(pokemon) -> float:
    hp = _num(_get(pokemon, "hp", 0))
    max_hp = _num(_get(pokemon, "maxHp", hp))
    if max_hp <= 0:
        return 0.0
    return max(0.0, min(1.0, hp / max_hp))


def _players(current):
    return _get(current, "players", []) or []


def _player_indices(current):
    """Return (your_index, opp_index), defaulting to (0, 1)."""
    your = int(_num(_get(current, "yourIndex", 0)))
    if your not in (0, 1):
        your = 0
    return your, 1 - your


def _player_at(current, idx):
    players = _players(current)
    if 0 <= idx < len(players):
        return players[idx] or {}
    return {}


def _active_of(player):
    active = _get(player, "active", []) or []
    return active[0] if active else None


def state_features(obs_dict) -> np.ndarray:
    """Fixed-length board summary from our perspective. Shape (STATE_DIM,).

    Robust to deck-selection observations (current is None) and partial states:
    any missing field maps to a neutral value. Never raises on well-typed dicts.
    """
    vec = np.zeros(STATE_DIM, dtype=np.float32)
    current = _get(obs_dict, "current") or {}

    your_idx, opp_idx = _player_indices(current)
    me = _player_at(current, your_idx)
    opp = _player_at(current, opp_idx)

    vec[0] = _num(_get(current, "turn", 0)) / _TURN_SCALE

    first = _get(current, "first", None)
    if first is None:
        first = _get(current, "isFirst", None)
    if first is None:
        vec[1] = 0.5
        vec[2] = 0.5
    else:
        # `first` may be a bool or a player index. Treat truthy/our-index as first.
        is_first = bool(first) if isinstance(first, bool) else (int(_num(first)) == your_idx)
        vec[1] = 1.0 if is_first else 0.0
        vec[2] = 0.0 if is_first else 1.0

    our_prize = _prize_remaining(me)
    opp_prize = _prize_remaining(opp)
    vec[3] = our_prize / _PRIZE_SCALE
    vec[4] = opp_prize / _PRIZE_SCALE
    vec[5] = (opp_prize - our_prize) / _PRIZE_SCALE

    vec[6] = _num(_get(me, "deckCount", 0)) / _DECK_SCALE
    vec[7] = _num(_get(opp, "deckCount", 0)) / _DECK_SCALE
    vec[8] = _hand_count(me) / _HAND_SCALE
    vec[9] = _hand_count(opp) / _HAND_SCALE

    our_bench = _get(me, "bench", []) or []
    opp_bench = _get(opp, "bench", []) or []
    vec[10] = len(our_bench) / _BENCH_MAX
    vec[11] = len(opp_bench) / _BENCH_MAX

    vec[12] = 1.0 if bool(_get(current, "supporterUsed", False)) else 0.0
    vec[13] = 1.0 if bool(_get(current, "energyAttached", False)) else 0.0

    me_active = _active_of(me)
    if me_active is not None:
        vec[14] = 1.0
        vec[15] = _hp_fraction(me_active)
        vec[16] = _num(_get(me_active, "hp", 0)) / _HP_SCALE
        vec[17] = _energy_count(me_active) / _ENERGY_SLOTS
        vec[18] = _is_ex_role(_get(me_active, "id", 0) or 0)
        vec[19] = _has_status(me_active)

    opp_active = _active_of(opp)
    if opp_active is not None:
        vec[20] = 1.0
        vec[21] = _hp_fraction(opp_active)
        vec[22] = _num(_get(opp_active, "hp", 0)) / _HP_SCALE
        vec[23] = _energy_count(opp_active) / _ENERGY_SLOTS
        vec[24] = _is_ex_role(_get(opp_active, "id", 0) or 0)
        vec[25] = _has_status(opp_active)

    vec[26], vec[27], vec[28] = _bench_aggregate(our_bench)
    vec[29], vec[30], vec[31] = _bench_aggregate(opp_bench)

    return vec


def _prize_remaining(player) -> float:
    """Count face-up + face-down prize cards still in the prize area."""
    prize = _get(player, "prize", None)
    if prize is None:
        # Some observations expose only a count.
        return _num(_get(player, "prizeCount", 0))
    try:
        return float(len(prize))
    except TypeError:
        return 0.0


def _hand_count(player) -> float:
    hand = _get(player, "hand", None)
    if hand is not None:
        try:
            return float(len(hand))
        except TypeError:
            pass
    return _num(_get(player, "handCount", 0))


def _bench_aggregate(bench):
    """(total_energy/scale, max_hp_fraction, ex_count/benchmax) over a bench."""
    total_energy = 0.0
    max_hp_frac = 0.0
    ex_count = 0.0
    for mon in bench or []:
        if mon is None:
            continue
        total_energy += _energy_count(mon)
        max_hp_frac = max(max_hp_frac, _hp_fraction(mon))
        ex_count += _is_ex_role(_get(mon, "id", 0) or 0)
    return (
        min(1.0, total_energy / _BENCH_ENERGY_SCALE),
        max_hp_frac,
        min(1.0, ex_count / _BENCH_MAX),
    )


def option_features(obs_dict, option) -> np.ndarray:
    """Fixed-length per-option vector. Shape (OPTION_DIM,).

    Designed for pointer-style scoring: stack this over every option in
    select["option"] to get an (n_options, OPTION_DIM) matrix that a masked
    policy head can score row-wise. Robust to missing fields.
    """
    vec = np.zeros(OPTION_DIM, dtype=np.float32)
    current = _get(obs_dict, "current") or {}
    select = _get(obs_dict, "select") or {}

    opt_type = _get(option, "type", None)
    if isinstance(opt_type, int) and 0 <= opt_type < N_OPT_TYPES:
        vec[opt_type] = 1.0

    base = N_OPT_TYPES
    area = _get(option, "area", None)
    if area is not None:
        vec[base + 0] = 1.0
        vec[base + 1] = 1.0 if area == AREA_ACTIVE else 0.0
        vec[base + 2] = 1.0 if area == AREA_BENCH else 0.0
        vec[base + 3] = 1.0 if area == AREA_HAND else 0.0
        vec[base + 4] = 1.0 if area == AREA_DECK else 0.0
        vec[base + 5] = 1.0 if area == AREA_DISCARD else 0.0

    your_idx, _opp_idx = _player_indices(current)
    player_index = _get(option, "playerIndex", None)
    if player_index is not None and int(_num(player_index)) != your_idx:
        vec[base + 6] = 1.0

    pokemon = _target_pokemon(option, current)
    if pokemon is not None:
        vec[base + 7] = _hp_fraction(pokemon)
        vec[base + 8] = _num(_get(pokemon, "hp", 0)) / _HP_SCALE
        vec[base + 9] = _energy_count(pokemon) / _ENERGY_SLOTS
        vec[base + 10] = _is_ex_role(_get(pokemon, "id", 0) or 0)

    if opt_type == OPT_ATTACK:
        attack = _attack_data(_get(option, "attackId", 0) or 0)
        damage = _num(_get(attack, "damage", 0)) if attack is not None else 0.0
        vec[base + 11] = min(1.0, damage / _DMG_SCALE)
        opp_active = _opponent_active(current)
        if opp_active is not None and damage > 0:
            opp_hp = _num(_get(opp_active, "hp", 0))
            if opp_hp and damage >= opp_hp:
                vec[base + 12] = 1.0

    if opt_type == OPT_NUMBER:
        vec[base + 13] = min(1.0, _num(_get(option, "number", 0)) / _NUMBER_SCALE)

    remain_cost = _get(select, "remainEnergyCost", None)
    if remain_cost is not None:
        rc = _num(remain_cost)
        # Lower remaining cost => closer to fitting. Map 0 cost -> 1.0.
        vec[base + 14] = 1.0 / (1.0 + max(0.0, rc))

    card_id = _option_card_id(option, current, select)
    vec[base + 15] = _role_norm(card_id)

    return vec


# --- option target / card resolution (mirrors agent.agent, numpy-free) -------

_ATTACK_DATA: "dict[int, Any] | None" = None


def _attack_data(attack_id):
    global _ATTACK_DATA
    if _ATTACK_DATA is None:
        _ATTACK_DATA = {}
        try:
            from cg.api import all_attack  # type: ignore

            _ATTACK_DATA = {a.attackId: a for a in all_attack()}
        except Exception:
            _ATTACK_DATA = {}
    return _ATTACK_DATA.get(attack_id)


def _opponent_active(current):
    your_idx, opp_idx = _player_indices(current)
    return _active_of(_player_at(current, opp_idx))


def _target_pokemon(option, current):
    """Resolve the in-play Pokemon an option targets, if any (ACTIVE/BENCH)."""
    area = _get(option, "area", None)
    if area not in (AREA_ACTIVE, AREA_BENCH):
        return None
    index = int(_num(_get(option, "index", 0)))
    your_idx, _opp = _player_indices(current)
    player_index = _get(option, "playerIndex", None)
    pidx = your_idx if player_index is None else int(_num(player_index))
    player = _player_at(current, pidx)
    if area == AREA_ACTIVE:
        active = _get(player, "active", []) or []
        return active[index] if 0 <= index < len(active) else None
    bench = _get(player, "bench", []) or []
    return bench[index] if 0 <= index < len(bench) else None


def _option_card_id(option, current, select):
    """Best-effort card id referenced by an option (for role lookup)."""
    direct = _get(option, "cardId", None)
    if direct:
        return int(_num(direct))
    pokemon = _target_pokemon(option, current)
    if pokemon is not None:
        return int(_num(_get(pokemon, "id", 0)))
    area = _get(option, "area", None)
    index = int(_num(_get(option, "index", 0)))
    if area == AREA_LOOKING:
        looking = _get(current, "looking", []) or []
        card = looking[index] if 0 <= index < len(looking) else None
        return int(_num(_get(card, "id", 0)))
    if area == AREA_DECK:
        deck = _get(select, "deck", []) or []
        card = deck[index] if 0 <= index < len(deck) else None
        return int(_num(_get(card, "id", 0)))
    if area == AREA_HAND:
        your_idx, _opp = _player_indices(current)
        hand = _get(_player_at(current, your_idx), "hand", []) or []
        card = hand[index] if 0 <= index < len(hand) else None
        return int(_num(_get(card, "id", 0)))
    return 0


def _role_norm(card_id) -> float:
    """Normalized role signal in [0,1]: megaEx=1.0, ex=0.66, else 0."""
    if not card_id:
        return 0.0
    card = _card_data(card_id)
    if card is None:
        return 0.0
    if bool(_get(card, "megaEx", False)):
        return 1.0
    if bool(_get(card, "ex", False)):
        return 0.66
    return 0.0


def options_matrix(obs_dict) -> np.ndarray:
    """Stack option_features over every legal option. Shape (n_options, OPTION_DIM).

    Returns an empty (0, OPTION_DIM) array when there are no options (e.g. the
    deck-selection phase or an empty option list).
    """
    select = _get(obs_dict, "select") or {}
    options = _get(select, "option", []) or []
    if not options:
        return np.zeros((0, OPTION_DIM), dtype=np.float32)
    return np.stack([option_features(obs_dict, opt) for opt in options])


if __name__ == "__main__":
    # Self-check: build features from a synthetic deck-selection obs and a
    # synthetic MAIN obs without crashing. Pure numpy/stdlib, no engine needed.
    deck_obs = {"logs": [], "current": None, "select": None}
    sv = state_features(deck_obs)
    assert sv.shape == (STATE_DIM,), sv.shape
    assert np.all(np.isfinite(sv)), "deck-phase state vector has non-finite values"

    main_obs = {
        "logs": [],
        "current": {
            "turn": 3,
            "first": True,
            "yourIndex": 0,
            "supporterUsed": False,
            "energyAttached": False,
            "players": [
                {
                    "deckCount": 40,
                    "prize": [None, None, None, None, None, None],
                    "hand": [{"id": 721}, {"id": 3}],
                    "active": [{"id": 721, "hp": 120, "maxHp": 150,
                               "energies": [3, 3], "poisoned": True}],
                    "bench": [
                        {"id": 722, "hp": 90, "maxHp": 90, "energies": [3]},
                        None,
                    ],
                    "benchMax": 5,
                },
                {
                    "deckCount": 38,
                    "prize": [None, None, None, None, None],
                    "handCount": 4,
                    "active": [{"id": 179, "hp": 60, "maxHp": 180,
                               "energies": [3, 3, 3]}],
                    "bench": [{"id": 159, "hp": 100, "maxHp": 100, "energies": []}],
                },
            ],
        },
        "select": {
            "type": 0, "context": 0, "minCount": 1, "maxCount": 1,
            "remainEnergyCost": 1,
            "option": [
                {"type": OPT_END},
                {"type": OPT_PLAY, "index": 0},
                {"type": OPT_ATTACH, "area": AREA_ACTIVE, "index": 0,
                 "inPlayArea": AREA_ACTIVE, "inPlayIndex": 0},
                {"type": OPT_ATTACK, "attackId": 12},
                {"type": OPT_CARD, "area": AREA_BENCH, "index": 0,
                 "playerIndex": 1},
            ],
        },
    }
    sv2 = state_features(main_obs)
    assert sv2.shape == (STATE_DIM,), sv2.shape
    assert np.all(np.isfinite(sv2)), "MAIN state vector has non-finite values"

    mat = options_matrix(main_obs)
    assert mat.shape == (5, OPTION_DIM), mat.shape
    assert np.all(np.isfinite(mat)), "option matrix has non-finite values"

    for opt in main_obs["select"]["option"]:
        ov = option_features(main_obs, opt)
        assert ov.shape == (OPTION_DIM,), ov.shape

    print(
        f"OK: features v{FEATURE_VERSION} self-check passed | "
        f"STATE_DIM={STATE_DIM} OPTION_DIM={OPTION_DIM} "
        f"options_matrix={mat.shape}"
    )
