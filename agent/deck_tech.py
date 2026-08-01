"""Small deck-specific tech tables for otherwise generic scorers.

The rule core stays deck-agnostic. These tables describe card facts that are
not reliably visible from engine card tables alone, such as gust cards or a
non-ex backup attacker line for wall matchups.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeckTech:
    name: str
    gust_cards: frozenset[int] = frozenset()
    switch_cards: frozenset[int] = frozenset()
    draw_cards: frozenset[int] = frozenset()
    search_cards: frozenset[int] = frozenset()
    stadium_cards: frozenset[int] = frozenset()
    non_ex_wall_attackers: frozenset[int] = frozenset()
    non_ex_wall_bases: frozenset[int] = frozenset()
    energy_accel_cards: frozenset[int] = frozenset()
    setup_priority: tuple[tuple[int, float], ...] = ()

    @property
    def wall_line(self) -> frozenset[int]:
        return self.non_ex_wall_attackers | self.non_ex_wall_bases


DEFAULT_TECH = DeckTech(name="default")

LUCARIO_TECH = DeckTech(
    name="mega_lucario_ex",
    gust_cards=frozenset({1182}),  # Boss's Orders
    switch_cards=frozenset({1123}),  # Switch
    draw_cards=frozenset({1192, 1227}),  # Carmine, Lillie's Determination
    search_cards=frozenset({1102, 1141, 1142, 1152}),  # Dusk Ball, PPP, Gong, Pad
    stadium_cards=frozenset({1252}),  # Gravity Mountain
    non_ex_wall_attackers=frozenset({674}),  # Hariyama
    non_ex_wall_bases=frozenset({673}),  # Makuhita
    energy_accel_cards=frozenset({678}),  # Mega Lucario ex
    setup_priority=(
        (677, 45.0),  # Riolu — primary evolution line
        (676, 40.0),  # Solrock — secondary attacker
        (673, 35.0),  # Makuhita — wall line
        (675, -40.0),  # Lunatone — only with Solrock
    ),
)

# pool_alakazam_dudunsparce.csv — Abra/Kadabra/Alakazam (MEG) + Dudunsparce line
ALAKAZAM_TECH = DeckTech(
    name="alakazam_dudunsparce",
    gust_cards=frozenset({1182}),  # Boss's Orders
    switch_cards=frozenset({1123}),  # Switch
    draw_cards=frozenset({1192, 1227, 1224}),  # Carmine, Lillie, Iono
    search_cards=frozenset({1102, 1141}),  # Dusk Ball, Premium Power Pro
    stadium_cards=frozenset({1245}),  # Festival Grounds
    setup_priority=(
        (741, 50.0),  # Abra — bench first
        (65, 45.0),   # Dunsparce
        (742, 30.0),  # Kadabra (evolve line)
        (245, 25.0),  # Alakazam TWM
        (743, 25.0),  # Alakazam MEG
    ),
)

# agent_decks/crustle_MissingNo_rank1.csv — Dwebble/Crustle + Ogerpon + Kangaskhan
CRUSTLE_TECH = DeckTech(
    name="crustle_missingno",
    gust_cards=frozenset({1182}),  # Boss's Orders
    switch_cards=frozenset({1123}),  # Switch
    draw_cards=frozenset({1227, 1225, 1212}),  # Lillie, Hilda, Cook
    search_cards=frozenset({1121, 1086, 1122}),  # Ultra Ball, Buddy Poffin, Pokegear
    stadium_cards=frozenset({1257}),  # Team Rocket's Factory
    # Our wall *is* Crustle; non_ex_wall_* empty (we are not the anti-wall side).
    energy_accel_cards=frozenset({756}),  # Kangaskhan Run Errand (draw)
    setup_priority=(
        (344, 50.0),  # Dwebble — evolve into wall
        (756, 45.0),  # Mega Kangaskhan ex — early draw
        (117, 40.0),  # Cornerstone Ogerpon ex
    ),
)


def tech_for_deck(deck_ids: list[int]) -> DeckTech:
    ids = set(deck_ids)
    if {673, 674, 676, 677, 678}.issubset(ids):
        return LUCARIO_TECH
    if {741, 742}.issubset(ids) and (245 in ids or 743 in ids):
        return ALAKAZAM_TECH
    # Crustle MissingNo shell (Dwebble+Crustle + Ogerpon and/or Kangaskhan)
    if {344, 345}.issubset(ids) and (117 in ids or 756 in ids):
        return CRUSTLE_TECH
    return DEFAULT_TECH
