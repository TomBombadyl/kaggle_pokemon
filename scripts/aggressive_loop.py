#!/usr/bin/env python3
"""NEVER-STOP aggressive train/eval/package/submit loop for PTCG Simulation.

Competition constraints (user update 2026-07-30):
  1. Max 5 submissions/day; only the LATEST 2 stay on the leaderboard.
  2. Battle clock 10 min/player — timeout = lose → inference speed first.
  3. Official card pool only (validate_deck / EN_Card_Data).
  4. Almost no competition training compute → maximize local self-play + MCTS.
  5. Pre-submit local gate: no illegal actions + games finish + WR >> random.
  6. Aggressive parallel LOCAL work; submit only the current strongest version.
  7. Daily: download/analyze public episodes → deck + strategy adjustments.

Auto policy:
  - All train/eval/package/file/Kaggle API ops auto-approved
  - Gate pass + strongest rank → auto-submit (≤5/day, soft prefer ≤2 quality slots)
  - On submit fail: one retry then leave package for manual upload
  - Always refresh STATE.md (repo + workspace root)

Run:
  python scripts/aggressive_loop.py
  python scripts/aggressive_loop.py --once
  python scripts/aggressive_loop.py --poll-seconds 30 --min-wr 56
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
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.auto_submit import (  # noqa: E402
    MAX_PER_DAY,
    ensure_token,
    submits_today,
)

STATE_PATH = ROOT / "STATE.md"
ROOT_STATE_PATH = ROOT.parent / "STATE.md"
DAILY_LOG_PATH = ROOT.parent / "DAILY_LOG.md"
ENGINE_CG = ROOT / "data" / "sim" / "sample_submission" / "cg"
LOOP_LOG = ROOT / "dist" / "loop_log.jsonl"
EPISODE_MARKER = ROOT / "dist" / "episode_refresh_day.txt"
BEST_GATE_PATH = ROOT / "dist" / "best_gate.json"
LOCK_PATH = ROOT / "dist" / "aggressive_loop.lock"
PY = Path(sys.executable)


_lock_fd: int | None = None
_mutex_handle = None  # Windows named mutex


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        SYNCHRONIZE = 0x00100000
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
    except Exception:
        pass
    return False


def acquire_single_instance_lock() -> bool:
    """Single-instance lock: Windows named mutex + O_EXCL file (multi-session safe)."""
    global _lock_fd, _mutex_handle
    # --- Named mutex (primary on Windows) ---
    if sys.platform.startswith("win"):
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            ERROR_ALREADY_EXISTS = 183
            name = "Global\\PTCG_AggressiveLoop_E_Drive_v1"
            handle = kernel32.CreateMutexW(None, True, name)
            last = kernel32.GetLastError()
            if not handle:
                print("[LOCK] CreateMutex failed", flush=True)
                return False
            if last == ERROR_ALREADY_EXISTS:
                kernel32.CloseHandle(handle)
                print(f"[LOCK] named mutex already held ({name})", flush=True)
                return False
            _mutex_handle = handle
        except Exception as e:
            print(f"[LOCK] mutex error (fallback to file): {e}", flush=True)

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            old_pid = int(data.get("pid") or 0)
            if old_pid and not _pid_alive(old_pid):
                LOCK_PATH.unlink(missing_ok=True)
            elif old_pid and old_pid != os.getpid() and _pid_alive(old_pid):
                print(f"[LOCK] held by live pid={old_pid} path={LOCK_PATH}", flush=True)
                return False
            elif (time.time() - LOCK_PATH.stat().st_mtime) > 48 * 3600:
                LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            try:
                if (time.time() - LOCK_PATH.stat().st_mtime) > 3600:
                    LOCK_PATH.unlink(missing_ok=True)
            except Exception:
                pass
    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
    try:
        _lock_fd = os.open(str(LOCK_PATH), flags)
    except FileExistsError:
        # If we own the mutex, force-replace stale file lock
        if _mutex_handle is not None:
            try:
                LOCK_PATH.unlink(missing_ok=True)
                _lock_fd = os.open(str(LOCK_PATH), flags)
            except Exception:
                print(f"[LOCK] exclusive create failed path={LOCK_PATH}", flush=True)
                return False
        else:
            print(f"[LOCK] exclusive create failed — another instance path={LOCK_PATH}", flush=True)
            return False
    payload = {
        "pid": os.getpid(),
        "started": datetime.now().isoformat(timespec="seconds"),
        "py": str(PY),
        "cwd": str(ROOT),
    }
    os.write(_lock_fd, json.dumps(payload, indent=2).encode("utf-8"))
    return True


def release_single_instance_lock() -> None:
    global _lock_fd, _mutex_handle
    try:
        if _lock_fd is not None:
            os.close(_lock_fd)
            _lock_fd = None
        if LOCK_PATH.exists():
            try:
                data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
                if int(data.get("pid") or 0) in (0, os.getpid()):
                    LOCK_PATH.unlink(missing_ok=True)
            except Exception:
                LOCK_PATH.unlink(missing_ok=True)
        if _mutex_handle is not None and sys.platform.startswith("win"):
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.ReleaseMutex(_mutex_handle)
            kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Competition rules (hard constraints)
# ---------------------------------------------------------------------------
RULES = {
    "max_submits_per_day": MAX_PER_DAY,  # 5
    "active_on_board": 2,  # only latest 2 submissions count on ladder
    "battle_time_limit_sec": 600,  # 10 min / player
    "official_card_pool_only": True,
    # Quality-over-quantity (user 2026-07-30 sprint):
    #  - Soft slots 2 already used; 3rd only clear+stable upgrade above board ~710
    "soft_quality_slots_per_day": 2,
    "max_submit_per_cycle": 1,  # only the single strongest each cycle
    "prefer_fast_brains": True,  # rule pilots over heavy MCTS at ship time
    # Require clear local lift vs last best before burning soft slot after first ships.
    "min_upgrade_wr_delta": 5.0,
    # Never auto-ship demoted lines (Dragapult/Alakazam) under #1 chase lock.
    # Strategy lock 2026-07-30: day-flip + μ chase = Crustle only via wait_and_submit_crustle.
    # Never auto-ship Arch/Dra/Alak from this loop (manual or dedicated ship path only).
    # Arch is PRIMARY ship path — never block it. Only demote weak lines.
    "block_submit_ids": ("dragapult_ex_sample", "alakazam"),
    # CUDA field MCTS ON (user sprint) — background; Arch gates remain primary.
    "skip_mcts_train": False,
}

# Leaderboard snap 2026-07-30 (user intel) — top tier ~1176–1198.
LEADERBOARD_TOP = [
    {"rank": 1, "team": "flg", "score": 1198.4},
    {"rank": 2, "team": "Dries @ Tufa Labs", "score": 1197.7},
    {"rank": 3, "team": "James Cox & Henry Chao", "score": 1190.3},
    {"rank": 4, "team": "LiamK", "score": 1183.1},
    {"rank": 5, "team": "Majkel1337", "score": 1182.2},
    {"rank": 6, "team": "Luca", "score": 1176.5},
]

CONFIG = {
    # Scout bar: clearly > random (local iteration signal).
    "min_wr_pct": 60.0,
    # Ship bar (Director 2026-07-31): Arch≥83 / Iono≥55 / Crustle≥89 / dual>baseline.
    # Do NOT burn quota for inflated random-gate overall WR.
    "ship_min_wr_pct": 83.0,
    "ship_min_games": 80,  # deepen before any quality ship
    "ship_crustle_min_wr_pct": 89.0,  # deep Crustle floor (min flg/majkel)
    "min_games": 24,
    "gate_games": 16,  # sparse non-primary (rare probes only)
    "gate_games_primary": 32,  # sprint: Iono+Crustle+Grimmsnarl
    "gate_deepen_primary": 56,  # pre-ship deepen (Iono signal)
    "gate_parallel_workers": 1,  # Archaludon-only focus; no fan-out waste
    "selfplay_games_when_idle": 40,
    "episode_refresh_hours": 12,  # more aggressive meta refresh
    # Archaludon PRIMARY — board ~656–681; hist pin 1196.1.
    "primary_focus": "archaludon",
    "primary_deck": "agent_decks/archaludon_ex_cinderace.csv",
    "board_mu_target": 681.6,  # live board to clearly beat for slot #3
    "ladder_pin_mu": 1196.1,  # historical ceiling — target to re-hit / pass
    "ladder_top1_mu": 1198.4,  # flg
    "ladder_top6_floor": 1176.5,  # first-tier band
    "primary_gate_suite": "sprint",  # Iono + Crustle×2 + Grimmsnarl×2
    # Any quality ship: native Iono floor (random meta must not inflate ship).
    "ship_iono_min_wr_pct": 55.0,  # stable Iono floor before quality ship
    # Director gate module is authoritative; keep mirrors in sync.
    "director_gate_enabled": True,
}

# Package targets. PRIMARY = Archaludon (live 793.7 + hist 1196.1 pin).
# Dragapult demoted (live ~593.7) — gated only every N cycles to save compute.
CANDIDATES = [
    {
        "id": "archaludon",
        "priority": 200,  # PRIMARY — re-hit 1196 pin / chase 1198 top
        "primary": True,
        "speed_class": "fast",  # rule pilot
        "package": ["scripts/package_archaludon.py"],
        "gate": [
            "scripts/gate_archaludon.py",
            "--games",
            str(CONFIG["gate_games_primary"]),
            "--suite",
            str(CONFIG.get("primary_gate_suite") or "sprint"),
        ],
        "tarball": "dist/candidates/archaludon.tar.gz",
        "deck": "agent_decks/archaludon_ex_cinderace.csv",
        "change": (
            "Archaludon PRIMARY sprint (Iono/Crustle/Grimmsnarl) R14e — "
            f"beat board {CONFIG['board_mu_target']} / pin {CONFIG.get('ladder_pin_mu')}"
        ),
        "brain": "archaludon_agent",
        "every_n_cycles": 1,  # always
    },
    {
        "id": "dragapult_ex_sample",
        "priority": 25,  # heavily demoted (~593.7 live)
        "primary": False,
        "speed_class": "fast",
        "package": ["scripts/package_dragapult.py"],
        "gate": ["scripts/gate_dragapult.py", "--games", str(CONFIG["gate_games"]), "--suite", "core"],
        "tarball": "dist/candidates/dragapult_ex_sample.tar.gz",
        "deck": "agent_decks/dragapult_ex_sample.csv",
        "change": "auto-loop: Dragapult rare probe only",
        "brain": "dragapult_agent",
        # Arch-only μ factory: Dra blocked from submit — do not waste gate CPU.
        "every_n_cycles": 9999,
    },
    {
        "id": "alakazam",
        "priority": 20,
        "primary": False,
        "speed_class": "fast",
        "package": ["scripts/package_alakazam.py"],
        "gate": ["scripts/gate_alakazam.py", "--games", str(CONFIG["gate_games"]), "--suite", "core"],
        "tarball": "dist/candidates/ryotasueyoshi_alakazam_best5_dragapult_lever.tar.gz",
        "deck": "agent_decks/ryotasueyoshi_alakazam_best5.csv",
        "change": "auto-loop: Alakazam rare probe",
        "brain": "alakazam_agent",
        # Arch-only μ factory: Alak blocked from submit — do not waste gate CPU.
        "every_n_cycles": 9999,
    },
]


def candidates_for_cycle(cycle: int) -> list[dict]:
    """Always gate primary (Archaludon); sparse-gate demoted lines."""
    out: list[dict] = []
    for c in CANDIDATES:
        n = int(c.get("every_n_cycles") or 1)
        if c.get("primary") or cycle % n == 0 or n <= 1:
            out.append(c)
    if not out:
        out = [c for c in CANDIDATES if c.get("primary")] or list(CANDIDATES[:1])
    return out


def rank_gate_results(results: list[dict]) -> list[dict]:
    """Prefer primary Archaludon when competitive; else WR then priority."""
    primary = str(CONFIG.get("primary_focus") or "archaludon")

    def sort_key(r: dict):
        wr = r["wr"] if r["wr"] is not None else -1.0
        ok = 1 if r.get("ok") else 0
        is_primary = 1 if r.get("id") == primary else 0
        # Primary that passes gate ranks above non-primary pass with similar WR.
        # Primary close-to-bar still preferred for deepen / ship consideration.
        return (ok, is_primary, wr, r.get("priority", 0))

    results = list(results)
    results.sort(key=sort_key, reverse=True)
    return results


def log_event(event: str, **kwargs) -> None:
    LOOP_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event, **kwargs}
    with LOOP_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{row['ts']}] {event} {json.dumps(kwargs, ensure_ascii=False) if kwargs else ''}", flush=True)


def run(cmd: list[str], timeout: int | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        proc = subprocess.run(
            [str(PY)] + cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out
    except subprocess.TimeoutExpired as e:
        out = (str(e.stdout or "") if not isinstance(e.stdout, str) else (e.stdout or "")) + (
            str(e.stderr or "") if not isinstance(e.stderr, str) else (e.stderr or "")
        )
        return 124, out + "\n[TIMEOUT]"


def engine_ready() -> bool:
    """Require full cabt package (game + sim + native lib) — partial trees fail gates."""
    need = [
        ENGINE_CG / "game.py",
        ENGINE_CG / "api.py",
        ENGINE_CG / "sim.py",
        ENGINE_CG / "utils.py",
    ]
    if not all(p.exists() and p.stat().st_size > 0 for p in need):
        return False
    # Native binary for this OS
    if sys.platform.startswith("win"):
        return (ENGINE_CG / "cg.dll").exists()
    if sys.platform == "darwin":
        return (ENGINE_CG / "libcg.dylib").exists() or (ENGINE_CG / "libcg.so").exists()
    return (ENGINE_CG / "libcg.so").exists()


def clear_corrupt_engine_cache() -> None:
    """Remove partial / bad engine archives so the next fetch can succeed."""
    sim_dl = ROOT / "data" / "sim_download"
    if sim_dl.exists():
        for p in sim_dl.glob("pokemon-tcg-ai-battle*"):
            try:
                p.unlink()
                log_event("cleared_partial", path=str(p))
            except OSError as e:
                log_event("clear_partial_fail", path=str(p), err=str(e))
    # kagglehub cache for this competition (best-effort)
    cache_roots = [
        Path.home() / ".cache" / "kagglehub" / "competitions" / "pokemon-tcg-ai-battle",
        Path.home() / ".cache" / "kagglehub" / "datasets",
    ]
    for c in cache_roots:
        if c.exists():
            try:
                # Only wipe competition folder if present
                if "pokemon-tcg-ai-battle" in str(c):
                    shutil.rmtree(c, ignore_errors=True)
                    log_event("cleared_kagglehub_cache", path=str(c))
            except OSError:
                pass


def fetch_engine() -> bool:
    if engine_ready():
        return True
    if not ensure_token():
        return False
    log_event("fetch_engine_start")
    # 1) Light file-by-file download (avoids huge zip BadZipFile)
    code_l, out_l = _fetch_engine_light_files()
    log_event("fetch_engine_light", rc=code_l, ready=engine_ready(), tail=out_l[-500:])
    if engine_ready():
        return True
    # 2) Full kagglehub package
    code, out = run(["scripts/fetch_sim_engine.py"], timeout=900)
    if code != 0 or not engine_ready():
        if "BadZipFile" in out or "bad magic" in out.lower() or "partial" in out.lower():
            log_event("fetch_engine_corrupt", tail=out[-400:])
            clear_corrupt_engine_cache()
            code, out = run(["scripts/fetch_sim_engine.py"], timeout=900)
        if not engine_ready():
            code2, out2 = _fetch_engine_via_kaggle_cli()
            log_event("fetch_engine_cli", rc=code2, tail=out2[-500:])
            out = out + "\n" + out2
    log_event("fetch_engine_done", rc=code, ready=engine_ready(), tail=out[-800:])
    return engine_ready()


def _fetch_engine_light_files() -> tuple[int, str]:
    """Download only required sample_submission/cg files via kaggle CLI -f."""
    ensure_token()
    cg = ENGINE_CG
    cg.mkdir(parents=True, exist_ok=True)
    base = ROOT / "data" / "sim" / "sample_submission"
    base.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "data" / "sim_download" / "light"
    tmp.mkdir(parents=True, exist_ok=True)
    remote_to_dest = [
        ("sample_submission/sample_submission/cg/sim.py", cg / "sim.py"),
        ("sample_submission/sample_submission/cg/utils.py", cg / "utils.py"),
        ("sample_submission/sample_submission/cg/api.py", cg / "api.py"),
        ("sample_submission/sample_submission/cg/game.py", cg / "game.py"),
        ("sample_submission/sample_submission/cg/__init__.py", cg / "__init__.py"),
        ("sample_submission/sample_submission/cg/cg.dll", cg / "cg.dll"),
        ("sample_submission/sample_submission/cg/libcg.so", cg / "libcg.so"),
        ("sample_submission/sample_submission/cg/libcg-arm64.so", cg / "libcg-arm64.so"),
        ("sample_submission/sample_submission/cg/libcg.dylib", cg / "libcg.dylib"),
        ("sample_submission/sample_submission/main.py", base / "main.py"),
        ("sample_submission/sample_submission/deck.csv", base / "deck.csv"),
        ("EN_Card_Data.csv", ROOT / "data" / "EN_Card_Data.csv"),
    ]
    logs: list[str] = []
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    for remote, dest in remote_to_dest:
        if dest.exists() and dest.stat().st_size > 0:
            continue
        cmd = [
            str(PY),
            "-m",
            "kaggle",
            "competitions",
            "download",
            "-c",
            "pokemon-tcg-ai-battle",
            "-f",
            remote,
            "-p",
            str(tmp),
            "--force",
        ]
        try:
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=300, env=env)
            logs.append(f"{remote}: rc={proc.returncode}")
            # find downloaded file
            name = Path(remote).name
            hits = list(tmp.rglob(name))
            if hits:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(hits[-1], dest)
                logs.append(f"  -> {dest}")
        except Exception as e:
            logs.append(f"{remote}: ERR {e}")
    # empty __init__ is ok
    init = cg / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
    return (0 if engine_ready() else 1), "\n".join(logs)


def _fetch_engine_via_kaggle_cli() -> tuple[int, str]:
    """Fallback download using kaggle CLI + extract sample_submission."""
    dl_dir = ROOT / "data" / "sim_download"
    dl_dir.mkdir(parents=True, exist_ok=True)
    for p in dl_dir.glob("pokemon-tcg-ai-battle*"):
        try:
            p.unlink()
        except OSError:
            pass
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    # ensure token loaded into env for CLI
    ensure_token()
    cmd = [
        str(PY),
        "-m",
        "kaggle",
        "competitions",
        "download",
        "-c",
        "pokemon-tcg-ai-battle",
        "-p",
        str(dl_dir),
    ]
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=900, env=env)
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            return proc.returncode, out
    except subprocess.TimeoutExpired as e:
        return 124, str(e) + "\n[TIMEOUT]"

    zips = list(dl_dir.glob("*.zip"))
    if not zips:
        return 1, out + "\n[ERROR] no zip after kaggle download"
    zpath = max(zips, key=lambda p: p.stat().st_size)
    if zpath.stat().st_size < 1_000_000:
        return 1, out + f"\n[ERROR] zip too small ({zpath.stat().st_size})"
    import zipfile

    dst = ROOT / "data" / "sim"
    dst.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zpath, "r") as zf:
            for name in zf.namelist():
                if name.lower().endswith(".pdf"):
                    continue
                zf.extract(name, dst)
    except zipfile.BadZipFile as e:
        clear_corrupt_engine_cache()
        return 1, out + f"\n[ERROR] BadZipFile: {e}"
    return 0, out + f"\n[OK] extracted {zpath.name} → data/sim/"


def fetch_card_pool() -> bool:
    """Ensure official EN_Card_Data.csv exists (official card pool only)."""
    cards = ROOT / "data" / "EN_Card_Data.csv"
    if cards.exists() and cards.stat().st_size > 1000:
        return True
    if not ensure_token():
        return False
    if not (ROOT / "scripts" / "fetch_card_data.py").exists():
        log_event("card_pool_script_missing")
        return False
    log_event("fetch_card_pool_start")
    code, out = run(["scripts/fetch_card_data.py"], timeout=600)
    ok = code == 0 and cards.exists()
    log_event("fetch_card_pool_done", rc=code, ok=ok, tail=out[-500:])
    return ok


def offline_smoke() -> bool:
    code, out = run(["scripts/smoke_test.py"], timeout=120)
    ok = code == 0 and ("0 failed" in out or "passed, 0 failed" in out or "17 passed" in out)
    log_event("offline_smoke", rc=code, ok=ok, tail=out[-400:])
    return ok


def parse_wr_from_gate_output(out: str) -> float | None:
    """Best-effort overall WR%% parse from gate / harness printers."""
    patterns = [
        r"overall[^0-9%]*([0-9]+(?:\.[0-9]+)?)\s*%",
        r"win[_ ]?rate[^0-9%]*([0-9]+(?:\.[0-9]+)?)\s*%",
        r"WR[=:\s]+([0-9]+(?:\.[0-9]+)?)\s*%",
        r"E\[win\][=:\s]+(0?\.[0-9]+|[01](?:\.[0-9]+)?)",
        r"([0-9]+)\s*/\s*([0-9]+)\s*wins",
        r"wins?\s*[:=]\s*([0-9]+).*games?\s*[:=]\s*([0-9]+)",
    ]
    m = re.search(patterns[3], out, re.I)
    if m:
        return float(m.group(1)) * 100.0
    for pat in patterns[:3]:
        m = re.search(pat, out, re.I)
        if m:
            val = float(m.group(1))
            if val <= 1.0:
                return val * 100.0
            return val
    m = re.search(patterns[4], out, re.I)
    if m:
        w, g = int(m.group(1)), int(m.group(2))
        if g > 0:
            return 100.0 * w / g
    m = re.search(patterns[5], out, re.I | re.S)
    if m:
        w, g = int(m.group(1)), int(m.group(2))
        if g > 0:
            return 100.0 * w / g
    for line in out.splitlines():
        if "overall" in line.lower() or "total" in line.lower():
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", line)
            if m:
                return float(m.group(1))
    return None


def gate_candidate(c: dict) -> dict:
    """Run one candidate gate; returns result dict (for parallel map)."""
    script = c["gate"][0]
    # Infer games-per-opp from gate argv when present
    games_n = int(CONFIG.get("gate_games") or 16)
    try:
        if "--games" in c["gate"]:
            games_n = int(c["gate"][c["gate"].index("--games") + 1])
    except (ValueError, IndexError, TypeError):
        pass
    result = {
        "id": c["id"],
        "ok": False,  # scout bar (iteration signal)
        "ship_ok": False,  # quality ship bar (submit eligibility)
        "wr": None,
        "games": games_n,
        "legal": True,
        "finished": True,
        "tail": "",
        "priority": c.get("priority", 0),
        "speed_class": c.get("speed_class", "unknown"),
        "candidate": c,
    }
    if not (ROOT / script).exists():
        result["tail"] = f"missing {script}"
        return result
    code, out = run(c["gate"], timeout=2400)
    wr = parse_wr_from_gate_output(out)
    result["wr"] = wr
    result["tail"] = out[-2000:]
    bad_illegal = any(
        s in out.lower()
        for s in (
            "no legal",
            "illegal action",
            "illegal move",
            "invalid action",
        )
    )
    bad_crash = any(
        s in out.lower()
        for s in (
            "traceback",
            "filenotfounderror",
            "cg engine not found",
            "battle_start failed",
        )
    )
    unfinished = any(
        s in out.lower()
        for s in ("step cap", "max_steps", "did not finish", "unfinished", "timeout")
    )
    result["legal"] = not bad_illegal
    result["finished"] = not unfinished
    base_ok = (
        code == 0
        and not bad_illegal
        and not bad_crash
        and not unfinished
        and wr is not None
    )
    # Scout: legal + finish + WR > random-ish
    result["ok"] = bool(base_ok and wr >= float(CONFIG["min_wr_pct"]))
    # Ship: higher WR + enough games for stability (quality over quantity)
    ship_bar = float(CONFIG.get("ship_min_wr_pct") or CONFIG["min_wr_pct"])
    ship_games = int(CONFIG.get("ship_min_games") or 40)
    result["ship_ok"] = bool(
        base_ok and wr >= ship_bar and games_n >= ship_games // 3  # per-opp; 3 opps ≈ ship_min
    )
    log_event(
        "gate",
        id=c["id"],
        rc=code,
        wr=wr,
        ok=result["ok"],
        legal=result["legal"],
        finished=result["finished"],
        speed=c.get("speed_class"),
        tail=out[-500:],
    )
    return result


def parallel_gates(candidates: list[dict]) -> list[dict]:
    """Run gates in parallel (local aggressive compute)."""
    runnable = [
        c
        for c in candidates
        if (ROOT / c["package"][0]).exists() and (ROOT / c["gate"][0]).exists()
    ]
    if not runnable:
        return []
    workers = min(int(CONFIG["gate_parallel_workers"]), len(runnable))
    log_event("parallel_gates_start", n=len(runnable), workers=workers)
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(gate_candidate, c): c["id"] for c in runnable}
        for fut in as_completed(futs):
            try:
                results.append(fut.result())
            except Exception as e:
                log_event("gate_parallel_error", id=futs[fut], err=str(e))
    results = rank_gate_results(results)
    log_event(
        "parallel_gates_done",
        ranking=[{"id": r["id"], "wr": r["wr"], "ok": r["ok"]} for r in results],
        primary=CONFIG.get("primary_focus"),
    )
    return results


def validate_official_deck(c: dict) -> bool:
    """Official card pool only: every ID ∈ EN_Card_Data, size=60.

    Note: the full validate_deck evolution-line heuristic is intentionally NOT a
    hard submit block — champion ladder decks (e.g. Archaludon/Cinderace) can
    omit intermediate stages while remaining engine-legal. Hard rules:
    official IDs only + 60 cards. Engine battle_start is preferred when ready.
    """
    deck = c.get("deck")
    if not deck:
        return True
    deck_path = ROOT / deck
    if not deck_path.exists():
        log_event("deck_missing", id=c["id"], deck=deck)
        return False
    cards_path = ROOT / "data" / "EN_Card_Data.csv"
    if not cards_path.exists():
        log_event("deck_validate_skip_no_pool", id=c["id"])
        return True
    try:
        import csv as _csv

        pool: set[int] = set()
        with cards_path.open(encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                try:
                    pool.add(int(row.get("Card ID") or row.get("card_id") or list(row.values())[0]))
                except (TypeError, ValueError):
                    continue
        ids: list[int] = []
        for line in deck_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            ids.append(int(s.split(",")[0]))
        if len(ids) != 60:
            log_event("deck_validate", id=c["id"], ok=False, reason=f"size={len(ids)}!=60")
            return False
        bad = sorted({i for i in ids if i not in pool})
        if bad:
            log_event("deck_validate", id=c["id"], ok=False, reason=f"not_in_official_pool={bad[:10]}")
            return False
        log_event("deck_validate", id=c["id"], ok=True, mode="official_pool_ids", n=60)
        return True
    except Exception as e:
        log_event("deck_validate_error", id=c["id"], err=str(e))
        return False


def package_candidate(c: dict) -> Path | None:
    script = c["package"][0]
    if not (ROOT / script).exists():
        log_event("package_missing", id=c["id"], script=script)
        return None
    code, out = run(c["package"], timeout=300)
    log_event("package", id=c["id"], rc=code, tail=out[-500:])
    tb = ROOT / c["tarball"]
    if not tb.exists():
        cand_dir = ROOT / "dist" / "candidates"
        if cand_dir.exists():
            hits = sorted(cand_dir.glob(f"*{c['id']}*.tar.gz"), key=lambda p: p.stat().st_mtime)
            if hits:
                tb = hits[-1]
    if code == 0 and tb.exists():
        return tb
    cand_dir = ROOT / "dist" / "candidates"
    if cand_dir.exists() and code == 0:
        hits = sorted(cand_dir.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime)
        if hits:
            return hits[-1]
    return None


def should_submit_today(n_already: int, is_clear_upgrade: bool) -> bool:
    """Hard cap 5; soft prefer ≤ soft_quality_slots unless clear upgrade."""
    if n_already >= RULES["max_submits_per_day"]:
        return False
    soft = int(RULES["soft_quality_slots_per_day"])
    if n_already >= soft and not is_clear_upgrade:
        log_event(
            "submit_soft_cap",
            n=n_already,
            soft=soft,
            note="reserve slots; only clear upgrades may use remaining of 5",
        )
        return False
    return True


def load_best_gate() -> dict:
    if BEST_GATE_PATH.exists():
        try:
            return json.loads(BEST_GATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_best_gate(r: dict) -> None:
    BEST_GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": r.get("id"),
        "wr": r.get("wr"),
        "ts": datetime.now().isoformat(timespec="seconds"),
        "speed_class": r.get("speed_class"),
    }
    BEST_GATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def try_submit_strongest(results: list[dict]) -> dict:
    """Submit only ship-quality primary-capable builds (latest-2 board aware).

    Quality bar (2026-07-30 LB intel): WR ≥ ship_min_wr_pct, deep games,
    clearly better than last local best; soft ≤2 ships/day after UTC reset.
    """
    n = submits_today()
    status = {"last_submit": "—", "submitted": 0}
    if n >= RULES["max_submits_per_day"]:
        log_event("submit_skipped_cap", n=n)
        status["last_submit"] = f"daily_cap {n}/{RULES['max_submits_per_day']}"
        return status

    ship_bar = float(CONFIG.get("ship_min_wr_pct") or 64.0)
    # Prefer ship_ok primary; fall back to any ship_ok
    shippable = [r for r in results if r.get("ship_ok") and r.get("legal") and r.get("finished")]
    if not shippable:
        # Log best scout for iteration even when not ship-ready
        scouts = [r for r in results if r.get("ok")]
        if scouts:
            log_event(
                "submit_hold_quality",
                best_id=scouts[0].get("id"),
                wr=scouts[0].get("wr"),
                ship_bar=ship_bar,
                note="scout pass but below ship quality bar — keep iterating",
            )
            status["last_submit"] = (
                f"hold_quality best={scouts[0].get('id')} wr={scouts[0].get('wr')} "
                f"need_ship>={ship_bar}"
            )
            save_best_gate(scouts[0])
        else:
            status["last_submit"] = "no gate-pass candidate"
        return status

    prev = load_best_gate()
    prev_wr = float(prev.get("wr") or 0.0)
    top = shippable[0]
    top_wr = float(top["wr"] or 0.0)
    delta = float(RULES.get("min_upgrade_wr_delta") or 3.0)
    is_upgrade = top_wr >= prev_wr + delta or (prev.get("id") != top["id"] and top_wr >= ship_bar)

    if not should_submit_today(n, is_clear_upgrade=is_upgrade or n == 0):
        status["last_submit"] = f"soft_cap hold best={top['id']} wr={top_wr}"
        save_best_gate(top)
        return status

    # Prefer Archaludon primary among shippable
    primary_id = str(CONFIG.get("primary_focus") or "archaludon")
    blocked = set(RULES.get("block_submit_ids") or ())
    # First ship of UTC day: Archaludon ONLY (Round0 policy lock).
    if n == 0:
        shippable = [r for r in shippable if r.get("id") == primary_id]
        if not shippable:
            log_event(
                "submit_hold_first_must_be_primary",
                primary=primary_id,
                note="UTC day first quality slot reserved for Archaludon only",
            )
            status["last_submit"] = f"hold_first_ship_primary_only={primary_id}"
            return status
    else:
        # After first ship: never submit blocked ids (Dragapult etc.)
        shippable = [r for r in shippable if r.get("id") not in blocked]
        if not shippable:
            status["last_submit"] = "no non-blocked shippable after first"
            return status

    ordered = sorted(
        shippable,
        key=lambda r: (1 if r.get("id") == primary_id else 0, r.get("wr") or -1),
        reverse=True,
    )

    for best in ordered:
        c = best["candidate"]
        cur_wr = float(best["wr"] or 0.0)
        if c.get("id") in blocked:
            log_event("submit_skip_blocked", id=c["id"])
            continue
        if cur_wr < ship_bar:
            log_event("submit_skip_ship_bar", id=c["id"], wr=cur_wr, bar=ship_bar)
            continue
        # Director multi-floor: Iono≥55 / Crustle≥89 / Arch≥83 — every ship slot.
        # Parse gate tail lines like: real_iono ... 52.5%
        if c.get("id") == primary_id and CONFIG.get("director_gate_enabled", True):
            iono_floor = float(CONFIG.get("ship_iono_min_wr_pct") or 55.0)
            crustle_floor = float(CONFIG.get("ship_crustle_min_wr_pct") or 89.0)
            tail = str(best.get("tail") or "")
            iono_wr = None
            m_iono = re.search(
                r"real_iono\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%",
                tail,
            )
            if m_iono:
                iono_wr = float(m_iono.group(1))
            crustle_wrs = [
                float(x)
                for x in re.findall(
                    r"meta_crustle_(?:flg|majkel)\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%",
                    tail,
                )
            ]
            crustle_min = min(crustle_wrs) if crustle_wrs else None
            if iono_wr is None or iono_wr < iono_floor:
                log_event(
                    "submit_hold_iono_floor",
                    wr=cur_wr,
                    iono_wr=iono_wr,
                    iono_floor=iono_floor,
                    note="director: need stable Iono before any quality ship",
                )
                status["last_submit"] = (
                    f"hold_iono iono={iono_wr} need>={iono_floor} overall={cur_wr}"
                )
                save_best_gate(best)
                continue
            if crustle_min is None or crustle_min < crustle_floor:
                log_event(
                    "submit_hold_crustle_floor",
                    wr=cur_wr,
                    crustle_min=crustle_min,
                    crustle_floor=crustle_floor,
                    note="director: Crustle min flg/majkel must clear 89%",
                )
                status["last_submit"] = (
                    f"hold_crustle min={crustle_min} need>={crustle_floor} overall={cur_wr}"
                )
                save_best_gate(best)
                continue
        if RULES["official_card_pool_only"] and not validate_official_deck(c):
            log_event("submit_skip_deck", id=c["id"])
            continue
        path = package_candidate(c)
        if path is None:
            log_event("submit_skip_package", id=c["id"])
            continue

        msg = (
            f"{c['change']} | local_wr={cur_wr:.1f} | speed={c.get('speed_class')} | "
            f"board_keep_latest_{RULES['active_on_board']}"
        )
        code, out = run(
            [
                "scripts/auto_submit.py",
                "--file",
                str(path),
                "--message",
                msg,
                "--local-gate",
                str(cur_wr),
                "--strength-note",
                f"STRONGEST {c['id']} WR={cur_wr} legal+finish speed={c.get('speed_class')}",
            ],
            timeout=300,
        )
        log_event("submit_strongest", id=c["id"], rc=code, wr=cur_wr, tail=out[-500:])
        status["last_submit"] = f"{c['id']} rc={code} wr={cur_wr}"
        if code == 0:
            status["submitted"] = 1
            save_best_gate(best)
        return status

    status["last_submit"] = "all winners failed deck/package"
    return status


def write_leaderboard_intel() -> None:
    """Persist top-tier snapshot for meta focus (user + API intel)."""
    meta_dir = ROOT / "report" / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    path = meta_dir / "leaderboard_top_20260730.json"
    payload = {
        "as_of": "2026-07-30",
        "source": "user_browser_snap",
        "top": LEADERBOARD_TOP,
        "our_live": {"archaludon": CONFIG.get("board_mu_target"), "note": "publicScore ~793.7"},
        "our_pin": CONFIG.get("ladder_pin_mu"),
        "goal": "re-hit pin 1196.1 and enter 1190+ first tier",
        "strategy": "Archaludon primary; quality ships only; deep local gates",
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md = meta_dir / "leaderboard_top_20260730.md"
    lines = [
        "# Leaderboard top (2026-07-30)",
        "",
        "| Rank | Team | Score |",
        "|-----:|------|------:|",
    ]
    for row in LEADERBOARD_TOP:
        lines.append(f"| {row['rank']} | {row['team']} | {row['score']} |")
    lines += [
        "",
        f"- Our live Archaludon ≈ **{CONFIG.get('board_mu_target')}**",
        f"- Historical pin ≈ **{CONFIG.get('ladder_pin_mu')}** (near current #1)",
        f"- Ship bar local WR ≥ **{CONFIG.get('ship_min_wr_pct')}%** (deep n)",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    log_event("leaderboard_intel_written", path=str(path))


def refresh_episodes_if_due() -> None:
    """Public episode pull + mine; prioritize high-rank meta signals."""
    if not ensure_token():
        write_leaderboard_intel()
        return
    today = date.today().isoformat()
    # Always refresh intel file (cheap)
    try:
        write_leaderboard_intel()
    except Exception as e:
        log_event("leaderboard_intel_fail", err=str(e))
    if EPISODE_MARKER.exists():
        try:
            last = EPISODE_MARKER.read_text(encoding="utf-8").strip()
            if last == today:
                return
        except OSError:
            pass
    log_event("episode_refresh_start", day=today, focus="top10_meta_archaludon_rl")
    # High-value: top-10 LB decks + gauntlet (does not block on multi-GB daily packs)
    if (ROOT / "scripts" / "episode_rl_pipeline.py").exists():
        code, out = run(
            [
                "scripts/episode_rl_pipeline.py",
                "--top-only",
                "--top",
                "10",
                "--episodes-per-team",
                "4",
            ],
            timeout=2400,
        )
        log_event("episode_rl_pipeline_top", rc=code, tail=out[-800:])
    if (ROOT / "scripts" / "track_ladder.py").exists():
        code, out = run(["scripts/track_ladder.py"], timeout=180)
        log_event("track_ladder", rc=code, tail=out[-400:])
    # Skip heavy update_from_kaggle (broken shell heredoc) — bulk days via episode_rl_pipeline
    if (ROOT / "scripts" / "episode_rl_pipeline.py").exists():
        # Fire-and-forget bulk day download so gate loop is not blocked for hours
        try:
            log_path = ROOT / "recordings" / "logs" / "bulk_episode_bg.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as lo:
                lo.write(f"\n--- bulk {datetime.now().isoformat(timespec='seconds')} ---\n")
                lo.flush()
                subprocess.Popen(
                    [
                        str(PY),
                        "-u",
                        "scripts/episode_rl_pipeline.py",
                        "--bulk-only",
                        "--days",
                        "2",
                        "--keep-days",
                        "3",
                    ],
                    cwd=str(ROOT),
                    stdout=lo,
                    stderr=lo,
                    env=os.environ.copy(),
                )
            log_event("episode_bulk_bg_started", log=str(log_path))
        except Exception as e:
            log_event("episode_bulk_bg_fail", err=str(e))
    if (ROOT / "scripts" / "analyze_meta_by_mu_band.py").exists():
        code, out = run(["scripts/analyze_meta_by_mu_band.py"], timeout=300)
        log_event("meta_by_mu_band", rc=code, tail=out[-500:])
    if (ROOT / "scripts" / "mine_episode_decks.py").exists():
        ep_dirs = [
            ROOT / "data" / "kaggle_ref" / "episodes",
            ROOT / "data" / "episodes" / "raw",
            ROOT / "report" / "submission_replays",
            ROOT / "report" / "deck_logs",
        ]
        for ep in ep_dirs:
            if ep.exists() and any(ep.rglob("*.json")):
                code, out = run(
                    [
                        "scripts/mine_episode_decks.py",
                        "--episodes",
                        str(ep),
                        "--out-dir",
                        "agent_decks",
                        "--report",
                        "report/real_decks_mined.md",
                        "--leaders",
                    ],
                    timeout=600,
                )
                log_event("episode_mine_decks", path=str(ep), rc=code, tail=out[-500:])
                break
    if (ROOT / "scripts" / "summarize_archaludon_episodes.py").exists():
        code, out = run(["scripts/summarize_archaludon_episodes.py"], timeout=300)
        log_event("archaludon_episode_summary", rc=code, tail=out[-500:])
    if (ROOT / "scripts" / "mine_episode_replays.py").exists():
        code, out = run(["scripts/mine_episode_replays.py"], timeout=300)
        log_event("episode_mine_replays", rc=code, tail=out[-400:])
    # Auto data clean after episode pull/mine (low-quality → recordings/low_quality)
    if (ROOT / "scripts" / "clean_low_quality_data.py").exists():
        code, out = run(
            [
                "scripts/clean_low_quality_data.py",
                "--execute",
                "--min-rating",
                "900",
                "--min-steps",
                "30",
                "--min-turns",
                "3",
                "--max-age-days",
                "60",
                "--update-state",
            ],
            timeout=600,
        )
        log_event("episode_data_clean", rc=code, tail=out[-800:])
    EPISODE_MARKER.parent.mkdir(parents=True, exist_ok=True)
    EPISODE_MARKER.write_text(today, encoding="utf-8")
    log_event("episode_refresh_done", day=today)


def local_selfplay_burst() -> None:
    """Maximize local self-play when engine ready and daily submit slots not urgent.

    MCTS train is fire-and-forget (background) so a long train cannot kill the
    never-stop gate/self-play loop.
    """
    if not engine_ready():
        return
    if not (ROOT / "scripts" / "selfplay.py").exists():
        return
    n = int(CONFIG["selfplay_games_when_idle"])
    log_event("selfplay_burst_start", games=n)
    code, out = run(["scripts/selfplay.py", str(n)], timeout=3600)
    log_event("selfplay_burst_done", rc=code, tail=out[-600:])
    # Archaludon #1 chase lock: never spend cycles on Lucario field MCTS.
    # Flag lives on RULES (strategy lock); also honor CONFIG override if set.
    if RULES.get("skip_mcts_train") or CONFIG.get("skip_mcts_train"):
        log_event(
            "mcts_train_skip",
            reason="strategy_lock_archaludon_primary",
            note="all compute → Archaludon gates + selfplay",
        )
        return
    # Optional Lucario field MCTS if torch+CUDA available — non-blocking.
    try:
        import torch

        if not torch.cuda.is_available():
            log_event(
                "mcts_train_skip",
                reason="torch_cpu_only",
                version=getattr(torch, "__version__", "?"),
                note="install cu124 wheel for field MCTS; self-play+gates still run",
            )
            return
        train = ROOT / "scripts" / "train_lucario_field_mcts.py"
        if not train.exists():
            return
        try:
            import subprocess as _sp

            chk = _sp.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                 "Where-Object { $_.CommandLine -like '*train_lucario_field_mcts*' }).Count"],
                capture_output=True, text=True, timeout=15,
            )
            if chk.returncode == 0 and int((chk.stdout or "0").strip() or "0") > 0:
                log_event("mcts_train_skip", reason="already_running")
                return
        except Exception:
            pass
        env = os.environ.copy()
        # Deeper CUDA search (user sprint) — keep lighter than max so Arch gates stay responsive
        env["LUC_SELFPLAY_GAMES"] = str(max(24, n // 2))
        env["LUC_SEARCH_COUNT"] = "40"
        env["LUC_DEVICE"] = "cuda"
        env.setdefault("PYTHONUTF8", "1")
        log_path = ROOT / "dist" / "mcts_train.out.log"
        err_path = ROOT / "dist" / "mcts_train.err.log"
        log_event(
            "mcts_train_bg_start",
            LUC_SELFPLAY_GAMES=env["LUC_SELFPLAY_GAMES"],
            LUC_SEARCH_COUNT=env["LUC_SEARCH_COUNT"],
            device="cuda",
            log=str(log_path),
        )
        with log_path.open("a", encoding="utf-8") as lo, err_path.open("a", encoding="utf-8") as le:
            lo.write(f"\n--- {datetime.now().isoformat(timespec='seconds')} CUDA MCTS ---\n")
            lo.flush()
            subprocess.Popen(
                [
                    str(PY),
                    "-u",
                    str(train),
                    "--device",
                    "cuda",
                    "--cycles",
                    "4",
                    "--search-count",
                    "40",
                    "--selfplay-games",
                    env["LUC_SELFPLAY_GAMES"],
                    "--games-per-opponent",
                    "8",
                    "--time-budget-sec",
                    "7200",
                    "--auto-resume",
                ],
                cwd=str(ROOT),
                stdout=lo,
                stderr=le,
                env=env,
            )
    except ImportError:
        log_event("mcts_train_skip", reason="torch not installed")


def refresh_state(status: dict) -> None:
    """Rewrite live status; keep Auto-submit log only (no Loop design bloat)."""
    now = datetime.now().isoformat(timespec="seconds")
    header = f"""# STATE — PTCG AI Battle Aggressive Ladder Climb

> **Mode:** NEVER-STOP aggressive parallel loop (rules-locked 2026-07-30)  
> **Workspace:** `{ROOT}`  
> **Goal:** Simulation ladder as high as possible; prep Strategy top-8  
> **Auto-approve:** ALL train / eval / package / file / Kaggle API  
> **Auto-submit:** strongest only · legal+finish · WR≥{CONFIG['min_wr_pct']}% · max {RULES['max_submits_per_day']}/day · board keeps latest {RULES['active_on_board']}  
> **Clock:** {RULES['battle_time_limit_sec']}s/player → prefer `speed_class=fast` brains  

---

## Live status ({now})

| Item | Status |
|------|--------|
| Loop | **RUNNING** |
| Token | {status.get('token')} |
| Engine cg/ | {status.get('engine')} |
| Card pool | {status.get('card_pool')} |
| Offline smoke | {status.get('smoke')} |
| Today submits | {status.get('submits_today')} / {RULES['max_submits_per_day']} (soft quality ≤{RULES['soft_quality_slots_per_day']}) |
| Last gate | {status.get('last_gate')} |
| Last submit | {status.get('last_submit')} |
| Best local | {status.get('best_local')} |
| Cycle | {status.get('cycle')} |
| Blocker | {status.get('blocker') or 'none'} |

### Competition rules (active)
1. Max **{RULES['max_submits_per_day']}** submits/day; only **latest {RULES['active_on_board']}** stay on board → submit strongest, not spray.
2. **10 min** battle clock → inference speed first; heavy MCTS trains locally, ships only if time-safe.
3. **Official card pool only** (`validate_deck` + EN_Card_Data).
4. Almost **no competition training compute** → local self-play + MCTS on this machine.
5. Pre-submit gate: **no illegal** + **games finish** + **WR >> random** (≥{CONFIG['min_wr_pct']}%).
6. **Parallel local** gates/train; submit path is serial + capped.
7. **Daily episodes** refresh for deck/meta adjustment.

### Auto rules
1. Never ask for confirmation on train/eval/package/Kaggle API.
2. Parallel gates → rank by WR → package **one** strongest → `auto_submit.py` (retry once).
3. Daily hard cap {RULES['max_submits_per_day']}; soft quality slots {RULES['soft_quality_slots_per_day']} unless clear upgrade.
4. API fail ×2 → package stays in `dist/candidates/`; STATE logs MANUAL.
5. Loop never exits except SIGINT / --once.

## Loop design

```
while True:
  ensure_token
  fetch_engine + official card pool
  daily episode refresh (once/day)
  offline_smoke
  PARALLEL gates [Archaludon, Dragapult, Alakazam, ...]
  rank by WR (prefer fast brains)
  if strongest passes legal+finish+WR:
    validate official deck → package → auto_submit (≤5/day, soft ≤2)
  if idle / slots full: local self-play + optional MCTS train
  update STATE.md
  sleep (adaptive)
```

"""
    old = STATE_PATH.read_text(encoding="utf-8") if STATE_PATH.exists() else ""
    keep = ""
    marker = "## Auto-submit log"
    idx = old.find(marker)
    if idx != -1:
        # Keep only the Auto-submit log section; drop duplicated Loop design tails
        keep = "\n\n" + old[idx:]
        # Truncate runaway duplicate content inside keep
        if keep.count("## Loop design") > 0:
            keep = "\n\n" + marker + "\n\n_(see live status above; historical submit blocks retained below if present)_\n"
            # re-extract only auto-submit blocks
            blocks = re.findall(r"(### Auto-submit[\s\S]*?)(?=\n### Auto-submit|\n## |\Z)", old)
            if blocks:
                keep = "\n\n" + marker + "\n" + "\n".join(blocks[-20:]) + "\n"
    else:
        keep = f"\n\n{marker}\n\n_(empty — waiting for first gate-pass submit)_\n"

    STATE_PATH.write_text(header + keep, encoding="utf-8")

    # Mirror live block into workspace-root STATE.md
    try:
        live_block = f"""## 2. Live status（loop sync {now}）

| Item | Status |
|------|--------|
| Workspace | `{ROOT.parent}` |
| Code | `{ROOT}` |
| Loop | **RUNNING** |
| Token | {status.get('token')} |
| Engine cg/ | {status.get('engine')} |
| Card pool | {status.get('card_pool')} |
| Offline smoke | {status.get('smoke')} |
| Today submits | {status.get('submits_today')} / {RULES['max_submits_per_day']} (soft ≤{RULES['soft_quality_slots_per_day']}) |
| Last gate | {status.get('last_gate')} |
| Last submit | {status.get('last_submit')} |
| Best local | {status.get('best_local')} |
| Focus | {status.get('focus') or CONFIG.get('primary_focus')} |
| Primary | **{CONFIG.get('primary_focus')}** → beat {CONFIG.get('board_mu_target')} / pin {CONFIG.get('ladder_pin_mu')} |
| Cycle | {status.get('cycle')} |
| Blocker | {status.get('blocker') or 'none'} |

**Rules lock:** ≤5/day · board latest {RULES['active_on_board']} · Archaludon PRIMARY · Dragapult demoted · 10-min · official pool · soft ≤2 after UTC reset

"""
        if ROOT_STATE_PATH.exists():
            root_old = ROOT_STATE_PATH.read_text(encoding="utf-8")
            if "## 2. Live status" in root_old:
                root_new = re.sub(
                    r"## 2\. Live status.*?(?=\n## [0-9]+\.|\Z)",
                    lambda _m: live_block,
                    root_old,
                    count=1,
                    flags=re.S,
                )
            else:
                root_new = root_old.rstrip() + "\n\n" + live_block
            ROOT_STATE_PATH.write_text(root_new, encoding="utf-8")
        else:
            ROOT_STATE_PATH.write_text(header + keep, encoding="utf-8")
    except Exception as e:
        log_event("root_state_sync_fail", err=str(e))


def cycle_once(cycle: int) -> dict:
    status = {
        "cycle": cycle,
        "token": "OK" if ensure_token() else "MISSING",
        "engine": "OK" if engine_ready() else "MISSING",
        "card_pool": "OK" if (ROOT / "data" / "EN_Card_Data.csv").exists() else "MISSING",
        "smoke": "?",
        "submits_today": submits_today(),
        "last_gate": "—",
        "last_submit": "—",
        "best_local": "—",
        "blocker": None,
    }

    if not ensure_token():
        status["blocker"] = "Kaggle API token missing — place .kaggle/access_token or KAGGLE_API_TOKEN"
        status["smoke"] = "OK" if offline_smoke() else "FAIL"
        refresh_state(status)
        return status

    if not engine_ready():
        if not fetch_engine():
            status["blocker"] = "engine fetch failed (token? rules accepted? corrupt zip cleared & retry)"
            status["engine"] = "MISSING"
            status["smoke"] = "OK" if offline_smoke() else "FAIL"
            refresh_state(status)
            return status
        status["engine"] = "OK"

    # Official card pool (non-blocking for gates if already have decks)
    if status["card_pool"] != "OK":
        if fetch_card_pool():
            status["card_pool"] = "OK"
        else:
            status["card_pool"] = "MISSING (soft)"

    # Daily episodes (meta / decks)
    try:
        refresh_episodes_if_due()
    except Exception as e:
        log_event("episode_refresh_error", err=str(e))

    status["smoke"] = "OK" if offline_smoke() else "FAIL"
    if status["smoke"] != "OK":
        status["blocker"] = "offline smoke failed"
        refresh_state(status)
        return status

    if (ROOT / "scripts" / "smoke_cg_engine.py").exists():
        code, out = run(["scripts/smoke_cg_engine.py"], timeout=120)
        log_event("cg_smoke", rc=code, tail=out[-300:])

    # --- Parallel local gates (Archaludon primary; Dragapult sparse) ---
    focus = candidates_for_cycle(cycle)
    status["focus"] = ",".join(c["id"] for c in focus)
    log_event("cycle_focus", cycle=cycle, ids=[c["id"] for c in focus], primary=CONFIG["primary_focus"])
    results = parallel_gates(focus)

    # Deepen PRIMARY toward ship bar (cut variance before any quality ship)
    bar = float(CONFIG["min_wr_pct"])
    ship_bar = float(CONFIG.get("ship_min_wr_pct") or 64.0)
    primary_id = str(CONFIG.get("primary_focus") or "archaludon")
    deepen_target = None
    for r in results:
        if r.get("id") == primary_id and r.get("wr") is not None:
            wr = float(r["wr"])
            # Near scout bar, or scout-ok but below ship quality, or ship-ok thin margin
            if (not r.get("ok")) and (bar - 8.0) <= wr < bar:
                deepen_target = r
                break
            if r.get("ok") and wr < ship_bar:
                deepen_target = r
                break
            if r.get("ship_ok") and wr < ship_bar + 3.0:
                deepen_target = r
                break
    if deepen_target is None and results and results[0].get("wr") is not None:
        top_wr = float(results[0]["wr"])
        if (not results[0].get("ok")) and (bar - 6.0) <= top_wr < bar:
            deepen_target = results[0]
    if deepen_target is not None:
        deep_games = int(CONFIG.get("gate_deepen_primary") or 48)
        if deepen_target.get("id") != primary_id:
            deep_games = max(int(CONFIG["gate_games"]) * 2, 32)
        log_event(
            "gate_deepen",
            id=deepen_target["id"],
            from_wr=deepen_target.get("wr"),
            games=deep_games,
            primary=deepen_target.get("id") == primary_id,
            ship_bar=ship_bar,
        )
        c = deepen_target["candidate"]
        deep_c = dict(c)
        g = list(c["gate"])
        if len(g) >= 3 and g[1] == "--games":
            g[2] = str(deep_games)
        deep_c["gate"] = g
        deep = gate_candidate(deep_c)
        results = [deep if r["id"] == deep["id"] else r for r in results]
        results = rank_gate_results(results)

    if results:
        top = results[0]
        status["last_gate"] = (
            f"{top['id']} wr={top['wr']} ok={top['ok']} legal={top.get('legal')} fin={top.get('finished')}"
        )
        status["best_local"] = ", ".join(
            f"{r['id']}={r['wr']}" for r in results[:3] if r.get("wr") is not None
        )
        # Prefer saving primary best when it passes
        primary_pass = next(
            (r for r in results if r.get("id") == primary_id and r.get("ok")), None
        )
        if primary_pass:
            save_best_gate(primary_pass)
        elif top.get("ok"):
            save_best_gate(top)

    # --- Submit strongest only ---
    try:
        sub = try_submit_strongest(results)
        status["last_submit"] = sub.get("last_submit", "—")
    except Exception as e:
        log_event("submit_error", err=str(e), tb=traceback.format_exc()[-500:])
        status["last_submit"] = f"error: {e}"

    status["submits_today"] = submits_today()

    # --- Local self-play / MCTS when engine ready ---
    # Run burst when: no submit this cycle OR daily soft/hard cap reached
    try:
        if engine_ready() and (
            status["submits_today"] >= RULES["soft_quality_slots_per_day"]
            or not any(r.get("ok") for r in results)
            or cycle % 3 == 0
        ):
            local_selfplay_burst()
    except Exception as e:
        log_event("selfplay_error", err=str(e))

    status["blocker"] = None
    refresh_state(status)
    log_event("cycle_done", cycle=cycle, status={k: status[k] for k in status if k != "blocker" or status[k]})
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll-seconds", type=int, default=30)
    ap.add_argument("--min-wr", type=float, default=CONFIG["min_wr_pct"])
    ap.add_argument("--gate-games", type=int, default=CONFIG["gate_games"])
    ap.add_argument("--workers", type=int, default=CONFIG["gate_parallel_workers"])
    args = ap.parse_args()

    CONFIG["min_wr_pct"] = float(args.min_wr)
    CONFIG["gate_games"] = int(args.gate_games)
    CONFIG["gate_parallel_workers"] = int(args.workers)
    # Rebuild candidate gate argv with updated games (primary gets deeper default)
    for c in CANDIDATES:
        if len(c["gate"]) >= 3 and c["gate"][1] == "--games":
            if c.get("primary"):
                c["gate"][2] = str(CONFIG.get("gate_games_primary") or CONFIG["gate_games"])
            else:
                c["gate"][2] = str(CONFIG["gate_games"])

    if not acquire_single_instance_lock():
        log_event("loop_refused_lock", lock=str(LOCK_PATH))
        return 4
    try:
        log_event(
            "loop_start",
            once=args.once,
            min_wr=CONFIG["min_wr_pct"],
            gate_games=CONFIG["gate_games"],
            workers=CONFIG["gate_parallel_workers"],
            rules=RULES,
            py=str(PY),
            pid=os.getpid(),
        )
        cycle = 0
        while True:
            cycle += 1
            try:
                status = cycle_once(cycle)
            except Exception:
                log_event("cycle_crash", cycle=cycle, tb=traceback.format_exc()[-1500:])
                status = {"blocker": "cycle crash — see loop_log"}
            if args.once:
                return (
                    0
                    if not status.get("blocker")
                    or "token" in str(status.get("blocker", "")).lower()
                    else 1
                )
            sleep_s = args.poll_seconds
            blocker = str(status.get("blocker") or "")
            if "token" in blocker.lower():
                sleep_s = min(args.poll_seconds, 30)
            elif status.get("engine") == "MISSING":
                sleep_s = min(max(args.poll_seconds, 60), 120)
            elif submits_today() >= RULES["max_submits_per_day"]:
                sleep_s = max(args.poll_seconds, 300)  # cap hit — train/self-play focus
            time.sleep(sleep_s)
    finally:
        release_single_instance_lock()


if __name__ == "__main__":
    raise SystemExit(main())
