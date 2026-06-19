"""Audit packaged candidate archives and summarize validation confidence."""

from __future__ import annotations

import argparse
import math
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = ROOT / "dist" / "candidates"
FORBIDDEN_PARTS = {
    ".kaggle",
    "dist",
    "__pycache__",
}
FORBIDDEN_SUFFIXES = {
    ".pyc",
}


def wilson_interval(wins: int, games: int, z: float = 1.96) -> tuple[float, float]:
    if games <= 0:
        return 0.0, 0.0
    p = wins / games
    denom = 1 + z * z / games
    center = (p + z * z / (2 * games)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * games)) / games) / denom
    return 100 * (center - margin), 100 * (center + margin)


def audit_archive(path: Path) -> dict[str, object]:
    with tarfile.open(path, "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.isfile()]
    names = [m.name.replace("\\", "/") for m in members]
    top_level = {name.split("/", 1)[0] for name in names}
    required = {"main.py", "deck.csv", "agent/agent.py", "cg/api.py", "cg/game.py", "cg/sim.py"}
    missing = sorted(required - set(names))
    forbidden = []
    for name in names:
        parts = set(name.split("/"))
        suffix = Path(name).suffix
        if parts & FORBIDDEN_PARTS or suffix in FORBIDDEN_SUFFIXES:
            forbidden.append(name)
    return {
        "archive": path.name,
        "files": len(names),
        "size_kb": round(path.stat().st_size / 1024, 1),
        "top_level": ",".join(sorted(top_level)),
        "missing_required": ";".join(missing),
        "forbidden": ";".join(forbidden[:8]),
    }


def render_markdown(audits: list[dict[str, object]], validations: list[tuple[str, int, int]]) -> str:
    lines = [
        "# Candidate Package Audit",
        "",
        "## Archive Contents",
        "",
        "| Archive | Size KiB | Files | Top-level entries | Missing required | Forbidden sample |",
        "|---|---:|---:|---|---|---|",
    ]
    for row in audits:
        lines.append(
            f"| {row['archive']} | {row['size_kb']} | {row['files']} | "
            f"{row['top_level']} | {row['missing_required']} | {row['forbidden']} |"
        )
    if validations:
        lines.extend([
            "",
            "## Validation Confidence",
            "",
            "| Candidate | Wins | Games | Win % | Wilson 95% CI |",
            "|---|---:|---:|---:|---|",
        ])
        for name, wins, games in validations:
            lo, hi = wilson_interval(wins, games)
            win_pct = 100 * wins / games if games else 0.0
            lines.append(
                f"| {name} | {wins} | {games} | {win_pct:.2f} | {lo:.2f}-{hi:.2f} |"
            )
    return "\n".join(lines) + "\n"


def parse_validation(raw: str) -> tuple[str, int, int]:
    # NAME=WINS/GAMES
    name, result = raw.split("=", 1)
    wins, games = result.split("/", 1)
    return name, int(wins), int(games)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--validation", action="append", default=[], help="NAME=WINS/GAMES")
    parser.add_argument("--out", type=Path, default=ROOT / "report" / "candidate_package_audit.md")
    args = parser.parse_args(argv)

    candidate_dir = args.candidate_dir if args.candidate_dir.is_absolute() else ROOT / args.candidate_dir
    audits = [audit_archive(path) for path in sorted(candidate_dir.glob("*.tar.gz"))]
    validations = [parse_validation(raw) for raw in args.validation]
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(audits, validations))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
