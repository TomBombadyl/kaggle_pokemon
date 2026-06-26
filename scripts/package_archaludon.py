"""Package Archaludon ex / Cinderace into a Kaggle submission tarball.

Canonical name: ``archaludon`` (ref 54083197 was uploaded as
``archaludon_ex_cinderace_r7_bench.tar.gz`` @ 1224.2 μ).

Produces:
  dist/candidates/archaludon.tar.gz
  dist/candidates/archaludon.manifest.json
"""
from __future__ import annotations

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
AGENT_SRC = os.path.join(ROOT, "agent", "archaludon_agent.py")
BENCH_GUARD_SRC = os.path.join(ROOT, "agent", "archaludon_bench_guard.py")
EMPTY_GUARD_SRC = os.path.join(ROOT, "agent", "empty_bench_guard.py")
DECK_SRC = os.path.join(ROOT, "agent_decks", "archaludon_ex_cinderace.csv")
NAME = "archaludon"
LADDER_REF = "54083197"
LADDER_MU = 1224.2
KAGGLE_UPLOAD_ALIASES = ("archaludon_ex_cinderace_r7_bench",)
BUILD_DIR = os.path.join(ROOT, "dist", "submission_build", NAME)
CAND_DIR = os.path.join(ROOT, "dist", "candidates")
TARBALL = os.path.join(CAND_DIR, NAME + ".tar.gz")
MANIFEST = os.path.join(CAND_DIR, NAME + ".manifest.json")

MAIN_PY = '''"""Kaggle cabt submission entry point — Archaludon ex / Cinderace."""
import os
import sys

_agent_dir = os.getcwd()
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from archaludon_agent import agent  # noqa: E402,F401
'''


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


def build() -> None:
    if not os.path.isdir(ENGINE_CG):
        raise FileNotFoundError(f"engine cg/ not found: {ENGINE_CG}")
    for p in (AGENT_SRC, BENCH_GUARD_SRC, EMPTY_GUARD_SRC, DECK_SRC):
        if not os.path.exists(p):
            raise FileNotFoundError(p)
    deck_lines = [x for x in open(DECK_SRC, encoding="utf-8").read().split("\n") if x.strip()]
    if len(deck_lines) != 60:
        raise ValueError(f"deck must be 60 cards, got {len(deck_lines)}")

    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR)
    with open(os.path.join(BUILD_DIR, "main.py"), "w", encoding="utf-8") as f:
        f.write(MAIN_PY)
    shutil.copy2(AGENT_SRC, os.path.join(BUILD_DIR, "archaludon_agent.py"))
    shutil.copy2(BENCH_GUARD_SRC, os.path.join(BUILD_DIR, "archaludon_bench_guard.py"))
    shutil.copy2(EMPTY_GUARD_SRC, os.path.join(BUILD_DIR, "empty_bench_guard.py"))
    shutil.copy2(DECK_SRC, os.path.join(BUILD_DIR, "deck.csv"))
    _copytree_no_pyc(ENGINE_CG, os.path.join(BUILD_DIR, "cg"))

    os.makedirs(CAND_DIR, exist_ok=True)
    with tarfile.open(TARBALL, "w:gz") as tar:
        for item in (
            "main.py",
            "archaludon_agent.py",
            "archaludon_bench_guard.py",
            "empty_bench_guard.py",
            "deck.csv",
            "cg",
        ):
            tar.add(os.path.join(BUILD_DIR, item), arcname=item)

    manifest = {
        "name": NAME,
        "agent": "agent/archaludon_agent.py (community v5 + R7 empty-bench guard)",
        "deck": "agent_decks/archaludon_ex_cinderace.csv",
        "ladder_benchmark_mu": LADDER_MU,
        "ladder_benchmark_ref": LADDER_REF,
        "kaggle_upload_aliases": list(KAGGLE_UPLOAD_ALIASES),
        "deck_sha1": _sha(DECK_SRC),
        "agent_sha1": _sha(AGENT_SRC),
        "git_commit": _git_commit(),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "tarball": os.path.relpath(TARBALL, ROOT),
        "tarball_sha256": _sha(TARBALL, "sha256"),
        "submission": {
            "ref": LADDER_REF,
            "submitted_at": "2026-06-26T16:15:56.833000",
            "mu_readings": [600.0, 731.3, LADDER_MU],
            "status": "COMPLETE",
            "local_gate_overall_pct": 72.7,
            "kaggle_message": (
                "archaludon_rules x archaludon_ex_cinderace: community v5 + R7 empty-bench guard; "
                "local 72.7% full n=30"
            ),
        },
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"built {os.path.relpath(TARBALL, ROOT)} ({os.path.getsize(TARBALL)/1024:.1f} KiB)")
    print(f"manifest {os.path.relpath(MANIFEST, ROOT)}")


def dry_run() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        with tarfile.open(TARBALL) as tar:
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
        f"--manifest {os.path.relpath(MANIFEST, ROOT)} "
        f'--change "Archaludon v5 port + R7 empty-bench guard" --local-gate <WR>'
    )


if __name__ == "__main__":
    build()
    dry_run()
