"""Archaludon ex / Cinderace — community rule pilot + R7 bench guard.

**Primary iteration file** — all Archaludon deck logic lives here (+ thin wrapper at
``agent()``). Deck: ``agent_decks/archaludon_ex_cinderace.csv`` (**= sample_archaludon_75wr shell**,
2026-07-30: 4×Cinderace + 4×Full Metal Lab + 11×Metal; legacy Charmeleon line retired).
Do not port levers from Dragapult/Lucario/Alakazam pilots.

Bench safety: ``score_setup`` / ``score_play`` / ``apply_overrides`` / ``score_option``
(empty bench → bench Duraludon/Relicanth before END/items). R12 dead-active tempo:
energize bench attacker / retreat when Active is low-HP dead weight (82062971).

Built by scripts/bootstrap_archaludon.py — re-run after reference updates.
"""

import os
import random
import sys

try:
    ROOT = __file__
except NameError:
    ROOT = None
CG_PATH = "/kaggle_simulations/agent"
for p in ([os.path.dirname(os.path.abspath(ROOT))] if ROOT else []) + [CG_PATH]:
    if p and p not in sys.path and os.path.isdir(p):
        sys.path.insert(0, p)

from cg.api import (
    AreaType,
    CardType,
    LogType,
    OptionType,
    SelectContext,
    all_card_data,
    to_observation_class,
)

try:
    from cg.api import all_attack
    ALL_ATTACKS = {a.attackId: a for a in all_attack()}
except Exception:
    ALL_ATTACKS = {}

# ── Card IDs ──

DURALUDON = 169
ARCHALUDON_EX = 190
CINDERACE = 666
RELICANTH = 57
CRUSTLE_LINE = {344, 345, 532, 533}
STARMIE_LINE = {1030, 1031}
LUCARIO_LINE = {677, 678}
HOP_LINE = {288, 289, 299, 304, 307, 308, 309, 310, 878, 879}
HOP_SNORLAX = 304
# 2026-07 meta: Marnie Grimmsnarl darkness engine (dominant ladder archetype)
GRIMMSNARL_LINE = {646, 647, 648, 642, 643, 644, 645, 649}  # Impidimp→Grimmsnarl + Marnie line
MUNKIDORI_IDS = {112, 139}
SPIKEMUTH_GYM = 1259
SPIKY_ENERGY = 14
IONO_LINE = {265, 266, 268, 269, 270, 271}  # Voltorb/Electrode/Tadbulb/Bellibolt/Wattrel/Kilowattrel
IONO_THREATS = {269, 271}  # Bellibolt ex / Kilowattrel — prize + burst
LIGHTNING_ENERGY = 4
IONO_STADIUM = 1254  # Levincia
DRAGAPULT_LINE = {119, 120, 121}  # Dreepy / Drakloak / Dragapult ex
DRAGAPULT_EX = 121
DRAKLOAK = 120

METAL_ENERGY = 8

POKE_PAD = 1152
ULTRA_BALL = 1121
POKEGEAR = 1122
NIGHT_STRETCHER = 1097
JUMBO_ICE_CREAM = 1147
HERO_CAPE = 1159
BOSS = 1182
EXPLORER = 1185
LILLIE = 1227
FULL_METAL_LAB = 1244
CRUSHING_HAMMER = 1120  # majkel energy denial (×4)

# crustle lever `deckcons` (KEPT 2026-07-31): deck size above which Explorer's
# Guidance (-6 deck) is still affordable in the Crustle deck-out race.
# Overridable for threshold sweeps; ARCH_CRUSTLE_DECKCONS=0 disables the lever.
DECKCONS_EXPLORER_FLOOR = int(os.environ.get("ARCH_DECKCONS_FLOOR", "30"))

RAGING_HAMMER = 224
METAL_DEFENDER = 253
TURBO_FLARE = 965  # Cinderace — re-fuel bench after Hammer

_ATTACK_BASE_DMG = {METAL_DEFENDER: 220, TURBO_FLARE: 50, 223: 30, 61: 30}

_SETUP_ACTIVE_PRIORITY = {
    CINDERACE: (100000, "Active: Cinderace Explosiveness"),
    DURALUDON: (20000, "Active fallback: Duraludon"),
    RELICANTH: (5000, "Active fallback: Relicanth"),
}

_SETUP_BENCH_PRIORITY = {
    DURALUDON: (25000, "Setup bench: Duraludon"),
    RELICANTH: (22000, "Setup bench: Relicanth"),
}

ALWAYS_SAFE_DISCARD = {METAL_ENERGY, CINDERACE}

CARD_DB = {c.cardId: c for c in all_card_data()}

MEGA_BRAVE = 983
PREMIUM_POWER_PRO = 1141
HARIYAMA_LINE = {673, 674}

# Track opponent's last-turn attack via logs
_opp_last_attack_id = None
_cur_turn_logs = []


def _update_opp_attack_tracking(obs):
    global _opp_last_attack_id, _cur_turn_logs
    yi = obs.current.yourIndex
    for entry in obs.logs:
        if entry.type == LogType.TURN_END:
            for prev in _cur_turn_logs:
                if prev.type == LogType.ATTACK and getattr(prev, 'playerIndex', yi) != yi:
                    _opp_last_attack_id = prev.attackId
            _cur_turn_logs.clear()
        else:
            _cur_turn_logs.append(entry)


# ── Board helpers ──

def read_deck_csv():
    fp = "deck.csv"
    if not os.path.exists(fp):
        fp = "/kaggle_simulations/agent/deck.csv"
    with open(fp) as f:
        return [int(line) for line in f.read().strip().split("\n")]


def get_card(obs, area, index, player_index):
    if area is None or index is None:
        return None
    ps = obs.current.players[player_index]
    if area == AreaType.DECK and obs.select and obs.select.deck is not None:
        return obs.select.deck[index] if index < len(obs.select.deck) else None
    if area == AreaType.HAND and ps.hand is not None:
        return ps.hand[index] if index < len(ps.hand) else None
    if area == AreaType.DISCARD:
        return ps.discard[index] if index < len(ps.discard) else None
    if area == AreaType.ACTIVE:
        return ps.active[index] if index < len(ps.active) else None
    if area == AreaType.BENCH:
        return ps.bench[index] if index < len(ps.bench) else None
    if area == AreaType.PRIZE:
        return ps.prize[index] if index < len(ps.prize) else None
    if area == AreaType.STADIUM:
        return obs.current.stadium[index] if index < len(obs.current.stadium) else None
    if area == AreaType.LOOKING and obs.current.looking is not None:
        return obs.current.looking[index] if index < len(obs.current.looking) else None
    return None


def option_card(obs, opt):
    yi = obs.current.yourIndex
    pi = opt.playerIndex if opt.playerIndex is not None else yi
    if opt.type == OptionType.PLAY:
        return get_card(obs, AreaType.HAND, opt.index, pi)
    return get_card(obs, opt.area, opt.index, pi)


def option_target(obs, opt):
    if opt.inPlayArea is None or opt.inPlayIndex is None:
        return None
    return get_card(obs, opt.inPlayArea, opt.inPlayIndex, obs.current.yourIndex)


def my_state(obs):
    return obs.current.players[obs.current.yourIndex]


def _bench_is_empty(obs) -> bool:
    return len([p for p in my_state(obs).bench if p]) == 0


def _main_has_basic_play(obs) -> bool:
    """True if MAIN menu includes PLAY for Duraludon or Relicanth."""
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return False
    for opt in obs.select.option:
        if opt.type != OptionType.PLAY:
            continue
        card = option_card(obs, opt)
        if card and card.id in {DURALUDON, RELICANTH}:
            return True
    return False


def _active_is_empty(obs) -> bool:
    ps = my_state(obs)
    return not ps.active or not ps.active[0]


def _empty_bench_basic_score(obs, opt, score: int, reason: str) -> tuple[int, str]:
    """Central empty-bench policy for this deck (169/57 are engine Basics)."""
    if not _bench_is_empty(obs):
        return score, reason
    card = option_card(obs, opt)
    cid = card.id if card else None
    ctx = obs.select.context

    if cid in {DURALUDON, RELICANTH}:
        if opt.type == OptionType.PLAY and ctx == SelectContext.MAIN:
            return max(score, 50000), "empty bench: bench basic (MAIN)"
        if opt.type == OptionType.CARD and ctx in {
            SelectContext.SETUP_BENCH_POKEMON,
            SelectContext.TO_BENCH,
            SelectContext.TO_FIELD,
        }:
            return max(score, 25000), "empty bench: place basic"

    if opt.type == OptionType.PLAY and ctx == SelectContext.MAIN and cid == ULTRA_BALL:
        return min(score, -5000), "empty bench: no Ultra Ball"

    if opt.type == OptionType.END and ctx == SelectContext.MAIN and _main_has_basic_play(obs):
        return -50000, "empty bench: must bench basic"

    return score, reason


def _best_bench_attacker(obs):
    ps = my_state(obs)
    best = None
    best_prio = -1
    prio = {ARCHALUDON_EX: 3, DURALUDON: 2, CINDERACE: 1}
    for p in ps.bench:
        if not p or p.id not in prio:
            continue
        if prio[p.id] > best_prio:
            best_prio = prio[p.id]
            best = p
    return best


def _active_is_dead_weight(obs) -> bool:
    active = active_pokemon(obs)
    if not active:
        return False
    max_hp = getattr(active, "maxHp", None) or active.hp
    if max_hp <= 0:
        return False
    ratio = active.hp / max_hp
    if active.id == RELICANTH and ratio <= 0.25:
        return True
    return ratio <= 0.25 and energy_count(active) == 0


def _dead_active_tempo_score(obs, opt, score: int, reason: str) -> tuple[int, str]:
    """R12: dead Active — power bench attacker instead of END/attach stall (82062971 class)."""
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return score, reason
    if not _active_is_dead_weight(obs):
        return score, reason
    attacker = _best_bench_attacker(obs)
    if not attacker:
        return score, reason

    if opt.type == OptionType.ATTACH:
        target = option_target(obs, opt)
        if (
            target
            and target.id == attacker.id
            and getattr(opt, "inPlayArea", None) == AreaType.BENCH
        ):
            return max(score, 35000), "R12: energize bench attacker"
        return score, reason

    if opt.type == OptionType.RETREAT and not obs.current.retreated:
        ok, _ = attack_energy_route(obs, attacker)
        if ok or energy_count(attacker) >= 1:
            return max(score, 30000), "R12: retreat to bench attacker"

    if opt.type == OptionType.END and not obs.current.energyAttached:
        if METAL_ENERGY in hand_ids(obs) or energy_count(attacker) >= 1:
            return min(score, -15000), "R12: don't END on dead active"

    return score, reason


def _main_legal_attack_ko(obs) -> bool:
    """True if any legal MAIN attack KOs opponent Active."""
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return False
    opp_act = opp_active_pokemon(obs)
    if not opp_act:
        return False
    for opt in obs.select.option:
        if opt.type != OptionType.ATTACK:
            continue
        dmg = best_attack_damage(obs, getattr(opt, "attackId", None) or 0)
        if effective_damage(dmg, opp_act) >= opp_act.hp:
            return True
    return False


def _prize_race_attach_cap(obs, opt, score: int, reason: str) -> tuple[int, str]:
    """R11: when behind in prizes and a legal attack KOs Active, cap attach/tempo below the KO."""
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return score, reason
    our_prizes, opp_prizes = _prize_counts(obs)
    if our_prizes <= opp_prizes:
        return score, reason
    if _bench_is_empty(obs) and _main_has_basic_play(obs):
        return score, reason
    if not _main_legal_attack_ko(obs):
        return score, reason

    if opt.type == OptionType.ATTACK:
        opp_act = opp_active_pokemon(obs)
        aid = getattr(opt, "attackId", None) or 0
        dmg = best_attack_damage(obs, aid)
        if opp_act and effective_damage(dmg, opp_act) >= opp_act.hp:
            pv = prize_value(opp_act)
            boost = 55000 + pv * 5000
            if our_prizes <= pv:
                boost += 10000
            return max(score, boost), "R11: lethal attack when behind"
        return score, reason

    if opt.type == OptionType.ATTACH:
        return min(score, 5000), "R11: cap attach when lethal available"

    if opt.type == OptionType.PLAY:
        card = option_card(obs, opt)
        cid = card.id if card else None
        if cid in {DURALUDON, RELICANTH}:
            return score, reason
        return min(score, 5000), "R11: cap tempo when lethal available"

    if opt.type == OptionType.EVOLVE:
        return min(score, 5000), "R11: cap evolve when lethal ready"

    return score, reason


def _mandatory_promote_score(obs, opt, score: int, reason: str) -> tuple[int, str]:
    """After active KO — must pick new Active from bench (82068759 class). R8a lever."""
    ctx = obs.select.context
    if ctx not in {SelectContext.TO_ACTIVE, SelectContext.SWITCH}:
        return score, reason
    if opt.type != OptionType.CARD:
        return score, reason
    yi = obs.current.yourIndex
    if getattr(opt, "playerIndex", yi) != yi:
        return score, reason
    if not _active_is_empty(obs):
        return score, reason
    card = option_card(obs, opt)
    if not card:
        return score, reason
    promote_priority = {
        ARCHALUDON_EX: 60000,
        CINDERACE: 55000,
        DURALUDON: 50000,
        RELICANTH: 48000,
    }
    boost = promote_priority.get(card.id)
    if boost is not None:
        return max(score, boost), "must promote: empty active"
    return score, reason


def _prize_counts(obs) -> tuple[int, int]:
    us = len(my_state(obs).prize or [])
    them = len(opp_state(obs).prize or [])
    return us, them


def score_attack(obs, opt) -> tuple[int, str]:
    """R10 + sample_75wr matchup attack priorities (Starmie/Crustle)."""
    aid = getattr(opt, "attackId", None) or 0
    dmg = best_attack_damage(obs, aid)
    opp = opp_active_pokemon(obs)
    our_prizes, opp_prizes = _prize_counts(obs)
    behind = our_prizes > opp_prizes
    matchup = detect_matchup(obs)

    # Crustle: Metal Defender does 0 into common shells — hard ban MD
    if matchup == "crustle" and aid == METAL_DEFENDER:
        return -12000, "Crustle: Metal Defender does 0 (hard ban)"

    if opp and effective_damage(dmg, opp) >= opp.hp:
        pv = prize_value(opp)
        score = 50000 + pv * 5000
        if behind:
            score += 5000
        if our_prizes <= pv:
            score += 10000
        # Starmie: prefer clean 220 MD KO over RH chip when both lethal
        if matchup == "starmie" and aid == METAL_DEFENDER:
            score += 3000
        # Crustle: RH KO is the only clean prize path
        if matchup == "crustle" and aid == RAGING_HAMMER:
            score += 8000
        return score, "attack KO"

    score = dmg + (3000 if behind else 0)
    if aid == METAL_DEFENDER and opp and effective_damage(dmg, opp) >= opp.hp - 30:
        score += 2000
    # Starmie race: pressure with MD when Relicanth online even if not KO
    if matchup == "starmie" and aid == METAL_DEFENDER and has_in_play(obs, RELICANTH):
        score += 1500
    if matchup == "crustle" and aid == RAGING_HAMMER:
        # RH is the only real attack path — strong default over END/items
        score += 4500
        active = active_pokemon(obs)
        if active and damage_on(active) >= 60:
            score += 2000  # RH scales with our damage counters
    if matchup == "dragapult" and aid == METAL_DEFENDER and has_in_play(obs, RELICANTH):
        score += 800
    if matchup == "iono" and aid == METAL_DEFENDER and has_in_play(obs, RELICANTH):
        score += 700
        if opp and opp.id in IONO_THREATS:
            score += 300
    return score, "attack"


def opp_state(obs):
    return obs.current.players[1 - obs.current.yourIndex]


def active_pokemon(obs):
    ps = my_state(obs)
    return ps.active[0] if ps.active else None


def opp_active_pokemon(obs):
    ps = opp_state(obs)
    return ps.active[0] if ps.active else None


def opp_bench_pokemon(obs):
    return [p for p in opp_state(obs).bench if p]


def all_my_pokemon(obs):
    ps = my_state(obs)
    return [p for p in (ps.active + ps.bench) if p]


def hand_ids(obs):
    hand = my_state(obs).hand
    return [c.id for c in hand if c] if hand else []


def discard_ids(obs):
    return [c.id for c in (my_state(obs).discard or []) if c]


def metal_in_discard(obs):
    return sum(1 for c in (my_state(obs).discard or []) if c and c.id == METAL_ENERGY)


def energy_count(pokemon):
    if pokemon is None:
        return 0
    if getattr(pokemon, "energyCards", None) is not None:
        return len(pokemon.energyCards)
    return len(getattr(pokemon, "energies", []) or [])


def retreat_cost(pokemon):
    data = CARD_DB.get(pokemon.id) if pokemon else None
    return getattr(data, "retreatCost", 0) if data else 0


def damage_on(pokemon):
    if pokemon is None:
        return 0
    return max(0, getattr(pokemon, "maxHp", pokemon.hp) - pokemon.hp)


def has_tool(pokemon):
    return bool(getattr(pokemon, "tools", []) or [])


def count_in_play(obs, card_id):
    return sum(1 for p in all_my_pokemon(obs) if p.id == card_id)


def has_in_play(obs, card_id):
    return any(p.id == card_id for p in all_my_pokemon(obs))


def need_duraludon(obs):
    return sum(1 for p in all_my_pokemon(obs) if p.id in {DURALUDON, ARCHALUDON_EX}) < 2


def need_archaludon(obs):
    has_dura, ex_count = False, 0
    for p in all_my_pokemon(obs):
        if p.id == DURALUDON:
            has_dura = True
        elif p.id == ARCHALUDON_EX:
            ex_count += 1
    return has_dura and ex_count < 2


def safe_discard_count(obs):
    ids = hand_ids(obs)
    mt = metal_in_discard(obs)
    safe = 0
    for cid in ids:
        if cid == METAL_ENERGY and mt + safe < 2:
            safe += 1
        elif cid == CINDERACE:
            safe += 1
    draw_in_hand = sum(1 for c in ids if c in (LILLIE, EXPLORER))
    if draw_in_hand >= 2:
        safe += draw_in_hand - 1
    return safe


def prize_value(pokemon):
    data = CARD_DB.get(pokemon.id) if pokemon else None
    if data and getattr(data, "megaEx", False):
        return 3
    if data and getattr(data, "ex", False):
        return 2
    return 1


def best_attack_damage(obs, attack_id):
    if attack_id == RAGING_HAMMER:
        return 80 + damage_on(active_pokemon(obs)) // 10 * 10
    return _ATTACK_BASE_DMG.get(attack_id, 0)


def is_metal_weak(pokemon):
    if pokemon is None:
        return False
    data = CARD_DB.get(pokemon.id)
    w = getattr(data, "weakness", None) if data else None
    if w is None:
        return False
    return getattr(w, "value", w) == METAL_ENERGY


def effective_damage(base_damage, target):
    return base_damage * 2 if is_metal_weak(target) else base_damage


def _first_option_index(obs, card_id):
    for o in obs.select.option:
        oc = option_card(obs, o)
        if oc and oc.id == card_id:
            return getattr(o, 'index', None)
    return None


# ── Attack routes ──

def direct_attack_energy_route(obs, pokemon):
    e = energy_count(pokemon)
    if e >= 3:
        return True, False
    if e == 2 and not obs.current.energyAttached and METAL_ENERGY in hand_ids(obs):
        return True, True
    return False, False


def can_evolve_to_archaludon_now(pokemon, obs):
    if pokemon is None or pokemon.id != DURALUDON:
        return False
    if ARCHALUDON_EX not in hand_ids(obs):
        return False
    return not getattr(pokemon, "appearThisTurn", True)


def alloy_attack_energy_route(obs, pokemon):
    if not can_evolve_to_archaludon_now(pokemon, obs):
        return False, False
    current = energy_count(pokemon)
    alloy = min(2, metal_in_discard(obs))
    total = current + alloy
    if total >= 3:
        return True, False
    if total == 2 and not obs.current.energyAttached and METAL_ENERGY in hand_ids(obs):
        return True, True
    return False, False


def attack_energy_route(obs, pokemon):
    if pokemon is None:
        return False, False
    if pokemon.id == ARCHALUDON_EX:
        return direct_attack_energy_route(obs, pokemon)
    if pokemon.id == DURALUDON:
        ok, uses_attach = direct_attack_energy_route(obs, pokemon)
        if ok:
            return True, uses_attach
        return alloy_attack_energy_route(obs, pokemon)
    return False, False


def archaludon_ex_attack_route(obs):
    active = active_pokemon(obs)
    if active and active.id in {ARCHALUDON_EX, DURALUDON}:
        ok, uses_attach = attack_energy_route(obs, active)
        if ok:
            return {"attacker": active, "uses_attach": uses_attach, "needs_retreat": False}

    if active is None or obs.current.retreated or energy_count(active) < retreat_cost(active):
        return None
    ps = my_state(obs)
    for pokemon in [p for p in ps.bench if p]:
        if pokemon.id not in {ARCHALUDON_EX, DURALUDON}:
            continue
        ok, uses_attach = attack_energy_route(obs, pokemon)
        if ok:
            return {"attacker": pokemon, "uses_attach": uses_attach, "needs_retreat": True}
    return None


def planned_archaludon_attacks(obs):
    route = archaludon_ex_attack_route(obs)
    if route is None:
        return []
    attacker = route["attacker"]
    attacks = []
    if attacker.id == ARCHALUDON_EX:
        attacks.append({"damage": 220})
        if has_in_play(obs, RELICANTH):
            attacks.append({"damage": 80 + damage_on(attacker) // 10 * 10})
    if attacker.id == DURALUDON:
        attacks.append({"damage": 80 + damage_on(attacker) // 10 * 10})
        if can_evolve_to_archaludon_now(attacker, obs):
            attacks.append({"damage": 220})
    return attacks


# ── Matchup detection & opponent max damage ──
# Ported from sample_archaludon_75wr (75% WR vs 1300 Starmie public agent)

ALAKAZAM_LINE = {741, 742, 743}
_ALA_BOARD_GAIN = {66: 3, 742: 2, 305: 2, 65: 2, 741: 1}  # Dudunsparce, Kadabra, Dunsparce, Abra


def _estimate_alakazam_from_pokes(opp, pokes):
    """(floor, ceiling, ceiling_with_boss) damage from visible Alakazam line."""
    ids = [p.id for p in pokes if p]
    if not (ALAKAZAM_LINE & set(ids)):
        return 0, 0, 0
    base = opp.handCount + 1
    gain = sum(_ALA_BOARD_GAIN.get(i, 0) for i in ids)
    enriching_seen = (
        any(c and c.id == 13 for c in (opp.discard or []))
        or any(c and c.id == 13 for p in pokes if p for c in (getattr(p, "energyCards", None) or []))
    )
    if not enriching_seen:
        gain += 3
    if any(i == 140 for i in ids):
        gain += 3
    return base * 20, (base + gain + 2) * 20, (base + gain - 1) * 20


def _estimate_alakazam(obs):
    """(floor, ceiling, ceiling_with_boss) from Powerful Hand — sample_75wr."""
    opp = opp_state(obs)
    pokes = ([opp.active[0]] if opp.active else []) + list(opp.bench or [])
    return _estimate_alakazam_from_pokes(opp, pokes)


# flg / イワパレス shell extras (2026-07 LB#1): wall + Spiky + Boss toolbox
MEGA_KANGASKHAN_EX = 756
CORNERSTONE_OGERPON_EX = 117
FLG_WALL_SHELL = {MEGA_KANGASKHAN_EX, CORNERSTONE_OGERPON_EX} | CRUSTLE_LINE


def _opp_board_has_spiky(obs) -> bool:
    opp = opp_state(obs)
    for p in ([opp.active[0]] if opp.active else []) + list(opp.bench or []):
        if p and _opp_has_spiky(p):
            return True
    return False


def _opp_hammer_seen(obs) -> bool:
    """True if opponent has already played Crushing Hammer (in discard).

    crustle single lever `hammer_prior` (2026-07-31): the default is reactive —
    it only fires after a Hammer has already stripped an energy. majkel runs 4x
    Crushing Hammer (flg runs 0, see recordings/metrics/crustle_majkel_vs_flg_diagnosis.md)
    and the two shells are visually identical on board, so under this lever we
    presume hammer pressure for the whole Crustle matchup instead of waiting for
    discard evidence. Costs some flg win rate by construction — gate both.
    """
    opp = opp_state(obs)
    if any(c and c.id == CRUSHING_HAMMER for c in (opp.discard or [])):
        return True
    return False


def _board_metal_energy(obs) -> int:
    return sum(energy_count(p) for p in all_my_pokemon(obs) if p)


def _energy_starved(obs) -> bool:
    """After Hammer strips: Active attacker needs re-fuel or board metal is thin."""
    active = active_pokemon(obs)
    if active and active.id in {DURALUDON, ARCHALUDON_EX} and energy_count(active) < 2:
        return True
    if _board_metal_energy(obs) <= 1:
        return True
    if metal_in_discard(obs) >= 2 and METAL_ENERGY not in hand_ids(obs):
        return True
    return False


def _crustle_boss_actually_playable(obs) -> bool:
    """crustle single lever A/B (2026-07-31), env ARCH_CRUSTLE_LEVER=rhsoft.

    The Spiky branch drops Raging Hammer to 2500 whenever Boss is *in hand*,
    on the theory that gusting first is better. But Boss in hand is not Boss
    on the board: if the supporter for the turn is already spent, or the
    opponent has no bench to gust, that turn we neither Boss nor swing — the
    only wincon line goes idle while Crushing Hammer strips us. This gate
    keeps the soft-RH deferral only when the Boss can really be played now.

    Default (lever unset) returns True → byte-identical to previous behaviour.
    """
    if os.environ.get("ARCH_CRUSTLE_LEVER", "").strip().lower() != "rhsoft":
        return True
    if getattr(obs.current, "supporterPlayed", False):
        return False
    opp = opp_state(obs)
    return any(p for p in (opp.bench or []) if p)


def _crustle_explorer_allowed(obs) -> bool:
    """crustle lever `deckcons` — KEPT and default ON 2026-07-31.

    Terminal-state profiling of 6000 Crustle games (recordings/metrics/
    crustle_deckout_diagnosis.md) shows we practically never lose the prize race
    here: 76-82% of losses are our own deck-out, and in those the opponent still
    has ~7 cards of deck left. The wall matchups are a deck-out race we lose by
    a handful of cards.

    Explorer's Guidance is the single biggest self-inflicted burn in the list:
    it looks at 6 and *discards 4* to gain 2, i.e. -6 deck per copy, x4 copies.
    Lillie's Determination by contrast shuffles the hand back in and is roughly
    deck-neutral, and Poke Pad / Pokegear / Ultra Ball are -1 each. So Explorer
    is only allowed while the deck is deep enough that six cards cannot decide
    the race. The old guard fired at deckCount <= 10, long past the point of no
    return, and it lumped in Lillie, which actually refills the deck.

    Pooled A/B, gate_archaludon.py 5x1500 per cell, same session:

        arm       majkel            flg
        base      86.16 +- 0.23     89.06 +- 0.57
        deckcons  95.30 +- 0.43     95.78 +- 0.30

    +9.14pp / +6.72pp, both CI95 disjoint. min(flg, majkel) 86.16 -> 95.30
    against a ship floor of 89.

    Set ARCH_CRUSTLE_DECKCONS=0 to restore the old behaviour (A/B arm A).
    """
    if os.environ.get("ARCH_CRUSTLE_DECKCONS", "1").strip() == "0":
        return True
    return my_state(obs).deckCount > DECKCONS_EXPLORER_FLOOR


def detect_matchup(obs):
    opp = opp_state(obs)
    ids = {p.id for p in (opp.active + opp.bench) if p}
    # Priority: Crustle / flg wall shell (metal-hate) → Grimmsnarl → …
    # Early flg often leads Ogerpon/Kangaskhan before Crustle is visible.
    if ids & CRUSTLE_LINE or ids & FLG_WALL_SHELL:
        return "crustle"
    if _opp_board_has_spiky(obs) and not (ids & GRIMMSNARL_LINE):
        # Spiky Energy toolbox strongly correlates with flg/Crustle shells
        return "crustle"
    if ids & GRIMMSNARL_LINE or ids & MUNKIDORI_IDS:
        return "grimmsnarl"
    if ids & ALAKAZAM_LINE:
        return "alakazam"
    # Iono: mon line, lightning energy on board, or Levincia stadium
    stadium = getattr(obs.current, "stadium", None) or getattr(obs.current, "stadiumCard", None)
    stadium_id = getattr(stadium, "id", None) if stadium else None
    if ids & IONO_LINE or stadium_id == IONO_STADIUM:
        return "iono"
    # Lightning energy without other mon tags → likely Iono shell
    for p in list(opp.active or []) + list(opp.bench or []):
        if not p:
            continue
        for c in getattr(p, "energyCards", None) or []:
            if getattr(c, "id", None) == LIGHTNING_ENERGY:
                return "iono"
    if ids & DRAGAPULT_LINE:
        return "dragapult"
    if ids & HOP_LINE:
        return "hop"
    if ids & STARMIE_LINE:
        return "starmie"
    if ids & LUCARIO_LINE:
        return "lucario"
    return "generic"


def opp_max_damage(obs):
    matchup = detect_matchup(obs)
    if matchup == "alakazam":
        _, ceiling, _ = _estimate_alakazam(obs)
        return ceiling or 220
    if matchup == "crustle":
        return 120
    if matchup == "grimmsnarl":
        # Grimmsnarl ex + Munkidori spread — treat as high burst
        return 280
    if matchup == "iono":
        return 240
    if matchup == "dragapult":
        return 200  # Phantom Dive / multi-prize pressure; FML helps
    if matchup == "hop":
        return 220
    if matchup == "lucario":
        return 270
    if matchup == "starmie":
        return 210
    return 220


def _opp_has_spiky(poke) -> bool:
    if not poke:
        return False
    return any(getattr(c, "id", None) == SPIKY_ENERGY for c in (getattr(poke, "energyCards", None) or []))


# ── Overrides ──

def apply_overrides(obs, opt, score, reason):
    score, reason = _empty_bench_basic_score(obs, opt, score, reason)
    score, reason = _dead_active_tempo_score(obs, opt, score, reason)
    # Global prize-race: don't attach when a legal attack already KOs Active
    score, reason = _prize_race_attach_cap(obs, opt, score, reason)

    if opt.type == OptionType.PLAY:
        card = option_card(obs, opt)
        cid = card.id if card else None
        if my_state(obs).deckCount <= 10 and cid == EXPLORER:
            return -5000, "hard: don't Explorer with low deck"

    matchup = detect_matchup(obs)
    if matchup == "grimmsnarl":
        return _apply_grimmsnarl_overrides(obs, opt, score, reason)
    if matchup == "iono":
        # R14k light stack FAILED 2026-07-31 (14.6–23.4%). Single-lever A/B via ARCH_IONO_LEVER.
        # R14m NULL. R14n MD-pressure KEEP: 33.8% vs 27.8% none @ n400 (+6.0pp).
        # Default r14n. Stacked variants: r14o = r14n + Relicanth; r14p = r14n + FML.
        # Default tomato (2026-07-31): iono-only sample_75wr delegate ≥55% local.
        # Score-path levers (r14n etc.) only apply when not using tomato agent path.
        lever = os.environ.get("ARCH_IONO_LEVER", "tomato").strip().lower()
        if lever in ("tomato", "75wr", "sample75"):
            return score, reason  # full-agent delegate in _agent_impl
        if lever in ("", "none", "off", "0", "r14h"):
            return score, reason
        if lever == "r14m":
            return _apply_iono_r14m_evolve_race(obs, opt, score, reason)
        if lever == "r14n":
            return _apply_iono_r14n_md_pressure(obs, opt, score, reason)
        if lever == "r14n2":
            # REJECTED n400: 27.8% vs r14n 30.8%
            return _apply_iono_r14n2_lethal_hard(obs, opt, score, reason)
        if lever == "r14u":
            # REJECTED n400: 27.5% vs r14n 33.8%
            return _apply_iono_r14u_rh_fallback(obs, opt, score, reason)
        if lever == "r14n_draw":
            # Component A/B: only soft-cap draw when MD ready
            return _apply_iono_r14n_component(obs, opt, score, reason, mode="draw")
        if lever == "r14n_atk":
            # Component A/B: only MD/RH attack boosts
            return _apply_iono_r14n_component(obs, opt, score, reason, mode="atk")
        if lever == "r14n_end":
            # Component A/B: only END penalty when MD ready
            return _apply_iono_r14n_component(obs, opt, score, reason, mode="end")
        if lever == "r14o":
            # REJECTED n400: 28.5% vs r14n 32.0%
            score, reason = _apply_iono_r14n_md_pressure(obs, opt, score, reason)
            return _apply_iono_r14o_relicanth(obs, opt, score, reason)
        if lever == "r14p":
            # NULL n400: 32.5% vs r14n 32.0%
            score, reason = _apply_iono_r14n_md_pressure(obs, opt, score, reason)
            return _apply_iono_r14p_fml(obs, opt, score, reason)
        if lever == "r14q":
            # REJECTED n400: 25.8%
            score, reason = _apply_iono_r14n_md_pressure(obs, opt, score, reason)
            return _apply_iono_r14q_attach_race(obs, opt, score, reason)
        if lever == "r14r":
            # REJECTED n400: 31.2%
            score, reason = _apply_iono_r14n_md_pressure(obs, opt, score, reason)
            return _apply_iono_r14r_turbo_flare(obs, opt, score, reason)
        if lever == "r14s":
            # REJECTED n400: 26.2%
            score, reason = _apply_iono_r14n_md_pressure(obs, opt, score, reason)
            return _apply_iono_r14s_boss_loaded(obs, opt, score, reason)
        if lever == "r14v":
            # NULL n400 2026-07-31: 28.5% ≈ none 28.0% — soft pre-MD engine no lift
            return _apply_iono_r14v_md_plus_engine(obs, opt, score, reason)
        if lever == "r14w":
            # REJECTED n400 2026-07-31: 25.2% vs r14n 33.2%
            return _apply_iono_r14w_prize_boss(obs, opt, score, reason)
        if lever == "r14x":
            # stacked r14n+r14w — only if r14w alone KEPT (it was not)
            score, reason = _apply_iono_r14n_md_pressure(obs, opt, score, reason)
            return _apply_iono_r14w_prize_boss(obs, opt, score, reason)
        if lever == "r14y":
            # NULL/REJECT n400 2026-07-31: 28.8% vs r14n 29.5%
            return _apply_iono_r14y_cape(obs, opt, score, reason)
        if lever in ("tomato", "75wr", "sample75"):
            # Iono-only full-agent delegate handled in _agent_impl (not score path).
            # If we reached apply_overrides, tomato path missed — no-op.
            return score, reason
        return score, reason
    if matchup == "dragapult":
        return _apply_dragapult_light_overrides(obs, opt, score, reason)
    if matchup != "crustle":
        return score, reason

    card = option_card(obs, opt)
    cid = card.id if card else getattr(opt, 'cardId', None)
    ctx = obs.select.context

    if opt.type == OptionType.EVOLVE and cid == ARCHALUDON_EX:
        return -15000, "Crustle: never evolve to ex (MD dead)"

    if opt.type == OptionType.ATTACK:
        aid = getattr(opt, 'attackId', None)
        if aid == METAL_DEFENDER:
            return -12000, "Crustle: Metal Defender does 0"
        if aid == RAGING_HAMMER:
            opp_act = opp_active_pokemon(obs)
            active = active_pokemon(obs)
            rh_dmg = 80 + damage_on(active) // 10 * 10 if active else 80
            if opp_act and rh_dmg < opp_act.hp and _opp_has_spiky(opp_act):
                # Spiky×4 shells (flg/majkel): prefer Boss first, but still RH if
                # we need tempo (don't stall into deck-out / Hammer denial).
                if hand_ids(obs) and BOSS in hand_ids(obs):
                    return 2500, "Crustle: RH into Spiky soft (Boss preferred)"
                # No Boss: RH is still the only wincon — keep positive
                return max(score, 7000), "Crustle: RH into Spiky (no Boss)"
            # Strong default: RH is the only real pressure
            boost = 14000
            if opp_act and rh_dmg >= opp_act.hp:
                boost = 30000
            elif active and damage_on(active) >= 40:
                boost = 18000
            return max(score, boost), "Crustle: Raging Hammer primary"
        # Cinderace Turbo Flare — re-accelerate after Crushing Hammer
        if aid == TURBO_FLARE:
            bench_needs = any(
                p and p.id == DURALUDON and energy_count(p) < 3
                for p in (my_state(obs).bench or [])
            )
            if bench_needs or _energy_starved(obs) or _opp_hammer_seen(obs):
                return max(score, 16000), "Hammer: Turbo Flare re-fuel bench"
            return max(score, 8000), "Crustle: Turbo Flare setup"
        # Weak basic attacks only if RH unavailable
        if aid not in (RAGING_HAMMER, METAL_DEFENDER, TURBO_FLARE):
            return min(score, 500), "Crustle: weak attack fallback"

    if opt.type == OptionType.RETREAT:
        active = active_pokemon(obs)
        # If stuck as Archaludon ex vs Crustle, retreat to Duraludon for RH line
        if active and active.id == ARCHALUDON_EX:
            return max(score, 16000), "Crustle: retreat ex → Duraludon RH line"
        if active and active.id == RELICANTH:
            return max(score, 12000), "Crustle: retreat Relicanth (no RH)"
        if active and active.id == CINDERACE:
            # After Turbo setup, get attacker in Active
            if has_in_play(obs, DURALUDON):
                return max(score, 9000), "Crustle: Cinderace out → Duraludon"

    if opt.type == OptionType.PLAY:
        if cid == RELICANTH:
            return -8000, "Crustle: skip Relicanth (MD path dead)"
        if cid == BOSS:
            # flg: Spiky Active or fat Crustle → Boss for better RH target
            opp_act = opp_active_pokemon(obs)
            if opp_act and (_opp_has_spiky(opp_act) or opp_act.hp >= 180):
                return max(score, 20000), "Crustle/flg: Boss off Spiky/fat wall"
            return max(score, 12000), "Crustle: Boss for better RH target"
        if cid == FULL_METAL_LAB:
            return max(score, 9000), "Crustle: Full Metal Lab wall"
        if cid == HERO_CAPE:
            return max(score, 8500), "Crustle: Cape for RH tank"
        if cid == CINDERACE:
            # 75wr: Explosiveness + Turbo Flare is the energy engine (Hammer resilience)
            if not has_in_play(obs, CINDERACE):
                return max(score, 17000), "Crustle/Hammer: Cinderace re-fuel engine"
        if cid == NIGHT_STRETCHER:
            md = metal_in_discard(obs)
            if md >= 1 and _energy_starved(obs):
                return max(score, 24000), "Hammer: Stretcher metal (starved)"
            if md >= 2 or (_opp_hammer_seen(obs) and md >= 1):
                return max(score, 19000), "Hammer: Stretcher metal recovery"
        if cid == EXPLORER and _crustle_explorer_allowed(obs):
            if _energy_starved(obs) and not obs.current.supporterPlayed:
                return max(score, 14000), "Hammer: Explorer dig energy/line"
        elif cid == EXPLORER:
            return -5000, "Crustle/deckcons: Explorer burns 6 deck for 2"
        dc = my_state(obs).deckCount
        if dc <= 10 and cid in (EXPLORER, LILLIE):
            if cid == LILLIE and dc <= 3 and my_state(obs).handCount >= dc + 6:
                return 15000, "Crustle: Lillie to refill deck"
            return -5000, "Crustle: don't draw with low deck"
        if cid == LILLIE:
            has_metal = any(c and c.id == METAL_ENERGY for c in (my_state(obs).hand or []) if c)
            if not has_metal:
                return score, "Crustle: Lillie OK (no energy in hand)"

    if opt.type == OptionType.ATTACH:
        target = option_target(obs, opt)
        tid = target.id if target else None
        area = getattr(opt, 'inPlayArea', None)
        starved = _energy_starved(obs) or _opp_hammer_seen(obs)
        if area == AreaType.BENCH and tid == DURALUDON:
            boost = 16000 if starved else 14000
            return score + boost, "Crustle/Hammer: bench Duraludon energy"
        if area == AreaType.ACTIVE:
            active = active_pokemon(obs)
            if active and active.id == DURALUDON:
                ec = energy_count(active)
                if ec < 2:
                    # After Hammer strip — re-attach is top priority
                    return score + (20000 if starved else 15000), "Hammer: re-fuel Active RH"
                if ec < 3:
                    return score + 12000, "Crustle: fuel Active Duraludon for RH"
                return score + 4000, "Crustle: overfuel Active Duraludon"
            if active and active.id == ARCHALUDON_EX:
                return score - 2000, "Crustle: don't fuel ex (prefer retreat)"
            if active and active.id == CINDERACE and energy_count(active) < 1:
                return score + 10000, "Hammer: enable Cinderace Turbo"
            if active and energy_count(active) >= 2:
                return score + 3000, "Crustle: Active 3rd energy"

    if opt.type == OptionType.END:
        # Never pass the turn with metal in hand and attach still available
        if (
            not obs.current.energyAttached
            and METAL_ENERGY in hand_ids(obs)
            and active_pokemon(obs)
            and active_pokemon(obs).id in {DURALUDON, ARCHALUDON_EX, CINDERACE}
        ):
            return -8000, "Hammer: don't END with attach available"

    if ctx == SelectContext.TO_HAND and opt.type == OptionType.CARD and cid == ARCHALUDON_EX:
        return -8000, "Crustle: skip Archaludon ex to hand"

    if ctx == SelectContext.TO_HAND and opt.type == OptionType.CARD and cid == DURALUDON:
        return max(score, 5000), "Crustle: prefer Duraludon to hand"

    # Night Stretcher / search: prefer metal energy when starved (Hammer)
    if ctx == SelectContext.TO_HAND and opt.type == OptionType.CARD and cid == METAL_ENERGY:
        if _energy_starved(obs) or _opp_hammer_seen(obs) or metal_in_discard(obs) >= 1:
            return max(score, 15000), "Hammer: pick metal energy"

    if ctx in {SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD}:
        if cid == ARCHALUDON_EX and score < 0:
            return 12000, "Crustle: discard Archaludon ex"
        if cid == RELICANTH:
            return max(score, 4000), "Crustle: discard Relicanth OK"
        # Never discard metal from hand when Hammer pressure is real
        if cid == METAL_ENERGY and (_opp_hammer_seen(obs) or _energy_starved(obs)):
            return -12000, "Hammer: keep metal in hand"

    return score, reason


def _apply_grimmsnarl_overrides(obs, opt, score, reason):
    """R13 — Marnie Grimmsnarl / Munkidori (2026-07 ladder #1 meta).

    Goals: race to Metal Defender 220 KO; Boss damaged Grimmsnarl/Munkidori;
    keep bench Basic alive; don't stall with dead Relicanth Active.
    """
    card = option_card(obs, opt)
    cid = card.id if card else getattr(opt, "cardId", None)
    ctx = obs.select.context
    active = active_pokemon(obs)
    opp_act = opp_active_pokemon(obs)

    # Attack selection: prefer lethal Metal Defender; Raging Hammer if it KOs / chips better
    if opt.type == OptionType.ATTACK:
        aid = getattr(opt, "attackId", None)
        if opp_act and active:
            md = effective_damage(220, opp_act) if has_in_play(obs, RELICANTH) else 0
            # Metal Defender only if Relicanth in play (ability path) — still score MD high when available
            if aid == METAL_DEFENDER:
                if opp_act.hp <= 220 or (md and md >= opp_act.hp):
                    return max(score, 25000), "Grimmsnarl: Metal Defender KO"
                return max(score, 8000), "Grimmsnarl: Metal Defender pressure"
            if aid == RAGING_HAMMER:
                rh = 80 + damage_on(active) // 10 * 10
                if effective_damage(rh, opp_act) >= opp_act.hp:
                    return max(score, 24000), "Grimmsnarl: Raging Hammer KO"
                # Prefer RH when MD unavailable and we need chip
                if not has_in_play(obs, RELICANTH):
                    return max(score, 5000), "Grimmsnarl: RH without Relicanth"

    # Boss: pull low-HP threat or Munkidori off bench
    if opt.type == OptionType.PLAY and cid == BOSS:
        return max(score, 18000), "Grimmsnarl: Boss priority"

    # Keep Relicanth for Metal Defender engine — unlike Crustle matchup
    if opt.type == OptionType.PLAY and cid == RELICANTH:
        if not has_in_play(obs, RELICANTH):
            return max(score, 16000), "Grimmsnarl: play Relicanth for MD"

    # Evolve to Archaludon ex aggressively (need 220)
    if opt.type == OptionType.EVOLVE and cid == ARCHALUDON_EX:
        return max(score, 20000), "Grimmsnarl: evolve to ex for 220"

    # Energy: load Active Archaludon/Duraludon first (race)
    if opt.type == OptionType.ATTACH:
        target = option_target(obs, opt)
        tid = target.id if target else None
        area = getattr(opt, "inPlayArea", None)
        if area == AreaType.ACTIVE and tid in {DURALUDON, ARCHALUDON_EX}:
            return score + 8000, "Grimmsnarl: Active metal attach race"
        if area == AreaType.BENCH and tid == DURALUDON:
            # secondary attacker OK but secondary to Active race
            return score + 2000, "Grimmsnarl: bench Duraludon attach"

    # Heal only when under KO range from ~280 burst
    if opt.type == OptionType.PLAY and cid == JUMBO_ICE_CREAM and active:
        if active.id == ARCHALUDON_EX and active.hp <= 280:
            return max(score, 12000), "Grimmsnarl: Ice Cream under burst range"

    # TO_HAND / search: prefer energy + Boss + evolve pieces
    if ctx == SelectContext.TO_HAND and opt.type == OptionType.CARD:
        if cid == METAL_ENERGY:
            return max(score, 9000), "Grimmsnarl: grab Metal"
        if cid == BOSS:
            return max(score, 8500), "Grimmsnarl: grab Boss"
        if cid == ARCHALUDON_EX:
            return max(score, 8000), "Grimmsnarl: grab ex"
        if cid == RELICANTH:
            return max(score, 7000), "Grimmsnarl: grab Relicanth"

    return score, reason


def _apply_iono_r14m_evolve_race(obs, opt, score, reason):
    """R14m single lever — evolve for Metal Defender race vs Lightning.

    Global score_evolve returns −500 when Active Dura has energy but metal_in_discard==0.
    A/B NULL 2026-07-31: 29.4% vs 30.0% n160 — do not default.
    """
    if opt.type != OptionType.EVOLVE:
        return score, reason
    card = option_card(obs, opt)
    cid = card.id if card else getattr(opt, "cardId", None)
    if cid != ARCHALUDON_EX:
        return score, reason
    target = option_target(obs, opt)
    if not target or target.id != DURALUDON:
        return score, reason
    if getattr(opt, "inPlayArea", None) != AreaType.ACTIVE:
        return score, reason
    ec = energy_count(target)
    if ec < 2:
        return score, reason
    boost = 19000 if ec >= 3 else 14000
    return max(score, boost), f"Iono R14m: evolve Active Dura e={ec} for MD race"


def _iono_md_legal(obs) -> bool:
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return False
    if not has_in_play(obs, RELICANTH):
        return False
    return any(
        o.type == OptionType.ATTACK and getattr(o, "attackId", None) == METAL_DEFENDER
        for o in (obs.select.option or [])
    )


def _apply_iono_r14n_component(obs, opt, score, reason, mode: str):
    """Component split of R14n for A/B (draw | atk | end)."""
    if not _iono_md_legal(obs):
        return score, reason
    opp_act = opp_active_pokemon(obs)

    if mode == "atk" and opt.type == OptionType.ATTACK:
        aid = getattr(opt, "attackId", None)
        if aid == METAL_DEFENDER and opp_act:
            if effective_damage(220, opp_act) >= opp_act.hp:
                return max(score, score + 5000), "Iono R14n_atk: MD lethal"
            return max(score, score + 2500), "Iono R14n_atk: MD pressure"
        if aid == RAGING_HAMMER and opp_act:
            active = active_pokemon(obs)
            rh = 80 + (damage_on(active) // 10 * 10 if active else 0)
            if effective_damage(rh, opp_act) >= opp_act.hp:
                return max(score, score + 4000), "Iono R14n_atk: RH lethal"
        return score, reason

    if mode == "draw" and opt.type == OptionType.PLAY:
        card = option_card(obs, opt)
        cid = card.id if card else None
        if cid in {LILLIE, EXPLORER, POKE_PAD, ULTRA_BALL, POKEGEAR}:
            return min(score, 3000), "Iono R14n_draw: attack > draw when MD ready"
        return score, reason

    if mode == "end" and opt.type == OptionType.END:
        return score - 8000, "Iono R14n_end: don't END with MD ready"
    return score, reason


def _apply_iono_r14n_md_pressure(obs, opt, score, reason):
    """R14n single lever — prefer Metal Defender pressure / KO over tempo items.

    KEEP 2026-07-31: 33.8% vs none 27.8% @ n400 (+6.0pp). Default lever.
    """
    if not _iono_md_legal(obs):
        return score, reason
    opp_act = opp_active_pokemon(obs)

    if opt.type == OptionType.ATTACK:
        aid = getattr(opt, "attackId", None)
        if aid == METAL_DEFENDER and opp_act:
            if effective_damage(220, opp_act) >= opp_act.hp:
                return max(score, score + 5000), "Iono R14n: MD lethal"
            return max(score, score + 2500), "Iono R14n: MD pressure"
        if aid == RAGING_HAMMER and opp_act:
            active = active_pokemon(obs)
            rh = 80 + (damage_on(active) // 10 * 10 if active else 0)
            if effective_damage(rh, opp_act) >= opp_act.hp:
                return max(score, score + 4000), "Iono R14n: RH lethal"
        return score, reason

    if opt.type == OptionType.PLAY:
        card = option_card(obs, opt)
        cid = card.id if card else None
        if cid in {LILLIE, EXPLORER, POKE_PAD, ULTRA_BALL, POKEGEAR}:
            return min(score, 3000), "Iono R14n: attack > draw when MD ready"
    if opt.type == OptionType.END:
        return score - 8000, "Iono R14n: don't END with MD ready"
    return score, reason


def _apply_iono_r14n2_lethal_hard(obs, opt, score, reason):
    """R14n2 — when any legal attack KOs Active, hard-prioritize it (R11-style always-on).

    Differs from r14n: triggers on ANY lethal attack (not only MD-present), and uses
    absolute floors so attach/play cannot outrank a prize take.
    """
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return score, reason
    opp_act = opp_active_pokemon(obs)
    if not opp_act:
        return score, reason

    lethal_aids = []
    for o in obs.select.option or []:
        if o.type != OptionType.ATTACK:
            continue
        aid = getattr(o, "attackId", None) or 0
        dmg = best_attack_damage(obs, aid)
        if effective_damage(dmg, opp_act) >= opp_act.hp:
            lethal_aids.append(aid)

    if lethal_aids:
        if opt.type == OptionType.ATTACK:
            aid = getattr(opt, "attackId", None)
            if aid in lethal_aids:
                pv = prize_value(opp_act)
                return max(score, 55000 + pv * 5000), "Iono R14n2: hard lethal"
            return score, reason
        if opt.type in {OptionType.ATTACH, OptionType.PLAY, OptionType.EVOLVE, OptionType.END}:
            return min(score, 4000), "Iono R14n2: cap tempo when lethal"
        return score, reason

    # No lethal — fall back to r14n MD pressure behavior
    return _apply_iono_r14n_md_pressure(obs, opt, score, reason)


def _apply_iono_r14u_rh_fallback(obs, opt, score, reason):
    """R14u — r14n when MD ready; else RH/attack pressure when Relicanth missing.

    Diagnosis: r14n only fires with Relicanth+MD legal (~late game). Early Lightning
    race is lost while we draw/setup. Prefer swinging RH (or any attack) over END/draw.
    """
    # First apply r14n (no-op if MD not legal)
    score, reason = _apply_iono_r14n_md_pressure(obs, opt, score, reason)

    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return score, reason
    # If MD already legal, r14n handled it
    if has_in_play(obs, RELICANTH) and any(
        o.type == OptionType.ATTACK and getattr(o, "attackId", None) == METAL_DEFENDER
        for o in (obs.select.option or [])
    ):
        return score, reason

    has_attack = any(o.type == OptionType.ATTACK for o in (obs.select.option or []))
    if not has_attack:
        return score, reason

    opp_act = opp_active_pokemon(obs)
    if opt.type == OptionType.ATTACK:
        aid = getattr(opt, "attackId", None)
        active = active_pokemon(obs)
        if aid == RAGING_HAMMER and opp_act and active:
            rh = 80 + damage_on(active) // 10 * 10
            if effective_damage(rh, opp_act) >= opp_act.hp:
                return max(score, score + 4500), "Iono R14u: RH lethal (no MD)"
            return max(score, score + 2800), "Iono R14u: RH pressure (no MD)"
        # any other attack still better than END
        return max(score, score + 1500), "Iono R14u: take attack (no MD)"
    if opt.type == OptionType.PLAY:
        card = option_card(obs, opt)
        cid = card.id if card else None
        if cid in {LILLIE, EXPLORER, POKE_PAD, POKEGEAR}:
            return min(score, 2500), "Iono R14u: attack > draw (no MD)"
    if opt.type == OptionType.END:
        return score - 7000, "Iono R14u: don't END with attack (no MD)"
    return score, reason


def _apply_iono_r14o_relicanth(obs, opt, score, reason):
    """R14o single add-on — get Relicanth online for Metal Defender (needs ability).

    Only PLAY Relicanth when missing and a Dura/ex line is already in play.
    Modest boost (not 15k stack) so it doesn't starve energy attaches.
    """
    if opt.type != OptionType.PLAY:
        return score, reason
    card = option_card(obs, opt)
    cid = card.id if card else None
    if cid != RELICANTH:
        return score, reason
    if has_in_play(obs, RELICANTH):
        return score, reason
    if not (has_in_play(obs, DURALUDON) or has_in_play(obs, ARCHALUDON_EX)):
        return score, reason
    return max(score, score + 3500), "Iono R14o: Relicanth for MD"


def _apply_iono_r14p_fml(obs, opt, score, reason):
    """R14p single add-on — Full Metal Lab ASAP when Active is Metal (Lightning chip cut)."""
    if opt.type != OptionType.PLAY:
        return score, reason
    card = option_card(obs, opt)
    cid = card.id if card else None
    if cid != FULL_METAL_LAB:
        return score, reason
    active = active_pokemon(obs)
    if not active or active.id not in {DURALUDON, ARCHALUDON_EX}:
        return score, reason
    return max(score, score + 2800), "Iono R14p: FML on Metal Active"


def _apply_iono_r14q_attach_race(obs, opt, score, reason):
    """R14q single add-on — Active metal attach race before MD is online."""
    if opt.type != OptionType.ATTACH:
        return score, reason
    if getattr(obs.current, "energyAttached", False):
        return score, reason
    target = option_target(obs, opt)
    if not target:
        return score, reason
    if getattr(opt, "inPlayArea", None) != AreaType.ACTIVE:
        return score, reason
    if target.id not in {DURALUDON, ARCHALUDON_EX}:
        return score, reason
    ec = energy_count(target)
    if ec >= 3:
        return score, reason
    return score + 2500, f"Iono R14q: Active metal race e={ec}"


def _apply_iono_r14r_turbo_flare(obs, opt, score, reason):
    """R14r single add-on — Cinderace Turbo Flare into bench Duraludon (energy engine)."""
    if opt.type != OptionType.ATTACK:
        return score, reason
    aid = getattr(opt, "attackId", None)
    if aid != 965:  # Turbo Flare
        return score, reason
    active = active_pokemon(obs)
    if not active or active.id != CINDERACE:
        return score, reason
    if not any(p and p.id == DURALUDON for p in (my_state(obs).bench or [])):
        return score, reason
    return max(score, score + 3200), "Iono R14r: Turbo Flare -> bench Dura"


def _apply_iono_r14s_boss_loaded(obs, opt, score, reason):
    """R14s single add-on — Boss only loaded Bellibolt/Kilowattrel when we can attack."""
    if opt.type != OptionType.PLAY:
        return score, reason
    if getattr(obs.current, "supporterPlayed", False):
        return score, reason
    card = option_card(obs, opt)
    cid = card.id if card else None
    if cid != BOSS:
        return score, reason
    threats = [
        p
        for p in opp_bench_pokemon(obs)
        if p and p.id in IONO_THREATS and energy_count(p) >= 2
    ]
    if not threats:
        return score, reason
    if not any(o.type == OptionType.ATTACK for o in (obs.select.option or [])):
        return score, reason
    return max(score, score + 2200), "Iono R14s: Boss loaded threat + attack ready"


def _apply_iono_r14v_md_plus_engine(obs, opt, score, reason):
    """R14v — r14n when MD legal; soft pre-MD engine otherwise.

    Expert-iteration diagnosis (2026-07-31):
      - r14n only fires late (Relicanth + MD legal) → early Lightning race lost
      - r14u early RH spam REJECTED; r14k full light stack REJECTED
      - r14o hard Relicanth / r14q attach race REJECTED when always-on

    Design: keep r14n late; pre-MD only mild Active-metal race + Relicanth online
    when Dura line already in play + END penalty if attack/attach available.
    Soft magnitudes so attach/Boss/draw still compete.

    A/B NULL n400 2026-07-31: 28.5% vs none 28.0% — do not default.
    """
    score, reason = _apply_iono_r14n_md_pressure(obs, opt, score, reason)
    if _iono_md_legal(obs):
        return score, reason
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return score, reason

    if opt.type == OptionType.ATTACH:
        target = option_target(obs, opt)
        tid = target.id if target else None
        if getattr(opt, "inPlayArea", None) == AreaType.ACTIVE and tid in {
            DURALUDON,
            ARCHALUDON_EX,
        }:
            return max(score, score + 4500), "Iono R14v: Active metal race (pre-MD)"

    if opt.type == OptionType.PLAY:
        card = option_card(obs, opt)
        cid = card.id if card else None
        if cid == RELICANTH and not has_in_play(obs, RELICANTH):
            if has_in_play(obs, DURALUDON) or has_in_play(obs, ARCHALUDON_EX):
                return max(score, 11000), "Iono R14v: Relicanth online (pre-MD)"

    if opt.type == OptionType.END:
        has_atk = any(o.type == OptionType.ATTACK for o in (obs.select.option or []))
        if has_atk:
            return score - 5000, "Iono R14v: attack over END (pre-MD)"
        if not obs.current.energyAttached and METAL_ENERGY in hand_ids(obs):
            return score - 3500, "Iono R14v: attach over END (pre-MD)"

    return score, reason


def _iono_killable_threats(obs):
    """Bench Iono 2-prize threats we can KO with a planned attack this turn."""
    attacks = planned_archaludon_attacks(obs)
    if not attacks:
        return []
    out = []
    for target in opp_bench_pokemon(obs):
        if not target or target.id not in IONO_THREATS:
            continue
        if any(effective_damage(atk["damage"], target) >= target.hp for atk in attacks):
            out.append(target)
    return out


def _apply_iono_r14w_prize_boss(obs, opt, score, reason):
    """R14w single lever — prize-efficiency Boss vs Iono.

    Loss DS (n=200, 2026-07-31): losses end Active=None (board wipe) 100%;
    wins keep Arch 88% / Relicanth 62%. Opp Active on losses is Voltorb ~96%.
    Base Boss saves when Active is KO-able — so we take 1-prize Voltorb and leave
    loaded Bellibolt_ex / Kilowattrel to sweep us next.

    Lever: if a bench IONO_THREAT is KO-able, hard-prefer Boss PLAY (even when
    Active 1-prize is also KO-able). Target selection already weights prize_value.
    Does NOT stack r14n — pure single lever for A/B.
    """
    if obs.select is None:
        return score, reason
    ctx = obs.select.context

    # MAIN: play Boss when a 2-prize threat is KO-able
    if ctx == SelectContext.MAIN and opt.type == OptionType.PLAY:
        if getattr(obs.current, "supporterPlayed", False):
            return score, reason
        card = option_card(obs, opt)
        cid = card.id if card else None
        if cid != BOSS:
            return score, reason
        threats = _iono_killable_threats(obs)
        if not threats:
            return score, reason
        remaining = len(my_state(obs).prize)
        best_pv = max(prize_value(t) for t in threats)
        # Lethal close via Boss path
        if best_pv >= remaining:
            return max(score, 55000), "Iono R14w: LETHAL Boss 2-prize"
        return max(score, 28000), "Iono R14w: Boss KO-able Bellibolt/Kilo"

    # SWITCH/TO_ACTIVE (Boss target): hard prefer killable IONO_THREATS
    if ctx in {SelectContext.SWITCH, SelectContext.TO_ACTIVE}:
        card = option_card(obs, opt)
        if not card:
            return score, reason
        yi = obs.current.yourIndex
        pi = getattr(opt, "playerIndex", yi)
        if pi == yi:
            return score, reason
        attacks = planned_archaludon_attacks(obs)
        killable = any(
            effective_damage(atk["damage"], card) >= card.hp for atk in attacks
        ) if attacks else False
        if card.id in IONO_THREATS and killable:
            return max(score, 45000 + prize_value(card) * 3000), "Iono R14w: target 2-prize KO"
        if card.id in IONO_THREATS:
            return max(score, 18000 + energy_count(card) * 200), "Iono R14w: target threat"
        # Soft-down 1-prize Active snipes when a killable threat exists on bench
        if killable and card.id not in IONO_THREATS and _iono_killable_threats(obs):
            return min(score, 8000), "Iono R14w: deprior 1-prize vs threat"

    return score, reason


def _apply_iono_r14y_cape(obs, opt, score, reason):
    """R14y single lever — Hero's Cape on Arch/Dura ASAP vs Iono.

    Loss DS: 100% of losses end with no Active (board wipe by Voltorb). Arch is
    2-prize and dies before Relicanth/MD closes. +30 HP tool is the cheapest
    survival lever that does not rewire attack selection.

    Pure single lever (no r14n stack) for A/B.
    """
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return score, reason
    if opt.type != OptionType.PLAY:
        return score, reason
    card = option_card(obs, opt)
    cid = card.id if card else None
    if cid != HERO_CAPE:
        return score, reason
    targets = [
        p
        for p in all_my_pokemon(obs)
        if p and p.id in {ARCHALUDON_EX, DURALUDON} and not has_tool(p)
    ]
    if not targets:
        return score, reason
    # Prefer Caping Arch; still worth it on Dura that will evolve
    has_arch = any(p.id == ARCHALUDON_EX for p in targets)
    return max(score, 24000 if has_arch else 18000), (
        "Iono R14y: Cape Arch" if has_arch else "Iono R14y: Cape Dura"
    )


def _apply_iono_overrides(obs, opt, score, reason):
    """Legacy full R14 (kept for A/B; do not wire — regressed). Prefer light path."""
    return _apply_iono_light_overrides(obs, opt, score, reason)


def _apply_iono_light_overrides(obs, opt, score, reason):
    """R14k — R14j + END penalty when attack available.

    Base (safe): MD/RH lethal, Active metal attach, Relicanth for MD, Boss >=2e.
    + ONE new lever (R14i): Cinderace Turbo Flare (965) when Dura is on bench.
    """
    card = option_card(obs, opt)
    cid = card.id if card else getattr(opt, "cardId", None)
    active = active_pokemon(obs)
    opp_act = opp_active_pokemon(obs)

    # Never gift free Lightning turn if we can attack or attach
    if opt.type == OptionType.END and obs.select.context == SelectContext.MAIN:
        if planned_archaludon_attacks(obs):
            return score - 6000, "Iono: attack over END"
        if not obs.current.energyAttached and METAL_ENERGY in hand_ids(obs):
            return score - 4000, "Iono: attach over END"

    # Boss early threats (Bellibolt/Kilowattrel) before they load energy
    if opt.type == OptionType.PLAY and cid == BOSS:
        threats = [
            p for p in ([opp_act] if opp_act else []) + list(opp_bench_pokemon(obs) or [])
            if p and p.id in IONO_THREATS
        ]
        if threats:
            return max(score, 19000), "Iono: Boss threat off bench/active"
        return max(score, 8000), "Iono: Boss available"

    if opt.type == OptionType.PLAY and cid == RELICANTH and not has_in_play(obs, RELICANTH):
        return max(score, 15000), "Iono: Relicanth for MD race"

    if opt.type == OptionType.EVOLVE and cid == ARCHALUDON_EX:
        return max(score, 18000), "Iono: evolve for 220 MD"

    if opt.type == OptionType.ATTACH:
        target = option_target(obs, opt)
        area = getattr(opt, "inPlayArea", None)
        tid = target.id if target else None
        if area == AreaType.ACTIVE and tid in {DURALUDON, ARCHALUDON_EX}:
            return score + 9000, "Iono: Active metal race"
        if area == AreaType.ACTIVE and tid == CINDERACE and energy_count(target or active_pokemon(obs) or type("X", (), {"id": 0})()) < 1:
            return score + 7000, "Iono: enable Turbo Flare"

    if opt.type == OptionType.ATTACK and opp_act and active:
        aid = getattr(opt, "attackId", None)
        if aid == METAL_DEFENDER and has_in_play(obs, RELICANTH):
            if effective_damage(220, opp_act) >= opp_act.hp:
                return max(score, score + 4000), "Iono: MD lethal"
            if opp_act.id in IONO_LINE and energy_count(opp_act) <= 1:
                return max(score, score + 1000), "Iono: MD unloaded"
        if aid == RAGING_HAMMER:
            rh = 80 + damage_on(active) // 10 * 10
            if effective_damage(rh, opp_act) >= opp_act.hp:
                return max(score, score + 3500), "Iono: RH lethal"
        # R14i single new lever
        if aid == 965 and active and active.id == CINDERACE:
            if any(p and p.id == DURALUDON for p in (my_state(obs).bench or [])):
                return max(score, score + 3500), "Iono: Turbo Flare -> bench Dura"

    if opt.type == OptionType.ATTACH:
        target = option_target(obs, opt)
        tid = target.id if target else None
        if getattr(opt, "inPlayArea", None) == AreaType.ACTIVE and tid in {
            DURALUDON,
            ARCHALUDON_EX,
        }:
            return score + 1500, "Iono: Active metal attach"

    if opt.type == OptionType.PLAY and cid == RELICANTH and not has_in_play(obs, RELICANTH):
        if has_in_play(obs, DURALUDON) or has_in_play(obs, ARCHALUDON_EX):
            return max(score, score + 1200), "Iono: Relicanth for MD"

    if opt.type == OptionType.PLAY and cid == BOSS and not obs.current.supporterPlayed:
        threats = [
            p
            for p in opp_bench_pokemon(obs)
            if p and p.id in IONO_THREATS and energy_count(p) >= 2
        ]
        if threats and planned_archaludon_attacks(obs):
            return max(score, score + 1800), "Iono: Boss loaded threat"

    # R14j single lever: FML ASAP vs Lightning chip (don't wait for ex online)
    if opt.type == OptionType.PLAY and cid == FULL_METAL_LAB:
        return max(score, score + 2500), "Iono: FML ASAP (R14j)"

    return score, reason


def _apply_dragapult_light_overrides(obs, opt, score, reason):
    """R16c — Dragapult: prize-race attach cap + KO priority (no over-evolve).

    Global R11 attach cap is wired; here only matchup-specific KO/Boss/FML.
    """
    card = option_card(obs, opt)
    cid = card.id if card else getattr(opt, "cardId", None)
    ctx = obs.select.context
    active = active_pokemon(obs)
    opp_act = opp_active_pokemon(obs)
    lethal = _main_legal_attack_ko(obs)

    # Extra attach discipline when behind: no bench attach if we can attack
    our_prizes, opp_prizes = _prize_counts(obs)
    if (
        opt.type == OptionType.ATTACH
        and ctx == SelectContext.MAIN
        and our_prizes > opp_prizes
        and planned_archaludon_attacks(obs)
    ):
        if getattr(opt, "inPlayArea", None) == AreaType.BENCH:
            return min(score, 2000), "Draga: no bench attach when prize-behind"

    if opt.type == OptionType.END and ctx == SelectContext.MAIN and lethal:
        return score - 5000, "Draga: take KO over END"

    if opt.type == OptionType.ATTACK and opp_act and active:
        aid = getattr(opt, "attackId", None)
        if aid == METAL_DEFENDER and has_in_play(obs, RELICANTH):
            if effective_damage(220, opp_act) >= opp_act.hp:
                return max(score, score + 5000), "Draga: MD lethal"
            if opp_act.id == DRAGAPULT_EX:
                return max(score, score + 2200), "Draga: MD into ex"
        if aid == RAGING_HAMMER:
            rh = 80 + damage_on(active) // 10 * 10
            if effective_damage(rh, opp_act) >= opp_act.hp:
                return max(score, score + 4500), "Draga: RH lethal"
            if opp_act.id == DRAKLOAK and energy_count(opp_act) <= 2:
                return max(score, score + 1500), "Draga: RH chip Drakloak"

    if opt.type == OptionType.PLAY and cid == BOSS and not obs.current.supporterPlayed:
        bench_ex = [p for p in opp_bench_pokemon(obs) if p and p.id == DRAGAPULT_EX]
        if bench_ex and planned_archaludon_attacks(obs) and active and active.id in {
            ARCHALUDON_EX,
            DURALUDON,
        }:
            if opp_act and opp_act.id in {119, DRAKLOAK}:
                return max(score, score + 2800), "Draga: Boss pull ex"
            if any(energy_count(p) >= 2 for p in bench_ex):
                return max(score, score + 2000), "Draga: Boss loaded ex"

    if opt.type == OptionType.PLAY and cid == FULL_METAL_LAB:
        if active and active.id in {DURALUDON, ARCHALUDON_EX}:
            return max(score, score + 1500), "Draga: FML vs Dive"

    if opt.type == OptionType.ATTACH and not lethal:
        target = option_target(obs, opt)
        tid = target.id if target else None
        if getattr(opt, "inPlayArea", None) == AreaType.ACTIVE and tid in {
            DURALUDON,
            ARCHALUDON_EX,
        }:
            if target and energy_count(target) < 3:
                return score + 1200, "Draga: Active metal"

    if opt.type == OptionType.PLAY and cid == RELICANTH and not has_in_play(obs, RELICANTH):
        opp_ids = {p.id for p in (opp_state(obs).active + opp_state(obs).bench) if p}
        if DRAGAPULT_EX in opp_ids or DRAKLOAK in opp_ids:
            if has_in_play(obs, DURALUDON) or has_in_play(obs, ARCHALUDON_EX):
                return max(score, score + 1300), "Draga: Relicanth for MD"

    return score, reason


# ── Scoring ──

def score_setup(obs, opt):
    card = option_card(obs, opt)
    cid = card.id if card else None
    ctx = obs.select.context

    if ctx == SelectContext.MULLIGAN:
        return (10000, "no mulligan") if opt.type == OptionType.NO else (0, "mulligan")
    if ctx == SelectContext.IS_FIRST:
        return (10000, "choose second") if opt.type == OptionType.NO else (0, "go first")
    if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
        return _SETUP_ACTIVE_PRIORITY.get(cid, (0, "unknown Active"))
    if ctx == SelectContext.SETUP_BENCH_POKEMON:
        if cid in _SETUP_BENCH_PRIORITY:
            return _SETUP_BENCH_PRIORITY[cid]
        return -10000, "skip non-basic setup bench"
    return 0, "non-setup"


_ICE_CREAM_HP_THRESHOLD = {
    "lucario": 270,
    "starmie": 210,
    "crustle": 120,
    "grimmsnarl": 280,
    "iono": 240,
    "dragapult": 230,
    "alakazam": 200,  # floor/ceiling path preferred; threshold fallback
    "hop": 220,
    "generic": 230,
}


def should_skip_ice_cream(obs, active):
    """Ice Cream policy: sample_75wr Alakazam all-or-nothing + matchup HP floors."""
    if active.id != ARCHALUDON_EX:
        return True, "skip Ice Cream: not Archaludon ex"
    opp_act = opp_active_pokemon(obs)
    if opp_act and has_in_play(obs, RELICANTH):
        md_kills = effective_damage(220, opp_act) >= opp_act.hp
        if not md_kills:
            rh_dmg = 80 + damage_on(active) // 10 * 10
            rh_after = 80 + max(0, damage_on(active) - 80) // 10 * 10
            if effective_damage(rh_dmg, opp_act) >= opp_act.hp and effective_damage(rh_after, opp_act) < opp_act.hp:
                return True, "skip Ice Cream: healing loses Raging Hammer KO"
    matchup = detect_matchup(obs)
    # sample_75wr: Alakazam — only heal if multi-Ice reaches survival band
    if matchup == "alakazam":
        floor, ceiling, _ = _estimate_alakazam(obs)
        attacks = planned_archaludon_attacks(obs)
        if opp_act and attacks and any(effective_damage(a["damage"], opp_act) >= opp_act.hp for a in attacks):
            _, ceiling, _ = _estimate_alakazam_from_pokes(
                opp_state(obs),
                ([opp_act] if opp_act else []) + list(opp_bench_pokemon(obs) or []),
            )
        ice_count = sum(1 for c in (my_state(obs).hand or []) if c and c.id == JUMBO_ICE_CREAM)
        max_hp = getattr(active, "maxHp", active.hp)
        hp_after_all = min(max_hp, active.hp + ice_count * 80)
        if hp_after_all <= active.hp:
            return True, "skip Ice Cream: no effective healing"
        if floor and hp_after_all < floor:
            return True, f"skip Ice Cream: even {ice_count}x heal ({hp_after_all}) < floor {floor}"
        if ceiling and hp_after_all >= ceiling:
            return False, f"use Ice Cream: {ice_count}x heal ({hp_after_all}) >= ceil {ceiling}"
        return False, f"use Ice Cream: band floor={floor} ceil={ceiling}"
    # Starmie: tighter heal — 210 burst common; stay under KO range for trade
    if matchup == "starmie":
        threshold = 210
        if active.hp > threshold:
            return True, f"skip Ice Cream: HP {active.hp} > {threshold} (starmie)"
        # Prefer heal when under 210 so we survive next star attack
        return False, "use Ice Cream: starmie survival"
    threshold = _ICE_CREAM_HP_THRESHOLD.get(matchup, 220)
    if active.hp > threshold:
        return True, f"skip Ice Cream: HP {active.hp} > {threshold} ({matchup})"
    return False, ""


ITEMS = {POKE_PAD, ULTRA_BALL, POKEGEAR, NIGHT_STRETCHER, JUMBO_ICE_CREAM, HERO_CAPE}


def score_play(obs, opt):
    card = option_card(obs, opt)
    cid = card.id if card else None
    ids = hand_ids(obs)

    if cid in {DURALUDON, RELICANTH}:
        bench_empty = len([p for p in my_state(obs).bench if p]) == 0
        if bench_empty:
            return 50000, "play Pokemon (empty bench — R7)"
        return 18000, "play Pokemon"

    if cid == FULL_METAL_LAB:
        active = active_pokemon(obs)
        if active and active.id not in {DURALUDON, ARCHALUDON_EX}:
            return -200, "skip FML: Active not Metal"
        return 20000, "play Full Metal Lab"

    if cid in ITEMS:
        if cid == HERO_CAPE:
            if not any(p.id in {ARCHALUDON_EX, DURALUDON} and not has_tool(p) for p in all_my_pokemon(obs)):
                return -500, "save Hero's Cape: no target"
        if cid == JUMBO_ICE_CREAM:
            active = active_pokemon(obs)
            if active:
                skip, reason = should_skip_ice_cream(obs, active)
                if skip:
                    return -500, reason
        if cid == NIGHT_STRETCHER:
            disc = discard_ids(obs)
            matchup = detect_matchup(obs)
            # Crustle/majkel: Hammer puts metal in discard — recover aggressively
            if matchup == "crustle" and METAL_ENERGY in disc:
                if _energy_starved(obs) or _opp_hammer_seen(obs) or metal_in_discard(obs) >= 2:
                    return 24000, "Hammer: Night Stretcher metal"
                return 12000, "Crustle: Stretcher metal available"
            has_urgent = (
                (DURALUDON in disc and DURALUDON not in ids and count_in_play(obs, DURALUDON) + count_in_play(obs, ARCHALUDON_EX) <= 1)
                or (ARCHALUDON_EX in disc and ARCHALUDON_EX not in ids and has_in_play(obs, DURALUDON))
                or (METAL_ENERGY in disc and not obs.current.energyAttached
                    and sum(1 for c in (my_state(obs).hand or []) if c and c.id == METAL_ENERGY) == 0
                    and any(p and p.id in (DURALUDON, ARCHALUDON_EX) and energy_count(p) == 2 for p in all_my_pokemon(obs)))
            )
            if not has_urgent:
                return -500, "save Night Stretcher"
        if cid == ULTRA_BALL:
            bench_empty = len([p for p in my_state(obs).bench if p]) == 0
            if bench_empty:
                return -5000, "Ultra Ball: bench empty (must bench basic first)"
            metal_in_hand = sum(1 for c in (my_state(obs).hand or []) if c and c.id == METAL_ENERGY)
            metal_in_trash = metal_in_discard(obs)
            if metal_in_trash == 0 and metal_in_hand >= 1:
                return 20000, "Ultra Ball: fuel Alloy"
            if safe_discard_count(obs) >= 2 and (need_archaludon(obs) or need_duraludon(obs)):
                return 20000, "Ultra Ball: search line"
            return -1000, "skip Ultra Ball"
        return 20000, "play item"

    if cid == EXPLORER:
        if obs.current.supporterPlayed:
            return -1000, "Supporter already used"
        return 16000, "play Explorer"

    if cid == LILLIE:
        if obs.current.supporterPlayed:
            return -1000, "Supporter already used"
        if BOSS in ids and planned_archaludon_attacks(obs):
            return -500, "save Lillie: Boss in hand with attacker ready"
        return 5000, "play Lillie"

    if cid == BOSS:
        if obs.current.supporterPlayed:
            return -1000, "Supporter already used"
        if detect_matchup(obs) == "hop":
            active = active_pokemon(obs)
            opp_has_snorlax = any(p.id == HOP_SNORLAX for p in opp_bench_pokemon(obs))
            if opp_has_snorlax and active:
                if active.id == CINDERACE:
                    has_dura_bench = any(p.id in {DURALUDON, ARCHALUDON_EX}
                                        for p in my_state(obs).bench if p)
                    if has_dura_bench:
                        return 16500, "Boss: pull Snorlax (Cinderace Turbo Flare)"
                if active.id == ARCHALUDON_EX and active.hp > 220:
                    ok, _ = attack_energy_route(obs, active)
                    if ok:
                        return 16500, "Boss: pull Snorlax (Arch can tank Revenge 220)"
        if _opp_last_attack_id == MEGA_BRAVE:
            return -500, "save Boss: Mega Brave stuck"
        attacks = planned_archaludon_attacks(obs)
        if not attacks:
            return -500, "save Boss: no attacker"
        opp_act = opp_active_pokemon(obs)
        can_ko_active = opp_act and any(
            effective_damage(atk["damage"], opp_act) >= opp_act.hp for atk in attacks)
        remaining = len(my_state(obs).prize)
        if can_ko_active:
            if prize_value(opp_act) >= remaining:
                return -500, "save Boss: Active KO wins"
            for target in opp_bench_pokemon(obs):
                for atk in attacks:
                    if effective_damage(atk["damage"], target) >= target.hp:
                        if prize_value(target) >= remaining:
                            return 20000, "LETHAL Boss"
                        break
            return -500, "save Boss: can KO Active"
        best_score = -500
        best_reason = "save Boss"
        for target in opp_bench_pokemon(obs):
            for atk in attacks:
                if effective_damage(atk["damage"], target) >= target.hp:
                    pv = prize_value(target)
                    if pv >= remaining:
                        return 20000, "LETHAL Boss"
                    s = 4000 + pv * 200 + energy_count(target) * 100
                    if s > best_score:
                        best_score = s
                        best_reason = "Boss: pull bench target"
                    break
        if best_score <= 0:
            metal_total = sum(1 for c in (my_state(obs).hand or []) if c and c.id == METAL_ENERGY)
            metal_total += sum(energy_count(p) for p in all_my_pokemon(obs) if p)
            has_cind = has_in_play(obs, CINDERACE)
            draw_in_hand = any(c and c.id in (EXPLORER, LILLIE) for c in (my_state(obs).hand or []) if c)
            if metal_total <= 2 and not has_cind and not draw_in_hand:
                best_stall = -500
                stall_reason = "save Boss"
                for target in opp_bench_pokemon(obs):
                    te = energy_count(target)
                    cd = CARD_DB.get(target.id)
                    rc = cd.retreatCost if cd else 0
                    min_atk = 99
                    if cd and cd.attacks:
                        for aid in cd.attacks:
                            atk = ALL_ATTACKS.get(aid)
                            if atk:
                                min_atk = min(min_atk, len(atk.energies))
                    if min_atk == 99:
                        min_atk = 1
                    ss = 4000 + rc * 1000 + min_atk * 500 - te * 800
                    if ss > best_stall:
                        best_stall = ss
                        stall_reason = "Boss stall"
                return best_stall, stall_reason
        return best_score, best_reason

    return 1000, "generic play"


def score_evolve(obs, opt):
    card = option_card(obs, opt)
    target = option_target(obs, opt)
    cid = card.id if card else None
    tid = target.id if target else None
    if cid == ARCHALUDON_EX and tid == DURALUDON:
        target_is_active = opt.inPlayArea == AreaType.ACTIVE
        mc = metal_in_discard(obs)
        if target_is_active:
            if energy_count(target) >= 3 and not has_in_play(obs, ARCHALUDON_EX):
                return 17000, "evolve Active 3-energy Duraludon"
            if mc >= 2:
                return 28000 + mc * 2000, "evolve Active Duraludon"
            if mc == 1:
                return 8000, "delay Active evolve: 1 Metal"
            return -500, "hold: no Metal in discard"
        if mc >= 2:
            return 14000 + mc * 1000, "evolve Bench Duraludon"
        return -1000, "hold: evolve Active first"
    return 10000, "generic evolution"


def attach_target_score(obs, target, area):
    if target is None:
        return 0
    cid = target.id
    e = energy_count(target)

    if e >= 3:
        return -5000
    if cid == CINDERACE and e >= 1:
        return -3000

    score = 0
    if cid == CINDERACE:
        score = 3000
        if e == 0:
            score += 7000 + (12000 if area == AreaType.ACTIVE else 5000)
    elif cid in {DURALUDON, ARCHALUDON_EX}:
        score = 6000 if cid == ARCHALUDON_EX else 5500
        score += {2: 12000, 1: 7000, 0: 4000}.get(e, -1000)
        score += 1000 if area == AreaType.ACTIVE else 500
    else:
        score = 1000 + (1000 if e == 0 else 0)

    if target.hp > 0:
        max_hp = getattr(target, "maxHp", target.hp)
        ratio = target.hp / max_hp if max_hp > 0 else 1
        if ratio <= 0.25:
            score -= 1500
        elif ratio <= 0.50:
            score -= 500
        else:
            score += min(1000, target.hp // 40 * 100)
    return score


def score_attach(obs, opt):
    card = option_card(obs, opt)
    target = option_target(obs, opt)
    cid = card.id if card else None
    tid = target.id if target else None

    if cid == HERO_CAPE:
        if tid == ARCHALUDON_EX and target and not has_tool(target):
            return 11000, "Hero's Cape on Archaludon ex"
        if tid == DURALUDON and target and not has_tool(target) and energy_count(target) >= 1:
            return 8000, "Hero's Cape on Duraludon"
        return -1000, "save Hero's Cape"

    if cid != METAL_ENERGY:
        return -500, "skip non-Metal"
    if obs.current.energyAttached:
        return -1000, "already attached"

    return attach_target_score(obs, target, opt.inPlayArea), "attach Metal"


def score_retreat(obs, opt):
    active = active_pokemon(obs)
    if active and active.id == ARCHALUDON_EX and has_tool(active) and active.hp > 200:
        return -5000, "don't retreat HP400 tank"
    route = archaludon_ex_attack_route(obs)
    if route and route["needs_retreat"]:
        return 13000, "retreat to attack-ready ex"
    return -100, "avoid retreat"


_MAIN_DISPATCH = {
    OptionType.PLAY: score_play, OptionType.EVOLVE: score_evolve,
    OptionType.ATTACH: score_attach, OptionType.RETREAT: score_retreat,
}


def score_option(obs, opt):
    ctx = obs.select.context

    if ctx in {SelectContext.IS_FIRST, SelectContext.MULLIGAN,
               SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.SETUP_BENCH_POKEMON}:
        score, reason = score_setup(obs, opt)
        return _empty_bench_basic_score(obs, opt, score, reason)

    if opt.type in {OptionType.YES, OptionType.NO}:
        if ctx == SelectContext.IS_FIRST:
            return score_setup(obs, opt)
        if ctx == SelectContext.ACTIVATE:
            return (100000, "Explosiveness") if opt.type == OptionType.YES else (-100000, "never decline")
        return (1, "yes") if opt.type == OptionType.YES else (0, "no")

    if opt.type == OptionType.NUMBER:
        return (opt.number or 0), "number"

    if ctx == SelectContext.MAIN:
        fn = _MAIN_DISPATCH.get(opt.type)
        if fn:
            score, reason = fn(obs, opt)
        elif opt.type == OptionType.ABILITY:
            score, reason = 1, "ability"
        elif opt.type == OptionType.ATTACK:
            # Use matchup-aware score_attack (was raw damage only — ignored KO/levers)
            score, reason = score_attack(obs, opt)
        elif opt.type == OptionType.END:
            if _bench_is_empty(obs) and _main_has_basic_play(obs):
                score, reason = -50000, "empty bench: must bench basic"
            else:
                score, reason = 0, "end turn"
        else:
            score, reason = 500, "generic MAIN"
    elif ctx == SelectContext.TO_HAND:
        score, reason = score_to_hand(obs, opt)
    elif ctx in {SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD}:
        score, reason = score_discard(obs, opt)
    elif ctx in {SelectContext.ATTACH_TO, SelectContext.TO_FIELD, SelectContext.TO_BENCH,
                 SelectContext.ATTACH_FROM, SelectContext.SWITCH, SelectContext.TO_ACTIVE,
                 SelectContext.HEAL, SelectContext.DAMAGE}:
        score, reason = score_target(obs, opt)
    elif ctx == SelectContext.ATTACK:
        score, reason = score_attack(obs, opt)
    elif opt.type == OptionType.CARD:
        score, reason = score_to_hand(obs, opt)
    elif opt.type == OptionType.ENERGY:
        score, reason = 1000, "energy"
    elif opt.type == OptionType.END:
        score, reason = 0, "end"
    else:
        score, reason = 100, "fallback"

    return apply_overrides(obs, opt, score, reason)


def score_to_hand(obs, opt):
    card = option_card(obs, opt)
    cid = card.id if card else opt.cardId
    ids = hand_ids(obs)
    effect = getattr(obs.select, "effect", None)
    effect_id = effect.id if effect else None

    if effect_id == EXPLORER:
        has_ready = any(p and p.id in (DURALUDON, ARCHALUDON_EX) and energy_count(p) >= 3
                        for p in all_my_pokemon(obs))
        metal_in_hand = sum(1 for c in (my_state(obs).hand or []) if c and c.id == METAL_ENERGY)

        if cid == HERO_CAPE:
            has_target = any(p.id == ARCHALUDON_EX and not has_tool(p) for p in all_my_pokemon(obs))
            return (27000 if has_target else 22000), "Explorer: Hero's Cape"
        if cid == METAL_ENERGY:
            if has_ready or metal_in_hand > 0:
                return 0, "Explorer: skip energy"
            if getattr(opt, 'index', 0) == _first_option_index(obs, METAL_ENERGY):
                return 25000, "Explorer: take 1st energy"
            return 0, "Explorer: skip 2nd energy"
        if cid == ARCHALUDON_EX and need_archaludon(obs):
            return 20000, "Explorer: take Archaludon ex"
        if cid == DURALUDON and need_duraludon(obs):
            return 18000, "Explorer: take Duraludon"
        if cid == RELICANTH and not has_in_play(obs, RELICANTH) and RELICANTH not in ids:
            return 15000, "Explorer: take Relicanth"
        sup_count = sum(1 for c in (my_state(obs).hand or []) if c and c.id in (EXPLORER, LILLIE))
        if cid in (EXPLORER, LILLIE) and sup_count == 0:
            return 12000, "Explorer: take supporter"
        return 0, "Explorer: let discard"

    dura_ex_count = count_in_play(obs, DURALUDON) + count_in_play(obs, ARCHALUDON_EX)
    if cid == DURALUDON and DURALUDON not in ids and dura_ex_count <= 1:
        return 22000, "take Duraludon: backup"
    if cid == ARCHALUDON_EX and need_archaludon(obs):
        return 20000, "take Archaludon ex"
    if cid == DURALUDON and need_duraludon(obs):
        return 18000, "take Duraludon"
    if cid == CINDERACE:
        return -2000, "skip Cinderace"
    if cid == RELICANTH and not has_in_play(obs, RELICANTH):
        return 9000, "take Relicanth"
    if cid == METAL_ENERGY:
        return 8000, "take Metal Energy"
    if cid == EXPLORER and not obs.current.supporterPlayed:
        return 7500, "take Explorer"
    if cid == LILLIE and not obs.current.supporterPlayed:
        return 6500, "take Lillie"
    if cid == HERO_CAPE:
        has_target = any(p.id == ARCHALUDON_EX and not has_tool(p) for p in all_my_pokemon(obs))
        return (6000, "take Hero's Cape") if has_target else (1000, "generic take")
    if cid == FULL_METAL_LAB:
        return 5000, "take Full Metal Lab"
    if cid == BOSS:
        return 2500, "take Boss"
    return 1000, "generic take"


def score_discard(obs, opt):
    card = option_card(obs, opt)
    cid = card.id if card else opt.cardId
    ids = hand_ids(obs)
    mt = metal_in_discard(obs)
    effect = getattr(obs.select, "effect", None)
    effect_id = effect.id if effect else None

    if effect_id == ULTRA_BALL:
        mh = ids.count(METAL_ENERGY)
        if cid == METAL_ENERGY:
            if mt < 2 and mh >= 1:
                if getattr(opt, 'index', None) == _first_option_index(obs, METAL_ENERGY):
                    return 20000, "UB: 1st Metal"
                return 8000, "UB: 2nd Metal"
            return 8000, "UB: Metal"
        if cid == CINDERACE:
            return (18000, "UB: Cinderace") if (mt >= 2 or mh == 0) else (14000, "UB: Cinderace")
        draw_count = ids.count(LILLIE) + ids.count(EXPLORER)
        if cid in (LILLIE, EXPLORER) and draw_count >= 2:
            return (12000 if cid == LILLIE else 11000), "UB: surplus supporter"
        if cid == ULTRA_BALL and ids.count(ULTRA_BALL) > 1:
            return 10000, "UB: duplicate"
        if cid in (LILLIE, EXPLORER) and draw_count <= 1:
            return -3000, "UB: keep last supporter"

    if cid == METAL_ENERGY:
        if mt < 2:
            return 15000, "discard Metal"
        return (12000, "discard extra Metal") if ids.count(METAL_ENERGY) > 1 else (-1000, "keep last Metal")
    if cid == CINDERACE:
        return 10000, "discard Cinderace"
    if cid in {BOSS, FULL_METAL_LAB, POKEGEAR}:
        return 8500, "discard utility"
    if cid in {LILLIE, EXPLORER} and ids.count(cid) > 1:
        return 8000, "discard duplicate supporter"
    if cid == RELICANTH and (has_in_play(obs, RELICANTH) or ids.count(RELICANTH) > 1):
        return 6500, "discard extra Relicanth"
    if cid == ARCHALUDON_EX:
        return -5000, "keep Archaludon ex"
    if cid == DURALUDON:
        return -4000, "keep Duraludon"
    return 1000, "generic discard"


def score_target(obs, opt):
    card = option_card(obs, opt)
    cid = card.id if card else opt.cardId
    ctx = obs.select.context

    if ctx == SelectContext.ATTACH_TO:
        return (5000, "Metal") if cid == METAL_ENERGY else (1000, "attach")

    if ctx == SelectContext.ATTACH_FROM:
        if card and energy_count(card) >= 3:
            return -5000, "skip: 3+ energy"
        if card and cid == CINDERACE and energy_count(card) >= 1:
            return -3000, "skip: Cinderace ready"
        return attach_target_score(obs, card, opt.area), "effect attach"

    if ctx in {SelectContext.TO_FIELD, SelectContext.TO_BENCH}:
        if cid == ARCHALUDON_EX:
            return 18000, "target Archaludon ex"
        if cid == DURALUDON:
            return 16000, "target Duraludon"
        if cid == CINDERACE:
            return 3000, "avoid Cinderace"

    if ctx == SelectContext.HEAL:
        return (20000 + damage_on(card), "heal Archaludon ex") if cid == ARCHALUDON_EX else (damage_on(card), "heal")

    if ctx in {SelectContext.SWITCH, SelectContext.TO_ACTIVE}:
        yi = obs.current.yourIndex
        pi = getattr(opt, 'playerIndex', yi)
        if pi != yi and card:
            if detect_matchup(obs) == "hop" and cid == HOP_SNORLAX and card:
                active = active_pokemon(obs)
                e = energy_count(card)
                tools = len(getattr(card, 'tools', None) or [])
                if active and active.id == CINDERACE:
                    return 30000 - e * 100 - tools * 50 + card.hp, "Boss: Snorlax (immobile target)"
                else:
                    return 30000 + e * 100 + tools * 50 + card.hp, "Boss: Snorlax (biggest threat)"
            pv = prize_value(card)
            te = energy_count(card)
            killable = any(effective_damage(a["damage"], card) >= card.hp
                           for a in planned_archaludon_attacks(obs))
            if killable:
                return 20000 + pv * 3000 + te * 100, "Boss: KO"
            return 5000 + pv * 1000 + te * 200, "Boss: drag"
        if cid == CINDERACE:
            return 16000, "promote Cinderace (retreat 0)"
        if cid == ARCHALUDON_EX:
            return 15000, "promote Archaludon ex"
        if cid == DURALUDON:
            return 8000, "promote Duraludon"
        return 1000, "generic promote"

    if ctx == SelectContext.DAMAGE:
        hp = getattr(card, "hp", 999) if card else 999
        return 10000 - hp, "damage: lowest HP"

    return 1000, "generic target"


def choose_options(obs):
    scored = []
    for i, opt in enumerate(obs.select.option):
        try:
            score, reason = score_option(obs, opt)
        except Exception as e:
            score, reason = -999999, f"error {type(e).__name__}: {e}"
        scored.append((score, i, reason))

    scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)

    selected = []
    for score, i, reason in scored:
        if len(selected) >= obs.select.maxCount:
            break
        if score < 0 and len(selected) >= obs.select.minCount:
            continue
        selected.append(i)

    if len(selected) < obs.select.minCount:
        selected = [i for _, i, _ in scored[:obs.select.minCount]]

    return selected


_tomato_agent = None
_tomato_load_error = None


def _get_tomato_agent():
    """Lazy-load sample_archaludon_75wr agent (Iono-only delegate lever)."""
    global _tomato_agent, _tomato_load_error
    if _tomato_agent is not None:
        return _tomato_agent
    if _tomato_load_error is not None:
        return None
    try:
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(here, "..", "extracted_agents", "sample_archaludon_75wr", "main.py"),
            os.path.join(here, "sample_archaludon_75wr_main.py"),
        ]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if path is None:
            _tomato_load_error = "tomato main.py not found"
            return None
        tomato_dir = os.path.dirname(path)
        spec = importlib.util.spec_from_file_location("sample_archaludon_75wr_iono", path)
        mod = importlib.util.module_from_spec(spec)
        # Ensure tomato resolves its own deck.csv if needed at import
        prev = os.getcwd()
        try:
            os.chdir(tomato_dir)
            spec.loader.exec_module(mod)
        finally:
            os.chdir(prev)
        _tomato_agent = mod.agent
        return _tomato_agent
    except Exception as e:
        _tomato_load_error = f"{type(e).__name__}: {e}"
        return None


# Matchups where OUR specialist levers beat sample_75wr (Crustle wall, etc.).
_TOMATO_EXCLUDE_MATCHUPS = frozenset({
    "crustle", "grimmsnarl", "alakazam", "dragapult", "hop", "starmie", "lucario",
})


_specialist_latched = False


def _should_use_tomato(obs) -> bool:
    """Tomato default for Iono + early generic; keep ours on specialist matchups.

    Rationale (2026-07-31):
      - pure iono-only gate (detect==iono) → ~51.5% n400 (shy of 55)
      - early turns are often matchup=generic → our weak path poisons the board
        before Lightning is visible, then tomato inherits a losing setup
      - pure tomato full-game fails Crustle (~75–80) → must exclude specialist MUs
    """
    try:
        m = detect_matchup(obs)
    except Exception:
        m = "generic"
    excl = _TOMATO_EXCLUDE_MATCHUPS
    # arch single lever KEEP (2026-07-31): alakazam was our worst weighted
    # matchup. Delegating it to sample_75wr moved the alakazam suite
    # 36.98%±1.34 → 54.68%±2.34 (n=200 each, ci95 disjoint) with dual
    # unchanged at 93.0%. Default ON; ARCH_TOMATO_ALAKAZAM=0 restores ours.
    if os.environ.get("ARCH_TOMATO_ALAKAZAM", "1").strip().lower() not in ("0", "off", "false"):
        excl = excl - {"alakazam"}
    # arch R2 single lever KEEP (2026-07-31): dragapult carries the highest field
    # weight (0.365) and was 49.0% with our scorer. Delegating it to sample_75wr
    # moved the 4-deck dragapult suite 66.32%±2.04 → 73.18%±1.19 and `meta`
    # overall 74.06%±1.14 → 78.32%±0.54 (ci95 disjoint both), dual 93.0 → 92.5
    # (NULL, floor held). Default ON; ARCH_TOMATO_DRAGAPULT=0 restores ours.
    if os.environ.get("ARCH_TOMATO_DRAGAPULT", "1").strip().lower() not in ("0", "off", "false"):
        excl = excl - {"dragapult"}
    # arch R4 single lever KEEP (2026-07-31): grimmsnarl was the last big matchup
    # still on our own scorer and it is 65.7% of the live top-band field. Every
    # gate scores it against `opponent_brain: random` and saturates at
    # 97.18%±0.20, so the R13 override table had never been measured against a
    # pilot. Under `intel_pilot_ab.py --pilot rulecore` (3% illegal fallback,
    # U0) the same 3 decks measure our scorer at 74.00%±1.10 vs the sample_75wr
    # delegate at 91.12%±0.47 — +17.12pp, ci95 disjoint, 900 games per arm. So
    # _apply_grimmsnarl_overrides (R13) is a net liability against anything that
    # actually plays the deck; it only looked fine because the pilot was random.
    # Guards, both NULL (flat), no floor touched:
    #   meta 78.48%±0.36 → 78.60%±0.73  (2×se_diff 1.63)
    #   dual 96.40%±0.34 → 96.96%±0.27  (2×se_diff 0.87, floor ≥90 held)
    # meta/dual are flat *because* their grimmsnarl decks are random-piloted and
    # already saturated — the gain is real but invisible to the ship floors.
    # Verified no detection leak: none of the iono / alakazam / crustle /
    # dragapult gate decks contain any GRIMMSNARL_LINE or MUNKIDORI_IDS card, so
    # this cannot move those matchups (their per-opponent swings were seed noise).
    # Default ON; ARCH_TOMATO_GRIMMSNARL=0 restores ours.
    if os.environ.get("ARCH_TOMATO_GRIMMSNARL", "1").strip().lower() not in ("0", "off", "false"):
        excl = excl - {"grimmsnarl"}
    specialist = m in excl
    # arch R3 single lever A/B — verdict NULL, do NOT re-run (2026-07-31).
    # Hypothesis: tomato originally took every "generic" (pre-reveal) turn
    # because generic was also hiding the alakazam and dragapult boards it could
    # not yet identify. Both are now explicit tomato matchups, so "generic" is
    # mostly the opening turns of a crustle / grimmsnarl game — boards our
    # specialist scorer then has to inherit.
    # Measured (5 shards x 50 games/opp): meta 76.66%±0.50 → 77.34%±0.52,
    # diff +0.68 vs 2×se_diff 1.44 → not decisive; dual 93.76 → 93.76 flat.
    # Left env-gated and OFF by default; ARCH_TOMATO_GENERIC=0 restricts tomato
    # to the matchups it explicitly owns.
    if m == "generic" and os.environ.get(
        "ARCH_TOMATO_GENERIC", "1"
    ).strip().lower() in ("0", "off", "false"):
        return False
    # crustle single lever (2026-07-31): detect_matchup is stateless, so once the
    # Crustle / flg shell is KO'd off the board it decays back to "generic" and
    # tomato seizes control mid-game on a board our scorer built. Latch the
    # specialist verdict for the rest of the game instead.
    if os.environ.get("ARCH_CRUSTLE_LEVER", "").strip().lower() == "latch":
        global _specialist_latched
        if specialist:
            _specialist_latched = True
        elif _specialist_latched:
            return False
    return not specialist


# ── Iono BC prior runtime (NumPy-only, optional) ─────────────────────────────

_IONO_BC = None
_IONO_BC_ERROR = None
_BC_OPTION_TYPES = list(OptionType)
_BC_OPTION_TYPE_INDEX = {t: i for i, t in enumerate(_BC_OPTION_TYPES)}


def _to_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def _bc_pokemon_features(pkm):
    if pkm is None:
        return [0.0, 0.0, 0.0]
    hp = _to_int(getattr(pkm, "hp", 0))
    max_hp = _to_int(getattr(pkm, "maxHp", hp), hp)
    return [float(hp), float(max(0, max_hp - hp)), float(energy_count(pkm))]


def _bc_state_vector(obs):
    """Schema-v2 state vector, matched to scripts/collect_iono_decisions.py."""
    me = my_state(obs)
    opp = opp_state(obs)
    act = active_pokemon(obs)
    oact = opp_active_pokemon(obs)
    act_hp, act_dmg, act_en = _bc_pokemon_features(act)
    opp_hp, opp_dmg, opp_en = _bc_pokemon_features(oact)
    act_id = _to_int(getattr(act, "id", 0)) if act else 0
    opp_id = _to_int(getattr(oact, "id", 0)) if oact else 0
    ctx = getattr(getattr(obs, "select", None), "context", None)
    n_opts = len(getattr(getattr(obs, "select", None), "option", None) or [])
    odata = CARD_DB.get(opp_id)
    return [
        float(_to_int(getattr(obs.current, "turn", 0))),
        float(len(getattr(me, "prize", None) or [])),
        float(len(getattr(opp, "prize", None) or [])),
        float(_to_int(getattr(me, "handCount", 0))),
        float(_to_int(getattr(me, "deckCount", 0))),
        float(len(getattr(me, "discard", None) or [])),
        float(len(getattr(me, "bench", None) or [])),
        float(len(getattr(opp, "bench", None) or [])),
        act_hp, act_dmg, act_en,
        float(act_id == DURALUDON),
        float(act_id == ARCHALUDON_EX),
        float(act_id == CINDERACE),
        float(act_id == RELICANTH),
        float(act is None),
        opp_hp, opp_dmg, opp_en,
        float(bool(getattr(odata, "ex", False) or getattr(odata, "megaEx", False))) if oact else 0.0,
        float(opp_id in IONO_THREATS),
        float(ctx == SelectContext.MAIN),
        float(ctx in (SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.SETUP_BENCH_POKEMON)),
        float(ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE, SelectContext.TO_BENCH)),
        float(n_opts),
    ]


def _bc_option_vector(obs, opt):
    vec = [0.0] * len(_BC_OPTION_TYPES)
    idx = _BC_OPTION_TYPE_INDEX.get(getattr(opt, "type", None))
    if idx is not None:
        vec[idx] = 1.0
    card = option_card(obs, opt)
    card_id = _to_int(getattr(card, "id", 0)) if card is not None else _to_int(getattr(opt, "cardId", 0))
    cdata = CARD_DB.get(card_id)
    ctype = getattr(cdata, "cardType", None)
    is_pkm = float(ctype == CardType.POKEMON)
    is_energy = float(ctype in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY))
    targets_opp = 0.0
    try:
        yi = obs.current.yourIndex
        targets_opp = float(opt.playerIndex is not None and opt.playerIndex != yi)
    except Exception:
        pass
    return vec + [float(card_id), is_pkm, is_energy, targets_opp]


def _bc_is_fragile_state(s):
    # Raw schema-v2 indices: my_bench=6, active_energy=10, active Arch=12,
    # active Cinderace=13. Same cluster as analyze_iono_loss_clusters.py.
    return (not (s[12] >= 0.5 or s[13] >= 0.5)) or s[10] < 2.0 or s[6] <= 0.0


def _get_iono_bc():
    """Lazy-load the exported NumPy prior. Missing/failed model means fallback."""
    global _IONO_BC, _IONO_BC_ERROR
    if os.environ.get("ARCH_IONO_BC_ENABLE", "0").strip().lower() not in ("1", "true", "on"):
        return None
    if _IONO_BC is not None:
        return _IONO_BC
    if _IONO_BC_ERROR is not None:
        return None
    try:
        import numpy as np

        env = os.environ.get("ARCH_IONO_BC_NPZ")
        here = os.path.dirname(os.path.abspath(__file__)) if ROOT else os.getcwd()
        candidates = []
        if env:
            candidates.append(env)
        candidates += [
            os.path.join(here, "models", "iono_prior_v2.npz"),
            os.path.join(here, "iono_prior_v2.npz"),
            os.path.join(os.getcwd(), "iono_prior_v2.npz"),
        ]
        path = next((p for p in candidates if p and os.path.exists(p)), None)
        if path is None:
            _IONO_BC_ERROR = "iono_prior_v2.npz not found"
            return None
        z = np.load(path, allow_pickle=True)
        _IONO_BC = {"np": np, "path": path, **{k: z[k] for k in z.files}}
        return _IONO_BC
    except Exception as e:
        _IONO_BC_ERROR = f"{type(e).__name__}: {e}"
        return None


def _silu(np, x):
    return x / (1.0 + np.exp(-x))


def _iono_bc_pick(obs):
    """Return [option_index] from BC prior, or None to fall back to tomato."""
    model = _get_iono_bc()
    if model is None or obs.select is None:
        return None
    opts = list(obs.select.option or [])
    if not opts:
        return None
    # Model was trained only on single-choice decisions.
    if not (obs.select.minCount <= 1 <= obs.select.maxCount):
        return None
    max_options = int(model.get("max_options", [32])[0])
    if len(opts) > max_options:
        return None
    try:
        raw_s = _bc_state_vector(obs)
        scope = os.environ.get("ARCH_IONO_BC_SCOPE", "fragile").strip().lower()
        if scope == "fragile" and not _bc_is_fragile_state(raw_s):
            return None
        np = model["np"]
        s = np.asarray(raw_s, dtype=np.float32)
        s = (s - model["state_mean"]) / model["state_std"]
        o = np.asarray([_bc_option_vector(obs, opt) for opt in opts], dtype=np.float32)
        o[:, -4] = np.log1p(o[:, -4]) / 8.0

        se = _silu(np, s @ model["se0_w"].T + model["se0_b"])
        se = _silu(np, se @ model["se2_w"].T + model["se2_b"])
        oe = _silu(np, o @ model["oe0_w"].T + model["oe0_b"])
        se_exp = np.repeat(se.reshape(1, -1), len(opts), axis=0)
        h = _silu(np, np.concatenate([se_exp, oe], axis=1) @ model["sc0_w"].T + model["sc0_b"])
        logits = (h @ model["sc2_w"].T + model["sc2_b"]).reshape(-1)
        order = np.argsort(logits)[::-1]
        if len(order) < 1:
            return None
        margin = float(os.environ.get("ARCH_IONO_BC_MARGIN", "0.0") or 0.0)
        if len(order) > 1 and float(logits[order[0]] - logits[order[1]]) < margin:
            return None
        return [int(order[0])]
    except Exception:
        return None


def _agent_impl(obs_dict):
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        global _opp_last_attack_id, _cur_turn_logs, _specialist_latched
        _specialist_latched = False
        _opp_last_attack_id = None
        _cur_turn_logs.clear()
        return my_deck
    _update_opp_attack_tracking(obs)
    if not obs.select.option:
        return []

    # Single lever: tomato default except specialist matchups (Crustle/…).
    # A/B: tomato | tomato_md | tomato_strict | r14n | none
    lever = os.environ.get("ARCH_IONO_LEVER", "tomato").strip().lower()
    use_tomato = False
    if lever in (
        "tomato", "75wr", "sample75",
        "tomato_md", "tomato+md", "tomato_lethal",
        "tomato_setup", "tomato+setup",
        "tomato_fork", "tomato+fork",
        "tomato_boss", "tomato+boss",
        "tomato_boss2", "tomato+boss2",
        "tomato_bc", "tomato+bc", "bc",
    ):
        use_tomato = _should_use_tomato(obs)
    elif lever in ("tomato_strict", "iono_only"):
        try:
            use_tomato = detect_matchup(obs) == "iono"
        except Exception:
            use_tomato = False
    if use_tomato:
        if lever in ("tomato_bc", "tomato+bc", "bc"):
            bc = _iono_bc_pick(obs)
            if bc:
                return bc
        if lever in ("tomato_fork", "tomato+fork"):
            try:
                pre = _tomato_fork_preempt(obs)
            except Exception:
                pre = None
            if pre:
                return pre
        if lever in ("tomato_boss", "tomato+boss", "tomato_boss2", "tomato+boss2"):
            try:
                pre = _tomato_boss_preempt(
                    obs, lookahead=lever in ("tomato_boss2", "tomato+boss2")
                )
            except Exception:
                pre = None
            if pre:
                return pre
        ta = _get_tomato_agent()
        if ta is not None:
            try:
                out = ta(obs_dict)
                if isinstance(out, list) and out:
                    lever_pf = os.environ.get("ARCH_IONO_LEVER", "tomato").strip().lower()
                    if lever_pf in ("tomato_md", "tomato+md", "tomato_lethal"):
                        # REJECTED mean ~34.7% — hard-forcing lethal breaks tempo
                        out = _tomato_lethal_postfilter(obs, out)
                    elif lever_pf in ("tomato_setup", "tomato+setup"):
                        out = _tomato_setup_postfilter(obs, out)
                    return out
            except Exception:
                pass  # fall through to our scorer

    try:
        return choose_options(obs)
    except Exception:
        return random.sample(list(range(len(obs.select.option))), obs.select.maxCount)


def _tomato_lethal_postfilter(obs, chosen: list[int]) -> list[int]:
    """Single add-on over tomato: never END/draw when a legal attack KOs Active.

    Diagnosis: tomato mean ~50.7% n1000; gap to 55% ≈4pp. Avoids tempo miss
    when sample_75wr ranks supporter/item above a free prize take.
    """
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return chosen
    opts = list(obs.select.option or [])
    if not opts or not chosen:
        return chosen
    opp_act = opp_active_pokemon(obs)
    if not opp_act:
        return chosen
    lethal_idxs = []
    for i, o in enumerate(opts):
        if o.type != OptionType.ATTACK:
            continue
        aid = getattr(o, "attackId", None) or 0
        dmg = best_attack_damage(obs, aid)
        if effective_damage(dmg, opp_act) >= opp_act.hp:
            lethal_idxs.append(i)
    if not lethal_idxs:
        return chosen
    # If already attacking lethally, keep
    if any(i in lethal_idxs for i in chosen):
        return chosen
    # Prefer highest prize-value style: first lethal index (MD often earlier)
    return [lethal_idxs[0]]


def _tomato_setup_postfilter(obs, chosen: list[int]) -> list[int]:
    """Single add-on over tomato: force setup race pieces vs Lightning wipe.

    Tomato loss DS n200: losses 100% Active=None, Arch present only 10%;
    wins Arch 95%. Setup / keep-Arch online is the gap to 55%.

    Priority (MAIN only):
      1) empty bench → PLAY Dura/Relicanth if legal
      2) Active Dura e>=2 + Arch in hand → EVOLVE Arch
    Soft: only override when tomato chose END/draw/item instead.
    """
    if obs.select is None or obs.select.context != SelectContext.MAIN:
        return chosen
    opts = list(obs.select.option or [])
    if not opts:
        return chosen

    def _is_tempo_waste(idx: int) -> bool:
        if idx < 0 or idx >= len(opts):
            return True
        o = opts[idx]
        if o.type in {OptionType.END, OptionType.RETREAT}:
            return True
        if o.type == OptionType.PLAY:
            card = option_card(obs, o)
            cid = card.id if card else None
            if cid in {LILLIE, EXPLORER, POKE_PAD, POKEGEAR, ULTRA_BALL}:
                return True
        return False

    # 1) empty bench basics
    if _bench_is_empty(obs):
        for i, o in enumerate(opts):
            if o.type != OptionType.PLAY:
                continue
            card = option_card(obs, o)
            if card and card.id in {DURALUDON, RELICANTH}:
                if not chosen or all(_is_tempo_waste(c) for c in chosen):
                    return [i]
                break

    # 2) evolve Active Dura → Arch when energized
    active = active_pokemon(obs)
    if (
        active
        and active.id == DURALUDON
        and energy_count(active) >= 2
        and ARCHALUDON_EX in hand_ids(obs)
    ):
        for i, o in enumerate(opts):
            if o.type != OptionType.EVOLVE:
                continue
            card = option_card(obs, o)
            cid = card.id if card else getattr(o, "cardId", None)
            if cid != ARCHALUDON_EX:
                continue
            target = option_target(obs, o)
            if target and target.id == DURALUDON:
                if not chosen or all(_is_tempo_waste(c) for c in chosen):
                    return [i]
                # even if tomato chose attach, evolve is usually better for Alloy
                if chosen:
                    o0 = opts[chosen[0]] if chosen[0] < len(opts) else None
                    if o0 and o0.type in {OptionType.ATTACH, OptionType.END, OptionType.PLAY}:
                        return [i]
                break

    return chosen


# Bench floor for the tomato_fork lever (how many live bench Pokemon we insist on
# before letting the delegate spend the turn on anything else).
_FORK_BENCH_FLOOR = int(os.environ.get("ARCH_IONO_FORK_FLOOR", "2") or 2)


def _tomato_fork_preempt(obs):
    """PRE-delegation bench-depth floor (lever `tomato_fork`).

    Loss DS n200: 100% of tomato losses end with Active=None, i.e. we run out of
    Pokemon in play after a Lightning wipe. `_tomato_setup_postfilter` (REJECTED,
    50.3% null) only fired when bench was *completely* empty and only when tomato
    had already picked a tempo-waste option, so it never changed the commitment
    decision itself — by the time bench is 0 the recovery line is already gone.

    This lever instead pre-empts the delegate: while live bench < floor, if a
    basic can be benched right now, bench it. Returns an option index list to
    play, or None to hand the decision to tomato as usual.
    """
    if obs.select is None:
        return None
    opts = list(obs.select.option or [])
    if not opts:
        return None
    try:
        bench_n = len([p for p in my_state(obs).bench if p])
    except Exception:
        return None
    if bench_n >= _FORK_BENCH_FLOOR:
        return None

    ctx = obs.select.context
    if ctx == SelectContext.MAIN:
        want = OptionType.PLAY
    elif ctx in {
        SelectContext.SETUP_BENCH_POKEMON,
        SelectContext.TO_BENCH,
        SelectContext.TO_FIELD,
    }:
        want = OptionType.CARD
    else:
        return None

    # Prefer Duraludon (evolves into Archaludon ex, our win condition) over Relicanth.
    fallback = None
    for i, o in enumerate(opts):
        if o.type != want:
            continue
        card = option_card(obs, o)
        cid = card.id if card else None
        if cid == DURALUDON:
            return [i]
        if cid == RELICANTH and fallback is None:
            fallback = i
    return [fallback] if fallback is not None else None


def _boss2_loaded_threats(obs, attacks):
    """Tier-2 target set for `tomato_boss2`: the benched 2-prize IONO_THREAT
    (Bellibolt ex / Kilowattrel) already holding >= 2 energy that our planned
    attack two-shots. That Pokemon is the one promoted fully charged the moment
    our active dies, so dragging it up now starts the two-shot on our terms.
    """
    best = max((a["damage"] for a in attacks), default=0)
    if best <= 0:
        return []
    out = []
    for t in opp_bench_pokemon(obs):
        if not t or t.id not in IONO_THREATS or energy_count(t) < 2:
            continue
        hp = getattr(t, "hp", None)
        if not hp or effective_damage(best, t) * 2 < hp:
            continue
        out.append(t)
    return out


def _boss2_active_is_loaded_threat(obs) -> bool:
    """Gusting a loaded threat while one is already Active is a sidegrade."""
    oact = opp_active_pokemon(obs)
    return bool(oact is not None and oact.id in IONO_THREATS and energy_count(oact) >= 2)


def _tomato_boss_preempt(obs, lookahead: bool = False):
    """PRE-delegation gust-for-the-KO (lever `tomato_boss`).

    `lookahead=True` is the `tomato_boss2` widening: tier 1 (immediate KO) is
    unchanged and still wins whenever it applies, but when no bench target dies
    this turn we also gust a `_boss2_loaded_threats` target. Rationale: the
    immediate-KO condition only fires ~0.7x/game against a delegate that
    declines 95.4% of legal Bosses, so the mechanism is target-starved, not
    wrong.

    Bucket-matched regret over 13380 schema-v2 games
    (`recordings/intel/iono_fragile_transition.md`): inside matched
    (bench, active energy, turn band, own prizes) buckets, PLAY Boss's Orders
    is 89.42% WR when taken (n=3706) vs 67.62% when legal and declined
    (n=77655), ci95 disjoint — the delegate takes a legal Boss on only 4.6% of
    chances and usually spends the supporter on draw instead.

    The same scan closed the bench-depth family: when the bench first empties
    post-setup, a bench play is legal in only 11.55% of cases, which is why
    `tomato_fork` was NULL at floors 2 and 3 — there is nothing to bench.

    Unlike REJECTED R14w (25.2%), this does not swap in our own scorer: tomato
    still plays the whole game, we only pre-empt this one decision, and only
    when the gust converts into an immediate KO we could not otherwise take.
    Returns an option index list, or None to defer to the delegate.
    """
    if obs.select is None:
        return None
    opts = list(obs.select.option or [])
    if not opts:
        return None
    ctx = obs.select.context

    if ctx == SelectContext.MAIN:
        if getattr(obs.current, "supporterPlayed", False):
            return None
        boss_idx = None
        for i, o in enumerate(opts):
            if o.type != OptionType.PLAY:
                continue
            card = option_card(obs, o)
            if card and card.id == BOSS:
                boss_idx = i
                break
        if boss_idx is None:
            return None
        attacks = planned_archaludon_attacks(obs)
        if not attacks:
            return None
        killable = [
            t for t in opp_bench_pokemon(obs)
            if t and any(effective_damage(a["damage"], t) >= t.hp for a in attacks)
        ]
        if not killable:
            if not lookahead or _boss2_active_is_loaded_threat(obs):
                return None
            return [boss_idx] if _boss2_loaded_threats(obs, attacks) else None
        # Taking the prize already in front of us is at least as good unless the
        # bench holds a fatter target, so only gust when it gains prize value.
        oact = opp_active_pokemon(obs)
        if oact is not None and any(
            effective_damage(a["damage"], oact) >= oact.hp for a in attacks
        ):
            if max(prize_value(t) for t in killable) <= prize_value(oact):
                return None
        return [boss_idx]

    # Boss target select: take the KO-able opponent Pokemon worth the most prizes.
    if ctx in {SelectContext.SWITCH, SelectContext.TO_ACTIVE}:
        attacks = planned_archaludon_attacks(obs)
        if not attacks:
            return None
        yi = obs.current.yourIndex
        best = None
        alt = None  # tier-2 (`tomato_boss2`): loaded threat we only two-shot
        bestdmg = max((a["damage"] for a in attacks), default=0)
        for i, o in enumerate(opts):
            if o.playerIndex is None or o.playerIndex == yi:
                return None  # our own promotion — never hijack it
            target = option_card(obs, o)
            hp = getattr(target, "hp", None)
            if target is None or hp is None:
                continue
            if any(effective_damage(a["damage"], target) >= hp for a in attacks):
                key = (prize_value(target), -hp)
                if best is None or key > best[0]:
                    best = (key, i)
            elif (
                lookahead
                and target.id in IONO_THREATS
                and energy_count(target) >= 2
                and effective_damage(bestdmg, target) * 2 >= hp
            ):
                key = (energy_count(target), -hp)
                if alt is None or key > alt[0]:
                    alt = (key, i)
        if best is not None:
            return [best[1]]
        return [alt[1]] if alt is not None else None

    return None


def _resolve_deck_path() -> str:
    env = os.environ.get("ARCHALUDON_DECK")
    if env and os.path.exists(env):
        return env
    if os.path.exists("deck.csv"):
        return "deck.csv"
    try:
        here = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        here = None
    if here:
        packaged = os.path.join(here, "deck.csv")
        if os.path.exists(packaged):
            return packaged
        # Canonical 75wr shell (also written to archaludon_ex_cinderace.csv)
        for name in (
            "archaludon_ex_cinderace.csv",
            "nb_archaludon_75wr.csv",
            "from_notebooks/sample_archaludon_75wr_out_deck.csv",
        ):
            repo_default = os.path.join(here, "..", "agent_decks", name.replace("/", os.sep))
            if os.path.exists(repo_default):
                return repo_default
    return "/kaggle_simulations/agent/deck.csv"


with open(_resolve_deck_path(), "r", encoding="utf-8") as file:
    _csv = file.read().split("\n")
my_deck = [int(_csv[i]) for i in range(60)]


def _legal_fallback(obs_dict: dict) -> list[int]:
    sel = obs_dict.get("select")
    if sel is None:
        return my_deck
    n = len(sel.get("option", []))
    min_c = int(sel.get("minCount") or 0)
    max_c = int(sel.get("maxCount") or 0)
    if n == 0 or max_c == 0:
        return []
    k = min_c if min_c > 0 else min(1, max_c)
    k = min(k, max_c, n)
    return list(range(k))


def _is_legal(out, obs_dict: dict) -> bool:
    sel = obs_dict.get("select")
    if sel is None:
        return isinstance(out, list) and len(out) == 60
    if not isinstance(out, list):
        return False
    n = len(sel.get("option", []))
    min_c = int(sel.get("minCount") or 0)
    max_c = int(sel.get("maxCount") or 0)
    if len(out) != len(set(out)):
        return False
    if not all(isinstance(i, int) and 0 <= i < n for i in out):
        return False
    return min_c <= len(out) <= max_c


try:
    from agent.archaludon_bench_guard import apply_bench_guard
except ImportError:
    from archaludon_bench_guard import apply_bench_guard


def agent(obs_dict: dict) -> list[int]:
    try:
        raw = _agent_impl(obs_dict)
        bench_on = os.environ.get("ARCHALUDON_BENCH_GUARD", "1") != "0"
        out = apply_bench_guard(obs_dict, raw) if bench_on else raw
        if not _is_legal(out, obs_dict):
            return _legal_fallback(obs_dict)
    except Exception:
        return _legal_fallback(obs_dict)
    return out
