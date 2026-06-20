"""Load archetype search lanes from report/deck_rl/candidate_registry.csv."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "report" / "deck_rl" / "candidate_registry.csv"

CANONICAL_LANES: tuple[str, ...] = (
    "anti-Kyogre",
    "fast-basic",
    "spread/control",
    "resilient-generalist",
)

_LANE_ALIASES: dict[str, str] = {
    "anti-kyogre-baseline": "anti-Kyogre",
    "anti-kyogre": "anti-Kyogre",
}


def normalize_lane(raw: str) -> str:
    key = raw.strip()
    if not key:
        return ""
    return _LANE_ALIASES.get(key.lower(), key)


def _guess_lane_from_path(path: Path) -> str:
    name = path.stem.lower()
    if "starmie" in name or "spread" in name or "dragapult" in name or "greninja" in name:
        return "spread/control"
    if "kyogre" in name or "big_basic" in name or "basic_heavy" in name or "basic_water" in name:
        return "anti-Kyogre"
    if "abomasnow" in name and "mega" in name:
        return "fast-basic"
    if name.startswith("pool_") or "lucario" in name or "iono" in name:
        return "resilient-generalist"
    return ""


@dataclass
class LaneRegistry:
    path_to_lane: dict[Path, str] = field(default_factory=dict)
    lane_to_paths: dict[str, list[Path]] = field(default_factory=dict)
    label_to_lane: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        path: Path | None = None,
        *,
        lanes: tuple[str, ...] | list[str] | None = None,
        fallback_paths: list[Path] | None = None,
    ) -> "LaneRegistry":
        path = path or DEFAULT_REGISTRY
        wanted = set(lanes or CANONICAL_LANES)
        reg = cls()

        if path.exists():
            with path.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    raw_lane = normalize_lane(row.get("archetype_lane", ""))
                    if raw_lane not in wanted:
                        continue
                    rel = row.get("path", "").strip()
                    if not rel:
                        continue
                    deck_path = (ROOT / rel).resolve()
                    if not deck_path.exists():
                        print(f"lane registry: skip missing seed {rel}", flush=True)
                        continue
                    reg._register(deck_path, raw_lane)
        elif fallback_paths:
            for deck_path in fallback_paths:
                if not deck_path.exists():
                    continue
                lane = _guess_lane_from_path(deck_path)
                if lane and lane in wanted:
                    reg._register(deck_path.resolve(), lane)

        return reg

    def _register(self, deck_path: Path, lane: str) -> None:
        self.path_to_lane[deck_path] = lane
        self.lane_to_paths.setdefault(lane, []).append(deck_path)
        self.label_to_lane[deck_path.stem] = lane

    def lane_for_path(self, deck_path: Path) -> str:
        resolved = deck_path.resolve()
        if resolved in self.path_to_lane:
            return self.path_to_lane[resolved]
        for known, lane in self.path_to_lane.items():
            if known.name == deck_path.name:
                return lane
        return ""

    def lane_for_label(self, label: str) -> str:
        if not label:
            return ""
        if label in self.label_to_lane:
            return self.label_to_lane[label]
        for stem, lane in self.label_to_lane.items():
            if label == stem or label.startswith(stem) or stem in label:
                return lane
        return ""

    def seed_paths(self, lanes: tuple[str, ...] | list[str] | None = None) -> list[Path]:
        wanted = list(lanes or CANONICAL_LANES)
        out: list[Path] = []
        for lane in wanted:
            out.extend(self.lane_to_paths.get(lane, []))
        return out

    def is_empty(self) -> bool:
        return not self.path_to_lane
