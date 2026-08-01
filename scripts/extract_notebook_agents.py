#!/usr/bin/env python3
"""Scan downloaded Kaggle notebooks and extract agents / decks / search code.

Inputs:
  notebooks/kaggle_pull/<slug>/*.ipynb (+ optional output/)

Outputs:
  extracted_agents/<slug>/          main.py / agent snippets / MANIFEST.json
  agent_decks/from_notebooks/       deck CSVs when found
  recordings/metrics/notebook_extracts/  summary + usability flags

Usage:
  python scripts/extract_notebook_agents.py
  python scripts/extract_notebook_agents.py --src notebooks/kaggle_pull
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "notebooks" / "kaggle_pull"
OUT_AGENTS = ROOT / "extracted_agents"
OUT_DECKS = ROOT / "agent_decks" / "from_notebooks"
OUT_METRICS = ROOT / "recordings" / "metrics" / "notebook_extracts"

WRITEFILE_RE = re.compile(r"^%%writefile\s+(\S+)\s*$", re.M)
DECK_NAMES = {"DECK", "my_deck", "deck", "MY_DECK", "deck_list", "CARD_IDS", "card_ids"}


def code_cells(nb_path: Path) -> list[str]:
    nb = json.loads(nb_path.read_text(encoding="utf-8", errors="replace"))
    out = []
    for c in nb.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = c.get("source", [])
        if isinstance(src, list):
            out.append("".join(src))
        else:
            out.append(str(src))
    return out


def extract_writefiles(cells: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for src in cells:
        m = WRITEFILE_RE.search(src.lstrip())
        if not m:
            continue
        name = m.group(1).strip()
        body = src.split("\n", 1)[1] if "\n" in src else ""
        # strip leading magic line variants
        if body.lstrip().startswith("%%writefile"):
            body = body.split("\n", 1)[1] if "\n" in body else ""
        files[name] = body
    return files


def _int_list(node: ast.AST) -> list[int] | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    out = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, int):
            out.append(elt.value)
        else:
            return None
    return out


def extract_decks_from_cells(cells: list[str]) -> list[tuple[str, list[int]]]:
    found: list[tuple[str, list[int]]] = []
    # writefile deck.csv
    for name, body in extract_writefiles(cells).items():
        if name.endswith(".csv") or "deck" in name.lower():
            ids = [int(x) for x in body.splitlines() if x.strip().lstrip("-").isdigit()]
            if len(ids) >= 40:
                found.append((name, ids[:60] if len(ids) >= 60 else ids))
    # list literals
    for src in cells:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id in DECK_NAMES:
                        lst = _int_list(node.value)
                        if lst and len(lst) >= 40:
                            found.append((tgt.id, lst[:60] if len(lst) >= 60 else lst))
    return found


def detect_entrypoints(text: str) -> list[str]:
    hits = []
    patterns = [
        (r"def\s+agent\s*\(", "def agent(...)"),
        (r"def\s+act\s*\(", "def act(...)"),
        (r"class\s+\w*Agent\w*\s*\(", "class *Agent"),
        (r"def\s+select\s*\(", "def select(...)"),
        (r"MCTS|mcts|UCB1|ucb1|MonteCarlo", "MCTS/UCB keywords"),
        (r"battle_start|battle_select", "cg battle loop"),
        (r"stable_baselines|PPO|DQN|gymnasium", "RL library"),
    ]
    for pat, label in patterns:
        if re.search(pat, text):
            hits.append(label)
    return hits


def usability(entrypoints: list[str], writefiles: dict[str, str], has_deck: bool) -> dict:
    has_agent = any("agent" in e.lower() or "act" in e.lower() or "Agent" in e for e in entrypoints)
    has_main = any(k.endswith("main.py") or k == "main.py" for k in writefiles)
    has_mcts = any("MCTS" in e or "UCB" in e for e in entrypoints)
    deps = []
    blob = "\n".join(writefiles.values())
    for pkg in ("torch", "stable_baselines", "gymnasium", "numpy", "pandas", "cg"):
        if re.search(rf"\b{pkg}\b", blob) or re.search(rf"import {pkg}|from {pkg}", blob):
            deps.append(pkg)
    if has_main and has_agent:
        status = "ready_integrate"
    elif has_agent or has_mcts:
        status = "needs_rewrite"
    elif has_deck:
        status = "deck_only"
    else:
        status = "analysis_only"
    return {
        "status": status,
        "has_agent_entry": has_agent,
        "has_main_py": has_main,
        "has_mcts_search": has_mcts,
        "has_deck": has_deck,
        "deps": deps,
    }


def process_notebook(nb: Path, slug: str) -> dict:
    cells = code_cells(nb)
    writefiles = extract_writefiles(cells)
    decks = extract_decks_from_cells(cells)
    full_text = "\n\n".join(cells)
    entries = detect_entrypoints(full_text)

    agent_dir = OUT_AGENTS / slug
    agent_dir.mkdir(parents=True, exist_ok=True)
    # save writefiles
    saved_files = []
    for name, body in writefiles.items():
        # sanitize path
        safe = name.replace("\\", "/").lstrip("/")
        if ".." in safe:
            continue
        dest = agent_dir / Path(safe).name
        dest.write_text(body, encoding="utf-8")
        saved_files.append(str(dest.relative_to(ROOT)))

    # also dump concatenated code for search if no writefile
    if not writefiles:
        (agent_dir / "_notebook_code.py").write_text(full_text, encoding="utf-8")
        saved_files.append(str((agent_dir / "_notebook_code.py").relative_to(ROOT)))

    # decks
    deck_paths = []
    for i, (label, ids) in enumerate(decks):
        if len(ids) < 40:
            continue
        # pad/truncate to 60 only if exactly 60 preferred
        out_name = f"{slug}_{i}_{re.sub(r'[^\\w]+', '_', label)[:40]}.csv"
        dp = OUT_DECKS / out_name
        OUT_DECKS.mkdir(parents=True, exist_ok=True)
        # if not 60, still write with note
        dp.write_text("\n".join(str(x) for x in ids) + "\n", encoding="utf-8")
        deck_paths.append({"path": str(dp.relative_to(ROOT)), "n": len(ids), "label": label})

    use = usability(entries, writefiles, bool(deck_paths))
    manifest = {
        "slug": slug,
        "notebook": str(nb.relative_to(ROOT)) if nb.is_relative_to(ROOT) else str(nb),
        "n_code_cells": len(cells),
        "writefiles": list(writefiles.keys()),
        "saved_files": saved_files,
        "entrypoints": entries,
        "decks": deck_paths,
        "usability": use,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
    (agent_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    args = ap.parse_args()
    src = Path(args.src)
    OUT_AGENTS.mkdir(parents=True, exist_ok=True)
    OUT_DECKS.mkdir(parents=True, exist_ok=True)
    OUT_METRICS.mkdir(parents=True, exist_ok=True)

    manifests = []
    if not src.exists():
        print(f"[error] src missing: {src}")
        return 1

    for nb in sorted(src.rglob("*.ipynb")):
        # skip checkpoints
        if ".ipynb_checkpoints" in str(nb):
            continue
        # slug = parent folder under kaggle_pull if possible
        try:
            rel = nb.relative_to(src)
            slug = rel.parts[0] if len(rel.parts) > 1 else nb.stem
        except ValueError:
            slug = nb.stem
        print(f"[extract] {slug} <- {nb.name}")
        try:
            m = process_notebook(nb, slug)
            manifests.append(m)
            print(f"  status={m['usability']['status']} writefiles={m['writefiles']} decks={len(m['decks'])}")
        except Exception as e:
            print(f"  FAIL {e}")
            manifests.append({"slug": slug, "error": str(e)})

    # also scan output dirs for deck csv / py
    for out_py in src.rglob("output/**/*.py"):
        slug = out_py.relative_to(src).parts[0]
        dest = OUT_AGENTS / slug / "output" / out_py.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_py, dest)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "src": str(src),
        "n_notebooks": len(manifests),
        "by_status": dict(Counter(m.get("usability", {}).get("status", m.get("error", "err")) for m in manifests)),
        "items": manifests,
        "paths": {
            "agents": str(OUT_AGENTS.relative_to(ROOT)),
            "decks": str(OUT_DECKS.relative_to(ROOT)),
            "metrics": str(OUT_METRICS.relative_to(ROOT)),
        },
    }
    out_json = OUT_METRICS / "extract_summary.json"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # human md
    lines = [
        f"# Notebook extract summary — {summary['generated_at'][:19]}Z",
        "",
        f"Source: `{src}`",
        f"Agents: `{OUT_AGENTS.relative_to(ROOT)}` | Decks: `{OUT_DECKS.relative_to(ROOT)}`",
        "",
        "| Slug | Status | Entrypoints | Writefiles | Decks |",
        "|------|--------|-------------|------------|------:|",
    ]
    for m in manifests:
        if "error" in m:
            lines.append(f"| {m.get('slug')} | ERROR | {m['error'][:40]} | | |")
            continue
        u = m["usability"]
        lines.append(
            f"| {m['slug']} | **{u['status']}** | {', '.join(m['entrypoints'][:4]) or '—'} | "
            f"{', '.join(m['writefiles'][:4]) or '—'} | {len(m['decks'])} |"
        )
    lines += [
        "",
        "## Archaludon usage tips",
        "",
        "- **official_* rule agents**: use as field opponents (already in `agent/`); re-extract keeps reference main.py",
        "- **official_rl_mcts**: copy train/MCTS loop ideas into CUDA field train; do not ship raw torch in submission",
        "- **alakazam_search_***: search/audit patterns for matchup levers; decks if present → from_notebooks",
        "- **sample_archaludon_75wr / archaludon_metal_gpu_***: highest priority for Archaludon imitation",
        "- **meta_router / advanced_heuristic**: strategy notes + heuristics, usually needs rewrite",
        "",
    ]
    (OUT_METRICS / "EXTRACT_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[done] {out_json}")
    print(f"[done] {(OUT_METRICS / 'EXTRACT_SUMMARY.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
