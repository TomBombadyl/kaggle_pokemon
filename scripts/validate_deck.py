"""Deck legality validator for the cabt PTCG engine (Phase 0 foundation).

Validates a 60-card deck (one card ID per line, like agent/deck.csv) against the
card pool in data/EN_Card_Data.csv. Checks the rules we can determine from the
data:

  * exactly 60 card IDs
  * every ID exists in the card pool
  * at least one Basic Pokemon (the engine refuses a deck with no Basic)
  * at most 4 copies of any card, EXCEPT Basic Energy (unlimited)
  * at most 1 ACE SPEC card total
  * evolution-line sanity: every Stage 1 / Stage 2 Pokemon has its immediate
    pre-evolution (by name) present, and an evolution line is rooted by a Basic

Optionally (default on when importable) it also asks the real engine to
``battle_start`` the deck against itself, which is the ultimate legality oracle.

Usage:
    python scripts/validate_deck.py                  # validate every deck in agent_decks/
    python scripts/validate_deck.py --deck agent_decks/pool_dragapult.csv
    python scripts/validate_deck.py --no-engine      # data-only, no engine start
    python scripts/validate_deck.py --cards data/EN_Card_Data.csv

Exit code is 0 only if every validated deck passes.
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CARDS = ROOT / "data" / "EN_Card_Data.csv"
DECK_DIR = ROOT / "agent_decks"
ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"

DECK_SIZE = 60
MAX_COPIES = 4

# Column indices in EN_Card_Data.csv (see header row).
COL_ID = 0
COL_NAME = 1
COL_STAGE = 4   # "Stage (Pokemon)/Type (Energy and Trainer)"
COL_RULE = 5    # e.g. "Pokemon ex", "ACE SPEC"
COL_PREV = 7    # "Previous stage" -> evolvesFrom name, or "n/a"

STAGE_BASIC = "Basic Pokémon"
STAGE_STAGE1 = "Stage 1 Pokémon"
STAGE_STAGE2 = "Stage 2 Pokémon"
STAGE_BASIC_ENERGY = "Basic Energy"


@dataclass(frozen=True)
class CardInfo:
    card_id: int
    name: str
    stage: str
    rule: str
    evolves_from: str | None

    @property
    def is_basic_energy(self) -> bool:
        return self.stage == STAGE_BASIC_ENERGY

    @property
    def is_basic_pokemon(self) -> bool:
        return self.stage == STAGE_BASIC

    @property
    def is_evolution(self) -> bool:
        return self.stage in (STAGE_STAGE1, STAGE_STAGE2)

    @property
    def is_ace_spec(self) -> bool:
        return "ACE SPEC" in (self.rule or "").upper()


def load_card_pool(cards_path: Path = DEFAULT_CARDS) -> dict[int, CardInfo]:
    """Load one CardInfo per card ID from EN_Card_Data.csv (first row wins)."""
    pool: dict[int, CardInfo] = {}
    with cards_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header
        for row in reader:
            if not row or not row[COL_ID].strip():
                continue
            try:
                cid = int(row[COL_ID])
            except ValueError:
                continue
            if cid in pool:
                continue
            prev = (row[COL_PREV] or "").strip()
            pool[cid] = CardInfo(
                card_id=cid,
                name=(row[COL_NAME] or "").strip(),
                stage=(row[COL_STAGE] or "").strip(),
                rule=(row[COL_RULE] or "").strip(),
                evolves_from=None if prev in ("", "n/a") else prev,
            )
    return pool


def load_deck(path: Path) -> list[int]:
    """Read card IDs (one per line). Blank lines ignored."""
    ids: list[int] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for raw in fh:
            cell = raw.strip()
            if cell:
                ids.append(int(cell))
    return ids


def validate_deck(
    ids: list[int], pool: dict[int, CardInfo]
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). A deck is legal iff errors is empty."""
    errors: list[str] = []
    warnings: list[str] = []

    if len(ids) != DECK_SIZE:
        errors.append(f"deck has {len(ids)} cards, must be exactly {DECK_SIZE}")

    unknown = sorted({cid for cid in ids if cid not in pool})
    if unknown:
        errors.append(f"unknown card IDs not in pool: {unknown}")

    known_ids = [cid for cid in ids if cid in pool]
    cards = [pool[cid] for cid in known_ids]

    # Copy limits (basic energy is exempt).
    counts: dict[int, int] = {}
    for cid in known_ids:
        counts[cid] = counts.get(cid, 0) + 1
    for cid, n in sorted(counts.items()):
        info = pool[cid]
        if info.is_basic_energy:
            continue
        if n > MAX_COPIES:
            errors.append(
                f"{n} copies of {cid} ({info.name}); max {MAX_COPIES} for non-energy"
            )

    # ACE SPEC: at most 1 in the whole deck.
    ace = [cid for cid in known_ids if pool[cid].is_ace_spec]
    if len(ace) > 1:
        names = ", ".join(f"{cid} ({pool[cid].name})" for cid in ace)
        errors.append(f"{len(ace)} ACE SPEC cards (max 1): {names}")

    # Must have a Basic Pokemon or the engine cannot set up an Active.
    if not any(c.is_basic_pokemon for c in cards):
        errors.append("no Basic Pokemon in deck (engine needs at least one)")

    # Evolution-line sanity.
    names_in_deck = {c.name for c in cards}
    basic_names = {c.name for c in cards if c.is_basic_pokemon}
    stage1_by_name = {c.name for c in cards if c.stage == STAGE_STAGE1}
    for c in cards:
        if not c.is_evolution:
            continue
        if c.evolves_from is None:
            warnings.append(
                f"{c.card_id} ({c.name}) is {c.stage} but has no recorded pre-evolution"
            )
            continue
        if c.evolves_from not in names_in_deck:
            errors.append(
                f"{c.card_id} ({c.name}) needs pre-evolution "
                f"'{c.evolves_from}' which is not in the deck"
            )
        if c.stage == STAGE_STAGE2:
            # The Stage 1 evolves from some Basic; make sure a Basic roots the line.
            pre = c.evolves_from
            roots_ok = pre in stage1_by_name and any(
                pool_card.evolves_from in basic_names
                for pool_card in cards
                if pool_card.name == pre and pool_card.stage == STAGE_STAGE1
            )
            if not roots_ok and not basic_names:
                errors.append(
                    f"{c.card_id} ({c.name}) Stage 2 line has no Basic root in deck"
                )
    return errors, warnings


def engine_battle_start_ok(ids: list[int]) -> tuple[bool, str]:
    """Try to battle_start the deck vs itself via the real engine.

    Returns (ok, message). Imports are lazy so the data-only validator works
    without the engine present.
    """
    if str(ENGINE_DIR) not in sys.path:
        sys.path.insert(0, str(ENGINE_DIR))
    try:
        from cg import game  # noqa: WPS433 (local import by design)
    except Exception as exc:  # pragma: no cover - engine not available
        return False, f"engine import failed: {exc!r}"
    try:
        obs, start = game.battle_start(list(ids), list(ids))
        if obs is None:
            err = getattr(start, "errorType", "?")
            return False, f"battle_start returned no observation (errorType={err})"
        return True, "battle_start ok"
    except Exception as exc:  # pragma: no cover - depends on native lib
        return False, f"battle_start raised: {exc!r}"
    finally:
        try:
            from cg import game  # noqa: WPS433

            game.battle_finish()
        except Exception:
            pass


def _print_deck_report(
    name: str, errors: list[str], warnings: list[str],
    engine_ok: bool | None, engine_msg: str,
) -> bool:
    passed = not errors and (engine_ok is not False)
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    for w in warnings:
        print(f"    warn:  {w}")
    for e in errors:
        print(f"    error: {e}")
    if engine_ok is not None:
        tag = "ok" if engine_ok else "FAIL"
        print(f"    engine: {tag}: {engine_msg}")
    return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deck", action="append", default=[],
        help="A deck CSV to validate. Repeatable. Default: all of agent_decks/*.csv",
    )
    parser.add_argument("--cards", default=str(DEFAULT_CARDS), help="Card pool CSV.")
    parser.add_argument(
        "--no-engine", action="store_true",
        help="Skip the real-engine battle_start check (data validation only).",
    )
    args = parser.parse_args(argv)

    pool = load_card_pool(Path(args.cards))
    print(f"loaded {len(pool)} cards from {args.cards}")

    if args.deck:
        deck_paths = [Path(d) if Path(d).is_absolute() else ROOT / d for d in args.deck]
    else:
        deck_paths = sorted(DECK_DIR.glob("*.csv"))
    if not deck_paths:
        print("no deck files found")
        return 1

    all_ok = True
    for path in deck_paths:
        try:
            ids = load_deck(path)
        except Exception as exc:
            print(f"[FAIL] {path.name}")
            print(f"    error: could not read deck: {exc!r}")
            all_ok = False
            continue
        errors, warnings = validate_deck(ids, pool)
        engine_ok: bool | None = None
        engine_msg = ""
        if not args.no_engine and not errors:
            engine_ok, engine_msg = engine_battle_start_ok(ids)
        passed = _print_deck_report(path.name, errors, warnings, engine_ok, engine_msg)
        all_ok = all_ok and passed

    print("\nALL PASS" if all_ok else "\nSOME DECKS FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
