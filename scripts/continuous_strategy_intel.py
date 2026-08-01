#!/usr/bin/env python3
"""Background strategy intel: Kaggle LB + local metrics → strategy notes.

Does NOT use web browser (runs on machine with Kaggle API).
Interval default 45 minutes; never stops main factory.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
COMP = "pokemon-tcg-ai-battle"
LOG = ROOT / "report" / "aggressive"
METRICS = ROOT / "recordings" / "metrics"
STATE = ROOT / "STATE.md"
INTERVAL_SEC = int(os.environ.get("STRATEGY_INTEL_INTERVAL", "2700"))  # 45m

LOG.mkdir(parents=True, exist_ok=True)
METRICS.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with (LOG / "strategy_intel.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def ensure_token() -> None:
    if os.environ.get("KAGGLE_API_TOKEN"):
        return
    for p in (
        Path.home() / ".kaggle" / "access_token",
        ROOT / ".kaggle" / "access_token",
        ROOT.parent / ".kaggle" / "access_token",
    ):
        if p.exists():
            os.environ["KAGGLE_API_TOKEN"] = p.read_text(encoding="utf-8").strip().splitlines()[0]
            return


def kaggle(args: list[str], timeout: int = 120) -> str:
    ensure_token()
    try:
        p = subprocess.run(
            [PY, "-m", "kaggle"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT),
            env=os.environ.copy(),
        )
        return (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return f"ERR {e}"


def parse_lb(csv_text: str, n: int = 10) -> list[dict]:
    rows = []
    lines = [
        ln.strip()
        for ln in csv_text.splitlines()
        if ln.strip() and not ln.lower().startswith("next page")
    ]
    # find header
    start = 0
    for i, ln in enumerate(lines):
        if "teamid" in ln.lower().replace(" ", ""):
            start = i
            break
    import csv
    import io

    block = "\n".join(lines[start:])
    try:
        rdr = csv.DictReader(io.StringIO(block))
        for r in rdr:
            rk = {(k or "").strip(): v for k, v in r.items()}
            tid = rk.get("teamId") or rk.get("TeamId")
            if not tid:
                continue
            try:
                rows.append(
                    {
                        "teamId": int(float(tid)),
                        "teamName": (rk.get("teamName") or rk.get("TeamName") or "").strip(),
                        "score": float(rk.get("score") or rk.get("Score") or 0),
                    }
                )
            except Exception:
                continue
            if len(rows) >= n:
                break
    except Exception:
        pass
    return rows


def parse_our_best(sub_text: str) -> dict:
    best = {"ref": None, "score": None, "status": None}
    # table lines: ref fileName date description status score
    for ln in sub_text.splitlines():
        parts = ln.split()
        if parts and parts[0].isdigit() and len(parts[0]) >= 7:
            try:
                ref = parts[0]
                # score near end
                score = None
                for tok in reversed(parts):
                    try:
                        score = float(tok)
                        break
                    except ValueError:
                        continue
                status = "COMPLETE" if "COMPLETE" in ln else ("PENDING" if "PENDING" in ln else "?")
                if score is not None and (best["score"] is None or score > best["score"]):
                    best = {"ref": ref, "score": score, "status": status}
            except Exception:
                continue
    return best


def load_focus() -> dict:
    p = METRICS / "focus_latest.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_top_decks_summary() -> list[dict]:
    # latest top_decks_*.json
    files = sorted(METRICS.glob("top_decks_*.json"), reverse=True)
    for f in files:
        if "full" in f.name:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            return d.get("teams") or []
        except Exception:
            continue
    return []


def analyze(lb: list[dict], our: dict, focus: dict, top_decks: list[dict]) -> dict:
    top1 = lb[0] if lb else {}
    top_names = [t.get("teamName") for t in lb[:6]]
    # map known archetypes from our extract
    arch_by_team = {t.get("teamName"): t.get("primary_archetype") for t in top_decks}

    # Guess top strategy mix
    arch_counts: dict[str, int] = {}
    for name in top_names:
        a = arch_by_team.get(name) or "unknown"
        # fuzzy
        for t in top_decks:
            if t.get("teamName") and name and t["teamName"] in name or (name and name in str(t.get("teamName"))):
                a = t.get("primary_archetype") or a
        arch_counts[a] = arch_counts.get(a, 0) + 1

    iono = focus.get("iono_wr")
    majkel = focus.get("majkel_wr")
    flg = focus.get("flg_wr")
    dual = focus.get("dual_overall")

    gaps = []
    if iono is not None and iono < 55:
        gaps.append(f"Iono local WR {iono}% << 55% ship floor — #1 ladder gap vs Lightning tempo")
    if majkel is not None and majkel < 65:
        gaps.append(f"majkel Crustle {majkel}% < 65%")
    if our.get("score") and lb:
        gap_mu = lb[0]["score"] - float(our["score"])
        gaps.append(f"μ gap to #1: {gap_mu:.1f} (us {our['score']} vs {lb[0]['score']})")

    # Directions
    directions = []
    if iono is not None and iono < 55:
        directions.append(
            "PRIORITY-1: Iono lever stack — Boss Bellibolt/Kilowattrel early, Relicanth+MD race, never END with attach/attack, Turbo Flare re-fuel"
        )
    directions.append(
        "PRIORITY-2: Keep 75wr Arch shell; deep Crustle already strong vs random pilots — next need native/stronger pilots or belief search for flg/Dries quality"
    )
    if top1.get("teamName"):
        a1 = arch_by_team.get(top1["teamName"], "likely Grimmsnarl or Crustle from meta extract")
        directions.append(f"Study #1 {top1['teamName']} (@{top1.get('score')}) archetype≈{a1}; pull fresh episodes if μ drifts")

    # ship recommend
    ship = "HOLD"
    if (
        iono is not None
        and iono >= 55
        and majkel is not None
        and majkel >= 65
        and dual is not None
        and dual >= 72
        and our.get("score")
        and our["score"] >= 720
    ):
        ship = "CANDIDATE — only if also beats live board on ≥2 μ readings"

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "leaderboard_top": lb[:8],
        "our_best": our,
        "focus": {k: focus.get(k) for k in ("iono_wr", "majkel_wr", "flg_wr", "dual_overall", "cycle")},
        "top_archetype_guess": arch_counts,
        "top1_hypothesis": {
            "team": top1.get("teamName"),
            "mu": top1.get("score"),
            "likely_core": arch_by_team.get(top1.get("teamName") or "", "meta dual: Grimmsnarl/Crustle"),
        },
        "our_gaps": gaps,
        "next_directions": directions[:3],
        "ship_recommendation": ship,
        "sources": [
            "kaggle competitions leaderboard pokemon-tcg-ai-battle",
            "kaggle competitions submissions (ours)",
            "recordings/metrics/focus_latest.json",
            "recordings/metrics/top_decks_*.json (episode deck restore)",
            "prior meta: ptcg-meta / community 7/22 snapshot Grimmsnarl~31% Alakazam~30% Crustle~13%",
        ],
    }


def write_analysis(doc: dict) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = METRICS / f"strategy_analysis_{ts}.md"
    lb_lines = "\n".join(
        f"| {i+1} | {t.get('teamName')} | {t.get('score')} |"
        for i, t in enumerate(doc.get("leaderboard_top") or [])
    )
    gaps = "\n".join(f"- {g}" for g in doc.get("our_gaps") or [])
    dirs = "\n".join(f"{i+1}. {d}" for i, d in enumerate(doc.get("next_directions") or []))
    md = f"""# Strategy Analysis {doc.get('ts')}

## Leaderboard (live)
| Rank | Team | μ |
|------|------|--:|
{lb_lines}

## Our best
- ref: `{doc.get('our_best', {}).get('ref')}` score **{doc.get('our_best', {}).get('score')}** ({doc.get('our_best', {}).get('status')})

## Local focus
```json
{json.dumps(doc.get('focus'), indent=2)}
```

## #1 hypothesis
```json
{json.dumps(doc.get('top1_hypothesis'), indent=2, ensure_ascii=False)}
```

## Our biggest gaps
{gaps}

## Next 1–2 directions
{dirs}

## Ship
**{doc.get('ship_recommendation')}**

## Sources
{chr(10).join('- ' + s for s in doc.get('sources') or [])}
"""
    path.write_text(md, encoding="utf-8")
    # also latest pointer
    (METRICS / "strategy_analysis_latest.md").write_text(md, encoding="utf-8")
    (METRICS / "strategy_analysis_latest.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def patch_state(doc: dict) -> None:
    intel = f"""
## Strategy intel (auto {doc.get('ts')})
- #1: **{doc.get('top1_hypothesis', {}).get('team')}** @ {doc.get('top1_hypothesis', {}).get('mu')} · core≈{doc.get('top1_hypothesis', {}).get('likely_core')}
- Our best μ: **{doc.get('our_best', {}).get('score')}**
- Focus: Iono={doc.get('focus', {}).get('iono_wr')} majkel={doc.get('focus', {}).get('majkel_wr')} flg={doc.get('focus', {}).get('flg_wr')} dual={doc.get('focus', {}).get('dual_overall')}
- Ship: {doc.get('ship_recommendation')}
- Next: {(doc.get('next_directions') or ['—'])[0][:160]}
- File: `recordings/metrics/strategy_analysis_latest.md`
"""
    try:
        old = STATE.read_text(encoding="utf-8") if STATE.exists() else "# STATE\n"
        # replace or append intel block
        if "## Strategy intel" in old:
            import re as _re

            old = _re.sub(
                r"## Strategy intel.*?(?=\n## |\Z)",
                intel.strip() + "\n\n",
                old,
                count=1,
                flags=_re.S,
            )
        else:
            old = old.rstrip() + "\n" + intel
        STATE.write_text(old, encoding="utf-8")
    except Exception as e:
        log(f"state patch fail: {e}")


def cycle() -> Path | None:
    log("strategy intel cycle start")
    lb_raw = kaggle(["competitions", "leaderboard", COMP, "-s", "-v"])
    sub_raw = kaggle(["competitions", "submissions", COMP])
    lb = parse_lb(lb_raw, 10)
    our = parse_our_best(sub_raw)
    focus = load_focus()
    tops = load_top_decks_summary()
    doc = analyze(lb, our, focus, tops)
    path = write_analysis(doc)
    patch_state(doc)
    log(f"wrote {path} ship={doc.get('ship_recommendation')} our={our.get('score')} top1={lb[0] if lb else None}")
    return path


def main() -> int:
    os.chdir(ROOT)
    log(f"continuous_strategy_intel START interval={INTERVAL_SEC}s")
    # fire immediately
    while True:
        try:
            cycle()
        except Exception:
            log("ERROR " + traceback.format_exc()[-800:])
        time.sleep(INTERVAL_SEC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
