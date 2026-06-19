"""Record Kaggle Simulation-ladder submission history over time (Phase 0).

Runs ``kaggle competitions submissions -c pokemon-tcg-ai-battle -v`` (READ ONLY),
parses the CSV it prints, and appends any new rows into
``report/ladder_history.csv`` so the nightly run can watch whether our ladder mu
(publicScore) moves after matchmaking.

This script NEVER submits anything. It only reads the existing submissions.

Safe to run repeatedly: it dedupes by (ref, status, publicScore), so re-running
appends status transitions, new submissions, and ladder mu updates when the
public score changes for an existing ref.

Usage:
    python scripts/track_ladder.py
    python scripts/track_ladder.py --competition pokemon-tcg-ai-battle
    python scripts/track_ladder.py --from-file submissions.csv   # parse a saved CSV
    python scripts/track_ladder.py --fetch-logs                  # also download agent logs
"""
from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "report" / "ladder_history.csv"
DEFAULT_COMPETITION = "pokemon-tcg-ai-battle"

# The schema we persist. Superset of the required columns (ref, fileName, date,
# description, status, publicScore) plus recorded_at + privateScore, matching the
# existing report/ladder_history.csv so appends stay column-aligned. If the file
# already exists with a different header, we adapt to whatever header it has.
FIELDS = [
    "recorded_at", "ref", "fileName", "date",
    "description", "status", "publicScore", "privateScore",
]


def _normalize_status(value: str) -> str:
    """'SubmissionStatus.COMPLETE' -> 'COMPLETE'; pass other values through."""
    value = (value or "").strip()
    return value.rsplit(".", 1)[-1] if "." in value else value


def fetch_submissions_csv(competition: str) -> str:
    """Return the raw CSV text from the Kaggle CLI (READ ONLY command)."""
    cmd = ["kaggle", "competitions", "submissions", "-c", competition, "-v"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "kaggle CLI not found on PATH. Install with `pip install kaggle` and "
            "place kaggle.json credentials, then retry."
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"`{' '.join(cmd)}` failed (exit {proc.returncode}).\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc.stdout


def _extract_csv_block(text: str) -> str:
    """Pull the CSV block out of CLI output (skip any leading warning lines)."""
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        low = line.lower()
        if "filename" in low and "date" in low and "," in line:
            header_idx = i
            break
    if header_idx is None:
        return text  # let the caller's DictReader try its best
    return "\n".join(lines[header_idx:])


def _norm_key(key: str) -> str:
    return (key or "").lstrip("\ufeff").strip().lower().replace(" ", "").replace("_", "")


def parse_submissions(csv_text: str) -> list[dict[str, str]]:
    """Parse the Kaggle submissions CSV into our normalized schema rows."""
    block = _extract_csv_block(csv_text)
    reader = csv.DictReader(io.StringIO(block))
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, str]] = []
    for raw in reader:
        norm = {_norm_key(k): (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(norm.values()):
            continue
        file_name = norm.get("filename", "")
        date = norm.get("date", "")
        # The CLI usually provides a numeric ref; fall back to a stable synthetic
        # key only if it is absent.
        ref = norm.get("ref") or norm.get("url") or f"{date}|{file_name}"
        rows.append({
            "recorded_at": recorded_at,
            "ref": ref,
            "fileName": file_name,
            "date": date,
            "description": norm.get("description", ""),
            "status": _normalize_status(norm.get("status", "")),
            "publicScore": norm.get("publicscore", ""),
            "privateScore": norm.get("privatescore", ""),
        })
    return rows


def _read_existing(path: Path) -> tuple[list[str] | None, set[tuple[str, str, str]]]:
    """Return (header_fieldnames or None, set of (ref, status, publicScore) recorded)."""
    if not path.exists():
        return None, set()
    keys: set[tuple[str, str, str]] = set()
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames
        for row in reader:
            keys.add((
                (row.get("ref") or "").strip(),
                (row.get("status") or "").strip(),
                (row.get("publicScore") or "").strip(),
            ))
    return header, keys


def append_new_rows(path: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Append rows whose (ref, status, publicScore) is not already present.

    Adapts to the existing file's header (so a pre-existing history written with a
    different column order stays aligned). Dedupes by (ref, status, publicScore).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    header, existing = _read_existing(path)
    fieldnames = header or FIELDS

    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, str]] = []
    for r in rows:
        key = (r["ref"], r["status"], r.get("publicScore", ""))
        if key in existing or key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    write_header = header is None
    if deduped or write_header:
        with path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore", restval="")
            if write_header:
                writer.writeheader()
            writer.writerows(deduped)
    return deduped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--competition", default=DEFAULT_COMPETITION)
    parser.add_argument("--history", default=str(HISTORY_PATH))
    parser.add_argument(
        "--from-file", default=None,
        help="Parse this CSV file instead of calling the Kaggle CLI (for testing).",
    )
    parser.add_argument(
        "--fetch-logs", action="store_true",
        help="After recording submissions, run scripts/fetch_agent_logs.py (READ ONLY).",
    )
    args = parser.parse_args(argv)

    history_path = Path(args.history)
    if not history_path.is_absolute():
        history_path = ROOT / history_path

    if args.from_file:
        csv_text = Path(args.from_file).read_text(encoding="utf-8-sig")
    else:
        try:
            csv_text = fetch_submissions_csv(args.competition)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    rows = parse_submissions(csv_text)
    print(f"parsed {len(rows)} submission row(s) from Kaggle")
    new_rows = append_new_rows(history_path, rows)
    print(f"appended {len(new_rows)} new row(s) to {history_path}")
    for r in new_rows:
        print(f"  + {r['date']}  {r['status']:<10}  score={r['publicScore'] or '-':<8}"
              f"  {r['fileName']}")

    if args.fetch_logs:
        fetch_script = ROOT / "scripts" / "fetch_agent_logs.py"
        print(f"fetching agent logs via {fetch_script.name} ...")
        proc = subprocess.run(
            [sys.executable, str(fetch_script), "--competition", args.competition],
            cwd=ROOT,
            timeout=600,
        )
        if proc.returncode != 0:
            print(f"WARNING: fetch_agent_logs exited {proc.returncode}", file=sys.stderr)
            return proc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
