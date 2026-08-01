#!/usr/bin/env python3
"""Auto-submit to Kaggle Simulation with daily cap + one retry.

Policy (user 2026-07-30 + rules lock):
  - Auto-approve all train/eval/package/Kaggle API calls
  - Caller should only invoke for the CURRENT STRONGEST gate-pass agent
  - Hard cap: 5 submissions per calendar day (local timezone)
  - Leaderboard keeps only the LATEST 2 submissions — do not spray mediocre builds
  - Pre-submit expectation: legal + finish + WR clearly > random (local gate)
  - On API failure: retry once; if still fail, leave package ready and exit 3
  - Always append result to dist/submit_log.jsonl and refresh STATE.md section

Usage:
  python scripts/auto_submit.py --file dist/candidates/foo.tar.gz --message "..." \\
      --local-gate 62.5 --strength-note "dragapult gate 62.5%"
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPETITION = "pokemon-tcg-ai-battle"
LOG_PATH = ROOT / "dist" / "submit_log.jsonl"
COUNT_PATH = ROOT / "dist" / "submit_count.json"
STATE_PATH = ROOT / "STATE.md"
MAX_PER_DAY = 5
# Only the latest N submissions remain active on the Simulation ladder.
ACTIVE_ON_BOARD = 2
# Soft gate: refuse submit if local_gate provided and below this (unless --force).
# Quality ship floor (Director 2026-07-31: Arch overall ≥83).
# Only ship when dual-meta competitive (not random-gate vanity).
MIN_LOCAL_WR_PCT = 83.0
TOKEN_CANDIDATES = [
    ROOT / ".kaggle" / "access_token",
    ROOT / ".kaggle" / "kaggle.json",
    ROOT.parent / ".kaggle" / "access_token",  # E:\PTCG_AI_Battle_Challenge\.kaggle
    ROOT.parent / ".kaggle" / "kaggle.json",
    Path.home() / ".kaggle" / "access_token",
    Path.home() / ".kaggle" / "kaggle.json",
]


def ensure_token() -> bool:
    """Load KAGGLE_API_TOKEN / legacy kaggle.json into env if present."""
    if os.environ.get("KAGGLE_API_TOKEN"):
        return True
    # A refreshed token may have been persisted with
    # SetEnvironmentVariable(..., "User") after Windows Terminal was already
    # running. Existing tabs do not inherit that update, so read HKCU directly
    # at submission time before falling back to token files.
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                token, _ = winreg.QueryValueEx(key, "KAGGLE_API_TOKEN")
            if str(token).strip():
                os.environ["KAGGLE_API_TOKEN"] = str(token).strip()
                return True
        except (FileNotFoundError, OSError):
            pass
    for p in TOKEN_CANDIDATES:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            continue
        if p.name == "kaggle.json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            user = data.get("username") or data.get("userName")
            key = data.get("key") or data.get("token") or data.get("api_token")
            if user and key:
                os.environ["KAGGLE_USERNAME"] = str(user)
                os.environ["KAGGLE_KEY"] = str(key)
                # Newer CLI prefers bearer; if key looks like KGAT_, also set token.
                if str(key).startswith("KGAT_"):
                    os.environ["KAGGLE_API_TOKEN"] = str(key)
                return True
            if str(data.get("token", "")).startswith("KGAT_"):
                os.environ["KAGGLE_API_TOKEN"] = str(data["token"])
                return True
        else:
            # raw access_token file
            os.environ["KAGGLE_API_TOKEN"] = text.splitlines()[0].strip()
            return True
    return bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))


def _today() -> str:
    """Kaggle daily submission allowance resets on UTC midnight — track UTC day."""
    return datetime.now(timezone.utc).date().isoformat()


def load_count() -> dict:
    if COUNT_PATH.exists():
        try:
            # utf-8-sig tolerates Windows PowerShell BOM writes
            return json.loads(COUNT_PATH.read_text(encoding="utf-8-sig"))
        except Exception:
            pass
    return {"date": _today(), "count": 0, "refs": []}


def save_count(data: dict) -> None:
    COUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Write UTF-8 without BOM so other tools parse cleanly
    COUNT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def submits_today() -> int:
    data = load_count()
    if data.get("date") != _today():
        data = {"date": _today(), "count": 0, "refs": []}
        save_count(data)
    return int(data.get("count", 0))


def record_submit(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    data = load_count()
    if data.get("date") != _today():
        data = {"date": _today(), "count": 0, "refs": []}
    data["count"] = int(data.get("count", 0)) + 1
    data.setdefault("refs", []).append(entry)
    save_count(data)


def kaggle_bin() -> list[str]:
    venv_kaggle = ROOT.parent / ".venv" / "Scripts" / "kaggle.exe"
    if venv_kaggle.exists():
        return [str(venv_kaggle)]
    return [sys.executable, "-m", "kaggle"]


def run_submit(path: Path, message: str) -> tuple[int, str]:
    cmd = kaggle_bin() + [
        "competitions",
        "submit",
        "-c",
        COMPETITION,
        "-f",
        str(path),
        "-m",
        message,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def append_state_block(entry: dict) -> None:
    """Prepend a short submission block to STATE.md."""
    ts = entry.get("submitted_at_local") or datetime.now().isoformat(timespec="seconds")
    block = (
        f"\n### Auto-submit {ts}\n"
        f"- file: `{entry.get('file')}`\n"
        f"- status: **{entry.get('status')}**\n"
        f"- message: {entry.get('message')}\n"
        f"- local_gate: {entry.get('local_gate')}\n"
        f"- strength_note: {entry.get('strength_note')}\n"
        f"- submits_today: {entry.get('submits_today_after')}/{MAX_PER_DAY} "
        f"(board keeps latest {ACTIVE_ON_BOARD})\n"
        f"- api_output: ```{str(entry.get('api_output', ''))[:500]}```\n"
    )
    if not STATE_PATH.exists():
        STATE_PATH.write_text("# STATE\n" + block, encoding="utf-8")
        return
    text = STATE_PATH.read_text(encoding="utf-8")
    marker = "## Auto-submit log"
    if marker in text:
        text = text.replace(marker, marker + block, 1)
    else:
        text = text.rstrip() + f"\n\n---\n\n{marker}\n" + block + "\n"
    STATE_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True, help="Path to submission.tar.gz")
    ap.add_argument("--message", required=True)
    ap.add_argument("--local-gate", type=float, default=None, help="Local WR%% that passed")
    ap.add_argument("--strength-note", default="")
    ap.add_argument("--force", action="store_true", help="Ignore daily cap (DO NOT use normally)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"[ERROR] file not found: {path}")
        return 2

    if not ensure_token():
        print("[ERROR] No Kaggle token. Place ~/.kaggle/access_token or KAGGLE_API_TOKEN.")
        entry = {
            "status": "NO_TOKEN",
            "file": str(path),
            "message": args.message,
            "local_gate": args.local_gate,
            "strength_note": args.strength_note,
            "submitted_at_local": datetime.now().isoformat(timespec="seconds"),
            "submits_today_after": submits_today(),
            "api_output": "missing token",
        }
        append_state_block(entry)
        return 2

    n = submits_today()
    if n >= MAX_PER_DAY and not args.force:
        print(f"[SKIP] daily cap reached: {n}/{MAX_PER_DAY}")
        entry = {
            "status": "SKIPPED_DAILY_CAP",
            "file": str(path),
            "message": args.message,
            "local_gate": args.local_gate,
            "strength_note": args.strength_note,
            "submitted_at_local": datetime.now().isoformat(timespec="seconds"),
            "submits_today_after": n,
            "api_output": f"cap {MAX_PER_DAY}",
        }
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        append_state_block(entry)
        return 0

    # Pre-submit local gate floor (legal/finish implied by caller; WR must clear bar)
    if (
        args.local_gate is not None
        and args.local_gate >= 0
        and args.local_gate < MIN_LOCAL_WR_PCT
        and not args.force
    ):
        print(
            f"[SKIP] local_gate {args.local_gate}% < min {MIN_LOCAL_WR_PCT}% "
            f"(need WR clearly > random; use --force only if intentional)"
        )
        entry = {
            "status": "SKIPPED_WEAK_GATE",
            "file": str(path),
            "message": args.message,
            "local_gate": args.local_gate,
            "strength_note": args.strength_note,
            "submitted_at_local": datetime.now().isoformat(timespec="seconds"),
            "submits_today_after": n,
            "api_output": f"min_local_wr={MIN_LOCAL_WR_PCT}",
        }
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        append_state_block(entry)
        return 0

    if args.dry_run:
        print(
            f"[DRY-RUN] would submit {path} ({n+1}/{MAX_PER_DAY}); "
            f"board keeps latest {ACTIVE_ON_BOARD}"
        )
        return 0

    # Final enforcement point: every real automatic submission, including a
    # rollback/reship, must pass the authoritative pooled director gates at the
    # moment the API call is made. Message text and --force are not gate
    # exceptions; a user policy change must modify the SSOT explicitly.
    from director_gate import PRIMARY_ID, evaluate_ship, load_ship_snapshot, log_decision

    snapshot = load_ship_snapshot()
    verdict = evaluate_ship(
        snapshot,
        candidate_id=PRIMARY_ID,
        submits_today=n,
    ) if snapshot is not None else None
    if verdict is None or not verdict.ship:
        reasons = verdict.reasons if verdict is not None else ["no authoritative pooled snapshot"]
        print(f"[SKIP] director gates are not green: {'; '.join(reasons)}")
        if verdict is not None:
            log_decision(
                verdict,
                source="auto_submit",
                candidate_id=PRIMARY_ID,
                file=str(path),
            )
        entry = {
            "status": "SKIPPED_DIRECTOR_GATE",
            "file": str(path),
            "message": args.message,
            "local_gate": args.local_gate,
            "strength_note": args.strength_note,
            "submitted_at_local": datetime.now().isoformat(timespec="seconds"),
            "submits_today_after": n,
            "api_output": "; ".join(reasons),
        }
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        append_state_block(entry)
        return 0

    print(
        f"[SUBMIT] {path.name} attempt 1 ({n+1}/{MAX_PER_DAY}) "
        f"[board keeps latest {ACTIVE_ON_BOARD}; strongest-only policy]..."
    )
    code, out = run_submit(path, args.message)
    print(out)
    if code != 0:
        print("[SUBMIT] attempt 1 failed; retrying once after 5s...")
        time.sleep(5)
        code, out = run_submit(path, args.message)
        print(out)

    status = "OK" if code == 0 else "FAILED_READY_FOR_MANUAL"
    entry = {
        "status": status,
        "file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "message": args.message,
        "local_gate": args.local_gate,
        "strength_note": args.strength_note,
        "submitted_at_utc": datetime.now(timezone.utc).isoformat(),
        "submitted_at_local": datetime.now().isoformat(timespec="seconds"),
        "submitted_at_utc": datetime.now(timezone.utc).isoformat(),
        "utc_day": _today(),
        "api_rc": code,
        "api_output": out[-2000:],
        "submits_today_after": n + (1 if code == 0 else 0),
    }
    if code == 0:
        record_submit(entry)
    else:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    append_state_block(entry)

    if code != 0:
        print(
            f"[MANUAL] API submit failed twice. Package ready at:\n  {path}\n"
            f"Upload via Kaggle UI: competition {COMPETITION}"
        )
        return 3
    print(f"[OK] submitted. today={entry['submits_today_after']}/{MAX_PER_DAY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
