"""Package Starmie pilots into a Kaggle submission tarball.

  python scripts/package_starmie.py
  python scripts/package_starmie.py --deck agent_decks/starmie_froslass_risky_ruins.csv
  python scripts/package_starmie.py --deck agent_decks/starmie_cinderace_hybrid.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_CG = os.path.join(ROOT, "data", "sim", "sample_submission", "cg")
AGENT_SRC = os.path.join(ROOT, "agent", "starmie_agent.py")
BENCH_GUARD_SRC = os.path.join(ROOT, "agent", "starmie_bench_guard.py")
EMPTY_GUARD_SRC = os.path.join(ROOT, "agent", "empty_bench_guard.py")
PRIZE_SRC = os.path.join(ROOT, "agent", "prize_tracker.py")
FINISH_SRC = os.path.join(ROOT, "agent", "finish_search.py")
DEFAULT_DECK = os.path.join(ROOT, "agent_decks", "starmie_froslass_ashleysandlin.csv")
CAND_DIR = os.path.join(ROOT, "dist", "candidates")

MAIN_PY = '''"""Kaggle cabt submission entry point — Starmie / Froslass rule pilot."""
import os
import sys

_agent_dir = os.getcwd()
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from starmie_agent import agent  # noqa: E402,F401
'''

BUNDLE_FILES = (
    "main.py",
    "starmie_agent.py",
    "starmie_bench_guard.py",
    "empty_bench_guard.py",
    "prize_tracker.py",
    "finish_search.py",
    "deck.csv",
    "cg",
)


def _sha(path: str, algo: str = "sha1") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _copytree_no_pyc(src: str, dst: str) -> None:
    shutil.copytree(
        src,
        dst,
        ignore=lambda _d, names: {n for n in names if n == "__pycache__" or n.endswith(".pyc")},
    )


def build(*, deck_src: str | None = None, name: str | None = None) -> tuple[str, str]:
    deck_src = deck_src or DEFAULT_DECK
    if not os.path.isabs(deck_src):
        deck_src = os.path.join(ROOT, deck_src)
    name = name or os.path.splitext(os.path.basename(deck_src))[0]
    build_dir = os.path.join(ROOT, "dist", "submission_build", name)
    tarball = os.path.join(CAND_DIR, name + ".tar.gz")
    manifest = os.path.join(CAND_DIR, name + ".manifest.json")

    if not os.path.isdir(ENGINE_CG):
        raise FileNotFoundError(f"engine cg/ not found: {ENGINE_CG}")
    for p in (AGENT_SRC, BENCH_GUARD_SRC, EMPTY_GUARD_SRC, PRIZE_SRC, FINISH_SRC, deck_src):
        if not os.path.exists(p):
            raise FileNotFoundError(p)
    deck_lines = [x for x in open(deck_src, encoding="utf-8").read().split("\n") if x.strip()]
    if len(deck_lines) != 60:
        raise ValueError(f"deck must be 60 cards, got {len(deck_lines)}")

    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(MAIN_PY)
    shutil.copy2(AGENT_SRC, os.path.join(build_dir, "starmie_agent.py"))
    shutil.copy2(BENCH_GUARD_SRC, os.path.join(build_dir, "starmie_bench_guard.py"))
    shutil.copy2(EMPTY_GUARD_SRC, os.path.join(build_dir, "empty_bench_guard.py"))
    shutil.copy2(PRIZE_SRC, os.path.join(build_dir, "prize_tracker.py"))
    shutil.copy2(FINISH_SRC, os.path.join(build_dir, "finish_search.py"))
    shutil.copy2(deck_src, os.path.join(build_dir, "deck.csv"))
    _copytree_no_pyc(ENGINE_CG, os.path.join(build_dir, "cg"))

    os.makedirs(CAND_DIR, exist_ok=True)
    with tarfile.open(tarball, "w:gz") as tar:
        for item in BUNDLE_FILES:
            tar.add(os.path.join(build_dir, item), arcname=item)

    manifest_data = {
        "name": name,
        "agent": "agent/starmie_agent.py (spread/hybrid + PrizeTracker + finish search + R7 bench guard)",
        "deck": os.path.relpath(deck_src, ROOT),
        "ladder_benchmark_mu": None,
        "ladder_benchmark_ref": None,
        "deck_sha1": _sha(deck_src),
        "agent_sha1": _sha(AGENT_SRC),
        "git_commit": _git_commit(),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "tarball": os.path.relpath(tarball, ROOT),
        "tarball_sha256": _sha(tarball, "sha256"),
        "submission": {"ref": None, "submitted_at": None, "mu_readings": []},
    }
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"built {os.path.relpath(tarball, ROOT)} ({os.path.getsize(tarball)/1024:.1f} KiB)")
    print(f"manifest {os.path.relpath(manifest, ROOT)}")
    return tarball, manifest


def dry_run(tarball: str, manifest: str) -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        with tarfile.open(tarball) as tar:
            try:
                tar.extractall(tmp, filter="data")
            except TypeError:
                tar.extractall(tmp)
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            main_src = open(os.path.join(tmp, "main.py"), encoding="utf-8").read()
            env: dict = {"__builtins__": __builtins__}
            exec(compile(main_src, "main.py", "exec"), env)
            out = env["agent"]({"select": None, "current": None})
        finally:
            os.chdir(old_cwd)
        if not isinstance(out, list) or len(out) != 60:
            raise SystemExit(f"DRY-RUN FAILED: deck-select got {out!r}")
        print(f"dry-run OK: exec main (no __file__) + cg + deck-select -> {len(out)} cards")
    print(
        f"\nBefore upload: python scripts/check_upload_eligible.py "
        f"--manifest {os.path.relpath(manifest, ROOT)} "
        f'--change "starmie_rules: deck variant probe" --local-gate <WR>'
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deck", default=None, help="Deck CSV path (default: ashleysandlin)")
    ap.add_argument("--name", default=None, help="Package name override")
    args = ap.parse_args()
    tarball, manifest = build(deck_src=args.deck, name=args.name)
    dry_run(tarball, manifest)
