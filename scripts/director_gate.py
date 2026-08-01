#!/usr/bin/env python3
"""Submission & Evaluation Director — single source of ship gates.

Policy (user lock 2026-07-31):
  - Iono ≥ 55%
  - Arch overall ≥ 83%
  - Crustle (min flg/majkel) ≥ 89%
  - dual overall strictly above rolling baseline (no regression ship)
  - hard CAP 5/UTC-day; never auto-ship Dra/Alak
  - local strengthen only when CAP full

Import this from aggressive_loop / auto_submit / quota_reset_ship_monitor /
continuous_focus_gates so thresholds never drift.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "recordings" / "metrics"
DIST = ROOT / "dist"
BOARD_MD = ROOT.parent / "STATUS_BOARD.md"
BOARD_JSON = METRICS / "director_board.json"
BASELINE_PATH = METRICS / "ship_baseline.json"
REGRESS_LOG = METRICS / "regression_log.jsonl"
DECISION_LOG = METRICS / "director_decisions.jsonl"

# ─── Canonical ship floors (do not lower without director + user sign-off) ───
SHIP_ARCH_OVERALL = 83.0
SHIP_IONO = 55.0
SHIP_CRUSTLE_MIN = 89.0  # min(flg, majkel)
SHIP_DUAL_FLOOR = 90.0  # absolute floor; also must beat rolling baseline
SCOUT_MIN = 60.0  # iteration signal only, never ship
BLOCKED_SUBMIT_IDS = frozenset({"dragapult_ex_sample", "alakazam", "dragapult"})
PRIMARY_ID = "archaludon"
MAX_SUBMITS_UTC_DAY = 5
ACTIVE_ON_BOARD = 2
# Ship uses pooled/EWMA over last N focus cycles (single n=40 cycle is noise).
FOCUS_POOL_N = 8
# Instant-cycle collapse vs pool median → log only (not auto code-kill).
IONO_COLLAPSE_PP = 12.0
CRUSTLE_COLLAPSE_PP = 10.0
DUAL_COLLAPSE_PP = 8.0

# ─── Arch ship authority: pooled mean, never the best_gate.json max-latch ───
# dist/best_gate.json is written by aggressive_loop / archaludon_meta_train under
# `if wr >= prev` — it is a running MAXIMUM over noisy n=40-48 gates, so it is an
# upward-biased estimator and must never carry ship authority. Measured
# 2026-07-31: latch said 85.4 (PASS) while pooled meta n=250 said 76.66 ± 0.50
# (FAIL) — an 8.7pp false PASS on the only floor that was green.
POOLED_HISTORY = ROOT.parent / "fleet" / "state" / "pooled_history.jsonl"
ARCH_POOLED_SUITE = "meta"  # meta_fast is a different, much easier suite
ARCH_POOLED_MIN_GAMES = 200
ARCH_POOLED_MAX_AGE_H = 24.0
# ─── Second false-PASS pathway: the newest pooled row can be an EXPERIMENT ARM ───
# "newest qualifying pooled meta run" fixed the max-latch bias but left a hole: the
# fleet's A/B arms land in the same pooled_history.jsonl, so a lane's env-gated B arm
# silently becomes the arch ship number. Measured 2026-07-31T03:42Z: authority was
# `arch_r4_meta_B_grimtomato` (ARCH_*_GRIMTOMATO on, explicitly NOT promoted to
# default) — benign that time (78.6 vs base 78.48) but the mechanism is unbounded: a
# B arm that clears 83 would report PASS for a lever the packaged build does not
# contain. Ship authority now requires provable default config: Shard-Gate.ps1 records
# env_effective (every ARCH_*/PTCG_* the shards actually inherited, which also catches
# levers leaked from the shell rather than passed via -Env) and is_default_config.
# Rows without that provenance are rejected -> arch floor fails closed.
# Produce a compliant row with:  Shard-Gate.ps1 -ClearLeverEnv -Suite meta ...
ARCH_POOLED_REQUIRE_DEFAULT_CONFIG = True


@dataclass
class GateSnapshot:
    ts_utc: str
    arch_overall: float | None = None
    iono: float | None = None
    crustle_flg: float | None = None
    crustle_majkel: float | None = None
    crustle_min: float | None = None
    dual_overall: float | None = None
    source: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def crustle_floor_value(self) -> float | None:
        if self.crustle_min is not None:
            return self.crustle_min
        vals = [v for v in (self.crustle_flg, self.crustle_majkel) if v is not None]
        return min(vals) if vals else None


@dataclass
class ShipVerdict:
    ship: bool
    reasons: list[str]
    thresholds: dict[str, float]
    snapshot: dict[str, Any]
    dual_baseline: float | None
    decision: str  # SHIP | HOLD | REGRESS | CAP_FULL | BLOCKED


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_day() -> str:
    return utc_now().date().isoformat()


def seconds_to_utc_dayroll() -> float:
    now = utc_now()
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    # if already past midnight calc next
    if nxt <= now:
        nxt = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return max(0.0, (nxt - now).total_seconds())


def dayroll_eta_str() -> str:
    sec = seconds_to_utc_dayroll()
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    return f"{h}h{m:02d}m (UTC midnight)"


def load_dual_baseline() -> float:
    """Rolling dual overall baseline — ship must beat this (no μ/local regression)."""
    if BASELINE_PATH.exists():
        try:
            data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
            return float(data.get("dual_overall") or SHIP_DUAL_FLOOR)
        except Exception:
            pass
    return SHIP_DUAL_FLOOR


def maybe_raise_baseline(snap: GateSnapshot) -> None:
    """Only raise baseline when all floors pass (ratchet, never lower)."""
    dual = snap.dual_overall
    if dual is None:
        return
    crust = snap.crustle_floor_value()
    if (
        snap.iono is not None
        and snap.iono >= SHIP_IONO
        and crust is not None
        and crust >= SHIP_CRUSTLE_MIN
        and snap.arch_overall is not None
        and snap.arch_overall >= SHIP_ARCH_OVERALL
        and dual >= SHIP_DUAL_FLOOR
    ):
        prev = load_dual_baseline()
        if dual > prev:
            METRICS.mkdir(parents=True, exist_ok=True)
            BASELINE_PATH.write_text(
                json.dumps(
                    {
                        "dual_overall": dual,
                        "arch_overall": snap.arch_overall,
                        "iono": snap.iono,
                        "crustle_min": crust,
                        "raised_at": utc_now().isoformat(timespec="seconds"),
                        "source": snap.source,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )


def parse_gate_text(text: str) -> dict[str, float]:
    matchups: dict[str, float] = {}
    for line in text.splitlines():
        mm = re.search(
            r"^\s*(\S+)\s+\([^)]*\)\s+([0-9]+(?:\.[0-9]+)?)\s*%",
            line,
        )
        if mm:
            matchups[mm.group(1)] = float(mm.group(2))
    m = re.search(r"OVERALL[^\n]*?([0-9]+(?:\.[0-9]+)?)\s*%", text, re.I)
    if m:
        matchups["OVERALL"] = float(m.group(1))
    return matchups


def snapshot_from_matchups(
    matchups: dict[str, float],
    *,
    source: str = "",
    dual_overall: float | None = None,
    arch_overall: float | None = None,
) -> GateSnapshot:
    iono = None
    for k, v in matchups.items():
        if "iono" in k.lower():
            iono = v
            break
    flg = matchups.get("meta_crustle_flg")
    maj = matchups.get("meta_crustle_majkel")
    crust_vals = [v for k, v in matchups.items() if "crustle" in k.lower()]
    crust_min = min(crust_vals) if crust_vals else None
    overall = arch_overall if arch_overall is not None else matchups.get("OVERALL")
    dual = dual_overall if dual_overall is not None else matchups.get("OVERALL")
    return GateSnapshot(
        ts_utc=utc_now().isoformat(timespec="seconds"),
        arch_overall=overall,
        iono=iono,
        crustle_flg=flg,
        crustle_majkel=maj,
        crustle_min=crust_min,
        dual_overall=dual,
        source=source,
        raw=dict(matchups),
    )


def snapshot_from_focus_row(row: dict[str, Any]) -> GateSnapshot:
    flg = row.get("flg_wr")
    maj = row.get("majkel_wr")
    vals = [v for v in (flg, maj) if isinstance(v, (int, float))]
    # dual_overall is the dual-panel score; Arch ship overall prefers loop best_gate
    # (filled by dashboard) — do not treat dual as Arch overall.
    return GateSnapshot(
        ts_utc=str(row.get("ts") or utc_now().isoformat(timespec="seconds")),
        arch_overall=None,
        iono=row.get("iono_wr"),
        crustle_flg=flg if isinstance(flg, (int, float)) else None,
        crustle_majkel=maj if isinstance(maj, (int, float)) else None,
        crustle_min=min(vals) if vals else None,
        dual_overall=row.get("dual_overall"),
        source="continuous_focus_gates",
        raw=dict(row),
    )


def evaluate_ship(
    snap: GateSnapshot,
    *,
    candidate_id: str = PRIMARY_ID,
    submits_today: int = 0,
    enforce_dual_baseline: bool = True,
) -> ShipVerdict:
    thresholds = {
        "arch_overall": SHIP_ARCH_OVERALL,
        "iono": SHIP_IONO,
        "crustle_min": SHIP_CRUSTLE_MIN,
        "dual_floor": SHIP_DUAL_FLOOR,
    }
    reasons: list[str] = []
    dual_base = load_dual_baseline()

    if candidate_id in BLOCKED_SUBMIT_IDS:
        return ShipVerdict(
            ship=False,
            reasons=[f"blocked_id={candidate_id}"],
            thresholds=thresholds,
            snapshot=asdict(snap),
            dual_baseline=dual_base,
            decision="BLOCKED",
        )

    arch = snap.arch_overall
    iono = snap.iono
    crust = snap.crustle_floor_value()
    dual = snap.dual_overall

    if arch is None or arch < SHIP_ARCH_OVERALL:
        reasons.append(f"arch {arch} < {SHIP_ARCH_OVERALL}")
    if iono is None or iono < SHIP_IONO:
        reasons.append(f"iono {iono} < {SHIP_IONO}")
    if crust is None or crust < SHIP_CRUSTLE_MIN:
        reasons.append(f"crustle_min {crust} < {SHIP_CRUSTLE_MIN}")
    if dual is None or dual < SHIP_DUAL_FLOOR:
        reasons.append(f"dual {dual} < floor {SHIP_DUAL_FLOOR}")
    if enforce_dual_baseline and dual is not None and dual < dual_base:
        reasons.append(f"dual {dual} < baseline {dual_base} (no regression)")
        log_regression(
            {
                "kind": "dual_below_baseline",
                "dual": dual,
                "baseline": dual_base,
                "snap": asdict(snap),
            }
        )

    floors_ok = len(reasons) == 0

    if submits_today >= MAX_SUBMITS_UTC_DAY:
        cap_reasons = [f"CAP full {submits_today}/{MAX_SUBMITS_UTC_DAY}"] + reasons
        return ShipVerdict(
            ship=False,
            reasons=cap_reasons,
            thresholds=thresholds,
            snapshot=asdict(snap),
            dual_baseline=dual_base,
            decision="CAP_FULL",
        )

    ship = floors_ok
    decision = "SHIP" if ship else "HOLD"
    if any("baseline" in r or "REGRESS" in r for r in reasons):
        decision = "REGRESS"
    return ShipVerdict(
        ship=ship,
        reasons=reasons,
        thresholds=thresholds,
        snapshot=asdict(snap),
        dual_baseline=dual_base,
        decision=decision,
    )


def log_regression(payload: dict[str, Any]) -> None:
    METRICS.mkdir(parents=True, exist_ok=True)
    row = {"ts": utc_now().isoformat(timespec="seconds"), **payload}
    with REGRESS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def log_decision(verdict: ShipVerdict, **extra: Any) -> None:
    METRICS.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": utc_now().isoformat(timespec="seconds"),
        "decision": verdict.decision,
        "ship": verdict.ship,
        "reasons": verdict.reasons,
        "thresholds": verdict.thresholds,
        "dual_baseline": verdict.dual_baseline,
        "snapshot": verdict.snapshot,
        **extra,
    }
    with DECISION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_focus_latest() -> GateSnapshot | None:
    path = METRICS / "focus_latest.json"
    if not path.exists():
        return None
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        return snapshot_from_focus_row(row)
    except Exception:
        return None


def _read_focus_history(n: int = FOCUS_POOL_N) -> list[dict[str, Any]]:
    path = METRICS / "focus_history.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for ln in lines[-max(n * 3, n) :]:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        # require at least iono + one crustle + dual for ship pool quality
        if r.get("iono_wr") is None:
            continue
        rows.append(r)
    return rows[-n:]


def _mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def load_focus_pooled(n: int = FOCUS_POOL_N) -> GateSnapshot | None:
    """Pooled gate snapshot for ship decisions (reduces n=40 noise).

    Uses mean of last N complete-ish focus cycles. Instant latest alone is
    display-only / variance signal — never sole ship authority.
    """
    rows = _read_focus_history(n)
    if not rows:
        return load_focus_latest()

    ionos = [float(r["iono_wr"]) for r in rows if isinstance(r.get("iono_wr"), (int, float))]
    flgs = [float(r["flg_wr"]) for r in rows if isinstance(r.get("flg_wr"), (int, float))]
    majs = [float(r["majkel_wr"]) for r in rows if isinstance(r.get("majkel_wr"), (int, float))]
    duals = [float(r["dual_overall"]) for r in rows if isinstance(r.get("dual_overall"), (int, float))]
    crust_mins: list[float] = []
    for r in rows:
        vals = [v for v in (r.get("flg_wr"), r.get("majkel_wr")) if isinstance(v, (int, float))]
        if vals:
            crust_mins.append(float(min(vals)))

    iono_m = _mean(ionos)
    flg_m = _mean(flgs)
    maj_m = _mean(majs)
    dual_m = _mean(duals)

    # The floor is min(true_flg_wr, true_majkel_wr) >= 89. The unbiased estimator of
    # that is min(mean_flg, mean_majkel). mean(min per cycle) is NOT: by Jensen it is
    # biased *down* by ~E|flg-majkel|/2 (measured 0.8-2.4pp on live windows). With the
    # observed per-cycle sd 3.53 at pool_n=8, a Crustle sitting exactly ON the 89.0
    # floor would be reported ~87.0 and pass only 2.7% of the time — i.e. the old
    # estimator made this gate unpassable by construction and would have blocked a
    # legitimately green ship forever. Floor constant is unchanged at 89.0.
    crust_m = min(flg_m, maj_m) if (flg_m is not None and maj_m is not None) else None
    if crust_m is None:
        crust_m = _mean(crust_mins)
    crust_cycle_min_m = _mean(crust_mins)  # kept as a variance diagnostic only

    # Detect instant collapse vs pool (log only)
    latest = rows[-1]
    try:
        if iono_m is not None and isinstance(latest.get("iono_wr"), (int, float)):
            if float(latest["iono_wr"]) < iono_m - IONO_COLLAPSE_PP:
                log_regression(
                    {
                        "kind": "iono_instant_noise",
                        "instant": float(latest["iono_wr"]),
                        "pool_mean": iono_m,
                        "pool_n": len(ionos),
                        "action": "HOLD ship; do NOT rollback r14n on single cycle",
                    }
                )
        if crust_m is not None and crust_mins:
            inst_c = None
            vals = [v for v in (latest.get("flg_wr"), latest.get("majkel_wr")) if isinstance(v, (int, float))]
            if vals:
                inst_c = float(min(vals))
            if inst_c is not None and inst_c < crust_m - CRUSTLE_COLLAPSE_PP:
                log_regression(
                    {
                        "kind": "crustle_instant_noise",
                        "instant": inst_c,
                        "pool_mean": crust_m,
                        "action": "HOLD; reconfirm next cycles",
                    }
                )
        if dual_m is not None and isinstance(latest.get("dual_overall"), (int, float)):
            if float(latest["dual_overall"]) < dual_m - DUAL_COLLAPSE_PP:
                log_regression(
                    {
                        "kind": "dual_instant_noise",
                        "instant": float(latest["dual_overall"]),
                        "pool_mean": dual_m,
                        "action": "HOLD ship; dual baseline ratchet still stands",
                    }
                )
    except Exception:
        pass

    return GateSnapshot(
        ts_utc=utc_now().isoformat(timespec="seconds"),
        arch_overall=None,  # filled by loop best_gate at evaluate time
        iono=iono_m,
        crustle_flg=flg_m,
        crustle_majkel=maj_m,
        crustle_min=crust_m,
        dual_overall=dual_m,
        source=f"focus_pool_n{len(rows)}",
        raw={
            "pool_n": len(rows),
            "iono_mean": iono_m,
            "iono_n": len(ionos),
            "flg_mean": flg_m,
            "majkel_mean": maj_m,
            "crustle_min_mean": crust_m,
            "crustle_min_estimator": "min(mean_flg, mean_majkel)",
            "crustle_mean_of_cycle_mins": crust_cycle_min_m,  # diagnostic, Jensen-biased low
            "dual_mean": dual_m,
            "instant": latest,
            "iono_series": ionos[-FOCUS_POOL_N:],
            "crustle_min_series": crust_mins[-FOCUS_POOL_N:],
            "dual_series": duals[-FOCUS_POOL_N:],
        },
    )


def load_pooled_arch_overall() -> dict[str, Any] | None:
    """Most recent qualifying pooled Arch `meta` run from the fleet shard-gate feed.

    Deliberately the MOST RECENT qualifying run, never the max — taking a max here
    would reintroduce exactly the best_gate.json bias this function exists to remove.
    Returns None when there is no fresh pooled evidence, which makes the arch floor
    fail closed in evaluate_ship (arch_overall None → no ship).
    """
    if not POOLED_HISTORY.exists():
        return None
    best: dict[str, Any] | None = None
    rejected: list[dict[str, Any]] = []
    now = utc_now()
    try:
        text = POOLED_HISTORY.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("suite") != ARCH_POOLED_SUITE:
            continue
        if r.get("role") not in ("arch", "director"):
            continue
        if not isinstance(r.get("mean"), (int, float)):
            continue
        if float(r.get("total_games_approx") or 0) < ARCH_POOLED_MIN_GAMES:
            continue
        ts = _parse_ts(r.get("ts"))
        if ts is None or (now - ts).total_seconds() / 3600.0 > ARCH_POOLED_MAX_AGE_H:
            continue
        if ARCH_POOLED_REQUIRE_DEFAULT_CONFIG and not _is_default_config_row(r):
            rejected.append(
                {
                    "label": r.get("label"),
                    "mean": float(r["mean"]),
                    "ts": r.get("ts"),
                    "why": _nondefault_reason(r),
                }
            )
            continue
        if best is None or ts >= best["_ts"]:
            best = {
                "mean": float(r["mean"]),
                "stderr": r.get("stderr"),
                "n": r.get("total_games_approx"),
                "label": r.get("label"),
                "role": r.get("role"),
                "ts": r.get("ts"),
                "config": "default",
                "_ts": ts,
            }
    if best is not None:
        best.pop("_ts", None)
        if rejected:
            best["rejected_nondefault"] = rejected[-4:]
    elif rejected:
        return {"mean": None, "rejected_nondefault": rejected[-4:]}
    return best


def _is_default_config_row(row: dict[str, Any]) -> bool:
    """True only when the row PROVES it came from the default build.

    Absence of provenance is not proof of default: every row written before
    Shard-Gate.ps1 started recording env_effective is rejected on purpose, so the
    arch floor fails closed instead of trusting an unknown configuration.
    """
    eff = row.get("env_effective")
    if isinstance(eff, dict):
        return not _lever_env(eff)
    return row.get("is_default_config") is True


# Infra vars, not agent config (Launch-Fleet exports PTCG_ROOT into every lane shell).
# Kept in sync with $FLEET_BENIGN_ENV in fleet\Shard-Gate.ps1; tolerated here too so
# rows written by an older Shard-Gate are still judged on levers only.
BENIGN_ENV_KEYS = frozenset({"PTCG_SHARD", "PTCG_ROOT", "PTCG_QUIET"})


def _lever_env(eff: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in eff.items() if k not in BENIGN_ENV_KEYS and str(v) != ""}


def _nondefault_reason(row: dict[str, Any]) -> str:
    if "env_effective" not in row and "is_default_config" not in row:
        return "no config provenance (pre-dates env_effective recording)"
    eff = row.get("env_effective")
    if isinstance(eff, dict):
        lev = _lever_env(eff)
        if lev:
            return "levers on: " + " ".join(f"{k}={v}" for k, v in sorted(lev.items()))
    return "is_default_config=false"


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        d = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def load_ship_snapshot() -> GateSnapshot | None:
    """Authoritative snapshot for ship: pooled focus + POOLED Arch overall.

    Arch ship authority is the pooled multi-shard `meta` mean, not dist/best_gate.json
    (a max-latch, see ARCH_POOLED_* above). The latch is still carried in raw for the
    board, labelled as the optimistic upper bound it is.
    """
    snap = load_focus_pooled() or load_focus_latest()
    if snap is None:
        return None
    pooled = load_pooled_arch_overall()
    latch = load_best_gate_wr()
    if pooled is not None and pooled.get("mean") is not None:
        snap.arch_overall = pooled["mean"]
        snap.raw["arch_source"] = f"pooled:{pooled.get('label')} n={pooled.get('n')} config=default"
        snap.raw["arch_pooled"] = pooled
    else:
        snap.arch_overall = None  # fail closed: no fresh DEFAULT-CONFIG pooled evidence
        rej = (pooled or {}).get("rejected_nondefault") or []
        if rej:
            snap.raw["arch_source"] = (
                "none (%d fresh pooled meta run(s) rejected: not provably default config)" % len(rej)
            )
            snap.raw["arch_pooled_rejected"] = rej
        else:
            snap.raw["arch_source"] = "none (no pooled meta run within %.0fh)" % ARCH_POOLED_MAX_AGE_H
    snap.raw["arch_best_gate_latch"] = latch  # max-latch, NOT ship authority
    return snap


def load_best_gate_wr() -> float | None:
    p = DIST / "best_gate.json"
    if not p.exists():
        return None
    try:
        return float(json.loads(p.read_text(encoding="utf-8")).get("wr"))
    except Exception:
        return None


def pass_fail(val: float | None, thr: float) -> str:
    if val is None:
        return "—"
    mark = "PASS" if val >= thr else "FAIL"
    return f"{val:.1f}% {mark} (need ≥{thr:.0f}%)"


def format_board(
    *,
    snap: GateSnapshot | None,
    verdict: ShipVerdict | None,
    submits: int,
    processes: dict[str, Any],
    public_mu: dict[str, Any] | None = None,
    decision_line: str = "",
) -> str:
    now_u = utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")
    now_l = datetime.now().strftime("%Y-%m-%d %H:%M:%S local")
    rem = max(0, MAX_SUBMITS_UTC_DAY - submits)
    dual_base = load_dual_baseline()
    arch_loop = load_best_gate_wr()

    iono = snap.iono if snap else None
    flg = snap.crustle_flg if snap else None
    maj = snap.crustle_majkel if snap else None
    crust = snap.crustle_floor_value() if snap else None
    dual = snap.dual_overall if snap else None
    # Never fall back to the best_gate.json max-latch for the arch floor row: with no
    # snapshot there is no pooled evidence, and "—" is the honest reading.
    arch = snap.arch_overall if snap else None

    v_dec = verdict.decision if verdict else "—"
    v_why = "; ".join(verdict.reasons) if verdict and verdict.reasons else "all gates green" if verdict and verdict.ship else "—"

    mu_live = (public_mu or {}).get("live_board") or (public_mu or {}).get("latest2") or "—"
    mu_pin = (public_mu or {}).get("pin") or 1196.1
    mu_top = (public_mu or {}).get("top1") or 1198.4

    lines = [
        "# STATUS BOARD — Submission & Evaluation Director",
        "",
        f"**Updated**: {now_l} / {now_u}",
        f"**UTC day**: `{utc_day()}` · **dayroll in**: **{dayroll_eta_str()}**",
        f"**Canonical**: `E:\\PTCG_AI_Battle_Challenge\\kaggle_pokemon`",
        "",
        "## 1. CAP / Submit",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| Submits today (UTC) | **{submits}/{MAX_SUBMITS_UTC_DAY}** |",
        f"| Remaining | **{rem}** |",
        f"| Board keeps | latest **{ACTIVE_ON_BOARD}** |",
        f"| Auto Dra/Alak | **BLOCKED** |",
        f"| Primary | **{PRIMARY_ID}** |",
        f"| Ship decision | **{v_dec}** |",
        "",
        "## 2. Local gates (ship floors)",
        "",
        f"| Gate | Current (ship=pool) | Floor | Status |",
        f"|------|---------|-------|--------|",
        f"| Arch overall | {arch if arch is not None else '—'} | ≥{SHIP_ARCH_OVERALL:.0f}% | {pass_fail(arch if isinstance(arch, (int, float)) else None, SHIP_ARCH_OVERALL)} |",
        f"| Iono | {iono if iono is not None else '—'} | ≥{SHIP_IONO:.0f}% | {pass_fail(iono, SHIP_IONO)} |",
        f"| Crustle min (flg/majkel) | {crust if crust is not None else '—'} | ≥{SHIP_CRUSTLE_MIN:.0f}% | {pass_fail(crust, SHIP_CRUSTLE_MIN)} |",
        f"| flg Crustle | {flg if flg is not None else '—'} | (component) | — |",
        f"| majkel Crustle | {maj if maj is not None else '—'} | (component) | — |",
        f"| dual overall | {dual if dual is not None else '—'} | ≥max({SHIP_DUAL_FLOOR:.0f}, baseline {dual_base:.1f}) | {pass_fail(dual, max(SHIP_DUAL_FLOOR, dual_base))} |",
        f"| loop best_gate.json | {arch_loop if arch_loop is not None else '—'} | scout/deepen | max-latch, NOT ship authority |",
        f"| arch ship source | {(snap.raw.get('arch_source') if snap else '—')} | pooled `{ARCH_POOLED_SUITE}` n≥{ARCH_POOLED_MIN_GAMES} | fails closed if stale |",
        f"| crustle_min estimator | min(mean_flg, mean_majkel) | — | mean-of-cycle-mins = {(snap.raw.get('crustle_mean_of_cycle_mins') if snap else None)} (Jensen-biased low) |",
        f"| snapshot source | {(snap.source if snap else '—')} | pool_n={FOCUS_POOL_N} | ship uses pool mean |",
        "",
        f"**Hold reasons**: {v_why}",
        "",
        "## 3. Public μ / ladder",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| Live board (latest-2) | {mu_live} |",
        f"| Hist pin | **{mu_pin}** |",
        f"| Top1 target | **{mu_top}** |",
        f"| Gap to pin | see submissions |",
        "",
        "## 4. Process health",
        "",
        f"| Process | Status |",
        f"|---------|--------|",
    ]
    for name, st in processes.items():
        lines.append(f"| {name} | {st} |")
    lines.extend(
        [
            "",
            "## 5. Executable decision",
            "",
            decision_line or _default_decision(submits, rem, verdict, iono, crust, dual, arch),
            "",
            "## 6. Rules lock",
            "",
            "1. Hard CAP **5/UTC-day** — never force past cap.",
            "2. Wait **UTC dayroll** before any new ship when CAP full.",
            "3. **Never auto-submit** Dragapult / Alakazam.",
            "4. Local-only strengthen while CAP full or gates red.",
            "5. Any local regression → **rollback + log** (`recordings/metrics/regression_log.jsonl`).",
            "6. Ship only when **all** floors green AND dual ≥ rolling baseline.",
            "",
        ]
    )
    lines.extend(_fleet_lanes_lines())
    return "\n".join(lines)


# The board is fully regenerated on every run, so any hand-written Fleet-lanes
# section used to be clobbered. Workers own fleet\state\FLEET_LANES.md instead
# and it gets inlined here.
FLEET_LANES_MD = ROOT.parent / "fleet" / "state" / "FLEET_LANES.md"


def _fleet_lanes_lines() -> list[str]:
    try:
        body = FLEET_LANES_MD.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not body:
        return []
    return ["", "## 7. Fleet lanes", "", body, ""]


def _default_decision(
    submits: int,
    rem: int,
    verdict: ShipVerdict | None,
    iono: float | None,
    crust: float | None,
    dual: float | None,
    arch: float | None,
) -> str:
    if rem <= 0:
        return (
            f"**NO SUBMIT** — CAP full {submits}/{MAX_SUBMITS_UTC_DAY}. "
            f"Wait dayroll ({dayroll_eta_str()}). "
            f"Local focus: push Iono→≥{SHIP_IONO:.0f}% (now {iono}), "
            f"hold Crustle≥{SHIP_CRUSTLE_MIN:.0f}% (now {crust}), "
            f"Arch dual≥{SHIP_ARCH_OVERALL:.0f}% (now {arch}/{dual}). "
            f"**Do not** ship Dra/Alak. **Do not** re-wire light Iono stack."
        )
    if verdict and verdict.ship:
        return (
            f"**SHIP ELIGIBLE** — all floors green. Package Arch only; "
            f"1 slot; message must cite iono/crustle/dual. Soft: prefer first slot primary."
        )
    return (
        f"**HOLD** — remaining={rem} but gates red: "
        f"{'; '.join(verdict.reasons) if verdict else 'no snapshot'}. "
        f"Continue local A/B (single lever); no CAP burn."
    )


def write_board(
    *,
    snap: GateSnapshot | None,
    verdict: ShipVerdict | None,
    submits: int,
    processes: dict[str, Any],
    public_mu: dict[str, Any] | None = None,
    decision_line: str = "",
) -> Path:
    text = format_board(
        snap=snap,
        verdict=verdict,
        submits=submits,
        processes=processes,
        public_mu=public_mu,
        decision_line=decision_line,
    )
    BOARD_MD.parent.mkdir(parents=True, exist_ok=True)
    BOARD_MD.write_text(text, encoding="utf-8")
    METRICS.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": utc_now().isoformat(timespec="seconds"),
        "utc_day": utc_day(),
        "dayroll_sec": seconds_to_utc_dayroll(),
        "submits": submits,
        "remaining": max(0, MAX_SUBMITS_UTC_DAY - submits),
        "snapshot": asdict(snap) if snap else None,
        "verdict": {
            "ship": verdict.ship if verdict else False,
            "decision": verdict.decision if verdict else None,
            "reasons": verdict.reasons if verdict else [],
            "thresholds": verdict.thresholds if verdict else {},
            "dual_baseline": verdict.dual_baseline if verdict else load_dual_baseline(),
        }
        if verdict
        else None,
        "processes": processes,
        "public_mu": public_mu,
    }
    BOARD_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return BOARD_MD


if __name__ == "__main__":
    # Operational self-check: use the same authoritative pooled snapshot and
    # UTC submission counter as the shipping path. Never write a board with a
    # hard-coded CAP value.
    from auto_submit import submits_today

    submits = submits_today()
    snap = load_ship_snapshot() or GateSnapshot(ts_utc=utc_now().isoformat())
    v = evaluate_ship(snap, submits_today=submits)
    print(json.dumps({"snap": asdict(snap), "verdict": asdict(v)}, indent=2, ensure_ascii=False))
    p = write_board(
        snap=snap,
        verdict=v,
        submits=submits,
        processes={"self_check": "ok"},
        public_mu={"live_board": "648.4 / 699.7", "pin": 1196.1, "top1": 1198.4},
    )
    print("board ->", p)
