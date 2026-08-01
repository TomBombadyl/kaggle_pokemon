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
{scorer_import}

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


{agent_init}


def agent(obs_dict: dict) -> list[int]:
    if obs_dict.get("select") is None:
        return read_deck_csv()
    return _AGENT.act(obs_dict)
'''

MAIN_AGENT_INIT = "_AGENT = build_agent(seed=0, deck_path=KAGGLE_DECK)"
SEARCH_AGENT_INIT = (
    "from agent.search_policy import SearchScorer\n\n"
    "_AGENT = build_agent(seed=0, deck_path=KAGGLE_DECK, scorer=SearchScorer())"
)
LEARNED_AGENT_INIT = (
    "from agent.learned_policy import LearnedScorer\n\n"
    "_AGENT = build_agent(seed=0, deck_path=KAGGLE_DECK, scorer=LearnedScorer())"
)
RULECORE_AGENT_INIT = (
    "from agent.rule_core import RuleCoreScorer\n\n"
    "_AGENT = build_agent(seed=0, deck_path=KAGGLE_DECK, "
    "scorer=RuleCoreScorer(deck_path=KAGGLE_DECK))"
)
LUCARIO_AGENT_INIT = (
    "from agent.lucario_policy import LucarioScorer\n\n"
    "_AGENT = build_agent(seed=0, deck_path=KAGGLE_DECK, "
    "scorer=LucarioScorer(deck_path=KAGGLE_DECK))"
)
LUCARIO_SEARCH_AGENT_INIT = (
    "from agent.search_policy import LucarioSearchScorer\n\n"
    "_AGENT = build_agent(seed=0, deck_path=KAGGLE_DECK, "
    "scorer=LucarioSearchScorer(deck_path=KAGGLE_DECK))"
)
CRUSTLE_SEARCH_AGENT_INIT = (
    "from agent.search_policy import CrustleSearchScorer\n\n"
    "_AGENT = build_agent(seed=0, deck_path=KAGGLE_DECK, "
    "scorer=CrustleSearchScorer(deck_path=KAGGLE_DECK))"
)
LUCARIO_MCTS_AGENT_INIT = (
    "from agent.lucario_mcts_policy import build_lucario_mcts_scorer\n\n"
    "_AGENT = build_agent(seed=0, deck_path=KAGGLE_DECK, "
    "scorer=build_lucario_mcts_scorer("
    "deck_path=KAGGLE_DECK, "
    "model_path='agent/models/lucario_model_best.pth', "
    "meta_path='agent/models/lucario_run_meta.json'))"
)


def _copytree(src: Path, dst: Path) -> None:
    def ignore(_dir, names):
        return {n for n in names if n == "__pycache__" or n.endswith(".pyc")}

    shutil.copytree(src, dst, ignore=ignore)


def _copy_torch_checkpoint_compact(src: Path, dest: Path) -> None:
    try:
        import torch

        state = torch.load(src, map_location="cpu")
        if isinstance(state, dict):
            state = {
                k: v.half() if hasattr(v, "is_floating_point") and v.is_floating_point() else v
                for k, v in state.items()
            }
            torch.save(state, dest)
            return
    except Exception:
        pass
    shutil.copy2(src, dest)


def build(
    deck_path: Path | None = None,
    agent_module: str = "agent.agent",
    archive_path: Path = ARCHIVE,
    scorer: str = "heuristic",
    model_path: Path | None = None,
    meta_path: Path | None = None,
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

    if scorer == "search":
        scorer_import = ""
        agent_init = SEARCH_AGENT_INIT
    elif scorer == "learned":
        scorer_import = ""
        agent_init = LEARNED_AGENT_INIT
    elif scorer == "rulecore":
        scorer_import = ""
        agent_init = RULECORE_AGENT_INIT
    elif scorer == "lucario":
        scorer_import = ""
        agent_init = LUCARIO_AGENT_INIT
    elif scorer == "lucario_search":
        scorer_import = ""
        agent_init = LUCARIO_SEARCH_AGENT_INIT
    elif scorer == "crustle_search":
        scorer_import = ""
        agent_init = CRUSTLE_SEARCH_AGENT_INIT
    elif scorer == "lucario_mcts":
        scorer_import = ""
        agent_init = LUCARIO_MCTS_AGENT_INIT
    else:
        scorer_import = ""
        agent_init = MAIN_AGENT_INIT

    (build_dir / "main.py").write_text(
        MAIN_PY.format(
            agent_module=agent_module,
            scorer_import=scorer_import,
            agent_init=agent_init,
        ),
        encoding="utf-8",
    )
    shutil.copy2(deck, build_dir / "deck.csv")
    _copytree(ROOT / "agent", build_dir / "agent")
    # Kaggle main.py loads deck_path=/kaggle_simulations/agent/deck.csv —
    # must match the packaged deck, not whatever is currently in live agent/.
    shutil.copy2(deck, build_dir / "agent" / "deck.csv")
    if scorer == "learned" and model_path is not None:
        src_model = model_path if model_path.is_absolute() else ROOT / model_path
        if not src_model.exists():
            raise FileNotFoundError(f"learned model not found: {src_model}")
        dest = build_dir / "agent" / "models" / "distilled_v1.npz"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_model, dest)
    if scorer == "lucario_mcts":
        if model_path is None:
            raise ValueError("--model is required for --scorer lucario_mcts")
        src_model = model_path if model_path.is_absolute() else ROOT / model_path
        if not src_model.exists():
            raise FileNotFoundError(f"Lucario MCTS model not found: {src_model}")
        dest = build_dir / "agent" / "models" / "lucario_model_best.pth"
        dest.parent.mkdir(parents=True, exist_ok=True)
        _copy_torch_checkpoint_compact(src_model, dest)
        if meta_path is not None:
            src_meta = meta_path if meta_path.is_absolute() else ROOT / meta_path
            if src_meta.exists():
                shutil.copy2(src_meta, build_dir / "agent" / "models" / "lucario_run_meta.json")
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
    with tempfile.TemporaryDirectory(prefix="pokemon_submission_", ignore_cleanup_errors=True) as tmp:
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


def run_pre_submit_gates(archive: Path, *, l1_games: int = 12) -> None:
    """L0 smoke + L1 public gate. Raises RuntimeError on failure."""
    import subprocess

    py = sys.executable
    steps = [
        ([py, str(ROOT / "scripts" / "smoke_test.py")], "smoke_test"),
        ([py, str(ROOT / "scripts" / "smoke_replay.py")], "smoke_replay"),
    ]
    for cmd, label in steps:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            out = (proc.stdout or "") + (proc.stderr or "")
            raise RuntimeError(f"{label} failed (rc={proc.returncode})\n{out[-1500:]}")

    proc = subprocess.run(
        [py, str(ROOT / "scripts" / "gate_vs_public.py"),
         "--agent", str(archive), "--games", str(l1_games)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise RuntimeError(f"L1 gate failed (rc={proc.returncode})\n{out[-1500:]}")
    pct = 0.0
    for line in out.splitlines():
        if "SUITE MEAN:" in line:
            try:
                pct = float(line.split("SUITE MEAN:")[1].split("%")[0].strip())
            except ValueError:
                pass
    print(f"pre-submit gates OK — L1 public mean {pct:.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", help="Deck CSV to package. Defaults to agent/deck.csv.")
    parser.add_argument("--agent-module", default="agent.agent")
    parser.add_argument(
        "--name",
        default="submission",
        help="Archive basename. Use a candidate name for dist/candidates/<name>.tar.gz.",
    )
    parser.add_argument(
        "--scorer",
        choices=(
            "heuristic",
            "search",
            "learned",
            "rulecore",
            "lucario",
            "lucario_search",
            "crustle_search",
            "lucario_mcts",
        ),
        default="heuristic",
        help="Agent brain wired in main.py.",
    )
    parser.add_argument(
        "--model",
        help="For learned: npz model. For lucario_mcts: model_best.pth checkpoint.",
    )
    parser.add_argument(
        "--meta",
        help="Optional run_meta.json for --scorer lucario_mcts model dimensions/config.",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="After packaging, run L0 (smoke_test + smoke_replay) and L1 public gate.",
    )
    parser.add_argument("--gate-games", type=int, default=12, help="L1 games per opponent when --gate")
    args = parser.parse_args()

    archive_path = ARCHIVE if args.name == "submission" else ARCHIVE_DIR / f"{args.name}.tar.gz"
    archive = build(
        deck_path=_resolve_path(args.deck),
        agent_module=args.agent_module,
        archive_path=archive_path,
        scorer=args.scorer,
        model_path=_resolve_path(args.model),
        meta_path=_resolve_path(args.meta),
    )
    dry_run_import(archive)
    if args.gate:
        run_pre_submit_gates(archive, l1_games=args.gate_games)
    size_kb = archive.stat().st_size / 1024
    print(f"built {archive} ({size_kb:.1f} KiB)")
    print("dry-run import OK; deck-selection returns 60 card IDs")
    print("No Kaggle submission was attempted.")
    print(
        f"\nBefore upload: python scripts/check_upload_eligible.py "
        f"--brain <scorer> --deck {args.deck} "
        f'--change "YOUR ONE-LINE DELTA" --local-gate 58.0'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
