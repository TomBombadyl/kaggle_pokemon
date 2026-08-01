#!/usr/bin/env python3
"""Lean high-value episode pull — size-capped, top-ladder only.

Avoids multi-GB daily episode dumps (~20GB uncompressed/day). Instead:
  1. Read public leaderboard top N (default 25)
  2. For each team: best submission → recent PUBLIC episodes
  3. Download only those replay JSONs
  4. Extract decks + archetype tags
  5. Enforce disk budget; delete low-value / over-budget files
  6. Write training-ready deck CSVs + index under recordings/

Usage:
  python scripts/pull_high_value_episodes.py
  python scripts/pull_high_value_episodes.py --top 25 --episodes-per-team 3 --budget-gb 3
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.extract_deck_from_episode import (  # noqa: E402
    best_submission_for_team,
    classify_archetype,
    download_replay,
    extract_decks_from_file,
    fetch_leaderboard_top,
    list_episode_ids,
    load_card_table,
    safe_slug,
    write_deck_csv,
    write_named_list,
)

HV_ROOT = ROOT / "recordings" / "episodes_high_value"
REPLAY_DIR = HV_ROOT / "replays"
DECK_DIR = HV_ROOT / "decks"
AGENT_DIR = ROOT / "agent_decks" / "mined_top"
FIELD_DIR = ROOT / "field" / "mined_top"


def dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def enforce_budget(root: Path, budget_bytes: int) -> int:
    """Delete oldest/lowest-priority replays until under budget. Returns deleted count."""
    replays = sorted(
        (REPLAY_DIR.glob("ep*.json") if REPLAY_DIR.exists() else []),
        key=lambda p: p.stat().st_mtime,
    )
    deleted = 0
    while dir_size_bytes(root) > budget_bytes and replays:
        victim = replays.pop(0)  # oldest first
        try:
            victim.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            break
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=25, help="leaderboard top N teams")
    ap.add_argument("--episodes-per-team", type=int, default=3)
    ap.add_argument("--budget-gb", type=float, default=3.0, help="max keep under HV_ROOT")
    ap.add_argument("--hard-cap-gb", type=float, default=18.0, help="absolute refuse if would exceed")
    args = ap.parse_args()

    budget = int(args.budget_gb * (1024**3))
    hard = int(args.hard_cap_gb * (1024**3))
    HV_ROOT.mkdir(parents=True, exist_ok=True)
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    DECK_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    FIELD_DIR.mkdir(parents=True, exist_ok=True)

    # refuse if recordings already huge
    rec_size = dir_size_bytes(ROOT / "recordings")
    if rec_size > hard:
        print(f"[abort] recordings already {rec_size/1e9:.2f}GB > hard cap {args.hard_cap_gb}GB")
        return 2

    cards = load_card_table()
    print(f"[hv] leaderboard top {args.top}…")
    teams = fetch_leaderboard_top(args.top)
    if not teams:
        print("[error] empty leaderboard")
        return 1
    print(f"[hv] got {len(teams)} teams; budget={args.budget_gb}GB")

    kept_eps: list[dict] = []
    decks_by_arch: dict[str, list] = {}
    team_reps: list[dict] = []
    failed_dl = 0

    for rank, team in enumerate(teams, 1):
        tid = team["teamId"]
        tname = team["teamName"]
        mu = team.get("score")
        print(f"\n#{rank:02d} {tname} μ={mu} team={tid}")
        sub = best_submission_for_team(tid)
        if not sub:
            print("  no submission")
            continue
        sid = sub["submissionId"]
        eids = list_episode_ids(sid, limit=args.episodes_per_team)
        print(f"  sub={sid} episodes={eids}")
        focus_decks: list[dict] = []

        for eid in eids:
            if dir_size_bytes(HV_ROOT) > budget:
                print("  [budget] stop downloading more")
                break
            path = download_replay(eid, REPLAY_DIR)
            if not path or not path.exists() or path.stat().st_size < 1000:
                failed_dl += 1
                print(f"  ep{eid}: FAIL")
                continue
            # normalize name
            target = REPLAY_DIR / f"ep{eid}.json"
            if path.resolve() != target.resolve():
                try:
                    target.write_bytes(path.read_bytes())
                    path = target
                except Exception:
                    pass

            recs = extract_decks_from_file(path)
            print(f"  ep{eid}: {path.stat().st_size//1024}KB decks={len(recs)}")
            kept_eps.append(
                {
                    "episode_id": eid,
                    "path": str(path.relative_to(ROOT)),
                    "bytes": path.stat().st_size,
                    "team": tname,
                    "rank": rank,
                    "lb_score": mu,
                    "submission_id": sid,
                    "n_decks": len(recs),
                }
            )
            for r in recs:
                deck = r.get("deck") or []
                if len(deck) != 60:
                    continue
                meta = classify_archetype(deck, cards)
                arch = meta["primary_archetype"]
                match = (
                    r.get("team")
                    and tname
                    and str(r["team"]).strip().lower() == str(tname).strip().lower()
                )
                rec = {
                    **{k: v for k, v in r.items() if k != "deck"},
                    "deck": deck,
                    "rank": rank,
                    "teamName": tname,
                    "lb_score": mu,
                    "submissionId": sid,
                    "is_focus_team": bool(match),
                    **meta,
                }
                decks_by_arch.setdefault(arch, []).append(rec)
                if match:
                    focus_decks.append(rec)
                    slug = safe_slug(tname)
                    csv_path = DECK_DIR / f"r{rank:02d}_{slug}_ep{eid}.csv"
                    write_deck_csv(deck, csv_path)
                    write_named_list(deck, cards, DECK_DIR / f"r{rank:02d}_{slug}_ep{eid}_named.txt")

        # representative deck → agent_decks + field for Archaludon training
        rep = next((d for d in focus_decks if d.get("reward") == 1), None)
        if rep is None and focus_decks:
            rep = focus_decks[0]
        if rep:
            slug = safe_slug(tname)
            canon = DECK_DIR / f"top{rank:02d}_{slug}.csv"
            write_deck_csv(rep["deck"], canon)
            write_deck_csv(rep["deck"], AGENT_DIR / f"top{rank:02d}_{slug}.csv")
            write_deck_csv(rep["deck"], FIELD_DIR / f"top{rank:02d}_{slug}.csv")
            team_reps.append(
                {
                    "rank": rank,
                    "teamName": tname,
                    "lb_score": mu,
                    "archetype": rep.get("primary_archetype"),
                    "top_cards": [c["name"] for c in rep.get("top_cards", [])[:6]],
                    "deck_csv": str(canon.relative_to(ROOT)),
                    "episode_id": rep.get("episode_id"),
                }
            )
            print(f"  REP {rep.get('primary_archetype')} {[c['name'] for c in rep.get('top_cards', [])[:5]]}")

    deleted = enforce_budget(HV_ROOT, budget)
    # also prune stray non-hv day dumps under recordings/_tmp*
    for p in (ROOT / "recordings").glob("_tmp*"):
        if p.is_dir():
            import shutil

            shutil.rmtree(p, ignore_errors=True)

    # archetype histogram
    arch_counts = {k: len(v) for k, v in sorted(decks_by_arch.items(), key=lambda x: -len(x[1]))}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "leaderboard_top_public_episodes",
        "top_n": args.top,
        "episodes_per_team": args.episodes_per_team,
        "budget_gb": args.budget_gb,
        "dates_note": "public episodes from current ladder submissions (not full daily dumps)",
        "n_teams": len(teams),
        "n_episodes_kept": len(kept_eps),
        "n_team_reps": len(team_reps),
        "failed_downloads": failed_dl,
        "deleted_for_budget": deleted,
        "size_bytes": dir_size_bytes(HV_ROOT),
        "size_mb": round(dir_size_bytes(HV_ROOT) / (1024**2), 1),
        "recordings_total_mb": round(dir_size_bytes(ROOT / "recordings") / (1024**2), 1),
        "paths": {
            "root": str(HV_ROOT.relative_to(ROOT)),
            "replays": str(REPLAY_DIR.relative_to(ROOT)),
            "decks": str(DECK_DIR.relative_to(ROOT)),
            "agent_decks": str(AGENT_DIR.relative_to(ROOT)),
            "field": str(FIELD_DIR.relative_to(ROOT)),
        },
        "archetype_counts": arch_counts,
        "team_reps": team_reps,
        "episodes": kept_eps,
    }
    out_json = HV_ROOT / "index.json"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # human summary
    md = [
        f"# High-value episodes — {report['generated_at'][:19]}Z",
        "",
        f"- Teams: top **{args.top}** | Episodes kept: **{len(kept_eps)}** | Size: **{report['size_mb']} MB**",
        f"- Budget: {args.budget_gb} GB | Recordings total: {report['recordings_total_mb']} MB",
        f"- Paths: `{report['paths']['root']}`",
        "",
        "## Top decks restored",
        "",
        "| Rank | Team | μ | Archetype | Top cards |",
        "|-----:|------|--:|-----------|-----------|",
    ]
    for t in team_reps:
        md.append(
            f"| {t['rank']} | {t['teamName']} | {t.get('lb_score')} | "
            f"{t.get('archetype')} | {', '.join(t.get('top_cards') or [])} |"
        )
    md += ["", "## Archetype mix", ""]
    for a, n in list(arch_counts.items())[:15]:
        md.append(f"- **{a}**: {n}")
    (HV_ROOT / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\n========== HIGH-VALUE EPISODE REPORT ==========")
    print(f"episodes_kept={len(kept_eps)} size_mb={report['size_mb']} path={HV_ROOT}")
    print(f"archetypes={arch_counts}")
    print(f"reps={len(team_reps)} failed_dl={failed_dl} deleted={deleted}")
    print(f"index -> {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
