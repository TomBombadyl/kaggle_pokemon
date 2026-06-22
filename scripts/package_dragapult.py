"""Package the standalone Dragapult ex agent into a Kaggle submission tarball.

The repo's package_submission.py wraps our scorer agents; the Dragapult agent is a
standalone `agent(obs_dict)` function, so it gets its own clean packager here.

Produces (under dist/, which is gitignored):
  dist/candidates/dragapult_ex_sample.tar.gz        main.py + dragapult_agent.py + deck.csv + cg/
  dist/candidates/dragapult_ex_sample.manifest.json submission record (version, hashes, baseline)

The manifest + the tracked eval/ladder_log.csv are how we correlate the ladder
submission ref back to this exact build later, then extract its episodes/replays
and eval them (RULINGS R1: record >=2 mu readings; R8: keep metadata).

Dry-run: extracts the tarball to a temp dir and imports main there (no repo on
path) to prove it is self-contained and the deck/cg resolve — the things that
ERROR a Kaggle submission. Full-game play is already verified by scripts/gate_dragapult.py.

Actual upload stays manual (5/day, your machine has Kaggle egress, explicit confirm).
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
AGENT_SRC = os.path.join(ROOT, "agent", "dragapult_agent.py")
DECK_SRC = os.path.join(ROOT, "agent_decks", "dragapult_ex_sample.csv")
NAME = "dragapult_ex_sample"
BUILD_DIR = os.path.join(ROOT, "dist", "submission_build", NAME)
CAND_DIR = os.path.join(ROOT, "dist", "candidates")
TARBALL = os.path.join(CAND_DIR, NAME + ".tar.gz")
MANIFEST = os.path.join(CAND_DIR, NAME + ".manifest.json")

MAIN_PY = '''"""Kaggle cabt submission entry point — Dragapult ex (standalone agent)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # cg/ + dragapult_agent

from dragapult_agent import agent  # noqa: E402,F401  (Kaggle calls main.agent)
'''

# Local gate baseline at build time (scripts/gate_dragapult.py) — LOCAL FILTER, not ladder truth.
GATE_BASELINE = {
    "harness": "scripts/gate_dragapult.py (asymmetric decks, seat-swapped, Wilson CI)",
    "vs_heuristic_30g_per_opp": {
        "real_mega_lucario_ex": 66.7, "top_mined_alakazam": 73.3,
        "top_mined_trevenant": 100.0, "real_mega_abomasnow_ex": 73.3, "overall": 78.3,
    },
    "vs_search_20g_per_opp": {
        "real_mega_lucario_ex": 85.0, "top_mined_alakazam": 85.0,
        "top_mined_trevenant": 95.0, "overall": 88.3,
    },
    "note": "LOCAL FILTER only; the Kaggle ladder is the judge (RULINGS R1/R2).",
}


def _sha(path: str, algo: str = "sha1") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       text=True).strip()
    except Exception:
        return "unknown"


def _copytree_no_pyc(src: str, dst: str) -> None:
    shutil.copytree(src, dst, ignore=lambda d, names: {n for n in names
                    if n == "__pycache__" or n.endswith(".pyc")})


def build() -> None:
    if not os.path.isdir(ENGINE_CG):
        raise FileNotFoundError(f"engine cg/ not found: {ENGINE_CG}")
    for p in (AGENT_SRC, DECK_SRC):
        if not os.path.exists(p):
            raise FileNotFoundError(p)
    deck_lines = [x for x in open(DECK_SRC).read().split("\n") if x.strip()]
    if len(deck_lines) != 60:
        raise ValueError(f"deck must be 60 cards, got {len(deck_lines)}")

    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR)
    with open(os.path.join(BUILD_DIR, "main.py"), "w", encoding="utf-8") as f:
        f.write(MAIN_PY)
    shutil.copy2(AGENT_SRC, os.path.join(BUILD_DIR, "dragapult_agent.py"))
    shutil.copy2(DECK_SRC, os.path.join(BUILD_DIR, "deck.csv"))
    _copytree_no_pyc(ENGINE_CG, os.path.join(BUILD_DIR, "cg"))

    os.makedirs(CAND_DIR, exist_ok=True)
    with tarfile.open(TARBALL, "w:gz") as tar:
        for item in ("main.py", "dragapult_agent.py", "deck.csv", "cg"):
            tar.add(os.path.join(BUILD_DIR, item), arcname=item)

    manifest = {
        "name": NAME,
        "agent": "agent/dragapult_agent.py (official Kaggle sample + never-crash/validation wrapper)",
        "variant": "Crispin aggressive (official sample)",
        "deck": "agent_decks/dragapult_ex_sample.csv",
        "deck_sha1": _sha(DECK_SRC),
        "agent_sha1": _sha(AGENT_SRC),
        "git_commit": _git_commit(),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "tarball": os.path.relpath(TARBALL, ROOT),
        "tarball_sha256": _sha(TARBALL, "sha256"),
        "local_gate_baseline": GATE_BASELINE,
        # Filled in after upload so we can extract + eval this submission's games:
        "submission": {"ref": None, "submitted_at": None, "mu_readings": []},
        "extract_and_eval": (
            "After upload: record ref in eval/ladder_log.csv + here; on a machine with "
            "Kaggle egress pull this ref's episodes/replays (scripts/fetch_agent_logs.py / "
            "episodes pipeline); eval win-rate, loss reasons, matchup split, and (if "
            "DRAGAPULT_LOG=1 was set) the decision trace from agent stdout."
        ),
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"built {os.path.relpath(TARBALL, ROOT)} "
          f"({os.path.getsize(TARBALL)/1024:.1f} KiB)")
    print(f"manifest {os.path.relpath(MANIFEST, ROOT)}")


def dry_run() -> None:
    """Extract the tarball to a temp dir and import main with ONLY that dir on the
    path — proves self-containment, cg import, and deck resolution."""
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(TARBALL) as tar:
            try:
                tar.extractall(tmp, filter="data")   # py>=3.12 safe extraction
            except TypeError:
                tar.extractall(tmp)
        code = (
            "import sys; sys.path.insert(0, '.'); import main; "
            "o = main.agent({'select': None, 'current': None}); "
            "assert isinstance(o, list) and len(o) == 60, ('bad deck-select', o); "
            "print('dry-run OK: import + cg + deck-select ->', len(o), 'cards')"
        )
        res = subprocess.run([sys.executable, "-c", code], cwd=tmp,
                             capture_output=True, text=True)
        sys.stdout.write(res.stdout)
        if res.returncode != 0:
            sys.stderr.write(res.stderr)
            raise SystemExit(f"DRY-RUN FAILED (rc={res.returncode})")


if __name__ == "__main__":
    build()
    dry_run()
