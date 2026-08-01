#!/usr/bin/env python3
"""Download public PTCG episodes → parse decks/trajectories → RL training assets.

Strategy lock (Archaludon #1 chase):
  1. Download episodes-index + latest N daily episode datasets
  2. Extract top-K leaderboard decks via competition replay API (high value, small)
  3. Mine bulk decks from daily datasets into gauntlet + field opponents
  4. Write BC / expert-iteration style trajectory stubs for high-μ games
  5. Refresh recordings/metrics + STATE snippet; never submits

Usage:
  python scripts/episode_rl_pipeline.py --days 2 --top 10
  python scripts/episode_rl_pipeline.py --top-only --top 10
  python scripts/episode_rl_pipeline.py --bulk-only --days 1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PY = Path(sys.executable)
EPISODES_ROOT = ROOT / "episodes"
RAW_DIR = EPISODES_ROOT / "raw"
INDEX_DIR = EPISODES_ROOT / "index"
REPLAYS_DIR = ROOT / "recordings" / "episodes" / "replays"
METRICS_DIR = ROOT / "recordings" / "metrics"
KEY_MOMENTS = ROOT / "recordings" / "key_moments"
LOGS_DIR = ROOT / "recordings" / "logs"
TRAIN_DIR = ROOT / "data" / "rl_from_episodes"
GAUNTLET_DIR = ROOT / "report" / "deck_rl" / "mined_decks"
FIELD_DECKS = ROOT / "field" / "decks" / "mined_top"
AGENT_DECKS = ROOT / "agent_decks"
PIPELINE_LOG = LOGS_DIR / "episode_rl_pipeline.jsonl"

# Priority meta tags for Archaludon training (user: オーロンゲex + Alakazam)
PRIORITY_ARCHS = {
    "marnie_grimmsnarl_ex",
    "alakazam",
    "crustle_iwapalace",
    "archaludon_ex",
    "dragapult_ex",
    "mega_lucario_ex",
    "cynthia_garchomp_ex",
    "rocket_spidops",
}


def log(event: str, **kw) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kw}
    with PIPELINE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{row['ts']}] {event} {json.dumps(kw, ensure_ascii=False) if kw else ''}", flush=True)


def ensure_token() -> None:
    if os.environ.get("KAGGLE_API_TOKEN"):
        return
    for p in (
        ROOT / ".kaggle" / "access_token",
        ROOT.parent / ".kaggle" / "access_token",
        Path.home() / ".kaggle" / "access_token",
    ):
        if p.exists():
            os.environ["KAGGLE_API_TOKEN"] = p.read_text(encoding="utf-8").strip().splitlines()[0]
            return


def kaggle(args: list[str], timeout: int = 3600) -> tuple[int, str]:
    ensure_token()
    # Prefer venv kaggle
    kag = ROOT.parent / ".venv" / "Scripts" / "kaggle.exe"
    cmd = [str(kag) if kag.exists() else "kaggle", *args]
    env = os.environ.copy()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=str(ROOT))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def run_py(script_args: list[str], timeout: int = 7200) -> tuple[int, str]:
    cmd = [str(PY), *script_args]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=str(ROOT))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def list_recent_episode_slugs(days: int) -> list[str]:
    """Return dataset slugs for recent daily episode packs (newest first)."""
    # Prefer index dataset listing via kaggle datasets list
    code, out = kaggle(
        ["datasets", "list", "-s", "pokemon-tcg-ai-battle-episodes", "--sort-by", "updated", "-v"],
        timeout=120,
    )
    slugs: list[str] = []
    for line in out.splitlines():
        m = re.search(r"(kaggle/pokemon-tcg-ai-battle-episodes-\d{4}-\d{2}-\d{2})", line)
        if m:
            slugs.append(m.group(1))
    # Fallback: construct last N calendar days
    if not slugs:
        today = datetime.now(timezone.utc).date()
        for i in range(1, days + 3):
            d = today - timedelta(days=i)
            slugs.append(f"kaggle/pokemon-tcg-ai-battle-episodes-{d.isoformat()}")
    # dedup preserve order
    seen: set[str] = set()
    out_slugs: list[str] = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            out_slugs.append(s)
    return out_slugs[: max(days, 1)]


def download_index() -> bool:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    marker = INDEX_DIR / ".downloaded"
    if marker.exists() and (time.time() - marker.stat().st_mtime) < 20 * 3600:
        log("index_cached", path=str(INDEX_DIR))
        return True
    log("index_download_start")
    code, out = kaggle(
        [
            "datasets",
            "download",
            "-d",
            "kaggle/pokemon-tcg-ai-battle-episodes-index",
            "-p",
            str(INDEX_DIR),
            "--unzip",
            "-q",
        ],
        timeout=600,
    )
    log("index_download_done", rc=code, tail=out[-400:])
    if code == 0:
        marker.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
        return True
    return False


def download_daily(slug: str) -> Path | None:
    """Download one daily episodes dataset into episodes/raw/<date>/."""
    date_part = slug.rsplit("-", 3)
    # slug: kaggle/pokemon-tcg-ai-battle-episodes-YYYY-MM-DD
    m = re.search(r"(\d{4}-\d{2}-\d{2})$", slug)
    day = m.group(1) if m else slug.replace("/", "_")
    dest = RAW_DIR / day
    dest.mkdir(parents=True, exist_ok=True)
    ready = dest / ".ready"
    if ready.exists():
        njson = sum(1 for _ in dest.rglob("*.json"))
        if njson > 10:
            log("daily_cached", slug=slug, n_json=njson, path=str(dest))
            return dest
    log("daily_download_start", slug=slug, dest=str(dest))
    code, out = kaggle(
        ["datasets", "download", "-d", slug, "-p", str(dest), "--unzip", "-q"],
        timeout=7200,
    )
    # Sometimes zip left unextracted
    for z in dest.glob("*.zip"):
        try:
            with zipfile.ZipFile(z, "r") as zf:
                zf.extractall(dest)
            log("unzipped", zip=z.name)
        except Exception as e:
            log("unzip_fail", zip=z.name, err=str(e))
    njson = sum(1 for _ in dest.rglob("*.json"))
    log("daily_download_done", slug=slug, rc=code, n_json=njson, tail=out[-300:])
    if njson > 0:
        ready.write_text(
            json.dumps({"slug": slug, "n_json": njson, "at": datetime.now(timezone.utc).isoformat()}),
            encoding="utf-8",
        )
        return dest
    return None


def run_top_extract(top: int, episodes_per_team: int) -> dict:
    out = ROOT / "recordings" / "metrics" / "top_extract"
    out.mkdir(parents=True, exist_ok=True)
    log("top_extract_start", top=top, ept=episodes_per_team)
    code, text = run_py(
        [
            "scripts/extract_deck_from_episode.py",
            "--top",
            str(top),
            "--episodes-per-team",
            str(episodes_per_team),
            "--download",
            "--out",
            str(out),
        ],
        timeout=3600,
    )
    log("top_extract_done", rc=code, tail=text[-800:])
    # Load summary if present
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    summary_path = out / f"top_decks_{day}.json"
    if not summary_path.exists():
        # pick newest
        cands = sorted(out.glob("top_decks_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        summary_path = cands[0] if cands else summary_path
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    return {"error": "no_summary", "rc": code, "tail": text[-500:]}


def mine_bulk_decks(replay_roots: list[Path], max_decks: int = 80) -> int:
    """Mine gauntlet decks from bulk episode JSON trees."""
    # Flatten: copy/link path list via mine by pointing extract_gauntlet at each day
    # Use mine_episode_replays / extract_gauntlet_from_replays on each day dir
    total = 0
    GAUNTLET_DIR.mkdir(parents=True, exist_ok=True)
    FIELD_DECKS.mkdir(parents=True, exist_ok=True)
    TRAIN_DIR.mkdir(parents=True, exist_ok=True)

    # Aggregate into a single temp view via extract_gauntlet per root
    for root in replay_roots:
        if not root.exists():
            continue
        code, out = run_py(
            [
                "scripts/extract_gauntlet_from_replays.py",
                "--replays",
                str(root),
                "--out",
                str(GAUNTLET_DIR),
                "--max-decks",
                str(max_decks),
            ],
            timeout=3600,
        )
        log("mine_gauntlet", root=str(root), rc=code, tail=out[-400:])
        total += 1

    # Also run mine_episode_decks if available
    for root in replay_roots:
        code, out = run_py(
            [
                "scripts/mine_episode_decks.py",
                "--episodes",
                str(root),
                "--out-dir",
                str(AGENT_DECKS),
                "--leaders",
                "--report",
                str(METRICS_DIR / f"mined_decks_{root.name}.md"),
            ],
            timeout=3600,
        )
        log("mine_episode_decks", root=str(root), rc=code, tail=out[-400:])

    # Copy gauntlet decks into field/ for gate opponents
    n_copy = 0
    if GAUNTLET_DIR.exists():
        for csvp in GAUNTLET_DIR.glob("*.csv"):
            shutil.copy2(csvp, FIELD_DECKS / csvp.name)
            n_copy += 1
    log("field_decks_synced", n=n_copy, path=str(FIELD_DECKS))
    return n_copy


def build_training_assets(top_summary: dict) -> dict:
    """Convert top decks + mined decks into RL training catalog."""
    TRAIN_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    catalog = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": [
            "behavior_cloning_targets",
            "expert_iteration_opponents",
            "archaludon_matchup_gauntlet",
        ],
        "priority_meta": sorted(PRIORITY_ARCHS),
        "top_teams": [],
        "opponent_decks": [],
        "grimmsnarl_alakazam_focus": [],
    }

    teams = top_summary.get("teams") or []
    for t in teams:
        if t.get("error"):
            continue
        entry = {
            "rank": t.get("rank"),
            "team": t.get("teamName"),
            "mu": t.get("lb_score"),
            "archetype": t.get("primary_archetype"),
            "deck_csv": t.get("deck_csv"),
            "top_cards": t.get("top_cards"),
        }
        catalog["top_teams"].append(entry)
        arch = str(t.get("primary_archetype") or "")
        if any(a in arch for a in ("grimmsnarl", "alakazam", "marnie")):
            catalog["grimmsnarl_alakazam_focus"].append(entry)
        # Copy into train dir
        src = t.get("deck_csv")
        if src and Path(src).exists():
            safe = re.sub(r"[^\w\-]+", "_", f"top{t.get('rank')}_{t.get('teamName')}")[:50]
            dst = TRAIN_DIR / "decks" / f"{safe}.csv"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            # Also agent_decks for gate wiring
            ad = AGENT_DECKS / f"top_mined_{safe}.csv"
            shutil.copy2(src, ad)
            catalog["opponent_decks"].append(str(dst))

    # Index gauntlet
    if GAUNTLET_DIR.exists():
        for p in sorted(GAUNTLET_DIR.glob("*.csv"))[:100]:
            catalog["opponent_decks"].append(str(p))

    outp = METRICS_DIR / "rl_episode_catalog.json"
    outp.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    (TRAIN_DIR / "catalog.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write BC manifest (deck-level expert targets; step-level later)
    bc = {
        "type": "deck_level_expert_targets",
        "n_top_teams": len(catalog["top_teams"]),
        "n_focus_grim_alak": len(catalog["grimmsnarl_alakazam_focus"]),
        "n_opponent_decks": len(catalog["opponent_decks"]),
        "note": "Full decision trajectories require episode step parse; decks ready for matchup gates now.",
    }
    (TRAIN_DIR / "bc_manifest.json").write_text(json.dumps(bc, indent=2), encoding="utf-8")
    (METRICS_DIR / "bc_manifest.json").write_text(json.dumps(bc, indent=2), encoding="utf-8")
    log("training_assets_built", path=str(outp), n_opp=len(catalog["opponent_decks"]))
    return catalog


def extract_decision_stubs(replay_dirs: list[Path], max_files: int = 200) -> int:
    """Lightweight decision sequence extraction for expert-iteration stubs."""
    out_dir = TRAIN_DIR / "trajectories"
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    files: list[Path] = []
    for d in replay_dirs:
        if not d.exists():
            continue
        files.extend(list(d.rglob("*.json"))[: max_files // max(len(replay_dirs), 1)])
    files = files[:max_files]

    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        steps = data.get("steps") or []
        if len(steps) < 2:
            continue
        teams = (data.get("info") or {}).get("TeamNames") or [None, None]
        rewards = data.get("rewards") or [None, None]
        # Sample action types across steps (cheap)
        action_hist: list[dict] = []
        for si, step in enumerate(steps[:80]):
            if not isinstance(step, list):
                continue
            for pi, agent in enumerate(step[:2]):
                if not isinstance(agent, dict):
                    continue
                act = agent.get("action")
                if act is None:
                    continue
                action_hist.append(
                    {
                        "step": si,
                        "player": pi,
                        "action_type": type(act).__name__,
                        "action_len": len(act) if isinstance(act, list) else None,
                    }
                )
        if not action_hist:
            continue
        stub = {
            "episode_file": str(fp),
            "teams": teams,
            "rewards": rewards,
            "n_steps": len(steps),
            "action_samples": action_hist[:40],
            "winner": 0 if (rewards and rewards[0] == 1) else (1 if rewards and len(rewards) > 1 and rewards[1] == 1 else None),
        }
        outp = out_dir / f"{fp.stem}_traj.json"
        outp.write_text(json.dumps(stub, indent=2, ensure_ascii=False), encoding="utf-8")
        n += 1
    log("trajectory_stubs", n=n, dir=str(out_dir))
    return n


def write_gate_hint(catalog: dict) -> None:
    """Write opponent list for Archaludon matchup focus (Grimmsnarl + Alakazam)."""
    focus = catalog.get("grimmsnarl_alakazam_focus") or []
    all_top = catalog.get("top_teams") or []
    hint = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "primary": "archaludon",
        "priority_matchups": ["marnie_grimmsnarl_ex", "alakazam"],
        "focus_decks": [t.get("deck_csv") for t in focus if t.get("deck_csv")],
        "all_top_decks": [t.get("deck_csv") for t in all_top if t.get("deck_csv")],
        "gauntlet_dir": str(GAUNTLET_DIR),
        "field_mined": str(FIELD_DECKS),
        "instruction": "gate_archaludon / selfplay should include these as extra opponents when present",
    }
    path = METRICS_DIR / "archaludon_matchup_hint.json"
    path.write_text(json.dumps(hint, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "dist" / "archaludon_matchup_hint.json").write_text(
        json.dumps(hint, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log("matchup_hint", path=str(path), n_focus=len(hint["focus_decks"]))


def update_state_snippet(summary: dict) -> None:
    state = ROOT / "STATE.md"
    block = (
        f"\n### Episode RL pipeline {datetime.now().isoformat(timespec='seconds')}\n"
        f"- days: {summary.get('days_downloaded')}\n"
        f"- top extract teams: {summary.get('n_top_teams')}\n"
        f"- decks mined to field: {summary.get('n_field_decks')}\n"
        f"- trajectories: {summary.get('n_traj')}\n"
        f"- paths: `episodes/raw`, `recordings/metrics`, `data/rl_from_episodes`\n"
        f"- focus: Grimmsnarl/Alakazam matchups for Archaludon\n"
    )
    if state.exists():
        text = state.read_text(encoding="utf-8")
        if "## Episode RL" not in text:
            text = text.rstrip() + "\n\n## Episode RL\n" + block + "\n"
        else:
            text = text + block
        state.write_text(text, encoding="utf-8")
    KEY_MOMENTS.mkdir(parents=True, exist_ok=True)
    (KEY_MOMENTS / f"episode_rl_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def cleanup_old_days(keep_days: int = 3) -> None:
    if not RAW_DIR.exists():
        return
    days = sorted([p for p in RAW_DIR.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
    for old in days[keep_days:]:
        try:
            shutil.rmtree(old)
            log("cleaned_old_day", path=str(old))
        except Exception as e:
            log("clean_fail", path=str(old), err=str(e))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=2, help="Latest daily episode datasets to download")
    ap.add_argument("--top", type=int, default=10, help="Leaderboard top N for targeted replay extract")
    ap.add_argument("--episodes-per-team", type=int, default=4)
    ap.add_argument("--top-only", action="store_true")
    ap.add_argument("--bulk-only", action="store_true")
    ap.add_argument("--keep-days", type=int, default=3)
    ap.add_argument("--max-traj", type=int, default=150)
    args = ap.parse_args()

    ensure_token()
    for d in (EPISODES_ROOT, RAW_DIR, INDEX_DIR, REPLAYS_DIR, METRICS_DIR, TRAIN_DIR, KEY_MOMENTS, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    summary: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "days_downloaded": [],
        "n_top_teams": 0,
        "n_field_decks": 0,
        "n_traj": 0,
        "top_archetypes": [],
    }

    download_index()

    bulk_roots: list[Path] = []
    if not args.top_only:
        slugs = list_recent_episode_slugs(args.days)
        log("slugs", slugs=slugs)
        for slug in slugs:
            dest = download_daily(slug)
            if dest:
                bulk_roots.append(dest)
                summary["days_downloaded"].append(dest.name)

    top_summary: dict = {}
    if not args.bulk_only:
        top_summary = run_top_extract(args.top, args.episodes_per_team)
        teams = top_summary.get("teams") or []
        summary["n_top_teams"] = len([t for t in teams if not t.get("error")])
        summary["top_archetypes"] = [
            {"rank": t.get("rank"), "team": t.get("teamName"), "arch": t.get("primary_archetype"), "mu": t.get("lb_score")}
            for t in teams
            if not t.get("error")
        ]
        # top extract replays dir
        top_replays = ROOT / "recordings" / "metrics" / "top_extract" / "replays"
        if top_replays.exists():
            bulk_roots.append(top_replays)

    if bulk_roots:
        summary["n_field_decks"] = mine_bulk_decks(bulk_roots)
        summary["n_traj"] = extract_decision_stubs(bulk_roots, max_files=args.max_traj)

    catalog = build_training_assets(top_summary if top_summary else {"teams": []})
    write_gate_hint(catalog)
    cleanup_old_days(args.keep_days)

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    summary["catalog"] = str(TRAIN_DIR / "catalog.json")
    summary["metrics"] = str(METRICS_DIR)
    update_state_snippet(summary)
    log("pipeline_done", **{k: v for k, v in summary.items() if k != "top_archetypes"})
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
