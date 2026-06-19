"""Dry-run submission packager for the cabt agent.

This does not submit to Kaggle. It builds a local archive matching the downloaded
sample_submission shape: top-level main.py, deck.csv, cg/, plus our agent package.

Run:
    python scripts/package_submission.py
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE_SAMPLE = ROOT / "data" / "sim" / "sample_submission"
BUILD_DIR = ROOT / "dist" / "submission_build"
ARCHIVE = ROOT / "dist" / "submission.tar.gz"


MAIN_PY = '''"""Kaggle cabt submission entry point."""

from __future__ import annotations

from pathlib import Path

from agent.agent import build_agent


_AGENT = build_agent(seed=0, deck_path=str(Path(__file__).with_name("deck.csv")))


def agent(obs_dict: dict) -> list[int]:
    return _AGENT.act(obs_dict)
'''


def _copytree(src: Path, dst: Path) -> None:
    def ignore(_dir, names):
        return {n for n in names if n == "__pycache__" or n.endswith(".pyc")}

    shutil.copytree(src, dst, ignore=ignore)


def build() -> Path:
    if not (ENGINE_SAMPLE / "cg").exists():
        raise FileNotFoundError(f"missing engine directory: {ENGINE_SAMPLE / 'cg'}")
    deck = ROOT / "agent" / "deck.csv"
    if not deck.exists():
        raise FileNotFoundError(f"missing deck: {deck}")

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    (BUILD_DIR / "main.py").write_text(MAIN_PY, encoding="utf-8")
    shutil.copy2(deck, BUILD_DIR / "deck.csv")
    _copytree(ROOT / "agent", BUILD_DIR / "agent")
    _copytree(ENGINE_SAMPLE / "cg", BUILD_DIR / "cg")

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with tarfile.open(ARCHIVE, "w:gz") as tar:
        for path in sorted(BUILD_DIR.rglob("*")):
            tar.add(path, arcname=path.relative_to(BUILD_DIR))
    return ARCHIVE


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
        try:
            spec = importlib.util.spec_from_file_location("submission_main", tmp_path / "main.py")
            if spec is None or spec.loader is None:
                raise RuntimeError("could not load main.py from archive")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            deck_out = module.agent({"logs": [], "current": None, "select": None})
        finally:
            sys.path.remove(str(tmp_path))

        if not isinstance(deck_out, list) or len(deck_out) != 60:
            raise RuntimeError(f"deck-selection smoke failed: got {len(deck_out) if isinstance(deck_out, list) else type(deck_out)}")


def main() -> int:
    archive = build()
    dry_run_import(archive)
    size_kb = archive.stat().st_size / 1024
    print(f"built {archive} ({size_kb:.1f} KiB)")
    print("dry-run import OK; deck-selection returns 60 card IDs")
    print("No Kaggle submission was attempted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
