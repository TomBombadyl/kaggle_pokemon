"""Prioritized fictitious self-play league for RL training."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEAGUE_DIR = ROOT / "report" / "rl_league"
POOL_DIR = ROOT / "agent_decks"


@dataclass
class LeagueMember:
    name: str
    kind: str  # snapshot | meta_proxy | current
    path: str = ""
    elo: float = 1500.0
    games: int = 0
    wins: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / max(1, self.games)


@dataclass
class League:
    members: list[LeagueMember] = field(default_factory=list)
    checkpoint_path: Path = LEAGUE_DIR / "league.json"

    def ensure_defaults(self) -> None:
        if self.members:
            return
        self.members.append(LeagueMember("current", "current", str(ROOT / "agent" / "agent.py")))
        for pool_path in sorted(POOL_DIR.glob("pool_*.csv")):
            self.members.append(
                LeagueMember(pool_path.stem, "meta_proxy", str(pool_path))
            )

    def pfsp_sample(self, rng: random.Random | None = None) -> LeagueMember:
        """Sample opponent weighted by difficulty (lower win-rate vs league mean)."""
        rng = rng or random.Random()
        self.ensure_defaults()
        weights = []
        mean_wr = sum(m.win_rate for m in self.members) / max(1, len(self.members))
        for m in self.members:
            difficulty = max(0.05, mean_wr - m.win_rate + 0.5)
            weights.append(difficulty ** 2)
        total = sum(weights)
        r = rng.random() * total
        acc = 0.0
        for m, w in zip(self.members, weights):
            acc += w
            if r <= acc:
                return m
        return self.members[-1]

    def record(self, name: str, won: bool) -> None:
        for m in self.members:
            if m.name == name:
                m.games += 1
                if won:
                    m.wins += 1
                return

    def save(self) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "members": [
                {
                    "name": m.name,
                    "kind": m.kind,
                    "path": m.path,
                    "elo": m.elo,
                    "games": m.games,
                    "wins": m.wins,
                }
                for m in self.members
            ]
        }
        self.checkpoint_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> "League":
        path = path or LEAGUE_DIR / "league.json"
        league = cls(checkpoint_path=path)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            league.members = [LeagueMember(**row) for row in data.get("members", [])]
        league.ensure_defaults()
        return league


if __name__ == "__main__":
    lg = League.load()
    opp = lg.pfsp_sample()
    print(f"PFSP sample: {opp.name} ({opp.kind})")
