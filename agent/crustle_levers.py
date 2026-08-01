"""Crustle MissingNo pilot levers (our side, not anti-Crustle matchup).

Deck spine: Dwebble (344) → Crustle (345) wall + Cornerstone Ogerpon (117)
+ Mega Kangaskhan ex (756) draw engine + Boss's Orders (1182).

Card facts (EN_Card_Data / engine):
  - Crustle Ability *Mysterious Rock Inn*: no damage from opponent Pokemon-ex.
  - Ogerpon Ability *Cornerstone Stance*: no damage from Pokemon with Abilities.
  - Kangaskhan Ability *Run Errand*: Active → draw 2 once/turn.
  - Crustle attack Superb Scissors 120 (G+CC), ignores Active effects.
  - Ogerpon Demolish 140 (F+CC), ignores W/R/effects.

Consumed by rule_core when deck_tech.name == "crustle_missingno".
Keep pure (no engine import at module load) so offline unit tests stay green.
"""

from __future__ import annotations

from typing import Any

# --- identity ---------------------------------------------------------------

CRUSTLE_ID = 345
DWEBBLE_ID = 344
KANGASKHAN_ID = 756
OGERPON_ID = 117
BOSS_ID = 1182

CRUSTLE_LINE = frozenset({DWEBBLE_ID, CRUSTLE_ID})
CRUSTLE_PILOT_IDS = frozenset({DWEBBLE_ID, CRUSTLE_ID, OGERPON_ID, KANGASKHAN_ID})

# Ability Pokemon IDs (Move Name contains [Ability] in EN_Card_Data).
# Used when caller does not pass has_ability; works without cg at import time.
ABILITY_CARD_IDS: frozenset[int] = frozenset(
    {
        28, 36, 37, 44, 49, 56, 57, 66, 72, 74, 75, 79, 80, 81, 83, 86, 90, 93, 96,
        98, 100, 102, 104, 106, 107, 109, 112, 116, 117, 118, 120, 122, 123, 125,
        126, 132, 133, 135, 139, 140, 141, 142, 144, 147, 150, 155, 156, 158, 159,
        167, 170, 173, 174, 175, 180, 182, 184, 190, 198, 202, 203, 205, 207, 209,
        210, 211, 214, 221, 225, 230, 232, 238, 240, 247, 249, 250, 255, 256, 259,
        262, 269, 271, 272, 279, 283, 287, 290, 293, 297, 304, 310, 315, 317, 322,
        326, 330, 340, 342, 343, 345, 351, 353, 356, 357, 359, 362, 380, 383, 392,
        401, 414, 416, 424, 428, 431, 436, 439, 442, 449, 457, 458, 461, 475, 481,
        487, 497, 504, 505, 512, 525, 530, 533, 537, 542, 547, 558, 564, 569, 576,
        596, 598, 604, 618, 623, 631, 637, 641, 648, 652, 666, 674, 675, 685, 688,
        698, 705, 710, 711, 713, 716, 725, 742, 743, 748, 750, 755, 756, 766, 772,
        784, 788, 795, 799, 806, 813, 818, 824, 829, 834, 835, 847, 851, 854, 856,
        858, 859, 866, 871, 882, 886, 896, 898, 901, 903, 904, 911, 915, 924, 962,
        968, 970, 976, 993, 994, 1009, 1019, 1022, 1024, 1027, 1029, 1033, 1036,
        1040, 1045, 1052, 1054, 1059, 1071, 1099, 1136, 1138, 1150, 1151,
    }
)

# Energy attach rank (higher = prefer). Crustle wall first, then Ogerpon
# (ability-immune attacker), then Kangaskhan (draw / finisher).
_ENERGY_PRIORITY: dict[int, float] = {
    CRUSTLE_ID: 100.0,
    OGERPON_ID: 80.0,
    KANGASKHAN_ID: 60.0,
    DWEBBLE_ID: 35.0,
}


def is_crustle_pilot_deck(deck_ids: list[int] | set[int] | frozenset[int]) -> bool:
    """True when the packaged deck is the Crustle MissingNo shell."""
    ids = set(deck_ids)
    return CRUSTLE_LINE.issubset(ids) and (OGERPON_ID in ids or KANGASKHAN_ID in ids)


def card_has_ability(card_id: int) -> bool:
    return int(card_id) in ABILITY_CARD_IDS


def energy_attach_priority(card_id: int) -> float:
    """Crustle > Ogerpon > Kangaskhan > Dwebble > other."""
    return float(_ENERGY_PRIORITY.get(int(card_id), 0.0))


def boss_target_score(card_id: int, is_ex: bool, has_ability: bool) -> float:
    """Score an opponent Pokemon as a Boss's Orders / gust target.

    Crustle walls *ex* damage, so non-ex attackers are the ones that can break
    the wall — they score highest. Non-ex without Ability can also hit Ogerpon
    (Cornerstone Stance), so they get a further bump. Pure ex into an online
    Crustle is low value (damage prevented).
    """
    _ = card_id  # reserved for future per-id overrides (setup stage, etc.)
    if not is_ex:
        # Can damage Crustle — primary wall-breakers.
        score = 1000.0
        if not has_ability:
            # Also punches through Ogerpon Stance → most dangerous.
            score += 250.0
        else:
            # Hits Crustle but bounces off Ogerpon.
            score += 80.0
        return score
    # ex / mega-ex: free damage into Crustle wall; only gust if needed for prizes.
    score = 80.0
    if has_ability:
        score -= 20.0
    return score


def should_promote_crustle(obs: Any) -> bool:
    """True when opponent Active is ex/mega-ex and our Bench has Crustle.

    Safe for both engine Observation objects and raw obs dicts. Returns False
    on any parse failure (never crash the agent).
    """
    try:
        me, opp = _players(obs)
        if me is None or opp is None:
            return False
        opp_active = _first_pokemon(opp, "active")
        if opp_active is None:
            return False
        if not _pokemon_is_ex(opp_active):
            return False
        for p in _pokemon_seq(me, "bench"):
            if p is not None and _pokemon_id(p) == CRUSTLE_ID:
                return True
        return False
    except Exception:
        return False


def active_choice_score(
    card_id: int,
    *,
    opp_active_is_ex: bool = False,
    opp_active_has_ability: bool = False,
    opp_active_is_single_prize: bool = True,
    turn: int = 1,
    select_context: str = "switch",
    energies: int = 0,
    hp: int = 0,
) -> float:
    """Score a candidate for SETUP_ACTIVE / SWITCH / TO_ACTIVE (our side).

    Priority ladder (additive):
      P0  Crustle vs opponent Active ex  — wall on, take free attacks.
      P1  Kangaskhan early (turn ≤ 3 or setup) — Run Errand draw engine.
      P1  Ogerpon vs Ability + single-prize Active — Stance walls them.
      base energy / HP / line presence tie-breaks.
    """
    cid = int(card_id)
    ctx = (select_context or "").lower()
    is_setup = ctx in ("setup_active", "setup_active_pokemon", "setup")
    score = 0.0

    # --- P0: Crustle walls ex Active ---------------------------------------
    if cid == CRUSTLE_ID and opp_active_is_ex:
        score += 5000.0
    elif cid == CRUSTLE_ID:
        score += 400.0 + min(3, max(0, energies)) * 80.0

    # --- P1: Kangaskhan early draw ----------------------------------------
    if cid == KANGASKHAN_ID:
        if is_setup or turn <= 3:
            score += 2200.0
        elif turn <= 6 and not opp_active_is_ex:
            score += 900.0
        else:
            score += 300.0
        # Prefer already-energized finisher later.
        score += min(3, max(0, energies)) * 40.0

    # --- P1: Ogerpon vs Ability single-prize ------------------------------
    if cid == OGERPON_ID:
        if opp_active_has_ability and opp_active_is_single_prize:
            score += 2400.0
        elif opp_active_has_ability:
            score += 1600.0
        elif not opp_active_is_ex:
            score += 700.0
        else:
            # ex Active → prefer Crustle wall over Ogerpon.
            score += 200.0
        score += min(3, max(0, energies)) * 50.0

    # --- Dwebble: evolve fodder, not a preferred Active once Crustle exists
    if cid == DWEBBLE_ID:
        if is_setup:
            score += 800.0  # legal open Basic; evolve ASAP
        else:
            score += 50.0

    # Generic bulk / readiness
    score += max(0, energies) * 15.0
    score += max(0, hp) / 20.0
    return score


# --- observation helpers (dict or typed) ------------------------------------

def _players(obs: Any) -> tuple[Any, Any]:
    """Return (me, opponent) player states."""
    if obs is None:
        return None, None
    # Typed Observation
    state = getattr(obs, "current", None)
    if state is not None and hasattr(state, "players"):
        yi = int(getattr(state, "yourIndex", 0) or 0)
        players = state.players
        if players is None or len(players) < 2:
            return None, None
        return players[yi], players[1 - yi]
    # Raw dict
    if isinstance(obs, dict):
        cur = obs.get("current") or {}
        yi = int(cur.get("yourIndex", 0) or 0)
        players = cur.get("players") or []
        if len(players) < 2:
            return None, None
        return players[yi], players[1 - yi]
    return None, None


def _pokemon_seq(player: Any, area: str) -> list[Any]:
    if player is None:
        return []
    if isinstance(player, dict):
        seq = player.get(area) or []
        return list(seq)
    seq = getattr(player, area, None) or []
    return list(seq)


def _first_pokemon(player: Any, area: str) -> Any | None:
    for p in _pokemon_seq(player, area):
        if p is not None:
            return p
    return None


def _pokemon_id(pokemon: Any) -> int:
    if pokemon is None:
        return 0
    if isinstance(pokemon, dict):
        return int(pokemon.get("id", 0) or 0)
    return int(getattr(pokemon, "id", 0) or 0)


def _pokemon_is_ex(pokemon: Any) -> bool:
    """Best-effort ex/mega-ex check without requiring cg at import."""
    cid = _pokemon_id(pokemon)
    if cid <= 0:
        return False
    # Prefer live engine card table when available.
    try:
        import cg.api as api  # type: ignore

        table = getattr(_pokemon_is_ex, "_table", None)
        if table is None:
            table = {c.cardId: c for c in api.all_card_data()}
            setattr(_pokemon_is_ex, "_table", table)
        data = table.get(cid)
        if data is not None:
            return bool(getattr(data, "ex", False) or getattr(data, "megaEx", False))
    except Exception:
        pass
    # Fallback without engine: common field ex/mega-ex IDs (not exhaustive).
    if cid in _KNOWN_EX_IDS:
        return True
    # Dict path may carry flags from some exporters.
    if isinstance(pokemon, dict):
        if pokemon.get("ex") or pokemon.get("megaEx") or pokemon.get("mega_ex"):
            return True
    return False


# Frequent ladder ex/mega-ex (engine is source of truth when present).
_KNOWN_EX_IDS: frozenset[int] = frozenset(
    {
        OGERPON_ID,
        KANGASKHAN_ID,
        108,  # Wellspring Ogerpon ex
        121,  # Dragapult ex
        269,  # Bellibolt ex family often
        270,
        271,
        678,  # Mega Lucario ex
        721,  # Kyogre ex
        723,  # Mega Abomasnow ex
        743,  # Alakazam MEG
        879,  # Trevenant ex (if present)
    }
)


def opp_active_flags(obs: Any) -> tuple[bool, bool, bool]:
    """(is_ex, has_ability, is_single_prize) for opponent Active."""
    try:
        _, opp = _players(obs)
        active = _first_pokemon(opp, "active")
        if active is None:
            return False, False, True
        cid = _pokemon_id(active)
        is_ex = _pokemon_is_ex(active)
        has_ab = card_has_ability(cid)
        # prize value: ex=2, megaEx=3, else 1 — single prize when not ex.
        single = not is_ex
        try:
            import cg.api as api  # type: ignore

            table = getattr(_pokemon_is_ex, "_table", None)
            if table is None:
                table = {c.cardId: c for c in api.all_card_data()}
                setattr(_pokemon_is_ex, "_table", table)
            data = table.get(cid)
            if data is not None:
                is_ex = bool(data.ex or data.megaEx)
                single = not is_ex
        except Exception:
            pass
        return is_ex, has_ab, single
    except Exception:
        return False, False, True


def promote_score_for_option(
    card_id: int,
    obs: Any,
    *,
    turn: int = 1,
    select_context: str = "switch",
    energies: int = 0,
    hp: int = 0,
) -> float:
    """Convenience: active_choice_score + mandatory Crustle promote boost."""
    is_ex, has_ab, single = opp_active_flags(obs)
    score = active_choice_score(
        card_id,
        opp_active_is_ex=is_ex,
        opp_active_has_ability=has_ab,
        opp_active_is_single_prize=single,
        turn=turn,
        select_context=select_context,
        energies=energies,
        hp=hp,
    )
    if should_promote_crustle(obs) and int(card_id) == CRUSTLE_ID:
        score += 3000.0
    return score


# --- MAIN-phase pilot helpers (rule_core integration) -----------------------

def my_active_id(obs: Any) -> int:
    try:
        me, _ = _players(obs)
        active = _first_pokemon(me, "active")
        return _pokemon_id(active) if active is not None else 0
    except Exception:
        return 0


def my_bench_has(obs: Any, card_id: int) -> bool:
    try:
        me, _ = _players(obs)
        for p in _pokemon_seq(me, "bench"):
            if p is not None and _pokemon_id(p) == int(card_id):
                return True
        return False
    except Exception:
        return False


def best_opp_bench_boss_score(obs: Any) -> float:
    """Max boss_target_score among opponent Bench Pokemon (0 if empty)."""
    try:
        _, opp = _players(obs)
        best = 0.0
        for p in _pokemon_seq(opp, "bench"):
            if p is None:
                continue
            cid = _pokemon_id(p)
            is_ex = _pokemon_is_ex(p)
            has_ab = card_has_ability(cid)
            best = max(best, boss_target_score(cid, is_ex, has_ab))
        return best
    except Exception:
        return 0.0


def should_gust_non_ex(obs: Any, *, min_score: float = 1000.0) -> bool:
    """True when a bench non-ex wall-breaker is worth Boss's Orders.

    Crustle walls ex damage, so the critical gust is a *non-ex* attacker that
    can actually break Mysterious Rock Inn (and ideally also Ogerpon Stance).
    """
    return best_opp_bench_boss_score(obs) >= min_score


def retreat_score_pilot(obs: Any, *, turn: int = 1) -> float:
    """MAIN RETREAT score when we pilot Crustle MissingNo.

    Returns a large positive when we should leave Active (promote wall / draw
    engine / Ogerpon stance), else 0 (caller keeps default scoring).
    """
    try:
        active_id = my_active_id(obs)
        if active_id <= 0:
            return 0.0
        is_ex, has_ab, single = opp_active_flags(obs)

        # P0: leave non-Crustle Active when opp Active is ex and Crustle is benched.
        if should_promote_crustle(obs) and active_id != CRUSTLE_ID:
            return 28000.0

        # P1: early game — if Active is a stuck Dwebble and Kangaskhan is benched,
        # retreat so Run Errand can fire next turn (after promote).
        if turn <= 3 and active_id == DWEBBLE_ID and my_bench_has(obs, KANGASKHAN_ID):
            return 16000.0

        # P1: Ogerpon Stance wall — promote Ogerpon when opp Active is Ability
        # single-prize and we are not already on Ogerpon/Crustle wall.
        if (
            has_ab
            and single
            and active_id not in (OGERPON_ID, CRUSTLE_ID)
            and my_bench_has(obs, OGERPON_ID)
        ):
            return 18000.0

        # Do not retreat off online Crustle vs ex (wall is the whole point).
        if active_id == CRUSTLE_ID and is_ex:
            return -50.0

        # Early Kangaskhan Active: stay for Run Errand (ability scored separately).
        if active_id == KANGASKHAN_ID and turn <= 4 and not is_ex:
            return -20.0

        return 0.0
    except Exception:
        return 0.0


def switch_play_score_pilot(obs: Any, *, turn: int = 1) -> float:
    """MAIN PLAY Switch card score for pilot (0 = defer to default)."""
    r = retreat_score_pilot(obs, turn=turn)
    if r >= 16000.0:
        return min(r + 2000.0, 30000.0)  # Switch preferred over paying retreat
    return 0.0


def boss_play_score_pilot(obs: Any, *, plan_targets_bench: bool = False) -> float:
    """MAIN PLAY Boss's Orders score for pilot.

    Prefer gusting non-ex wall-breakers even when plan has not yet locked a
    bench target (rule_core default only Bosses when plan.target >= 1).
    """
    try:
        if plan_targets_bench:
            return 14000.0
        if should_gust_non_ex(obs):
            # Higher when our Active is Crustle (wall online → remove the threat).
            active_id = my_active_id(obs)
            base = 13000.0 if active_id == CRUSTLE_ID else 11000.0
            return base + min(500.0, best_opp_bench_boss_score(obs) / 5.0)
        return 0.0  # defer / skip
    except Exception:
        return 0.0


def evolve_score_pilot(card_id: int, energies_on_target: int = 0) -> float:
    """Boost for evolving into pilot attackers (Dwebble→Crustle)."""
    cid = int(card_id)
    if cid == CRUSTLE_ID:
        # Always evolve into the wall; energy already on Dwebble is a bonus.
        return 15000.0 + max(0, energies_on_target) * 250.0
    return 0.0


def ability_score_pilot(obs: Any, active_id: int, *, turn: int = 1) -> float:
    """MAIN ABILITY score bias. Kangaskhan Run Errand early is critical.

    Base rule_core already scores ABILITY very high; this adds a pilot-specific
    bump so Run Errand outranks low-value plays when Active is Kangaskhan.
    """
    if int(active_id) == KANGASKHAN_ID:
        # Draw 2 once/turn — always fire when Active is Kangaskhan.
        return 35000.0 if turn <= 8 else 32000.0
    return 0.0  # keep generic ABILITY score


# --- unified decision prior (SearchScorer blend / guard) ---------------------

def decision_prior_our_active(
    card_id: int,
    obs: Any,
    *,
    turn: int = 1,
    select_context: str = "switch",
    energies: int = 0,
    hp: int = 0,
) -> float:
    """Prior mass for our promote/switch/setup-active (vs-ex wall + draw + Ogerpon).

    Used by CrustleSearchScorer as the AlphaZero-style rules prior that guards
    shallow cg search — search may only override when it agrees with top-k prior.
    """
    return promote_score_for_option(
        card_id,
        obs,
        turn=turn,
        select_context=select_context,
        energies=energies,
        hp=hp,
    )


def decision_prior_boss_target(
    card_id: int,
    *,
    is_ex: bool | None = None,
    has_ability: bool | None = None,
) -> float:
    """Prior mass for Boss's Orders / gust targets (opponent Pokemon).

    Prefer non-ex wall-breakers; deprioritize pure ex into online Crustle wall.
    """
    cid = int(card_id)
    if is_ex is None:
        # Fall back to Ability table only; ex flag unknown → treat as non-ex
        # mid-priority so we still prefer known Ability singles when possible.
        is_ex = False
    if has_ability is None:
        has_ability = card_has_ability(cid)
    return boss_target_score(cid, bool(is_ex), bool(has_ability))


def decision_prior_energy_home(card_id: int) -> float:
    """Prior mass for energy attach home: Crustle > Ogerpon > Kangaskhan > Dwebble."""
    return energy_attach_priority(int(card_id))


def decision_prior_card_score(
    card_id: int,
    obs: Any | None = None,
    *,
    side: str = "ours",
    turn: int = 1,
    select_context: str = "switch",
    energies: int = 0,
    hp: int = 0,
    is_ex: bool | None = None,
    has_ability: bool | None = None,
) -> float:
    """Single entry for hybrid search blend: promote / Boss / energy by role.

    side:
      - "ours"   → active_choice / promote prior (needs obs when available)
      - "opp"    → Boss gust target prior
      - "energy" → attach home prior
    """
    role = (side or "ours").lower()
    if role in ("opp", "opponent", "boss", "gust"):
        return decision_prior_boss_target(
            card_id, is_ex=is_ex, has_ability=has_ability,
        )
    if role in ("energy", "attach"):
        return decision_prior_energy_home(card_id)
    if obs is not None:
        return decision_prior_our_active(
            card_id,
            obs,
            turn=turn,
            select_context=select_context,
            energies=energies,
            hp=hp,
        )
    # Offline / no obs: still rank pilot IDs usefully for unit tests & blend.
    return active_choice_score(
        card_id,
        turn=turn,
        select_context=select_context,
        energies=energies,
        hp=hp,
    )
