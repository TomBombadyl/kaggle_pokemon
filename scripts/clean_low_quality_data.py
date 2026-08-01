#!/usr/bin/env python3
"""Clean low-quality episode / replay data for PTCG AI Battle training.

Scans episode-like JSON under configurable roots, scores quality, then:
  - moves low-quality files → recordings/low_quality/
  - copies (or marks) high-quality files → recordings/cleaned/
  - writes a markdown report → recordings/logs/clean_report_YYYYMMDD_HHMMSS.md

Quality rules (defaults tuned for this repo's mixed schemas):
  · both-side avg rating / μ too low
  · too few steps / turns / actions
  · error / illegal / crash / unfinished
  · old + low value (age days + weak score)
  · empty / unreadable / corrupt JSON

Usage:
  python scripts/clean_low_quality_data.py --dry-run
  python scripts/clean_low_quality_data.py --min-rating 900 --min-steps 30
  python scripts/clean_low_quality_data.py --min-rating 900 --min-steps 30 --max-age-days 45 --execute
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]  # kaggle_pokemon
WORKSPACE = ROOT.parent  # E:\PTCG_AI_Battle_Challenge
RECORDINGS = WORKSPACE / "recordings"
LOW_Q = RECORDINGS / "low_quality"
CLEANED = RECORDINGS / "cleaned"
LOGS = RECORDINGS / "logs"

# Default scan roots (existing + planned)
DEFAULT_SCAN_ROOTS = [
    ROOT / "episodes",
    RECORDINGS / "episodes",
    ROOT / "report" / "submission_replays",
    ROOT / "report" / "deck_logs",
    ROOT / "report" / "replays",
    ROOT / "data" / "episodes" / "raw",
    ROOT / "data" / "kaggle_ref" / "episodes",
]

# Manifests that map episode_id → scores
DEFAULT_MANIFESTS = [
    ROOT / "report" / "replays" / "manifest.csv",
    ROOT / "episodes" / "index" / "manifest.csv",
]

ERROR_MARKERS = (
    "traceback",
    "illegal action",
    "illegal move",
    "no legal",
    "invalid action",
    "error",
    "exception",
    "battle_start failed",
    "cg engine not found",
    "filenotfounderror",
    "crash",
    "timeout",
    "timed out",
    "step cap",
    "max_steps",
    "did not finish",
    "unfinished",
)

# Outcomes that are often low-value learning (not always discard alone)
WEAK_REASONS = frozenset({"error", "crash", "timeout", "illegal", "invalid"})


@dataclass
class EpisodeMeta:
    path: str
    episode_id: str = ""
    avg_rating: float | None = None
    min_rating: float | None = None
    steps: int = 0
    turns: int = 0
    actions: int = 0
    has_error: bool = False
    error_hint: str = ""
    outcome: str = ""
    result_reason: str = ""
    mtime_ts: float = 0.0
    size_bytes: int = 0
    schema: str = "unknown"
    notes: list[str] = field(default_factory=list)


@dataclass
class Decision:
    path: Path
    keep: bool
    reasons: list[str]
    meta: EpisodeMeta
    action: str  # keep | move_low | copy_clean | skip


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_float(x: Any) -> float | None:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _safe_int(x: Any) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def load_score_index(manifests: list[Path]) -> dict[str, dict[str, float]]:
    """episode_id → {avg_score, min_score, ...} from CSV manifests."""
    idx: dict[str, dict[str, float]] = {}
    for man in manifests:
        if not man.exists():
            continue
        try:
            with man.open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    eid = (
                        row.get("episode_id")
                        or row.get("EpisodeId")
                        or row.get("id")
                        or ""
                    ).strip()
                    if not eid:
                        continue
                    avg = _safe_float(
                        row.get("avg_score")
                        or row.get("avg_rating")
                        or row.get("top_avg_score")
                        or row.get("median_avg_score")
                    )
                    mn = _safe_float(
                        row.get("min_score") or row.get("min_rating") or row.get("min_score")
                    )
                    entry: dict[str, float] = {}
                    if avg is not None:
                        entry["avg_score"] = avg
                    if mn is not None:
                        entry["min_score"] = mn
                    if entry:
                        idx[eid] = entry
        except Exception:
            continue
    return idx


def extract_meta(path: Path, score_idx: dict[str, dict[str, float]]) -> EpisodeMeta:
    st = path.stat()
    meta = EpisodeMeta(
        path=str(path),
        mtime_ts=st.st_mtime,
        size_bytes=st.st_size,
        episode_id=path.stem,
    )

    # Tiny / empty → error
    if st.st_size < 20:
        meta.has_error = True
        meta.error_hint = "empty_or_tiny"
        meta.schema = "empty"
        return meta

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        meta.has_error = True
        meta.error_hint = f"read_fail:{e}"
        return meta

    low = text[:8000].lower()
    for marker in ERROR_MARKERS:
        if marker in low and marker in ("traceback", "illegal action", "illegal move", "no legal", "battle_start failed", "cg engine not found"):
            meta.has_error = True
            meta.error_hint = marker
            break

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        meta.has_error = True
        meta.error_hint = meta.error_hint or "invalid_json"
        meta.schema = "corrupt"
        return meta

    if not isinstance(data, dict):
        # list of steps? treat as raw steps wrapper
        if isinstance(data, list):
            meta.steps = len(data)
            meta.schema = "list_steps"
            return meta
        meta.has_error = True
        meta.error_hint = "non_object_json"
        return meta

    # --- episode id ---
    for k in ("episode_id", "episodeId", "id", "EpisodeId"):
        if data.get(k) is not None:
            meta.episode_id = str(data[k])
            break

    # --- schema detect ---
    if "raw_replay" in data or "our_deck_archetype" in data or "turn_count" in data:
        meta.schema = "submission_extract"
    elif "steps" in data and isinstance(data.get("steps"), list):
        meta.schema = "kaggle_replay"
    elif "info" in data and "rewards" in data:
        meta.schema = "kaggle_replay"
    else:
        meta.schema = "generic"

    # --- steps / turns / actions ---
    steps = data.get("steps")
    if isinstance(steps, list):
        meta.steps = len(steps)
    for k in ("num_steps", "step_count", "n_steps", "total_steps"):
        if data.get(k) is not None:
            meta.steps = max(meta.steps, _safe_int(data.get(k)))

    meta.turns = _safe_int(data.get("turn_count") or data.get("turns") or data.get("num_turns"))
    scc = data.get("selected_context_counts") or {}
    if isinstance(scc, dict):
        meta.actions = _safe_int(scc.get("action") or scc.get("actions") or 0)
    if meta.actions == 0:
        meta.actions = _safe_int(data.get("action_count") or data.get("num_actions"))

    # Effective step proxy for mixed schemas
    if meta.steps == 0:
        meta.steps = meta.actions or (meta.turns * 8 if meta.turns else 0)

    # --- ratings ---
    ratings: list[float] = []
    for k in (
        "p0_rating",
        "p1_rating",
        "rating_0",
        "rating_1",
        "score_0",
        "score_1",
        "mu_0",
        "mu_1",
    ):
        v = _safe_float(data.get(k))
        if v is not None:
            ratings.append(v)

    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    for k in ("TeamRatings", "teamRatings", "ratings", "Scores", "scores"):
        arr = info.get(k) if info else data.get(k)
        if isinstance(arr, list):
            for x in arr:
                v = _safe_float(x)
                if v is not None:
                    ratings.append(v)

    agents = data.get("agents")
    if isinstance(agents, list):
        for a in agents:
            if not isinstance(a, dict):
                continue
            for k in ("rating", "score", "mu", "publicScore"):
                v = _safe_float(a.get(k))
                if v is not None:
                    ratings.append(v)

    # manifest lookup
    if meta.episode_id and meta.episode_id in score_idx:
        sc = score_idx[meta.episode_id]
        if "avg_score" in sc:
            meta.avg_rating = sc["avg_score"]
        if "min_score" in sc:
            meta.min_rating = sc["min_score"]

    if ratings:
        meta.avg_rating = sum(ratings) / len(ratings) if meta.avg_rating is None else meta.avg_rating
        meta.min_rating = min(ratings) if meta.min_rating is None else meta.min_rating

    # top-level avg fields
    for k in ("avg_score", "avg_rating", "average_rating", "mean_rating"):
        v = _safe_float(data.get(k))
        if v is not None:
            meta.avg_rating = v if meta.avg_rating is None else meta.avg_rating

    meta.outcome = str(data.get("outcome") or data.get("result") or "")
    meta.result_reason = str(data.get("result_reason") or data.get("termination") or "")

    # error flags in payload
    if data.get("error") or data.get("has_error") or data.get("failed"):
        meta.has_error = True
        meta.error_hint = meta.error_hint or "flagged_error"
    rr = meta.result_reason.lower()
    if rr in WEAK_REASONS:
        meta.has_error = True
        meta.error_hint = meta.error_hint or rr

    # unfinished signals
    if str(data.get("unfinished") or "").lower() in ("1", "true", "yes"):
        meta.has_error = True
        meta.error_hint = meta.error_hint or "unfinished"

    return meta


def is_high_quality(
    meta: EpisodeMeta,
    *,
    min_rating: float,
    min_steps: int,
    min_turns: int,
    max_age_days: float | None,
    require_rating: bool,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if meta.has_error:
        reasons.append(f"error:{meta.error_hint or 'yes'}")

    if meta.steps < min_steps and meta.turns < min_turns and meta.actions < min_steps:
        reasons.append(
            f"too_short steps={meta.steps} turns={meta.turns} actions={meta.actions} "
            f"(need steps>={min_steps} or turns>={min_turns})"
        )

    if meta.avg_rating is not None:
        if meta.avg_rating < min_rating:
            reasons.append(f"low_avg_rating={meta.avg_rating:.1f}<{min_rating}")
    elif require_rating:
        reasons.append("missing_rating")

    if max_age_days is not None and meta.mtime_ts > 0:
        age_days = (datetime.now().timestamp() - meta.mtime_ts) / 86400.0
        # Old + weak (or missing rating treated as weak when old)
        weak = (meta.avg_rating is not None and meta.avg_rating < min_rating) or meta.avg_rating is None
        if age_days > max_age_days and weak:
            reasons.append(f"stale_low_value age_days={age_days:.1f}>{max_age_days}")

    # Hard empty
    if meta.size_bytes < 50:
        reasons.append("tiny_file")

    return (len(reasons) == 0, reasons)


# Non-episode JSON we should not treat as battles
SKIP_NAMES = frozenset(
    {
        "index.json",
        "losses.json",
        "manifest.json",
        "summary.json",
        "meta.json",
        "config.json",
        "kernel-metadata.json",
    }
)


def iter_episode_files(scan_roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for root in scan_roots:
        if not root.exists():
            continue
        # skip destination dirs if nested under scan (shouldn't be)
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".json", ".jsonl"):
                continue
            if p.name.lower() in SKIP_NAMES:
                continue
            # skip huge accidental dumps? allow up to 50MB
            try:
                if p.stat().st_size > 50 * 1024 * 1024:
                    continue
            except OSError:
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            # never scan our output dirs as sources (unless explicitly listed only as source)
            parts = {x.lower() for x in p.parts}
            if "low_quality" in parts or (p.parts and "cleaned" in parts and "recordings" in parts and "report" not in parts):
                # allow cleaned only if under report; skip recordings/cleaned and recordings/low_quality
                if "recordings" in parts:
                    continue
            seen.add(key)
            files.append(p)
    return files


def rel_under(path: Path, bases: list[Path]) -> Path:
    """Prefer path relative to kaggle_pokemon ROOT, then workspace, then bases.

    Keeps report/submission_replays vs report/deck_logs distinct under cleaned/.
    """
    try:
        return path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        pass
    try:
        return path.resolve().relative_to(WORKSPACE.resolve())
    except ValueError:
        pass
    for b in bases:
        try:
            return path.resolve().relative_to(b.resolve())
        except ValueError:
            continue
    # fallback: parent_name / filename
    return Path(path.parent.name) / path.name


def move_or_copy(
    src: Path,
    dest_root: Path,
    rel: Path,
    *,
    dry_run: bool,
    do_move: bool,
) -> Path:
    dest = dest_root / rel
    if dry_run:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if do_move:
        if dest.exists():
            dest.unlink()
        shutil.move(str(src), str(dest))
    else:
        shutil.copy2(src, dest)
    return dest


def write_quality_marker(path: Path, meta: EpisodeMeta, keep: bool, reasons: list[str], dry_run: bool) -> None:
    marker = path.with_suffix(path.suffix + ".quality.json")
    payload = {
        "keep": keep,
        "reasons": reasons,
        "meta": asdict(meta),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if dry_run:
        return
    try:
        marker.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def human_bytes(n: int) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if x < 1024 or unit == "GB":
            return f"{x:.1f} {unit}"
        x /= 1024.0
    return f"{n} B"


def run_clean(args: argparse.Namespace) -> int:
    scan_roots = [Path(p) for p in args.scan] if args.scan else list(DEFAULT_SCAN_ROOTS)
    # Ensure recordings/episodes exists for future pulls
    (RECORDINGS / "episodes").mkdir(parents=True, exist_ok=True)
    LOW_Q.mkdir(parents=True, exist_ok=True)
    CLEANED.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    manifests = [Path(p) for p in args.manifest] if args.manifest else list(DEFAULT_MANIFESTS)
    score_idx = load_score_index(manifests)

    files = iter_episode_files(scan_roots)
    before_low = dir_size_bytes(LOW_Q)
    before_clean = dir_size_bytes(CLEANED)

    decisions: list[Decision] = []
    reason_counter: Counter[str] = Counter()
    schema_counter: Counter[str] = Counter()

    dry_run = not args.execute  # default dry unless --execute; also honor --dry-run
    if args.dry_run:
        dry_run = True

    for path in files:
        meta = extract_meta(path, score_idx)
        schema_counter[meta.schema] += 1
        keep, reasons = is_high_quality(
            meta,
            min_rating=args.min_rating,
            min_steps=args.min_steps,
            min_turns=args.min_turns,
            max_age_days=args.max_age_days,
            require_rating=args.require_rating,
        )
        for r in reasons:
            # normalize counter keys
            key = r.split("=")[0].split(":")[0]
            reason_counter[key] += 1

        rel = rel_under(path, scan_roots + [ROOT, WORKSPACE])
        if keep:
            action = "copy_clean" if args.copy_high else "mark_high"
            if args.copy_high:
                move_or_copy(path, CLEANED, rel, dry_run=dry_run, do_move=False)
            if args.mark:
                write_quality_marker(path, meta, True, [], dry_run=dry_run)
            decisions.append(Decision(path, True, [], meta, action))
        else:
            action = "move_low"
            move_or_copy(path, LOW_Q, rel, dry_run=dry_run, do_move=not dry_run and not args.copy_low_only)
            if args.copy_low_only and not dry_run:
                move_or_copy(path, LOW_Q, rel, dry_run=False, do_move=False)
            if args.mark and path.exists():
                write_quality_marker(path, meta, False, reasons, dry_run=dry_run)
            decisions.append(Decision(path, False, reasons, meta, action))

    n_total = len(decisions)
    n_keep = sum(1 for d in decisions if d.keep)
    n_drop = n_total - n_keep
    after_low = dir_size_bytes(LOW_Q) if not dry_run else before_low
    after_clean = dir_size_bytes(CLEANED) if not dry_run else before_clean

    # Estimate dry-run size move
    drop_bytes = sum(d.meta.size_bytes for d in decisions if not d.keep)
    keep_bytes = sum(d.meta.size_bytes for d in decisions if d.keep)

    stamp = _now_stamp()
    report_path = LOGS / f"clean_report_{stamp}.md"
    mode = "DRY-RUN" if dry_run else "EXECUTE"

    lines = [
        f"# Clean report ({mode})",
        f"- time: {datetime.now().isoformat(timespec='seconds')}",
        f"- workspace: `{WORKSPACE}`",
        f"- min_rating: {args.min_rating}",
        f"- min_steps: {args.min_steps}",
        f"- min_turns: {args.min_turns}",
        f"- max_age_days: {args.max_age_days}",
        f"- require_rating: {args.require_rating}",
        f"- scan_roots:",
    ]
    for r in scan_roots:
        lines.append(f"  - `{r}` exists={r.exists()}")
    lines += [
        "",
        "## Summary",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Scanned files | {n_total} |",
        f"| High quality (keep) | {n_keep} |",
        f"| Low quality (drop) | {n_drop} |",
        f"| Keep bytes | {human_bytes(keep_bytes)} |",
        f"| Drop bytes | {human_bytes(drop_bytes)} |",
        f"| low_quality/ size | {human_bytes(after_low if not dry_run else before_low + (drop_bytes if dry_run else 0))} |",
        f"| cleaned/ size | {human_bytes(after_clean if not dry_run else before_clean + (keep_bytes if dry_run and args.copy_high else 0))} |",
        "",
        "## Schemas",
    ]
    for k, v in schema_counter.most_common():
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Drop reason counts"]
    for k, v in reason_counter.most_common():
        lines.append(f"- `{k}`: {v}")

    lines += ["", "## Sample drops (up to 40)"]
    for d in [x for x in decisions if not x.keep][:40]:
        lines.append(f"- `{d.path}` — {'; '.join(d.reasons)}")

    lines += ["", "## Sample keeps (up to 20)"]
    for d in [x for x in decisions if x.keep][:20]:
        ar = f"{d.meta.avg_rating:.1f}" if d.meta.avg_rating is not None else "n/a"
        lines.append(
            f"- `{d.path}` — steps={d.meta.steps} turns={d.meta.turns} rating={ar} schema={d.meta.schema}"
        )

    lines += [
        "",
        "## Destinations",
        f"- low_quality: `{LOW_Q}`",
        f"- cleaned: `{CLEANED}`",
        f"- this report: `{report_path}`",
    ]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Machine-readable summary for loop integration
    summary = {
        "mode": mode,
        "ts": datetime.now(timezone.utc).isoformat(),
        "scanned": n_total,
        "kept": n_keep,
        "dropped": n_drop,
        "keep_bytes": keep_bytes,
        "drop_bytes": drop_bytes,
        "report": str(report_path),
        "min_rating": args.min_rating,
        "min_steps": args.min_steps,
        "reason_counts": dict(reason_counter),
        "schema_counts": dict(schema_counter),
    }
    summary_path = LOGS / f"clean_summary_{stamp}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    # latest pointer
    (LOGS / "clean_summary_latest.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    # Compact console summary
    print(
        f"[{mode}] scanned={n_total} keep={n_keep} drop={n_drop} "
        f"keep_bytes={human_bytes(keep_bytes)} drop_bytes={human_bytes(drop_bytes)}"
    )
    print(f"report: {report_path}")
    print(f"summary: {summary_path}")
    if reason_counter:
        top = ", ".join(f"{k}={v}" for k, v in reason_counter.most_common(6))
        print(f"top_drop_reasons: {top}")

    # Optional STATE.md note
    if args.update_state:
        state = WORKSPACE / "STATE.md"
        note = (
            f"\n### Data clean {datetime.now().isoformat(timespec='seconds')} ({mode})\n"
            f"- scanned={n_total} keep={n_keep} drop={n_drop}\n"
            f"- report: `{report_path}`\n"
        )
        try:
            if state.exists():
                state.write_text(state.read_text(encoding="utf-8") + note, encoding="utf-8")
            else:
                state.write_text("# STATE\n" + note, encoding="utf-8")
        except OSError:
            pass

    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report; do not move/copy files (default if --execute not set)",
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Actually move low-quality files and optionally copy high-quality",
    )
    ap.add_argument("--min-rating", type=float, default=900.0, help="Min avg rating/μ (default 900)")
    ap.add_argument("--min-steps", type=int, default=30, help="Min steps/actions proxy (default 30)")
    ap.add_argument(
        "--min-turns",
        type=int,
        default=3,
        help="Min game turns alternative for extract schemas (default 3)",
    )
    ap.add_argument(
        "--max-age-days",
        type=float,
        default=60.0,
        help="Stale low-value cutoff in days (default 60; set <0 to disable)",
    )
    ap.add_argument(
        "--require-rating",
        action="store_true",
        help="Drop files that have no rating/score signal",
    )
    ap.add_argument(
        "--scan",
        action="append",
        default=None,
        help="Extra/override scan root (repeatable). Default: built-in episode roots",
    )
    ap.add_argument(
        "--manifest",
        action="append",
        default=None,
        help="CSV manifest with episode_id,avg_score (repeatable)",
    )
    ap.add_argument(
        "--copy-high",
        action="store_true",
        default=True,
        help="Copy high-quality files into recordings/cleaned/ (default on)",
    )
    ap.add_argument("--no-copy-high", action="store_true", help="Do not copy high-quality files")
    ap.add_argument(
        "--copy-low-only",
        action="store_true",
        help="Copy low-quality instead of moving (preserve sources)",
    )
    ap.add_argument(
        "--mark",
        action="store_true",
        help="Write sidecar .quality.json next to source (if still present)",
    )
    ap.add_argument(
        "--update-state",
        action="store_true",
        help="Append a short note to workspace STATE.md",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.no_copy_high:
        args.copy_high = False
    if args.max_age_days is not None and args.max_age_days < 0:
        args.max_age_days = None
    # Default to dry-run unless execute
    if not args.execute and not args.dry_run:
        args.dry_run = True
    return run_clean(args)


if __name__ == "__main__":
    raise SystemExit(main())
