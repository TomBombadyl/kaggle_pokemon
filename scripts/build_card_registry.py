"""Build the Deck RL card/archetype registry from competition card metadata.

Outputs:
  report/deck_rl/registry.json
  report/deck_rl/candidate_registry.csv
  report/deck_rl/archetype_seed_notes.md

The registry is feature guidance for deck search. Simulator legal options remain
the authority for whether a move/action is selectable in a real game state.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CARDS = ROOT / "data" / "EN_Card_Data.csv"
DEFAULT_BENCHMARK = ROOT / "agent_decks" / "benchmark" / "suite.json"
OUT_DIR = ROOT / "report" / "deck_rl"

STAGE_COL = "Stage (Pokémon)/Type (Energy and Trainer)"
NA = {"", "n/a", "N/A", "None", "none"}
ENERGY_RE = re.compile(r"\{([^}]+)\}")


@dataclass(frozen=True)
class Move:
    name: str
    cost: str
    damage: str
    effect: str


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _is_na(value: str | None) -> bool:
    return _clean(value) in NA


def _read_cards(path: Path) -> dict[int, list[dict[str, str]]]:
    rows_by_id: dict[int, list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            cid = int(row["Card ID"])
            rows_by_id[cid].append(row)
    return dict(sorted(rows_by_id.items()))


def _damage_value(raw: str) -> int:
    m = re.search(r"\d+", raw or "")
    return int(m.group(0)) if m else 0


def _energy_symbols(cost: str) -> list[str]:
    return ENERGY_RE.findall(cost or "")


def _colorless_count(cost: str) -> int:
    return (cost or "").count("●")


def _cost_profile(cost: str) -> dict[str, object]:
    symbols = _energy_symbols(cost)
    colorless = _colorless_count(cost)
    return {
        "raw": cost,
        "types": sorted(set(symbols)),
        "typed_count": len(symbols),
        "colorless_count": colorless,
        "total_count": len(symbols) + colorless,
    }


def _effect_tags(text: str) -> list[str]:
    t = text.lower()
    tags: set[str] = set()
    checks = [
        ("draw", ("draw", "draws")),
        ("search", ("search your deck", "look at the top", "reveal")),
        ("bench_pressure", ("benched pokémon", "benched pokemon", "damage counters")),
        ("targeting", ("choose", "switch 1 of your opponent", "opponent's active")),
        ("discard_self", ("discard", "from this pokémon", "from this pokemon", "top")),
        ("deck_mill_self", ("discard the top", "from your deck")),
        ("energy_acceleration", ("attach", "energy")),
        ("recovery", ("discard pile", "put into your hand", "heal")),
        ("status_control", ("poisoned", "asleep", "paralyzed", "confused", "burned")),
        ("damage_prevention", ("takes", "less damage", "prevent all damage")),
        ("opponent_hand", ("opponent's hand", "opponent’s hand")),
        ("bench_setup", ("put a basic", "onto your bench", "bench")),
    ]
    for tag, needles in checks:
        if all(n in t for n in needles):
            tags.add(tag)
    if "knocked out" in t or "knock out" in t:
        tags.add("ko_effect")
    if "can't use" in t or "can’t use" in t:
        tags.add("cooldown")
    return sorted(tags)


def _simulator_sensitive_tags(text: str) -> list[str]:
    t = text.lower()
    tags: set[str] = set()
    if "draw" in t:
        tags.add("draw_from_empty_deck")
    if "put a basic" in t and "bench" in t:
        tags.add("bench_full_basic_search")
    if "opponent's hand" in t or "opponent’s hand" in t:
        tags.add("opponent_empty_hand")
    if "damage counters" in t and "benched" in t:
        tags.add("spread_or_target_order")
    if "knocked out" in t or "knock out" in t:
        tags.add("simultaneous_ko_prize_order")
    return sorted(tags)


def _trainer_roles(name: str, text: str) -> set[str]:
    n = name.lower()
    t = text.lower()
    roles: set[str] = set()
    if "draw" in t or n in {"iono", "carmine"} or "professor" in n or "lillie" in n:
        roles.add("draw_trainer")
    if "search your deck" in t or "ball" in n or "dusk" in n or "nest" in n:
        roles.add("search_trainer")
    if "switch" in t or "retreat" in t:
        roles.add("switch_trainer")
    if "opponent's active" in t or "opponent’s active" in t or "boss's orders" in n:
        roles.add("gust_targeting")
    if "heal" in t or "discard pile" in t or "recover" in t:
        roles.add("recovery")
    if "attach" in t and "energy" in t:
        roles.add("energy_acceleration")
    if "opponent's hand" in t or "opponent’s hand" in t:
        roles.add("disruption")
    return roles


def _card_record(cid: int, rows: list[dict[str, str]]) -> dict[str, object]:
    first = rows[0]
    name = _clean(first["Card Name"])
    stage = _clean(first[STAGE_COL])
    rule = "" if _is_na(first["Rule"]) else _clean(first["Rule"])
    category = "" if _is_na(first["Category"]) else _clean(first["Category"])
    evolves_from = "" if _is_na(first["Previous stage"]) else _clean(first["Previous stage"])
    effects = " ".join(_clean(r["Effect Explanation"]) for r in rows if not _is_na(r["Effect Explanation"]))
    moves = [
        Move(
            name=_clean(r["Move Name"]),
            cost="" if _is_na(r["Cost"]) else _clean(r["Cost"]),
            damage="" if _is_na(r["Damage"]) else _clean(r["Damage"]),
            effect="" if _is_na(r["Effect Explanation"]) else _clean(r["Effect Explanation"]),
        )
        for r in rows
        if not _is_na(r["Move Name"])
    ]

    roles: set[str] = set()
    if "Energy" in stage:
        roles.add("basic_energy" if stage == "Basic Energy" else "special_energy")
    elif "Pokémon" in stage:
        roles.add("pokemon")
        if stage == "Basic Pokémon":
            roles.add("basic_pokemon")
        elif "Stage 1" in stage:
            roles.add("stage1_pokemon")
        elif "Stage 2" in stage:
            roles.add("stage2_pokemon")
        if moves:
            roles.add("attacker")
            roles.add("basic_attacker" if stage == "Basic Pokémon" else "evolution_attacker")
    else:
        roles.add("trainer")
        roles.update(_trainer_roles(name, effects))
    if rule:
        roles.add("special_rule")
    if "ACE SPEC" in rule.upper():
        roles.add("ace_spec")
    if any("bench_pressure" in _effect_tags(m.effect) or "damage counters" in m.effect.lower() for m in moves):
        roles.add("spread_control")
    if any("energy_acceleration" in _effect_tags(m.effect) for m in moves):
        roles.add("energy_acceleration")

    attack_profiles = []
    attack_types: set[str] = set()
    simulator_flags: set[str] = set()
    for move in moves:
        cost = _cost_profile(move.cost)
        attack_types.update(cost["types"])  # type: ignore[arg-type]
        simulator_flags.update(_simulator_sensitive_tags(move.effect))
        attack_profiles.append(
            {
                "name": move.name,
                "cost": cost,
                "damage_raw": move.damage,
                "damage_value": _damage_value(move.damage),
                "effect_tags": _effect_tags(move.effect),
                "simulator_sensitive": _simulator_sensitive_tags(move.effect),
                "effect": move.effect,
            }
        )

    return {
        "id": cid,
        "name": name,
        "stage": stage,
        "rule": rule,
        "category": category,
        "evolves_from": evolves_from,
        "hp": None if _is_na(first["HP"]) else int(first["HP"]),
        "type": "" if _is_na(first["Type"]) else _clean(first["Type"]),
        "weakness": "" if _is_na(first["Weakness"]) else _clean(first["Weakness"]),
        "retreat": None if _is_na(first["Retreat"]) else int(first["Retreat"]),
        "roles": sorted(roles),
        "attacks": attack_profiles,
        "energy_profile": {
            "printed_type": "" if _is_na(first["Type"]) else _clean(first["Type"]),
            "attack_required_types": sorted(t for t in attack_types if t),
            "max_attack_cost": max((a["cost"]["total_count"] for a in attack_profiles), default=0),
        },
        "simulator_sensitive": sorted(simulator_flags),
    }


def _role_index(cards: dict[int, dict[str, object]]) -> dict[str, list[int]]:
    idx: dict[str, list[int]] = defaultdict(list)
    for cid, rec in cards.items():
        for role in rec["roles"]:  # type: ignore[union-attr]
            idx[str(role)].append(cid)
    return {role: ids for role, ids in sorted(idx.items())}


def _evolution_chains(cards: dict[int, dict[str, object]]) -> dict[str, object]:
    by_name: dict[str, list[int]] = defaultdict(list)
    children: dict[str, list[int]] = defaultdict(list)
    for cid, rec in cards.items():
        by_name[str(rec["name"])].append(cid)
        prev = str(rec.get("evolves_from") or "")
        if prev:
            children[prev].append(cid)
    chains = {}
    for name, ids in sorted(by_name.items()):
        recs = [cards[cid] for cid in ids]
        if any(r["stage"] == "Basic Pokémon" for r in recs) or name in children:
            chains[name] = {
                "ids": sorted(ids),
                "children": sorted(children.get(name, [])),
            }
    return chains


def _load_deck_ids(path: Path) -> list[int]:
    return [int(line.strip()) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _deck_paths(benchmark_path: Path) -> list[Path]:
    paths: dict[str, Path] = {}
    for p in sorted((ROOT / "agent_decks").glob("*.csv")) + [ROOT / "agent" / "deck.csv"]:
        if p.exists():
            paths[str(p.relative_to(ROOT))] = p
    if benchmark_path.exists():
        data = json.loads(benchmark_path.read_text(encoding="utf-8"))
        for row in data.get("decks", []):
            p = ROOT / row["path"]
            if p.exists():
                paths[str(p.relative_to(ROOT))] = p
    return [paths[k] for k in sorted(paths)]


def _deck_summary(path: Path, cards: dict[int, dict[str, object]]) -> dict[str, object]:
    ids = _load_deck_ids(path)
    counts = Counter(ids)
    role_counts = Counter()
    attack_types = Counter()
    names = {}
    for cid, n in counts.items():
        rec = cards.get(cid)
        if not rec:
            continue
        names[cid] = rec["name"]
        roles = set(rec["roles"])  # type: ignore[arg-type]
        if "basic_energy" in roles:
            role_counts["energy"] += n
        elif "pokemon" in roles:
            role_counts["pokemon"] += n
            for typ in rec["energy_profile"]["attack_required_types"]:  # type: ignore[index]
                attack_types[str(typ)] += n
        else:
            role_counts["trainer"] += n
    basics = sum(n for cid, n in counts.items() if "basic_pokemon" in cards.get(cid, {}).get("roles", []))
    attackers = [
        (cid, counts[cid], str(cards[cid]["name"]))
        for cid in counts
        if cid in cards and "attacker" in cards[cid]["roles"]  # type: ignore[operator]
    ]
    attackers.sort(key=lambda x: (-x[1], x[2]))
    return {
        "path": str(path.relative_to(ROOT)),
        "cards": len(ids),
        "unique_cards": len(counts),
        "energy": role_counts["energy"],
        "pokemon": role_counts["pokemon"],
        "trainers": role_counts["trainer"],
        "basic_pokemon": basics,
        "primary_attack_types": dict(attack_types.most_common()),
        "top_attackers": attackers[:6],
        "has_ace_spec": any("ace_spec" in cards.get(cid, {}).get("roles", []) for cid in counts),
        "card_counts": {str(cid): n for cid, n in sorted(counts.items())},
    }


def _archetype(deck: dict[str, object]) -> str:
    energy = int(deck["energy"])
    pokemon = int(deck["pokemon"])
    trainers = int(deck["trainers"])
    names = " ".join(name.lower() for _cid, _n, name in deck["top_attackers"])  # type: ignore[index]
    top_types = deck["primary_attack_types"]  # type: ignore[assignment]
    if "starmie" in names or "greninja" in names or "dragapult" in names:
        return "spread/control"
    if "kyogre" in names:
        return "anti-kyogre-baseline"
    if energy >= 29 and pokemon <= 18:
        return "fast-basic"
    if trainers >= 22:
        return "resilient-generalist"
    if pokemon >= 18:
        return "evolution-line"
    if top_types:
        return "typed-goodstuff"
    return "unknown"


def _write_candidate_csv(path: Path, decks: list[dict[str, object]]) -> None:
    cols = [
        "path",
        "archetype_lane",
        "cards",
        "unique_cards",
        "energy",
        "pokemon",
        "trainers",
        "basic_pokemon",
        "primary_attack_types",
        "top_attackers",
        "has_ace_spec",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for deck in decks:
            row = {k: deck.get(k, "") for k in cols}
            row["archetype_lane"] = _archetype(deck)
            row["primary_attack_types"] = json.dumps(deck["primary_attack_types"], ensure_ascii=False)
            row["top_attackers"] = "; ".join(
                f"{n}x {name} ({cid})" for cid, n, name in deck["top_attackers"]  # type: ignore[index]
            )
            writer.writerow(row)


def _write_seed_notes(path: Path, decks: list[dict[str, object]], cards: dict[int, dict[str, object]]) -> None:
    lanes = {
        "anti-Kyogre": "Improve the protected Kyogre matchup without replacing Kyogre until ladder proof exists.",
        "fast-basic": "Low-complexity Basic attackers, high energy consistency, and low no-active risk.",
        "spread/control": "Bench pressure or damage-counter plans; watch simultaneous-KO draw behavior.",
        "resilient-generalist": "Draw/search-heavy support shell for broad benchmark coverage.",
    }
    by_lane: dict[str, list[dict[str, object]]] = defaultdict(list)
    for deck in decks:
        lane = _archetype(deck)
        if lane == "anti-kyogre-baseline":
            by_lane["anti-Kyogre"].append(deck)
        elif lane == "fast-basic":
            by_lane["fast-basic"].append(deck)
        elif lane == "spread/control":
            by_lane["spread/control"].append(deck)
        elif lane == "resilient-generalist":
            by_lane["resilient-generalist"].append(deck)

    lines = [
        "# Archetype Seed Notes",
        "",
        "Generated by `scripts/build_card_registry.py` from `data/EN_Card_Data.csv` and local seed decks.",
        "",
        "Simulator legal options remain authoritative; card text only guides deck search features.",
        "",
    ]
    for lane, purpose in lanes.items():
        lines.extend([f"## {lane}", "", purpose, ""])
        seeds = by_lane.get(lane, [])[:8]
        if seeds:
            lines.append("| Seed deck | E/P/T | Basics | Top attackers | Notes |")
            lines.append("|---|---:|---:|---|---|")
            for deck in seeds:
                attackers = "; ".join(
                    f"{n}x {name}" for _cid, n, name in deck["top_attackers"][:3]  # type: ignore[index]
                )
                notes = []
                if deck["basic_pokemon"] < 6:
                    notes.append("low Basic count")
                if deck["has_ace_spec"]:
                    notes.append("ACE SPEC present")
                if lane == "spread/control":
                    notes.append("track draw/simultaneous-KO rate")
                lines.append(
                    f"| `{deck['path']}` | {deck['energy']}/{deck['pokemon']}/{deck['trainers']} | "
                    f"{deck['basic_pokemon']} | {attackers or 'n/a'} | {', '.join(notes) or 'seed'} |"
                )
        else:
            lines.append("No current local seed deck matched this lane directly.")
        lines.append("")
    sensitive = [
        rec for rec in cards.values()
        if rec["simulator_sensitive"] and ("attacker" in rec["roles"] or "trainer" in rec["roles"])  # type: ignore[operator]
    ]
    lines.extend(["## Simulator-Sensitive Feature Flags", ""])
    lines.append("| Card | Flags |")
    lines.append("|---|---|")
    for rec in sorted(sensitive, key=lambda r: (str(r["name"]), int(r["id"])))[:40]:
        lines.append(f"| {rec['name']} ({rec['id']}) | {', '.join(rec['simulator_sensitive'])} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_registry(cards_path: Path, benchmark_path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    rows_by_id = _read_cards(cards_path)
    cards = {cid: _card_record(cid, rows) for cid, rows in rows_by_id.items()}
    decks = [_deck_summary(p, cards) for p in _deck_paths(benchmark_path)]
    registry = {
        "source": str(cards_path.relative_to(ROOT)),
        "card_count": len(cards),
        "generated_notes": [
            "Card text features are not final legality. Use simulator legal option masks in training/evaluation.",
            "Simulator-sensitive flags are heuristics seeded from data/SIMULATOR_RESOURCE_NOTES.md.",
        ],
        "cards": {str(cid): rec for cid, rec in cards.items()},
        "role_index": _role_index(cards),
        "evolution_chains": _evolution_chains(cards),
        "deck_summaries": decks,
        "archetype_lanes": {
            "anti-Kyogre": "benchmark/probe lane against protected Kyogre lists",
            "fast-basic": "stable Basic-heavy lists with high first-attack reliability",
            "spread/control": "bench pressure and damage-counter plans",
            "resilient-generalist": "draw/search-heavy shells for matchup breadth",
        },
    }
    return registry, decks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", default=str(DEFAULT_CARDS))
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    registry, decks = build_registry(Path(args.cards), Path(args.benchmark))

    registry_path = out_dir / "registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_candidate_csv(out_dir / "candidate_registry.csv", decks)
    cards = {int(cid): rec for cid, rec in registry["cards"].items()}  # type: ignore[union-attr]
    _write_seed_notes(out_dir / "archetype_seed_notes.md", decks, cards)

    print(f"wrote {registry_path}")
    print(f"wrote {out_dir / 'candidate_registry.csv'}")
    print(f"wrote {out_dir / 'archetype_seed_notes.md'}")
    print(f"cards={registry['card_count']} decks={len(decks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
