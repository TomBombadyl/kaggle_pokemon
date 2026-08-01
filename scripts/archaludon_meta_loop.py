#!/usr/bin/env python3
"""Archaludon meta-improvement loop (Grimmsnarl + Crustle focus).

- Gate vs field/registry meta / meta_fast suites (mined top decks)
- Deep core for variance control
- Package only; auto-submit only if meta WR clears bar AND daily cap remains
- Does not stop; sleeps between cycles

Usage:
  python scripts/archaludon_meta_loop.py
  python scripts/archaludon_meta_loop.py --once --games 24
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONPATH", str(ROOT) + os.pathsep + str(ROOT / "data" / "sim" / "sample_submission"))

PY = sys.executable
LOG = ROOT / "report" / "archaludon_meta" / "loop.jsonl"
STATE_SNIP = ROOT.parent / "STATE.md"
# Current ladder pin to beat (live reading 2026-07-30)
LADDER_PIN_MU = 798.4
# Meta suite uses random pilots on top lists (smoke only). Submit bar = deep CORE.
SUBMIT_META_WR = 70.0  # vs random meta decks — only soft filter
SUBMIT_CORE_WR = 58.0  # real official pilots — hard bar for submit


def log(event: str, **kw) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **kw}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{row['ts']}] {event} { {k:v for k,v in kw.items() if k!='tail'} }", flush=True)


def run(args: list[str], timeout: int = 3600) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "data" / "sim" / "sample_submission")
    env.setdefault("PYTHONUTF8", "1")
    p = subprocess.run(
        [PY] + args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def parse_overall_wr(text: str) -> float | None:
    m = re.search(r"OVERALL[^\n]*?([0-9]+(?:\.[0-9]+)?)\s*%", text, re.I)
    if m:
        return float(m.group(1))
    return None


def parse_matchup_wrs(text: str) -> dict[str, float]:
    out = {}
    for line in text.splitlines():
        # e.g. "  meta_grimmsnarl_dries ... 45.0%"
        m = re.search(r"^\s*(\S+)\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%", line)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def gate(suite: str, games: int) -> dict:
    code, out = run(
        ["scripts/gate_archaludon.py", "--games", str(games), "--suite", suite],
        timeout=max(900, games * 120),
    )
    wr = parse_overall_wr(out)
    mus = parse_matchup_wrs(out)
    log("gate", suite=suite, games=games, wr=wr, matchups=mus, rc=code, tail=out[-800:])
    return {"rc": code, "wr": wr, "matchups": mus, "out": out}


def package() -> Path | None:
    code, out = run(["scripts/package_archaludon.py"], timeout=300)
    log("package", rc=code, tail=out[-400:])
    tar = ROOT / "dist" / "candidates" / "archaludon.tar.gz"
    return tar if tar.exists() and code == 0 else None


def submits_today() -> int:
    p = ROOT / "dist" / "submit_count.json"
    if not p.exists():
        return 0
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        from datetime import date

        if d.get("date") != date.today().isoformat():
            return 0
        return int(d.get("count", 0))
    except Exception:
        return 0


def maybe_submit(tar: Path, meta_wr: float, core_wr: float | None) -> bool:
    n = submits_today()
    if n >= 5:
        log("submit_skip", reason="daily_cap", n=n)
        return False
    if meta_wr is None or meta_wr < SUBMIT_META_WR:
        log("submit_skip", reason="meta_wr_low", meta_wr=meta_wr, need=SUBMIT_META_WR)
        return False
    if core_wr is not None and core_wr < SUBMIT_CORE_WR:
        log("submit_skip", reason="core_wr_low", core_wr=core_wr, need=SUBMIT_CORE_WR)
        return False
    msg = (
        f"Arch R13 grimmsnarl+crustle levers metaWR={meta_wr:.1f} "
        f"coreWR={core_wr} pin~{LADDER_PIN_MU}"
    )
    code, out = run(
        [
            "scripts/auto_submit.py",
            "--file",
            str(tar),
            "--message",
            msg[:100],
            "--local-gate",
            str(meta_wr),
            "--strength-note",
            f"meta_fast WR={meta_wr}; core={core_wr}; R13 grimmsnarl levers",
        ],
        timeout=300,
    )
    log("submit", rc=code, tail=out[-500:])
    return code == 0


def refresh_root_state(meta: dict, core: dict) -> None:
    if not STATE_SNIP.exists():
        return
    now = datetime.now().isoformat(timespec="seconds")
    block = f"""
## Archaludon meta loop ({now})

| Item | Value |
|------|-------|
| Ladder pin (best today) | ~{LADDER_PIN_MU} μ (ref 55094337) |
| Meta-fast WR | {meta.get('wr')} matchups={meta.get('matchups')} |
| Core WR | {core.get('wr')} |
| Submits today | {submits_today()}/5 |
| Levers | R13 Grimmsnarl + existing Crustle |
| CUDA | available for Lucario field MCTS (parallel) |
| Next submit if | meta≥{SUBMIT_META_WR}% and core≥{SUBMIT_CORE_WR}% |
"""
    text = STATE_SNIP.read_text(encoding="utf-8")
    marker = "## Archaludon meta loop"
    if marker in text:
        import re as _re

        text = _re.sub(r"## Archaludon meta loop.*?(?=\n## |\Z)", block.strip() + "\n\n", text, flags=_re.S)
    else:
        text = text.rstrip() + "\n" + block
    STATE_SNIP.write_text(text, encoding="utf-8")


def maybe_mcts_background() -> None:
    """Kick Lucario CUDA field train if free (does not block Arch gates)."""
    train = ROOT / "scripts" / "train_lucario_field_mcts.py"
    if not train.exists():
        return
    try:
        import torch

        if not torch.cuda.is_available():
            return
    except Exception:
        return
    logf = ROOT / "report" / "archaludon_meta" / "mcts_side.log"
    logf.parent.mkdir(parents=True, exist_ok=True)
    # only one
    try:
        subprocess.Popen(
            [PY, str(train), "--device", "cuda", "--cycles", "2"],
            cwd=str(ROOT),
            stdout=open(logf, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )
        log("mcts_spawned", log=str(logf))
    except Exception as e:
        log("mcts_spawn_fail", err=str(e))


def cycle(games_meta: int, games_core: int, do_submit: bool) -> None:
    log("cycle_start", games_meta=games_meta, games_core=games_core)
    meta = gate("meta_fast", games_meta)
    core = gate("core", games_core)
    refresh_root_state(meta, core)
    tar = package()
    if do_submit and tar and meta.get("wr") is not None:
        maybe_submit(tar, meta["wr"], core.get("wr"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--games-meta", type=int, default=24)
    ap.add_argument("--games-core", type=int, default=20)
    ap.add_argument("--sleep", type=int, default=90)
    ap.add_argument("--no-submit", action="store_true")
    ap.add_argument("--mcts-side", action="store_true", help="also spawn CUDA Lucario MCTS side job")
    args = ap.parse_args()

    log("loop_start", pin=LADDER_PIN_MU, submit_bar=SUBMIT_META_WR)
    if args.mcts_side:
        maybe_mcts_background()

    while True:
        try:
            cycle(args.games_meta, args.games_core, do_submit=not args.no_submit)
        except Exception as e:
            log("cycle_error", err=str(e))
        if args.once:
            break
        time.sleep(args.sleep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
