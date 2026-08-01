"""Package a CLEAN Kaggle submission from an arbitrary (brain, deck) pair.

Why this exists
---------------
`package_archaludon.py` bundles the heavily-levered `agent/archaludon_agent.py`
(2515 lines) with `ARCH_IONO_LEVER=tomato`. Ladder ground truth
(`eval/ladder_log.csv`) says every lever stacked on top of the plain v5 brain
LOWERED mu:

    54083197  v5 + R7 bench guard          local 72.7%  ->  mu 1196.1 (peak 1224.2)
    54088877  v5 + R8a+R8b                 local 75.3%  ->  mu  983.8
    54109878  v5 + R7 + R8a                local 62.7%  ->  mu  967.3
    54109826  v5 + R7 + R10                local 62.0%  ->  mu  854.0
    54089078  v5 + R8a+R8b+R9              local 68.0%  ->  mu  841.0
    54138853  v5 + R7 + R11                local 58.7%  ->  mu  535.6

Local win-rate is anti-correlated with ladder mu on this track. So we build
straight from the untouched public brains instead.

Usage
-----
    python scripts/package_clean.py --preset arch_v5_r7
    python scripts/package_clean.py --preset arch_75wr_r7
    python scripts/package_clean.py --list
    python scripts/package_clean.py --brain <path.py> --deck <path.csv> \
        --name mything [--no-bench-guard]

Output: dist/candidates/<name>.tar.gz + <name>.manifest.json
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
BENCH_GUARD_SRC = os.path.join(ROOT, "agent", "archaludon_bench_guard.py")
EMPTY_GUARD_SRC = os.path.join(ROOT, "agent", "empty_bench_guard.py")
CAND_DIR = os.path.join(ROOT, "dist", "candidates")
BUILD_ROOT = os.path.join(ROOT, "dist", "submission_build")

# name -> (brain path, deck path, bench_guard, note)
PRESETS: dict[str, dict] = {
    # Exact brain of ref 54083197 (mu 1196.1 / peak 1224.2): community v5 public
    # release dated 2026-06-26, zero repo levers, plus the R7 empty-bench guard.
    "arch_v5_r7": {
        "brain": "notebooks/archaludon_ex_cinderace/archaludon_agent_public.py",
        "deck": "agent_decks/archaludon_ex_cinderace.csv",
        "bench_guard": True,
        "note": "community v5 (2026-06-26) + R7 empty-bench guard; brain of ref 54083197 mu 1196.1",
    },
    # Newer public Archaludon release; same lineage as v5 (+95 lines) and ships
    # the refined 4x Cinderace / 4x FML / 11x Metal shell.
    "arch_75wr_r7": {
        "brain": "extracted_agents/sample_archaludon_75wr/output/main.py",
        "deck": "extracted_agents/sample_archaludon_75wr/output/deck.csv",
        "bench_guard": True,
        "note": "public sample_archaludon_75wr verbatim + R7 empty-bench guard",
    },
    "arch_75wr_raw": {
        "brain": "extracted_agents/sample_archaludon_75wr/output/main.py",
        "deck": "extracted_agents/sample_archaludon_75wr/output/deck.csv",
        "bench_guard": False,
        "note": "public sample_archaludon_75wr verbatim, no wrapper",
    },
    "arch_v5_r7_legacy_deck": {
        "brain": "notebooks/archaludon_ex_cinderace/archaludon_agent_public.py",
        "deck": "agent_decks/archaludon_ex_cinderace_legacy_charmeleon.csv",
        "bench_guard": True,
        "note": "v5 + R7 on the Scorbunny/Raboot shell",
    },
    "dragapult_official_r7": {
        "brain": "extracted_agents/official_dragapult/from_submission_tar/main.py",
        "deck": "extracted_agents/official_dragapult/from_submission_tar/deck.csv",
        "bench_guard": False,
        "note": "official Dragapult sample; ref 53989933 scored mu 880.9",
    },
    "meta_router_844": {
        "brain": "extracted_agents/meta_router_844/from_submission_tar/main.py",
        "deck": "extracted_agents/meta_router_844/from_submission_tar/deck.csv",
        "bench_guard": False,
        "note": "public meta-router agent extracted from notebook submission tar",
    },
}

# main.py that never references __file__ (v1 submissions ERRORed on that).
MAIN_WITH_GUARD = '''"""Kaggle cabt submission entry point (clean build)."""
import os
import sys

_agent_dir = os.getcwd()
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from brain import agent as _brain_agent  # noqa: E402
from archaludon_bench_guard import apply_bench_guard  # noqa: E402


def _legal_fallback(obs_dict):
    """Last-resort legal selection straight off the option mask."""
    try:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if not sel:
            return []
        options = sel.get("option") or []
        min_count = sel.get("minCount", 0) or 0
        max_count = sel.get("maxCount", 0) or 0
        n = max(min_count, min(1, max_count) if max_count else 0)
        return list(range(min(n, len(options))))
    except Exception:
        return []


def agent(obs_dict):
    try:
        raw = _brain_agent(obs_dict)
    except Exception:
        return _legal_fallback(obs_dict)
    try:
        return apply_bench_guard(obs_dict, raw)
    except Exception:
        return raw
'''

MAIN_PLAIN = '''"""Kaggle cabt submission entry point (clean build, verbatim brain)."""
import os
import sys

_agent_dir = os.getcwd()
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from brain import agent  # noqa: E402,F401
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
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _copytree_no_pyc(src: str, dst: str) -> None:
    shutil.copytree(
        src, dst,
        ignore=lambda _d, names: {
            n for n in names if n == "__pycache__" or n.endswith(".pyc")
        },
    )


def build(name: str, brain: str, deck: str, bench_guard: bool, note: str) -> str:
    brain_src = brain if os.path.isabs(brain) else os.path.join(ROOT, brain)
    deck_src = deck if os.path.isabs(deck) else os.path.join(ROOT, deck)
    for p in (ENGINE_CG, brain_src, deck_src):
        if not os.path.exists(p):
            raise FileNotFoundError(p)
    if bench_guard:
        for p in (BENCH_GUARD_SRC, EMPTY_GUARD_SRC):
            if not os.path.exists(p):
                raise FileNotFoundError(p)

    deck_lines = [x for x in open(deck_src, encoding="utf-8").read().split("\n") if x.strip()]
    if len(deck_lines) != 60:
        raise ValueError(f"deck must be 60 cards, got {len(deck_lines)}: {deck_src}")

    build_dir = os.path.join(BUILD_ROOT, name)
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)

    members = ["main.py", "brain.py", "deck.csv", "cg"]
    with open(os.path.join(build_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(MAIN_WITH_GUARD if bench_guard else MAIN_PLAIN)
    shutil.copy2(brain_src, os.path.join(build_dir, "brain.py"))
    shutil.copy2(deck_src, os.path.join(build_dir, "deck.csv"))
    if bench_guard:
        shutil.copy2(BENCH_GUARD_SRC, os.path.join(build_dir, "archaludon_bench_guard.py"))
        shutil.copy2(EMPTY_GUARD_SRC, os.path.join(build_dir, "empty_bench_guard.py"))
        members[1:1] = ["archaludon_bench_guard.py", "empty_bench_guard.py"]
    _copytree_no_pyc(ENGINE_CG, os.path.join(build_dir, "cg"))

    os.makedirs(CAND_DIR, exist_ok=True)
    tarball = os.path.join(CAND_DIR, name + ".tar.gz")
    with tarfile.open(tarball, "w:gz") as tar:
        for item in members:
            tar.add(os.path.join(build_dir, item), arcname=item)

    manifest = {
        "name": name,
        "note": note,
        "brain_src": os.path.relpath(brain_src, ROOT),
        "deck_src": os.path.relpath(deck_src, ROOT),
        "bench_guard": bench_guard,
        "brain_sha1": _sha(brain_src),
        "deck_sha1": _sha(deck_src),
        "git_commit": _git_commit(),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "tarball": os.path.relpath(tarball, ROOT),
        "tarball_sha256": _sha(tarball, "sha256"),
        "deck_cards": len(deck_lines),
    }
    with open(os.path.join(CAND_DIR, name + ".manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    size_kib = os.path.getsize(tarball) / 1024
    print(f"built {os.path.relpath(tarball, ROOT)} ({size_kib:.1f} KiB)")
    return tarball


def dry_run(name: str) -> None:
    """Extract to a scratch cwd and exec main.py the way Kaggle does."""
    tarball = os.path.join(CAND_DIR, name + ".tar.gz")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        with tarfile.open(tarball) as tar:
            try:
                tar.extractall(tmp, filter="data")
            except TypeError:
                tar.extractall(tmp)
        old_cwd = os.getcwd()
        old_path = list(sys.path)
        try:
            os.chdir(tmp)
            src = open(os.path.join(tmp, "main.py"), encoding="utf-8").read()
            env: dict = {"__builtins__": __builtins__}
            exec(compile(src, "main.py", "exec"), env)
            # cg.api.Observation requires select/logs/current; the older stub
            # `{"select": None, "current": None}` blew up in to_observation_class
            # for brains that convert before checking for the deck-select phase.
            out = env["agent"]({"select": None, "logs": [], "current": None})
        finally:
            os.chdir(old_cwd)
            sys.path[:] = old_path
            for mod in ("brain", "archaludon_bench_guard", "empty_bench_guard"):
                sys.modules.pop(mod, None)
    if not isinstance(out, list) or len(out) != 60:
        raise SystemExit(f"DRY-RUN FAILED [{name}]: deck-select returned {out!r}")
    print(f"dry-run OK [{name}]: exec main (no __file__) -> {len(out)} cards")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", action="append", default=[],
                    help="preset name (repeatable); 'all' builds every preset")
    ap.add_argument("--brain", help="path to a brain .py exposing agent(obs_dict)")
    ap.add_argument("--deck", help="path to a 60-line deck csv")
    ap.add_argument("--name", help="output name for --brain/--deck builds")
    ap.add_argument("--no-bench-guard", action="store_true")
    ap.add_argument("--note", default="ad-hoc build")
    ap.add_argument("--list", action="store_true", help="list presets and exit")
    args = ap.parse_args(argv)

    if args.list:
        for k, v in PRESETS.items():
            print(f"{k:24s} {v['note']}")
        return 0

    jobs: list[tuple[str, dict]] = []
    presets = args.preset
    if presets == ["all"]:
        presets = list(PRESETS)
    for p in presets:
        if p not in PRESETS:
            print(f"unknown preset: {p}", file=sys.stderr)
            return 2
        jobs.append((p, PRESETS[p]))
    if args.brain:
        if not (args.deck and args.name):
            print("--brain requires --deck and --name", file=sys.stderr)
            return 2
        jobs.append((args.name, {
            "brain": args.brain, "deck": args.deck,
            "bench_guard": not args.no_bench_guard, "note": args.note,
        }))
    if not jobs:
        print("nothing to do; pass --preset or --brain/--deck/--name", file=sys.stderr)
        return 2

    failed = []
    for name, cfg in jobs:
        try:
            build(name, cfg["brain"], cfg["deck"], cfg["bench_guard"], cfg["note"])
            dry_run(name)
        except Exception as exc:
            print(f"FAILED [{name}]: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed.append(name)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
