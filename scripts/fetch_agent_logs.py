"""Download Kaggle Simulation agent logs for competition submissions (READ ONLY).

Lists recent submissions, fetches episode IDs for each ref, and downloads agent
logs via the Kaggle CLI:

    kaggle competitions submissions -c pokemon-tcg-ai-battle -v
    kaggle competitions episodes <ref> -v
    kaggle competitions logs <episode_id> <agent_index> -p <tmpdir>

Logs are saved as ``report/agent_logs/{episode_id}-{agent_index}.json`` (matching
the naming Kaggle uses in the web UI). A manifest CSV links episodes back to
submission refs. Safe to re-run: existing log files are skipped unless ``--force``.

This script NEVER submits anything.

Usage:
    python scripts/fetch_agent_logs.py
    python scripts/fetch_agent_logs.py --ref 53854707
    python scripts/fetch_agent_logs.py --ref 53854707 --agents 1
    python scripts/track_ladder.py --fetch-logs
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "report" / "agent_logs"
MANIFEST_PATH = LOGS_DIR / "manifest.csv"
DEFAULT_COMPETITION = "pokemon-tcg-ai-battle"

MANIFEST_FIELDS = [
    "fetched_at", "ref", "episode_id", "agent_index", "episode_type",
    "episode_state", "log_path",
]

# Import submission helpers from track_ladder (same CLI patterns, READ ONLY).
sys.path.insert(0, str(ROOT / "scripts"))
from track_ladder import (  # noqa: E402
    DEFAULT_COMPETITION as _TL_COMP,
    fetch_submissions_csv,
    parse_submissions,
)


def _ensure_kaggle_credentials() -> None:
    """Load project-local bearer token if the CLI env is unset."""
    tok_path = ROOT / ".kaggle" / "access_token"
    if tok_path.exists() and not os.environ.get("KAGGLE_API_TOKEN"):
        os.environ["KAGGLE_API_TOKEN"] = tok_path.read_text(encoding="utf-8").strip()


def _run_kaggle(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    _ensure_kaggle_credentials()
    cmd = ["kaggle", "competitions", *args]
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "kaggle CLI not found on PATH. Install with `pip install kaggle` and "
            "place credentials under .kaggle/, then retry."
        ) from exc


def _extract_csv_block(text: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        low = line.lower()
        if "," in line and ("id" in low or "ref" in low or "filename" in low):
            return "\n".join(lines[i:])
    return text


def _norm_key(key: str) -> str:
    return (key or "").lstrip("\ufeff").strip().lower().replace(" ", "").replace("_", "")


def fetch_episodes_csv(submission_ref: str) -> str:
    """Return raw CSV from ``kaggle competitions episodes <ref> -v``."""
    proc = _run_kaggle(["episodes", submission_ref, "-v"])
    if proc.returncode != 0:
        raise RuntimeError(
            f"`kaggle competitions episodes {submission_ref} -v` failed "
            f"(exit {proc.returncode}).\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc.stdout


def parse_episodes(csv_text: str) -> list[dict[str, str]]:
    """Parse episode list CSV into normalized rows."""
    block = _extract_csv_block(csv_text)
    reader = csv.DictReader(io.StringIO(block))
    rows: list[dict[str, str]] = []
    for raw in reader:
        norm = {_norm_key(k): (v or "").strip() for k, v in raw.items() if k is not None}
        ep_id = norm.get("id", "")
        if not ep_id.isdigit():
            continue
        state = norm.get("state", "")
        ep_type = norm.get("type", "")
        rows.append({
            "episode_id": ep_id,
            "create_time": norm.get("createtime", ""),
            "end_time": norm.get("endtime", ""),
            "state": state.rsplit(".", 1)[-1] if "." in state else state,
            "type": ep_type.rsplit(".", 1)[-1] if "." in ep_type else ep_type,
        })
    return rows


def _cli_log_filename(episode_id: str, agent_index: int) -> str:
    return f"episode-{episode_id}-agent-{agent_index}-logs.json"


def _dest_log_path(episode_id: str, agent_index: int, output_dir: Path) -> Path:
    return output_dir / f"{episode_id}-{agent_index}.json"


def download_agent_log(
    episode_id: str,
    agent_index: int,
    dest_path: Path,
    *,
    force: bool = False,
) -> bool:
    """Download one agent log file. Returns True if a new file was written."""
    if dest_path.exists() and not force:
        return False

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kaggle_logs_") as tmp:
        proc = _run_kaggle(["logs", episode_id, str(agent_index), "-p", tmp, "-q"])
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            if "403" in err or "Forbidden" in err:
                return False
            raise RuntimeError(
                f"`kaggle competitions logs {episode_id} {agent_index}` failed "
                f"(exit {proc.returncode}).\n{err}"
            )
        src = Path(tmp) / _cli_log_filename(episode_id, agent_index)
        if not src.exists():
            candidates = list(Path(tmp).glob("*.json"))
            if not candidates:
                return False
            src = candidates[0]
        shutil.move(str(src), str(dest_path))
    return True


def _read_manifest_keys(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    keys: set[tuple[str, str, str]] = set()
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            keys.add((
                (row.get("ref") or "").strip(),
                (row.get("episode_id") or "").strip(),
                (row.get("agent_index") or "").strip(),
            ))
    return keys


def append_manifest_rows(path: Path, rows: list[dict[str, str]]) -> int:
    """Append manifest rows not already present (ref, episode_id, agent_index)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_manifest_keys(path)
    write_header = not path.exists()
    added = 0
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in rows:
            key = (row["ref"], row["episode_id"], row["agent_index"])
            if key in existing:
                continue
            writer.writerow(row)
            existing.add(key)
            added += 1
    return added


def fetch_logs_for_ref(
    submission_ref: str,
    *,
    output_dir: Path,
    agents: list[int],
    force: bool = False,
) -> tuple[int, int]:
    """Download logs for all episodes of one submission ref.

    Returns (files_written, manifest_rows_added).
    """
    csv_text = fetch_episodes_csv(submission_ref)
    episodes = parse_episodes(csv_text)
    if not episodes:
        print(f"  ref {submission_ref}: no episodes listed")
        return 0, 0

    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    written = 0
    manifest_rows: list[dict[str, str]] = []

    for ep in episodes:
        ep_id = ep["episode_id"]
        for agent_idx in agents:
            dest = _dest_log_path(ep_id, agent_idx, output_dir)
            if dest.exists() and not force:
                rel = dest.relative_to(ROOT).as_posix()
                manifest_rows.append({
                    "fetched_at": fetched_at,
                    "ref": submission_ref,
                    "episode_id": ep_id,
                    "agent_index": str(agent_idx),
                    "episode_type": ep["type"],
                    "episode_state": ep["state"],
                    "log_path": rel,
                })
                continue
            try:
                if download_agent_log(ep_id, agent_idx, dest, force=force):
                    written += 1
                    print(f"  + {dest.name}  ({ep['type']}, {ep['state']})")
                    manifest_rows.append({
                        "fetched_at": fetched_at,
                        "ref": submission_ref,
                        "episode_id": ep_id,
                        "agent_index": str(agent_idx),
                        "episode_type": ep["type"],
                        "episode_state": ep["state"],
                        "log_path": dest.relative_to(ROOT).as_posix(),
                    })
            except RuntimeError as exc:
                print(f"  ! episode {ep_id} agent {agent_idx}: {exc}", file=sys.stderr)

    manifest_added = append_manifest_rows(MANIFEST_PATH, manifest_rows)
    return written, manifest_added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--competition", default=DEFAULT_COMPETITION or _TL_COMP)
    parser.add_argument("--output-dir", default=str(LOGS_DIR))
    parser.add_argument(
        "--ref", default=None,
        help="Fetch logs for this submission ref only (default: all submissions).",
    )
    parser.add_argument(
        "--agents", default="0,1",
        help="Comma-separated agent indices to try (default: 0,1). "
             "403 responses are skipped — usually only your agent index succeeds.",
    )
    parser.add_argument(
        "--status", default="COMPLETE",
        help="Only process submissions with this status (default: COMPLETE). "
             "Use 'ALL' to disable filtering.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max submission refs to process (most recent first).",
    )
    parser.add_argument("--force", action="store_true", help="Re-download existing logs.")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    try:
        agents = [int(x.strip()) for x in args.agents.split(",") if x.strip()]
    except ValueError:
        print("ERROR: --agents must be comma-separated integers", file=sys.stderr)
        return 1

    if args.ref:
        refs = [args.ref.strip()]
    else:
        try:
            csv_text = fetch_submissions_csv(args.competition)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        submissions = parse_submissions(csv_text)
        status_filter = None if args.status.upper() == "ALL" else args.status.upper()
        refs = []
        for sub in submissions:
            if status_filter and sub["status"].upper() != status_filter:
                continue
            refs.append(sub["ref"])
        if args.limit:
            refs = refs[: args.limit]

    if not refs:
        print("no submission refs to process")
        return 0

    total_written = 0
    for ref in refs:
        print(f"ref {ref}:")
        try:
            n, _ = fetch_logs_for_ref(
                ref, output_dir=output_dir, agents=agents, force=args.force,
            )
        except RuntimeError as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            continue
        total_written += n

    print(f"downloaded {total_written} new log file(s) under {output_dir}")
    print(f"manifest: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
