"""Trace ladder no_active losses from deck-perspective logs + raw replay."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "data" / "sim" / "sample_submission"
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ROOT))

from cg.api import SelectContext, OptionType  # noqa: E402
from scripts.episode_stats import infer_result_reason, _parse_result_from_obs  # noqa: E402

CTX = {int(v): k for k, v in SelectContext.__dict__.items() if k.isupper() and isinstance(v, int)}
OPT = {int(v): k for k, v in OptionType.__dict__.items() if k.isupper() and isinstance(v, int)}


def ctx_name(c: int) -> str:
    return CTX.get(c, str(c))


def load_replay(ep: str) -> dict:
    for base in (ROOT / "report" / "replays", ROOT / "report" / "submission_replays" / "archaludon"):
        p = base / f"{ep}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(ep)


def trace_episode(ep: str, hero_seat: int) -> None:
    data = load_replay(ep)
    deck_log = json.loads(
        (ROOT / "report" / "deck_logs" / "archaludon" / f"{ep}.json").read_text(encoding="utf-8")
    )
    print(f"\n{'='*72}\nEpisode {ep}  seat={hero_seat}  reason={deck_log['result_reason']}")
    print(f"turns={deck_log['turn_count']}  terminal bench={deck_log['terminal_us']['bench_count']}")

    steps = data.get("steps") or []
    for step in steps[-3:]:
        if not isinstance(step, list):
            continue
        ps = step[hero_seat]
        obs = ps.get("observation") or ps
        cur = obs.get("current") or {}
        sel = obs.get("select")
        w, reason = _parse_result_from_obs(obs)
        if w in (0, 1, 2):
            players = cur.get("players") or []
            print(f"  TERMINAL winner={w} reason={reason} infer={infer_result_reason(w, players)}")
        if sel:
            ctx = int(sel.get("context", -1))
            opts = sel.get("option") or []
            print(f"  select ctx={ctx_name(ctx)} opts={len(opts)} type={sel.get('type')}")

    print("\n  Key deck-log turns (bench=0 on MAIN or last 5):")
    turns = deck_log.get("turns") or []
    flagged = [
        t
        for t in turns
        if t["us"]["bench_count"] == 0
        and t["select"]["context"] == 0
        and t["select"]["option_count"] >= 5
    ]
    for t in (flagged[:3] + turns[-5:]):
        s = t["select"]
        print(
            f"    step={t['step']:3d} turn={t['turn']:2d} ctx={ctx_name(s['context'])} "
            f"opts={s['option_count']} action={t['action']} "
            f"bench={t['us']['bench_count']} hand={t['us']['hand_count']} "
            f"active={t['us'].get('active')}"
        )


def main() -> int:
    trace_episode("82055480", hero_seat=0)
    trace_episode("82068759", hero_seat=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
