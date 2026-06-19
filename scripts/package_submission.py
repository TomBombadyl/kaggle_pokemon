"""Dry-run submission packager for the cabt agent.

This does not submit to Kaggle. It builds a local archive matching the downloaded
sample_submission shape: top-level main.py, deck.csv, cg/, plus our agent package.

Run:
    python scripts/package_submission.py
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE_SAMPLE = ROOT / "data" / "sim" / "sample_submission"
BUILD_ROOT = ROOT / "dist" / "submission_build"
ARCHIVE = ROOT / "dist" / "submission.tar.gz"
ARCHIVE_DIR = ROOT / "dist" / "candidates"


MAIN_PY = '''"""Kaggle cabt submission entry point."""

from __future__ import annotations

import os

from {agent_module} import build_agent

# Kaggle loads this module via exec() without __file__; use cwd + known paths only.
KAGGLE_DECK = "/kaggle_simulations/agent/deck.csv"


def read_deck_csv() -> list[int]:
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = KAGGLE_DECK
    with open(file_path, "r") as file:
        csv = file.read().split("\\n")
    deck = []
    for i in range(60):
        deck.append(int(csv[i]))
    return deck


_AGENT = build_agent(seed=0, deck_path=KAGGLE_DECK)


def agent(obs_dict: dict) -> list[int]:
    if obs_dict.get("select") is None:
        return read_deck_csv()
    return _AGENT.act(obs_dict)
'''


def _copytree(src: Path, dst: Path) -> None:
    def ignore(_dir, names):
        return {n for n in names if n == "__pycache__" or n.endswith(".pyc")}

    shutil.copytree(src, dst, ignore=ignore)


def build(
    deck_path: Path | None = None,
    agent_module: str = "agent.agent",
    archive_path: Path = ARCHIVE,
) -> Path:
    if not (ENGINE_SAMPLE / "cg").exists():
        raise FileNotFoundError(f"missing engine directory: {ENGINE_SAMPLE / 'cg'}")
    deck = deck_path or ROOT / "agent" / "deck.csv"
    if not deck.exists():
        raise FileNotFoundError(f"missing deck: {deck}")

    build_dir = BUILD_ROOT / archive_path.stem
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    (build_dir / "main.py").write_text(
        MAIN_PY.format(agent_module=agent_module),
        encoding="utf-8",
    )
    shutil.copy2(deck, build_dir / "deck.csv")
    _copytree(ROOT / "agent", build_dir / "agent")
    if agent_module.startswith("agent_snapshots."):
        _copytree(ROOT / "agent_snapshots", build_dir / "agent_snapshots")
    _copytree(ENGINE_SAMPLE / "cg", build_dir / "cg")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()
    with tarfile.open(archive_path, "w:gz") as tar:
        for path in sorted(p for p in build_dir.rglob("*") if p.is_file()):
            tar.add(path, arcname=path.relative_to(build_dir).as_posix())
    return archive_path


def dry_run_import(archive: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="pokemon_submission_") as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp_path, filter="data")

        members = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
        required = {"main.py", "deck.csv", "agent/agent.py", "agent/__init__.py", "cg/api.py"}
        missing = required - set(members)
        if missing:
            raise RuntimeError(f"archive missing required files: {sorted(missing)}")

        sys.path.insert(0, str(tmp_path))
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Match Kaggle: exec main.py without __file__ in the module namespace.
            main_src = (tmp_path / "main.py").read_text(encoding="utf-8")
            env: dict = {"__builtins__": __builtins__}
            exec(compile(main_src, "main.py", "exec"), env)
            deck_out = env["agent"]({"logs": [], "current": None, "select": None})
        finally:
            os.chdir(old_cwd)
            sys.path.remove(str(tmp_path))

        if not isinstance(deck_out, list) or len(deck_out) != 60:
            raise RuntimeError(f"deck-selection smoke failed: got {len(deck_out) if isinstance(deck_out, list) else type(deck_out)}")

        names = tarfile.open(archive, "r:gz").getnames()
        if len(names) != len(set(names)):
            raise RuntimeError(f"archive has duplicate tar entries: {len(names) - len(set(names))}")


def _resolve_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", help="Deck CSV to package. Defaults to agent/deck.csv.")
    parser.add_argument("--agent-module", default="agent.agent")
    parser.add_argument(
        "--name",
        default="submission",
        help="Archive basename. Use a candidate name for dist/candidates/<name>.tar.gz.",
    )
    args = parser.parse_args()

    archive_path = ARCHIVE if args.name == "submission" else ARCHIVE_DIR / f"{args.name}.tar.gz"
    archive = build(
        deck_path=_resolve_path(args.deck),
        agent_module=args.agent_module,
        archive_path=archive_path,
    )
    dry_run_import(archive)
    size_kb = archive.stat().st_size / 1024
    print(f"built {archive} ({size_kb:.1f} KiB)")
    print("dry-run import OK; deck-selection returns 60 card IDs")
    print("No Kaggle submission was attempted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
