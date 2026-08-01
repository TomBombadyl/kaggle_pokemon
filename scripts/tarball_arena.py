"""Play real engine games between PACKAGED SUBMISSION TARBALLS.

The existing `eval/harness.py` scores repo modules. That is not what gets
uploaded. This runs the exact artifact: extract `dist/candidates/<name>.tar.gz`,
import its `main.py`, and play games through `cg.game`.

What it measures (the things that actually tracked ladder mu):
  * hard errors      - any exception escaping the agent
  * illegal picks    - selection outside the option mask
  * unfinished       - games that ran past max-steps (clock risk)
  * win rate         - head-to-head, with a Wilson interval

Usage
-----
    python scripts/tarball_arena.py --a arch_v5_r7 --b arch_75wr_r7 --games 200
    python scripts/tarball_arena.py --a arch_v5_r7 --gauntlet --games 60
    python scripts/tarball_arena.py --a arch_v5_r7 --b official_dragapult --games 100 \
        --workers 26 --json out.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import sys
import tarfile
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT, "data", "sim", "sample_submission")
CAND_DIR = os.path.join(ROOT, "dist", "candidates")
EXTRACT_ROOT = os.path.join(ROOT, "dist", "arena_unpack")
MAX_STEPS = 8000

# Opponents available as already-extracted public agent dirs.
GAUNTLET = [
    "extracted_agents/official_lucario/from_submission_tar",
    "extracted_agents/official_dragapult/from_submission_tar",
    "extracted_agents/official_iono/from_submission_tar",
    "extracted_agents/official_abomasnow/from_submission_tar",
    "extracted_agents/meta_router_844/from_submission_tar",
    "extracted_agents/alakazam_search_v12/from_submission_tar",
    "extracted_agents/dragapult_ucb1/from_submission_tar",
    "extracted_agents/advanced_heuristic/from_submission_tar",
]


def unpack(name: str) -> str:
    """Return a directory holding main.py + deck.csv for `name`.

    Accepts a candidate name, a path to a tarball, or a path to a directory
    that already contains main.py.
    """
    if os.path.isdir(name):
        return os.path.abspath(name)
    cand = os.path.join(ROOT, name)
    if os.path.isdir(cand):
        return cand
    tar_path = name if name.endswith(".tar.gz") else os.path.join(CAND_DIR, name + ".tar.gz")
    if not os.path.isabs(tar_path):
        tar_path = os.path.join(ROOT, tar_path)
    if not os.path.exists(tar_path):
        raise FileNotFoundError(tar_path)
    dest = os.path.join(EXTRACT_ROOT, os.path.basename(tar_path).replace(".tar.gz", ""))
    stamp = os.path.join(dest, ".stamp")
    mtime = str(os.path.getmtime(tar_path))
    if os.path.exists(stamp) and open(stamp).read() == mtime:
        return dest
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(tar_path) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)
    with open(stamp, "w") as f:
        f.write(mtime)
    return dest


def read_deck(agent_dir: str) -> list[int]:
    path = os.path.join(agent_dir, "deck.csv")
    with open(path, encoding="utf-8") as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


# --------------------------------------------------------------------------
# worker-side state (one process per worker, brains loaded once and reused)
# --------------------------------------------------------------------------
_BRAINS: dict[str, object] = {}


def _load_brain(agent_dir: str, tag: str):
    """Import `<agent_dir>/main.py` under a unique module name.

    Unique naming matters: these brains keep module-level mutable state
    (`_cur_turn_logs`, `_opp_last_attack_id`). Two seats sharing one module
    object would corrupt each other's tracking.
    """
    key = f"{tag}:{agent_dir}"
    if key in _BRAINS:
        return _BRAINS[key]
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)
    mod_name = f"_arena_{tag}_{abs(hash(agent_dir)) % 10**8}"
    spec = importlib.util.spec_from_file_location(
        mod_name, os.path.join(agent_dir, "main.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    old_cwd = os.getcwd()
    try:
        os.chdir(agent_dir)  # brains resolve deck.csv relative to cwd on import
        spec.loader.exec_module(mod)
    finally:
        os.chdir(old_cwd)
    _BRAINS[key] = mod.agent
    return mod.agent


def _wrap(brain, stats: dict, seat: str):
    """Count errors/illegal picks without letting either abort the game."""
    def call(obs):
        sel = obs.get("select")
        try:
            out = brain(obs)
        except Exception as exc:
            stats[f"{seat}_errors"] += 1
            stats.setdefault(f"{seat}_error_kinds", {})
            k = type(exc).__name__
            stats[f"{seat}_error_kinds"][k] = stats[f"{seat}_error_kinds"].get(k, 0) + 1
            out = None
        if sel is None:
            return out if isinstance(out, list) else []
        n = len(sel.get("option") or [])
        lo, hi = sel.get("minCount", 0) or 0, sel.get("maxCount", 0) or 0
        ok = (
            isinstance(out, list)
            and all(isinstance(i, int) and 0 <= i < n for i in out)
            and len(set(out)) == len(out)
            and lo <= len(out) <= hi
        )
        if not ok:
            stats[f"{seat}_illegal"] += 1
            return list(range(min(max(lo, 1), n)))
        return out
    return call


def _play(job: tuple) -> dict:
    dir_a, dir_b, deck_a, deck_b, seed, swap, max_steps = job
    sys.path.insert(0, ENGINE_DIR)
    from cg import game
    from cg.sim import Battle, lib

    random.seed(seed)
    stats = {
        "a_errors": 0, "b_errors": 0, "a_illegal": 0, "b_illegal": 0,
        "steps": 0,
    }
    brain_a = _wrap(_load_brain(dir_a, "a"), stats, "a")
    brain_b = _wrap(_load_brain(dir_b, "b"), stats, "b")

    # Alternate seats so first-player advantage cancels out.
    if swap:
        d0, d1, p0, p1 = deck_b, deck_a, brain_b, brain_a
    else:
        d0, d1, p0, p1 = deck_a, deck_b, brain_a, brain_b

    result = "unfinished"
    t0 = time.time()
    try:
        obs, start = game.battle_start(d0, d1)
        if obs is None:
            return {**stats, "result": "start_failed", "seed": seed,
                    "elapsed": 0.0, "swap": swap}
        policies = (p0, p1)
        for step in range(max_steps):
            stats["steps"] = step
            cur = obs["current"]
            if cur is not None and cur.get("result", -1) != -1:
                r = cur["result"]
                seat_winner = {0: "s0", 1: "s1", 2: "draw"}.get(r, "unfinished")
                if seat_winner == "draw":
                    result = "draw"
                elif seat_winner == "unfinished":
                    result = "unfinished"
                else:
                    won_seat0 = seat_winner == "s0"
                    a_won = (won_seat0 != swap)
                    result = "a" if a_won else "b"
                break
            if obs["select"] is None:
                break
            p = lib.GetBattleData(Battle.battle_ptr).selectPlayer
            obs = game.battle_select(policies[p](obs))
    except Exception as exc:
        stats["fatal"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            game.battle_finish()
        except Exception:
            pass
    return {**stats, "result": result, "seed": seed,
            "elapsed": time.time() - t0, "swap": swap}


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = wins / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p * 100, max(0.0, c - m) * 100, min(1.0, c + m) * 100


def run_pair(name_a: str, name_b: str, games: int, workers: int,
             seed0: int, max_steps: int) -> dict:
    dir_a, dir_b = unpack(name_a), unpack(name_b)
    deck_a, deck_b = read_deck(dir_a), read_deck(dir_b)
    jobs = [
        (dir_a, dir_b, deck_a, deck_b, seed0 + i, bool(i % 2), max_steps)
        for i in range(games)
    ]
    agg = {"a": 0, "b": 0, "draw": 0, "unfinished": 0, "start_failed": 0}
    tot = {"a_errors": 0, "b_errors": 0, "a_illegal": 0, "b_illegal": 0}
    kinds: dict[str, dict] = {"a": {}, "b": {}}
    fatals: list[str] = []
    elapsed: list[float] = []
    t0 = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_play, j) for j in jobs]
        for fut in as_completed(futs):
            r = fut.result()
            agg[r["result"]] = agg.get(r["result"], 0) + 1
            for k in tot:
                tot[k] += r.get(k, 0)
            for seat in ("a", "b"):
                for k, v in (r.get(f"{seat}_error_kinds") or {}).items():
                    kinds[seat][k] = kinds[seat].get(k, 0) + v
            if r.get("fatal"):
                fatals.append(r["fatal"])
            elapsed.append(r["elapsed"])
            done += 1
            if done % 20 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)} games "
                      f"({time.time() - t0:.0f}s)", flush=True)

    decided = agg["a"] + agg["b"]
    wr, lo, hi = wilson(agg["a"], decided)
    elapsed.sort()
    return {
        "a": name_a, "b": name_b, "games": games,
        "a_wins": agg["a"], "b_wins": agg["b"], "draws": agg["draw"],
        "unfinished": agg["unfinished"], "start_failed": agg["start_failed"],
        "a_wr_pct": round(wr, 2), "ci_low": round(lo, 2), "ci_high": round(hi, 2),
        **tot,
        "a_error_kinds": kinds["a"], "b_error_kinds": kinds["b"],
        "fatals": fatals[:5],
        "sec_per_game_p50": round(elapsed[len(elapsed) // 2], 2) if elapsed else 0,
        "sec_per_game_p95": round(elapsed[int(len(elapsed) * 0.95)], 2) if elapsed else 0,
        "wall_sec": round(time.time() - t0, 1),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True, help="candidate name / tarball / dir")
    ap.add_argument("--b", help="opponent (omit with --gauntlet)")
    ap.add_argument("--gauntlet", action="store_true",
                    help="play --a against every public agent in GAUNTLET")
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--workers", type=int,
                    default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--seed", type=int, default=20260731)
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS)
    ap.add_argument("--json", help="write results here")
    args = ap.parse_args(argv)

    opponents = GAUNTLET if args.gauntlet else [args.b]
    if not args.gauntlet and not args.b:
        print("need --b or --gauntlet", file=sys.stderr)
        return 2

    results = []
    for opp in opponents:
        label = os.path.basename(opp.rstrip("/")) if "/" in opp else opp
        if "/" in opp:
            label = opp.split("/")[1]
        print(f"\n=== {args.a} vs {label} ({args.games} games) ===", flush=True)
        r = run_pair(args.a, opp, args.games, args.workers, args.seed, args.max_steps)
        r["opponent_label"] = label
        results.append(r)
        print(f"  WR {r['a_wr_pct']}% [{r['ci_low']}-{r['ci_high']}] "
              f"| W{r['a_wins']} L{r['b_wins']} D{r['draws']} "
              f"unfinished={r['unfinished']} "
              f"| a_err={r['a_errors']} a_illegal={r['a_illegal']} "
              f"| p95={r['sec_per_game_p95']}s", flush=True)
        if r["fatals"]:
            print(f"  FATALS: {r['fatals']}", flush=True)

    if len(results) > 1:
        n = sum(x["a_wins"] + x["b_wins"] for x in results)
        w = sum(x["a_wins"] for x in results)
        wr, lo, hi = wilson(w, n)
        print(f"\n=== GAUNTLET OVERALL: {wr:.1f}% [{lo:.1f}-{hi:.1f}] "
              f"n={n} | errors={sum(x['a_errors'] for x in results)} "
              f"illegal={sum(x['a_illegal'] for x in results)} ===")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"wrote {args.json}")
    hard_fail = any(r["a_errors"] or r["a_illegal"] or r["fatals"] for r in results)
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
