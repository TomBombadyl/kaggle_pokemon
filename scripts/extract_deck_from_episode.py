#!/usr/bin/env python3
"""Extract full 60-card decks from PTCG Simulation episode replays.

Primary path (omniscient board state):
  steps[0][0].visualize[0].current.players[j].deck

Fallback (deck-select action at game start):
  steps[0][0].visualize[0].action[j]   # list of 60 card IDs

Usage:
  python scripts/extract_deck_from_episode.py --episode-id 88887914
  python scripts/extract_deck_from_episode.py --json path/to/replay.json
  python scripts/extract_deck_from_episode.py --top 6 --download --out recordings/metrics
  python scripts/extract_deck_from_episode.py --batch-dir data/episodes/raw
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMP = "pokemon-tcg-ai-battle"
PY = sys.executable

# High-signal Pokémon / archetype markers (card ID → label)
# Expanded for 2026-07 meta (Grimmsnarl / Alakazam / Crustle / Spidops / Garchomp / Dragapult)
ARCHETYPE_MARKERS: dict[int, str] = {
    # Dragapult line
    119: "Dreepy",
    120: "Drakloak",
    121: "Dragapult ex",
    # Alakazam / Abra line (フーディン)
    739: "Abra",
    740: "Kadabra",
    741: "Alakazam",
    742: "Alakazam ex",
    # Lucario
    677: "Riolu",
    678: "Mega Lucario ex",
    # Abomasnow
    721: "Snover",
    722: "Abomasnow",
    723: "Mega Abomasnow ex",
    # Archaludon
    169: "Duraludon",
    190: "Archaludon ex",
    # Crustle / イワパレス line (common IDs in pool)
    344: "Dwebble",
    345: "Crustle",
    532: "Crustle",
    # Spidops / ワナイダー (Team Rocket)
    # names resolved dynamically; IDs filled from card CSV when possible
    # Garchomp / ガブリアス
    # Grimmsnarl / オーロンゲ / Marnie
}

# Name-substring tags for archetype (case-insensitive)
NAME_ARCHETYPE_RULES: list[tuple[str, str]] = [
    ("grimmsnarl", "marnie_grimmsnarl_ex"),
    ("morgrem", "marnie_grimmsnarl_ex"),
    ("impidimp", "marnie_grimmsnarl_ex"),
    ("marnie's", "marnie_grimmsnarl_ex"),
    ("alakazam", "alakazam"),
    ("kadabra", "alakazam"),
    ("abra", "alakazam"),
    ("crustle", "crustle_iwapalace"),
    ("dwebble", "crustle_iwapalace"),
    ("spidops", "rocket_spidops"),
    ("tarountula", "rocket_spidops"),
    ("garchomp", "cynthia_garchomp_ex"),
    ("gible", "cynthia_garchomp_ex"),
    ("gabite", "cynthia_garchomp_ex"),
    ("cynthia", "cynthia_line"),
    ("dragapult", "dragapult_ex"),
    ("dreepy", "dragapult_ex"),
    ("drakloak", "dragapult_ex"),
    ("lucario", "mega_lucario_ex"),
    ("riolu", "mega_lucario_ex"),
    ("archaludon", "archaludon_ex"),
    ("duraludon", "archaludon_ex"),
    ("zoroark", "n_zoroark_ex"),
    ("zorua", "n_zoroark_ex"),
    ("abomasnow", "mega_abomasnow_ex"),
    ("snover", "mega_abomasnow_ex"),
    ("starmie", "starmie"),
    ("staryu", "starmie"),
    ("kangaskhan", "mega_kangaskhan_ogerpon"),
    ("ogerpon", "mega_kangaskhan_ogerpon"),
    ("munkidori", "marnie_grimmsnarl_ex"),  # common darkness engine with Marnie line
    ("spikemuth", "marnie_grimmsnarl_ex"),
]


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


def load_card_table() -> dict[int, str]:
    path = ROOT / "data" / "EN_Card_Data.csv"
    if not path.exists():
        path = ROOT / "data" / "sim" / "EN_Card_Data.csv"
    out: dict[int, str] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                cid = int(row.get("Card ID") or row.get("cardId") or row.get("id"))
            except (TypeError, ValueError):
                continue
            name = (row.get("Card Name") or row.get("name") or "").strip()
            out[cid] = name
    return out


def _as_card_list(raw: Any) -> list[int] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        ids: list[int] = []
        for x in raw:
            if isinstance(x, int):
                ids.append(x)
            elif isinstance(x, dict):
                got = False
                for k in ("cardId", "card_id", "id", "CardId"):
                    if k in x and x[k] is not None:
                        try:
                            ids.append(int(x[k]))
                            got = True
                            break
                        except (TypeError, ValueError):
                            pass
                if not got:
                    return None
            else:
                try:
                    ids.append(int(x))
                except (TypeError, ValueError):
                    return None
        return ids if len(ids) == 60 else None
    return None


def safe_slug(name: str, max_len: int = 48) -> str:
    s = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")
    s = re.sub(r"_+", "_", s)
    return (s or "team")[:max_len]


def extract_decks_from_obj(data: dict) -> list[dict[str, Any]]:
    """Return list of {player, deck, source, team} from one episode JSON object."""
    results: list[dict[str, Any]] = []
    team_names = (data.get("info") or {}).get("TeamNames") or [None, None]
    rewards = data.get("rewards") or [None, None]

    # --- primary: visualize[0].current.players[j].deck ---
    try:
        viz0 = data["steps"][0][0]["visualize"][0]
    except (KeyError, IndexError, TypeError):
        viz0 = None

    if isinstance(viz0, dict):
        current = viz0.get("current")
        if isinstance(current, dict):
            players = current.get("players")
            if isinstance(players, list):
                for j, pl in enumerate(players):
                    if not isinstance(pl, dict):
                        continue
                    deck = _as_card_list(pl.get("deck"))
                    if deck and len(deck) == 60:
                        results.append(
                            {
                                "player": j,
                                "deck": deck,
                                "source": "visualize.current.players.deck",
                                "team": team_names[j] if j < len(team_names) else None,
                                "reward": rewards[j] if j < len(rewards) else None,
                            }
                        )
        # fallback: action[j] at step 0 (deck submission)
        if not results:
            actions = viz0.get("action")
            if isinstance(actions, list):
                for j, act in enumerate(actions):
                    deck = _as_card_list(act)
                    if deck and len(deck) == 60:
                        results.append(
                            {
                                "player": j,
                                "deck": deck,
                                "source": "visualize.action",
                                "team": team_names[j] if j < len(team_names) else None,
                                "reward": rewards[j] if j < len(rewards) else None,
                            }
                        )

    # deeper scan if still empty
    if not results:
        for path, node in _walk(data):
            if path.endswith("deck") or path.endswith(".action"):
                deck = _as_card_list(node)
                if deck and len(deck) == 60:
                    results.append(
                        {
                            "player": None,
                            "deck": deck,
                            "source": f"scan:{path}",
                            "team": None,
                            "reward": None,
                        }
                    )
                    if len(results) >= 2:
                        break

    return results


def _walk(obj: Any, prefix: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            yield p, v
            yield from _walk(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:20]):  # bound
            p = f"{prefix}[{i}]"
            yield p, v
            if isinstance(v, (dict, list)):
                yield from _walk(v, p)


def extract_decks_from_file(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = extract_decks_from_obj(data)
    for r in rows:
        r["episode_file"] = str(path)
        r["episode_id"] = _episode_id_from_path(path)
    return rows


def _episode_id_from_path(path: Path) -> str | None:
    m = re.search(r"(\d{6,})", path.stem)
    return m.group(1) if m else path.stem


def classify_archetype(deck: list[int], card_table: dict[int, str]) -> dict[str, Any]:
    counts = Counter(deck)
    names = {cid: card_table.get(cid, f"#{cid}") for cid in counts}
    tag_scores: Counter = Counter()
    for cid, n in counts.items():
        nm = names[cid].lower()
        for needle, tag in NAME_ARCHETYPE_RULES:
            if needle in nm:
                tag_scores[tag] += n
        if cid in ARCHETYPE_MARKERS:
            # map known IDs
            label = ARCHETYPE_MARKERS[cid].lower()
            for needle, tag in NAME_ARCHETYPE_RULES:
                if needle in label:
                    tag_scores[tag] += n
    primary = tag_scores.most_common(1)[0][0] if tag_scores else "unknown"
    # top pokemon by count among non-energy/non-generic
    pokemonish = []
    for cid, n in counts.most_common():
        nm = names[cid]
        low = nm.lower()
        if "energy" in low:
            continue
        pokemonish.append({"card_id": cid, "name": nm, "count": n})
        if len(pokemonish) >= 12:
            break
    return {
        "primary_archetype": primary,
        "archetype_scores": dict(tag_scores.most_common(8)),
        "top_cards": pokemonish,
        "unique_cards": len(counts),
        "card_counts": {str(k): v for k, v in sorted(counts.items())},
    }


def write_deck_csv(deck: list[int], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(str(c) for c in deck) + "\n", encoding="utf-8")


def write_named_list(deck: list[int], card_table: dict[int, str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter(deck)
    lines = [
        f"{cid:>5}  {counts[cid]}x  {card_table.get(cid, '')}"
        for cid in sorted(counts, key=lambda c: (-counts[c], c))
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def kaggle_run(args: list[str], timeout: int = 180) -> tuple[int, str]:
    ensure_token()
    env = os.environ.copy()
    try:
        p = subprocess.run(
            [PY, "-m", "kaggle"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def _strip_kaggle_noise(out: str) -> str:
    """Drop Next Page Token / blank lines so DictReader sees a clean CSV."""
    lines = []
    for ln in out.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.lower().startswith("next page token"):
            continue
        lines.append(ln.rstrip())
    return "\n".join(lines)


def fetch_leaderboard_top(n: int = 6) -> list[dict[str, Any]]:
    """Return top-n teams: teamId, teamName, score."""
    code, out = kaggle_run(["competitions", "leaderboard", COMP, "-s", "-v"], timeout=120)
    if code != 0 and "teamId" not in out:
        code, out = kaggle_run(["competitions", "leaderboard", COMP, "-s"], timeout=120)
    rows: list[dict[str, Any]] = []
    cleaned = _strip_kaggle_noise(out)
    # Prefer CSV block starting at teamId header
    if "teamId" in cleaned:
        import io

        # keep from header line only
        idx = cleaned.lower().find("teamid,")
        if idx < 0:
            idx = cleaned.lower().find("teamid")
        block = cleaned[idx:] if idx >= 0 else cleaned
        rdr = csv.DictReader(io.StringIO(block))
        for r in rdr:
            # normalize keys (BOM / spaces)
            rk = { (k or "").strip(): v for k, v in r.items() }
            tid = rk.get("teamId") or rk.get("TeamId")
            name = rk.get("teamName") or rk.get("TeamName")
            score = rk.get("score") or rk.get("Score")
            if not tid:
                continue
            try:
                rows.append(
                    {
                        "teamId": int(float(str(tid).strip())),
                        "teamName": (name or "").strip(),
                        "score": float(score) if score not in (None, "") else None,
                    }
                )
            except Exception:
                continue
            if len(rows) >= n:
                return rows
        if rows:
            return rows
    # table / loose parse
    for ln in cleaned.splitlines():
        m = re.match(
            r"^(\d+)\s+(.+?)\s+(\d{4}-\d{2}-\d{2}\S*)\s+([\d.]+)\s*$",
            ln.strip(),
        )
        if m:
            rows.append(
                {
                    "teamId": int(m.group(1)),
                    "teamName": m.group(2).strip(),
                    "score": float(m.group(4)),
                }
            )
        if len(rows) >= n:
            break
    return rows[:n]


def best_submission_for_team(team_id: int) -> dict[str, Any] | None:
    code, out = kaggle_run(
        ["competitions", "team-submissions", str(team_id), "-v"],
        timeout=120,
    )
    cleaned = _strip_kaggle_noise(out)
    best = None
    if "dateSubmitted" in cleaned or re.search(r"(?m)^id,", cleaned):
        import io

        idx = cleaned.lower().find("id,")
        block = cleaned[idx:] if idx >= 0 else cleaned
        rdr = csv.DictReader(io.StringIO(block))
        for r in rdr:
            rk = {(k or "").strip(): v for k, v in r.items()}
            try:
                sid = int(rk.get("id") or rk.get("Id") or 0)
                sc = float(rk.get("publicScore") or rk.get("score") or 0)
            except Exception:
                continue
            if sid and (best is None or sc > best["score"]):
                best = {"submissionId": sid, "score": sc}
        if best:
            return best
    for ln in cleaned.splitlines():
        parts = ln.split()
        if parts and parts[0].isdigit():
            try:
                sid = int(parts[0])
                sc = float(parts[-1])
                if best is None or sc > best["score"]:
                    best = {"submissionId": sid, "score": sc}
            except Exception:
                pass
    return best


def list_episode_ids(submission_id: int, limit: int = 5) -> list[int]:
    code, out = kaggle_run(
        ["competitions", "episodes", str(submission_id), "-v"],
        timeout=120,
    )
    cleaned = _strip_kaggle_noise(out)
    ids: list[int] = []
    if re.search(r"(?m)^id,", cleaned):
        import io

        idx = cleaned.lower().find("id,")
        block = cleaned[idx:] if idx >= 0 else cleaned
        rdr = csv.DictReader(io.StringIO(block))
        public: list[int] = []
        other: list[int] = []
        for r in rdr:
            rk = {(k or "").strip(): v for k, v in r.items()}
            try:
                eid = int(rk.get("id") or 0)
            except Exception:
                continue
            typ = str(rk.get("type") or "")
            if "PUBLIC" in typ.upper():
                public.append(eid)
            else:
                other.append(eid)
        ids = public + other
        return ids[:limit]
    for ln in cleaned.splitlines():
        m = re.match(r"^(\d+),", ln.strip())
        if m:
            ids.append(int(m.group(1)))
        else:
            parts = ln.split()
            if parts and parts[0].isdigit() and len(parts[0]) >= 6:
                ids.append(int(parts[0]))
        if len(ids) >= limit:
            break
    return ids[:limit]


def download_replay(episode_id: int, dest_dir: Path, force: bool = False) -> Path | None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    cached = dest_dir / f"ep{episode_id}.json"
    if cached.exists() and cached.stat().st_size > 1000 and not force:
        return cached
    # kaggle writes episode_id.json typically
    code, out = kaggle_run(
        ["competitions", "replay", str(episode_id), "-p", str(dest_dir), "-q"],
        timeout=180,
    )
    candidates = list(dest_dir.glob(f"*{episode_id}*.json"))
    if not candidates:
        candidates = [p for p in dest_dir.glob("*.json") if p.stat().st_mtime > datetime.now().timestamp() - 120]
    if candidates:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        src = candidates[0]
        if src.resolve() != cached.resolve():
            try:
                cached.write_bytes(src.read_bytes())
            except Exception:
                return src
        return cached if cached.exists() else src
    if code != 0:
        print(f"[warn] replay {episode_id} failed: {out[-300:]}", file=sys.stderr)
    return None


def process_episode_file(
    path: Path,
    card_table: dict[int, str],
    out_root: Path,
    prefer_team: str | None = None,
) -> list[dict[str, Any]]:
    rows = extract_decks_from_file(path)
    enriched = []
    for r in rows:
        deck = r["deck"]
        if len(deck) != 60:
            # pad/truncate only if very close? prefer strict
            if len(deck) > 60:
                deck = deck[:60]
            else:
                continue
        meta = classify_archetype(deck, card_table)
        team = r.get("team") or prefer_team or f"player{r.get('player')}"
        safe = safe_slug(str(team), 60)
        eid = r.get("episode_id") or path.stem
        base = out_root / "decks" / f"{safe}_ep{eid}_p{r.get('player')}"
        write_deck_csv(deck, Path(str(base) + ".csv"))
        write_named_list(deck, card_table, Path(str(base) + "_named.txt"))
        rec = {
            **{k: v for k, v in r.items() if k != "deck"},
            "deck": deck,
            "deck_csv": str(Path(str(base) + ".csv")),
            "named_list": str(Path(str(base) + "_named.txt")),
            **meta,
        }
        enriched.append(rec)
    return enriched


def run_top_pipeline(top_n: int, episodes_per_team: int, out_dir: Path) -> dict[str, Any]:
    card_table = load_card_table()
    out_dir.mkdir(parents=True, exist_ok=True)
    replay_dir = out_dir / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)

    print(f"[info] fetching top {top_n} leaderboard…")
    teams = fetch_leaderboard_top(top_n)
    print(f"[info] teams: {[(t['teamId'], t['teamName'], t['score']) for t in teams]}")

    all_records: list[dict] = []
    team_summaries: list[dict] = []

    for rank, team in enumerate(teams, 1):
        tid = team["teamId"]
        tname = team["teamName"]
        print(f"\n=== #{rank} {tname} (team {tid}, μ={team.get('score')}) ===")
        sub = best_submission_for_team(tid)
        if not sub:
            print("  no submission found")
            team_summaries.append({**team, "rank": rank, "error": "no_submission"})
            continue
        sid = sub["submissionId"]
        print(f"  best submission {sid} score={sub['score']}")
        eids = list_episode_ids(sid, limit=episodes_per_team)
        print(f"  episodes: {eids}")
        team_decks: list[dict] = []
        for eid in eids:
            path = download_replay(eid, replay_dir)
            if not path:
                print(f"  replay {eid}: FAIL")
                continue
            # rename for clarity
            target = replay_dir / f"ep{eid}.json"
            if path.resolve() != target.resolve():
                try:
                    target.write_bytes(path.read_bytes())
                    path = target
                except Exception:
                    pass
            recs = process_episode_file(path, card_table, out_dir, prefer_team=tname)
            print(f"  ep{eid}: extracted {len(recs)} decks from {path.name}")
            for rec in recs:
                rec["leaderboard_rank"] = rank
                rec["teamId"] = tid
                rec["teamName"] = tname
                rec["submissionId"] = sid
                rec["lb_score"] = team.get("score")
                # mark which player matches this team name
                match = (
                    rec.get("team") is not None
                    and tname is not None
                    and str(rec["team"]).strip().lower() == str(tname).strip().lower()
                )
                rec["is_focus_team"] = bool(match)
                all_records.append(rec)
                if rec.get("is_focus_team"):
                    team_decks.append(rec)

        # pick representative deck for team (prefer focus team win)
        rep = None
        for rec in team_decks:
            if rec.get("is_focus_team") and rec.get("reward") == 1:
                rep = rec
                break
        if rep is None and team_decks:
            for rec in team_decks:
                if rec.get("is_focus_team"):
                    rep = rec
                    break
        if rep is None and team_decks:
            rep = team_decks[0]
        if rep:
            # canonical deck.csv for training
            canon = out_dir / "decks_csv" / f"top{rank:02d}_{safe_slug(tname)}.csv"
            write_deck_csv(rep["deck"], canon)
            # also drop into agent_decks for local gates / training
            agent_copy = ROOT / "agent_decks" / f"top_lb_{rank:02d}_{safe_slug(tname)}.csv"
            write_deck_csv(rep["deck"], agent_copy)
            # named readable dump
            write_named_list(
                rep["deck"],
                card_table,
                out_dir / "decks_csv" / f"top{rank:02d}_{safe_slug(tname)}_named.txt",
            )

            team_summaries.append(
                {
                    "rank": rank,
                    "teamId": tid,
                    "teamName": tname,
                    "lb_score": team.get("score"),
                    "submissionId": sid,
                    "primary_archetype": rep.get("primary_archetype"),
                    "top_cards": rep.get("top_cards", [])[:8],
                    "deck_csv": str(canon),
                    "source": rep.get("source"),
                    "episode_id": rep.get("episode_id"),
                    "n_episodes_parsed": len(eids),
                }
            )
            print(
                f"  REP archetype={rep.get('primary_archetype')} "
                f"top={[c['name'] for c in rep.get('top_cards', [])[:5]]} -> {canon}"
            )
        else:
            team_summaries.append(
                {
                    "rank": rank,
                    "teamId": tid,
                    "teamName": tname,
                    "lb_score": team.get("score"),
                    "error": "no_deck_extracted",
                }
            )

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "competition": COMP,
        "top_n": top_n,
        "teams": team_summaries,
        "n_deck_records": len(all_records),
        "meta_note": {
            "top100_snapshot_approx_2026_07_22": {
                "marnie_grimmsnarl_ex": 0.31,
                "alakazam": 0.30,
                "crustle_iwapalace": 0.13,
                "rocket_spidops": 0.06,
                "cynthia_garchomp_ex": 0.06,
                "dragapult_ex": 0.03,
            }
        },
    }
    out_json = out_dir / f"top_decks_{day}.json"
    # store full records separately (can be large)
    full_path = out_dir / f"top_decks_{day}_full.json"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    full_path.write_text(
        json.dumps({"summary": summary, "records": all_records}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # also symlink-style copy into recordings/metrics
    metrics = ROOT / "recordings" / "metrics"
    metrics.mkdir(parents=True, exist_ok=True)
    (metrics / f"top_decks_{day}.json").write_text(
        out_json.read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"\n[done] summary -> {out_json}")
    print(f"[done] full    -> {full_path}")
    print(f"[done] metrics -> {metrics / f'top_decks_{day}.json'}")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=str, help="Local episode JSON path")
    ap.add_argument("--episode-id", type=int, help="Download + parse one episode id")
    ap.add_argument("--batch-dir", type=str, help="Directory of episode JSON files")
    ap.add_argument("--top", type=int, default=0, help="Process leaderboard top N teams")
    ap.add_argument("--episodes-per-team", type=int, default=3)
    ap.add_argument("--download", action="store_true", help="With --top, download replays")
    ap.add_argument(
        "--out",
        type=str,
        default=str(ROOT / "recordings" / "metrics"),
        help="Output directory",
    )
    ap.add_argument("--player", type=int, default=None, help="Only emit this player index")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    card_table = load_card_table()

    if args.top and args.top > 0:
        if not args.download:
            print("[info] --top implies download of public episodes")
        run_top_pipeline(args.top, args.episodes_per_team, out_dir)
        return 0

    files: list[Path] = []
    if args.json:
        files.append(Path(args.json))
    if args.episode_id:
        ensure_token()
        p = download_replay(args.episode_id, out_dir / "replays")
        if not p:
            print(f"failed to download episode {args.episode_id}", file=sys.stderr)
            return 2
        files.append(p)
    if args.batch_dir:
        files.extend(sorted(Path(args.batch_dir).glob("*.json")))

    if not files:
        ap.print_help()
        return 1

    all_recs = []
    for f in files:
        recs = process_episode_file(f, card_table, out_dir)
        if args.player is not None:
            recs = [r for r in recs if r.get("player") == args.player]
        for r in recs:
            print(
                f"{f.name} p{r.get('player')} team={r.get('team')} "
                f"src={r.get('source')} arch={r.get('primary_archetype')} "
                f"top={[c['name'] for c in r.get('top_cards', [])[:5]]}"
            )
            print(f"  -> {r.get('deck_csv')}")
        all_recs.extend(recs)

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n": len(all_recs),
        "records": [
            {k: v for k, v in r.items() if k != "deck"}
            | {"deck_len": len(r.get("deck") or [])}
            for r in all_recs
        ],
    }
    out_json = out_dir / f"extract_{day}.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
