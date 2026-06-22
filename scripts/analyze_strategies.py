#!/usr/bin/env python3
"""Strongest current strategies — from the field episodes + OUR matches.

Goes beyond "which deck wins" (scripts/analyze_winners.py) to characterise the
*strategy* behind the wins, and locates OUR agent's games to see where we differ:

  A. How each archetype WINS — win-condition mix + tempo per winning archetype
     (aggressive KO-race vs board-wipe vs deck-out control).
  B. Skill signal — spread of team win rates (is the field decided by deck or pilot?).
  C. OUR games (team `TomBombadyl`) — per-game ledger: opponent archetype, W/L,
     win-condition, turns — i.e. exactly how we win and how we lose.

Run:  python scripts/analyze_strategies.py --replays report/replays
Writes report/strategy_analysis_<YYYYMMDD>.md (UTF-8). Read-only on replays.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.analyze_winners import (  # noqa: E402
    _final_current, _initial_deck, _win_condition,
)
from scripts.mine_episode_replays import _card_names, _archetype  # noqa: E402

OUR_TEAM = "TomBombadyl"


def _teams(data: dict) -> list[str]:
    info = data.get("info") or {}
    t = info.get("TeamNames") or info.get("Agents") or []
    return [str(x) for x in t] if isinstance(t, list) else []


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--replays", default=str(ROOT / "report" / "replays"))
    p.add_argument("--our-team", default=OUR_TEAM)
    args = p.parse_args(argv)

    files = sorted(Path(args.replays).glob("*.json"))
    if not files:
        print(f"No replays under {args.replays}.")
        return 0
    names = _card_names()

    n = 0
    # A. how each archetype wins
    arch_win_cond = defaultdict(Counter)     # arch -> {ko_race/board_wipe/deck_out: k}
    arch_win_turns = defaultdict(list)       # arch -> [turns] when winning
    arch_games = Counter(); arch_wins = Counter()
    # B. team skill
    team_rec = defaultdict(lambda: [0, 0])   # team -> [wins, games]
    # C. our games
    our = []  # dicts per game

    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        rewards = data.get("rewards")
        if not (isinstance(rewards, list) and len(rewards) == 2):
            continue
        try:
            r0, r1 = float(rewards[0]), float(rewards[1])
        except (TypeError, ValueError):
            continue
        if r0 == r1:
            continue
        n += 1
        win, lose = (0, 1) if r0 > r1 else (1, 0)
        aw = _archetype(_initial_deck(data, win), names) or "unknown"
        al = _archetype(_initial_deck(data, lose), names) or "unknown"
        arch_games[aw] += 1; arch_games[al] += 1; arch_wins[aw] += 1
        wc, lc = _final_current(data, win), _final_current(data, lose)
        cur = wc or lc
        turn = cur.get("turn") if isinstance(cur, dict) else None
        cond = _win_condition(wc, lc) if wc and lc else "other"
        arch_win_cond[aw][cond] += 1
        if isinstance(turn, int):
            arch_win_turns[aw].append(turn)
        # team records
        teams = _teams(data)
        if len(teams) == 2:
            for seat, tname in enumerate(teams):
                team_rec[tname][1] += 1
                if seat == win:
                    team_rec[tname][0] += 1
            # our games
            if args.our_team in teams:
                seat = teams.index(args.our_team)
                won = (seat == win)
                opp = teams[1 - seat]
                our.append({
                    "opp": opp,
                    "our_arch": _archetype(_initial_deck(data, seat), names) or "unknown",
                    "opp_arch": _archetype(_initial_deck(data, 1 - seat), names) or "unknown",
                    "won": won, "turn": turn,
                    # _win_condition reads the LOSER's board from the WINNER's view (1st arg);
                    # for our losses the winner is the opponent, so pass wc (winner view) first.
                    "cond": cond if won else (_win_condition(wc, lc) if wc and lc else "other"),
                })

    def pct(a, b): return f"{100*a/b:.1f}%" if b else "n/a"
    def med(xs): return sorted(xs)[len(xs)//2] if xs else 0

    L = [f"# Strongest current strategies ({datetime.now(timezone.utc):%Y-%m-%d})",
         "", f"Decided games: **{n}** from {len(files)} replays. Field = real ladder "
         f"(06-19 dump; median agent score ~1013).", ""]

    # A
    L += ["## A. How each archetype WINS (win-condition mix + tempo)", "",
          "| archetype | wins | win rate | median turns(win) | ko_race | board_wipe | deck_out |",
          "|---|---|---|---|---|---|---|"]
    for a, g in arch_games.most_common():
        if g < 30:
            continue
        wc_ = arch_win_cond[a]; tot = sum(wc_.values()) or 1
        L.append(f"| {a} | {arch_wins[a]} | {pct(arch_wins[a], g)} | "
                 f"{med(arch_win_turns[a])} | {pct(wc_['ko_race'],tot)} | "
                 f"{pct(wc_['board_wipe'],tot)} | {pct(wc_['deck_out'],tot)} |")

    # B
    sized = [(t, w, g) for t, (w, g) in team_rec.items() if g >= 6]
    sized.sort(key=lambda x: (-x[1]/x[2], -x[2]))
    L += ["", "## B. Skill signal — top teams (>= 6 games)", "",
          f"Distinct teams: {len(team_rec)}; with >=6 games: {len(sized)}.",
          "Wide win-rate spread among teams running the *same* hub deck = pilot decides.", "",
          "| team | win rate | games |", "|---|---|---|"]
    for t, w, g in sized[:20]:
        L.append(f"| {t} | {pct(w,g)} | {g} |")

    # C
    L += ["", f"## C. OUR games (`{args.our_team}`)", ""]
    if not our:
        L += [f"No games for team `{args.our_team}` found in this dump.", ""]
    else:
        wins = sum(1 for d in our if d["won"])
        L += [f"Found **{len(our)}** of our games: **{wins}W-{len(our)-wins}L = "
              f"{pct(wins,len(our))}**.", "",
              "### vs opponent archetype",
              "| opp archetype | our W | our L | win rate |", "|---|---|---|---|"]
        by_opp = defaultdict(lambda: [0, 0])
        for d in our:
            by_opp[d["opp_arch"]][0 if d["won"] else 1] += 1
        for a, (w, l) in sorted(by_opp.items(), key=lambda x: -(x[1][0]+x[1][1])):
            L.append(f"| {a} | {w} | {l} | {pct(w, w+l)} |")
        # losses detail
        losses = [d for d in our if not d["won"]]
        L += ["", f"### our {len(losses)} losses — how we lost",
              "| opp | opp arch | turns | loss type |", "|---|---|---|---|"]
        for d in sorted(losses, key=lambda d: (d["turn"] or 0)):
            L.append(f"| {d['opp'][:24]} | {d['opp_arch']} | {d['turn']} | {d['cond']} |")
        fast = [d for d in losses if isinstance(d["turn"], int) and d["turn"] <= 8]
        L += ["", f"Fast losses (<= turn 8): **{len(fast)}/{len(losses)}** "
              f"(early blowouts vs grind). Our win median "
              f"{med([d['turn'] for d in our if d['won'] and d['turn']])} turns, "
              f"loss median {med([d['turn'] for d in losses if d['turn']])} turns."]

    out = ROOT / "report" / f"strategy_analysis_{datetime.now(timezone.utc):%Y%m%d}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {out}  (games={n}, our_games={len(our)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
