"""Load report/deck_rl/registry.json for role/chain-aware deck mutations."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = ROOT / "report" / "deck_rl" / "registry.json"

SUPPORT_ROLES = (
    "draw_trainer",
    "search_trainer",
    "switch_trainer",
    "gust_targeting",
    "recovery",
    "energy_acceleration",
    "disruption",
)


@dataclass(frozen=True)
class EvoChain:
    root_name: str
    stages: tuple[tuple[int, ...], ...]


class CardRegistry:
    def __init__(self, data: dict[str, object]) -> None:
        cards_raw = data.get("cards", {})
        self._cards: dict[int, dict[str, object]] = {
            int(cid): rec for cid, rec in cards_raw.items()  # type: ignore[union-attr]
        }
        role_index = data.get("role_index", {})
        self._role_index: dict[str, list[int]] = {
            str(role): [int(cid) for cid in ids] for role, ids in role_index.items()  # type: ignore[union-attr]
        }
        self._evolution_chains: dict[str, dict[str, object]] = data.get("evolution_chains", {})  # type: ignore[assignment]
        self._chains_by_card: dict[int, EvoChain] = {}
        self._build_chain_index()

    def card_roles(self, card_id: int) -> set[str]:
        rec = self._cards.get(card_id)
        if not rec:
            return set()
        return set(rec.get("roles", []))  # type: ignore[arg-type]

    def support_roles(self, card_id: int) -> list[str]:
        return sorted(r for r in self.card_roles(card_id) if r in SUPPORT_ROLES)

    def cards_with_role(self, role: str) -> list[int]:
        return list(self._role_index.get(role, []))

    def is_ace_spec(self, card_id: int) -> bool:
        return "ace_spec" in self.card_roles(card_id)

    def chain_for_card(self, card_id: int) -> EvoChain | None:
        return self._chains_by_card.get(card_id)

    def chains_in_deck(self, counts: Counter) -> list[EvoChain]:
        seen: set[str] = set()
        chains: list[EvoChain] = []
        for cid, n in counts.items():
            if n <= 0:
                continue
            chain = self.chain_for_card(cid)
            if chain is None or chain.root_name in seen:
                continue
            if any(counts.get(c, 0) > 0 for stage in chain.stages for c in stage):
                seen.add(chain.root_name)
                chains.append(chain)
        return chains

    def _is_chain_root(self, name: str, entry: dict[str, object]) -> bool:
        for cid in entry.get("ids", []):
            rec = self._cards.get(int(cid))  # type: ignore[arg-type]
            if rec and "basic_pokemon" in rec.get("roles", []):
                return True
        return False

    def _walk_chain(self, root_name: str) -> list[list[int]]:
        entry = self._evolution_chains.get(root_name)
        if not entry:
            return []
        stages: list[list[int]] = [sorted(int(cid) for cid in entry.get("ids", []))]  # type: ignore[union-attr]
        frontier = [int(cid) for cid in entry.get("children", [])]  # type: ignore[union-attr]
        seen = {tuple(stages[0])}
        while frontier:
            stage_ids = sorted({cid for cid in frontier if cid in self._cards})
            if not stage_ids:
                break
            key = tuple(stage_ids)
            if key in seen:
                break
            seen.add(key)
            stages.append(stage_ids)
            next_frontier: list[int] = []
            for cid in stage_ids:
                name = str(self._cards[cid]["name"])
                child_entry = self._evolution_chains.get(name)
                if child_entry:
                    next_frontier.extend(int(x) for x in child_entry.get("children", []))  # type: ignore[union-attr]
            frontier = next_frontier
        return stages if len(stages) >= 2 else []

    def _build_chain_index(self) -> None:
        for root_name, entry in self._evolution_chains.items():
            if not self._is_chain_root(root_name, entry):
                continue
            stages = self._walk_chain(root_name)
            if len(stages) < 2:
                continue
            chain = EvoChain(root_name=root_name, stages=tuple(tuple(s) for s in stages))
            for stage in chain.stages:
                for cid in stage:
                    self._chains_by_card[cid] = chain


@lru_cache(maxsize=1)
def get_card_registry(path: str | None = None) -> CardRegistry | None:
    registry_path = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not registry_path.exists():
        return None
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    return CardRegistry(data)
