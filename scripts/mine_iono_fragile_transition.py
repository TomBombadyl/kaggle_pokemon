#!/usr/bin/env python3
"""Mine the *earliest preventable transition* into a fragile board (iono lane).

`analyze_iono_loss_clusters.py` showed `fragile_board_any` covers ~45% of Iono
losses vs ~6% of wins, but it reads the *terminal* decision, so it cannot say
whether the fragile board was preventable. `tomato_fork` (bench-depth floor
before delegation) came back NULL at floors 2 and 3, which already rules out
"we chose not to bench" as the cause.

This script answers the follow-up directly, from schema-v2 trajectories:

  Q1  When the bench first empties post-setup, was a bench play even legal?
      -> if it usually was not, bench-floor levers are dead and the lever must
         move upstream to *acquiring* or *not spending* basics.
  Q2  Do we discard our own Pokemon (Ultra Ball cost, Iono/Lillie shuffles,
      DISCARD contexts) and does that predict the loss?
  Q3  Regret table: for every (option_type, card_id) signature, win rate when
      chosen vs when legal-but-declined, inside matched state buckets.

Output: recordings/intel/iono_fragile_transition.{md,json}
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "episodes" / "iono_bc_v2"
OUT_DIR = ROOT / "recordings" / "intel"

# ---- schema v2 state indices (collect_iono_decisions.state_vector) ----
S_TURN, S_MY_PRIZE, S_OPP_PRIZE, S_HAND, S_DECK, S_DISCARD = 0, 1, 2, 3, 4, 5
S_BENCH, S_OPP_BENCH = 6, 7
S_ACT_HP, S_ACT_DMG, S_ACT_EN = 8, 9, 10
S_ACT_DURA, S_ACT_ARCH, S_ACT_CINDER, S_ACT_RELI, S_ACT_NONE = 11, 12, 13, 14, 15
S_OPP_HP, S_OPP_DMG, S_OPP_EN, S_OPP_EX, S_OPP_THREAT = 16, 17, 18, 19, 20
S_CTX_MAIN, S_CTX_SETUP, S_CTX_SWITCH, S_NOPTS = 21, 22, 23, 24

# ---- schema v2 option indices: 17 one-hot type slots then 4 scalars ----
N_TYPES = 17
O_CARD_ID, O_IS_PKM, O_IS_ENERGY, O_TARGETS_OPP = 17, 18, 19, 20

TYPE_NAMES = [
    "NUMBER", "YES", "NO", "CARD", "TOOL_CARD", "ENERGY_CARD", "ENERGY",
    "PLAY", "ATTACH", "EVOLVE", "ABILITY", "DISCARD", "RETREAT", "ATTACK",
    "END", "SKILL", "SPECIAL_CONDITION",
]
T_CARD, T_PLAY, T_ATTACH, T_EVOLVE, T_ABILITY = 3, 7, 8, 9, 10
T_DISCARD, T_RETREAT, T_ATTACK, T_END = 11, 12, 13, 14

DURALUDON, ARCHALUDON_EX, CINDERACE, RELICANTH = 169, 190, 666, 57
BASICS = {DURALUDON, RELICANTH, CINDERACE}
OUR_POKEMON = BASICS | {ARCHALUDON_EX}
ULTRA_BALL, POKEGEAR, POKE_PAD, IONO, LILLIE, EXPLORER = 1121, 1122, 1152, 1181, 1227, 1185

CARD_NAMES = {
    169: "Duraludon", 190: "Archaludon ex", 666: "Cinderace", 57: "Relicanth",
    1121: "Ultra Ball", 1122: "Pokegear 3.0", 1152: "Poke Pad", 1181: "Iono",
    1227: "Lillie's Determination", 1185: "Explorer's Guidance", 1182: "Boss's Orders",
    0: "-",
}


def otype(opt) -> int:
    for i in range(N_TYPES):
        if opt[i] >= 0.5:
            return i
    return -1


def bucket(s) -> tuple:
    """Matched-state bucket for the regret contrast."""
    bench = int(s[S_BENCH])
    en = int(s[S_ACT_EN])
    turn = int(s[S_TURN])
    tb = 0 if turn <= 4 else (1 if turn <= 9 else 2)
    return (min(bench, 3), min(en, 3), tb, int(s[S_MY_PRIZE]))


def scan_file(path_str: str) -> dict:
    """Single-pass scan of one shard file. Returns plain-dict counters."""
    path = Path(path_str)
    # Q1 counters: bench-empty entry events
    q1 = {"games": 0, "wins": 0, "entered": 0, "entered_loss": 0,
          "legal_bench_play": 0, "legal_bench_play_loss": 0,
          "no_option_at_all": 0}
    # Q1b: hand size at the entry decision, by outcome
    q1_hand = {"win": [0, 0], "loss": [0, 0]}  # [sum, n]
    # Q2 counters: discarding our own Pokemon
    q2 = defaultdict(lambda: [0, 0])  # card_id -> [n_discarded, n_wins]
    q2_games = {"any_pkm_discard": [0, 0]}  # -> [games, wins]
    # Q3 regret: bucket -> sig -> [chosen_n, chosen_wins, declined_n, declined_wins]
    q3 = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("schema_version") != 2:
                continue
            label = int(rec.get("label", 0))
            won = label == 1
            decs = rec.get("decisions") or []
            if not decs:
                continue
            q1["games"] += 1
            q1["wins"] += int(won)

            had_bench = False
            entry_done = False
            game_pkm_discard = False

            for d in decs:
                s = d["s"]
                opts = d["o"]
                pick = set(d.get("pick") or [])
                bench = int(s[S_BENCH])
                turn = int(s[S_TURN])
                is_main = s[S_CTX_MAIN] >= 0.5
                is_setup = s[S_CTX_SETUP] >= 0.5

                if bench >= 1:
                    had_bench = True

                # ---- Q1: first post-setup transition to an empty bench ----
                if (not entry_done) and had_bench and bench == 0 and turn >= 2 \
                        and not is_setup:
                    entry_done = True
                    q1["entered"] += 1
                    if not won:
                        q1["entered_loss"] += 1
                    tgt = q1_hand["win" if won else "loss"]
                    tgt[0] += int(s[S_HAND])
                    tgt[1] += 1
                    playable = False
                    for o in opts:
                        t = otype(o)
                        cid = int(o[O_CARD_ID])
                        if t in (T_PLAY, T_CARD) and cid in BASICS:
                            playable = True
                            break
                    if playable:
                        q1["legal_bench_play"] += 1
                        if not won:
                            q1["legal_bench_play_loss"] += 1
                    if not opts:
                        q1["no_option_at_all"] += 1

                # ---- Q2: discarding our own Pokemon ----
                for i in pick:
                    if i >= len(opts):
                        continue
                    o = opts[i]
                    t = otype(o)
                    cid = int(o[O_CARD_ID])
                    if t == T_DISCARD or (not is_main and not is_setup
                                          and t == T_CARD and cid in OUR_POKEMON):
                        if cid in OUR_POKEMON:
                            q2[cid][0] += 1
                            q2[cid][1] += int(won)
                            game_pkm_discard = True

                # ---- Q3: regret contrast on MAIN decisions ----
                if is_main and len(opts) >= 2:
                    b = bucket(s)
                    seen = set()
                    for i, o in enumerate(opts):
                        t = otype(o)
                        cid = int(o[O_CARD_ID])
                        sig = (t, cid if cid in CARD_NAMES else -1)
                        if sig in seen:
                            # collapse duplicate copies; chosen wins over declined
                            if i in pick:
                                row = q3[b][sig]
                                row[2] -= 1
                                row[3] -= int(won)
                                row[0] += 1
                                row[1] += int(won)
                            continue
                        seen.add(sig)
                        row = q3[b][sig]
                        if i in pick:
                            row[0] += 1
                            row[1] += int(won)
                        else:
                            row[2] += 1
                            row[3] += int(won)

            if game_pkm_discard:
                q2_games["any_pkm_discard"][0] += 1
                q2_games["any_pkm_discard"][1] += int(won)

    return {
        "q1": q1,
        "q1_hand": q1_hand,
        "q2": {str(k): v for k, v in q2.items()},
        "q2_games": q2_games,
        "q3": {json.dumps(list(b)): {json.dumps(list(sig)): row
                                     for sig, row in sm.items()}
               for b, sm in q3.items()},
    }


def wilson(k: int, n: int) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    z = 1.959964
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--files", type=int, default=14, help="how many shard files")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--min-n", type=int, default=400,
                    help="min chosen+declined n per regret row")
    args = ap.parse_args()

    paths = sorted(EPISODES.glob("*.jsonl"))
    paths = [p for p in paths if p.stat().st_size > 200_000][: args.files]
    if not paths:
        print("no v2 shard files found")
        return 1
    print(f"[mine] {len(paths)} files, {sum(p.stat().st_size for p in paths)/1e6:.0f} MB")

    q1 = defaultdict(int)
    q1_hand = {"win": [0, 0], "loss": [0, 0]}
    q2 = defaultdict(lambda: [0, 0])
    q2_games = [0, 0]
    q3 = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(scan_file, [str(p) for p in paths]):
            for k, v in res["q1"].items():
                q1[k] += v
            for k in ("win", "loss"):
                q1_hand[k][0] += res["q1_hand"][k][0]
                q1_hand[k][1] += res["q1_hand"][k][1]
            for cid, row in res["q2"].items():
                q2[int(cid)][0] += row[0]
                q2[int(cid)][1] += row[1]
            q2_games[0] += res["q2_games"]["any_pkm_discard"][0]
            q2_games[1] += res["q2_games"]["any_pkm_discard"][1]
            for bkey, sm in res["q3"].items():
                b = tuple(json.loads(bkey))
                for skey, row in sm.items():
                    sig = tuple(json.loads(skey))
                    tgt = q3[b][sig]
                    for i in range(4):
                        tgt[i] += row[i]

    games, wins = q1["games"], q1["wins"]
    base_wr = wins / games if games else 0.0

    # ---- Q3 aggregation: pooled, bucket-matched regret ----
    agg = defaultdict(lambda: [0, 0, 0, 0])
    for b, sm in q3.items():
        for sig, row in sm.items():
            if row[0] <= 0 or row[2] <= 0:
                continue  # bucket gives no within-bucket contrast
            t = agg[sig]
            for i in range(4):
                t[i] += row[i]
    rows = []
    for sig, (cn, cw, dn, dw) in agg.items():
        if cn + dn < args.min_n or cn < 60 or dn < 60:
            continue
        pc, pcl, pch = wilson(cw, cn)
        pd, pdl, pdh = wilson(dw, dn)
        rows.append({
            "type": TYPE_NAMES[sig[0]] if 0 <= sig[0] < N_TYPES else "?",
            "card": CARD_NAMES.get(sig[1], str(sig[1])),
            "card_id": sig[1],
            "chosen_n": cn, "chosen_wr": round(100 * pc, 2),
            "chosen_ci": [round(100 * pcl, 2), round(100 * pch, 2)],
            "declined_n": dn, "declined_wr": round(100 * pd, 2),
            "declined_ci": [round(100 * pdl, 2), round(100 * pdh, 2)],
            "delta_pp": round(100 * (pc - pd), 2),
            "disjoint": bool(pcl > pdh or pdl > pch),
        })
    rows.sort(key=lambda r: -abs(r["delta_pp"]))

    payload = {
        "games": games, "wins": wins, "base_wr": round(100 * base_wr, 2),
        "files": [p.name for p in paths],
        "q1_bench_empty_entry": dict(q1),
        "q1_hand_at_entry": {
            k: round(v[0] / v[1], 2) if v[1] else None for k, v in q1_hand.items()
        },
        "q2_pokemon_discard": {
            CARD_NAMES.get(cid, str(cid)): {
                "n": row[0], "wr": round(100 * row[1] / row[0], 2) if row[0] else None
            } for cid, row in sorted(q2.items())
        },
        "q2_games_with_pokemon_discard": {
            "games": q2_games[0],
            "wr": round(100 * q2_games[1] / q2_games[0], 2) if q2_games[0] else None,
            "share_of_games": round(100 * q2_games[0] / games, 2) if games else None,
        },
        "q3_regret": rows,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "iono_fragile_transition.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")

    ent = q1["entered"]
    lines = [
        "# Iono — earliest preventable transition into a fragile board",
        "",
        f"Scanned **{games} games** ({100*base_wr:.2f}% WR) over {len(paths)} schema-v2 shards.",
        "",
        "## Q1 — when the bench first empties post-setup",
        "",
        f"- games that ever reach an empty bench after setup: **{ent}** "
        f"({100*ent/games:.2f}% of games); of those **{q1['entered_loss']}** lost "
        f"(**{100*q1['entered_loss']/ent:.2f}%** loss rate vs {100*(1-base_wr):.2f}% overall)",
        f"- a bench play (Duraludon/Relicanth/Cinderace) was legal at that very decision "
        f"in **{q1['legal_bench_play']}** cases "
        f"(**{100*q1['legal_bench_play']/ent:.2f}%** of entries)" if ent else "",
        f"- mean hand size at the entry decision: win {payload['q1_hand_at_entry']['win']} "
        f"vs loss {payload['q1_hand_at_entry']['loss']}",
        "",
        "## Q2 — do we spend our own Pokemon as a cost?",
        "",
        f"- games with >=1 own-Pokemon discard: **{q2_games[0]}** "
        f"({payload['q2_games_with_pokemon_discard']['share_of_games']}% of games), "
        f"WR **{payload['q2_games_with_pokemon_discard']['wr']}%** vs base {100*base_wr:.2f}%",
        "",
        "| discarded card | n | WR |",
        "|---|---:|---:|",
    ]
    for name, v in payload["q2_pokemon_discard"].items():
        lines.append(f"| {name} | {v['n']} | {v['wr']}% |")
    lines += [
        "",
        "## Q3 — bucket-matched regret (MAIN decisions)",
        "",
        "Within matched `(bench, active energy, turn band, own prizes)` buckets: win rate "
        "when the option was taken vs when it was legal and declined. Observational, "
        "policy-confounded — a candidate generator, not proof.",
        "",
        "| option | card | chosen n | chosen WR | declined n | declined WR | delta | ci disjoint |",
        "|---|---|---:|---:|---:|---:|---:|:--:|",
    ]
    for r in rows[:30]:
        lines.append(
            f"| {r['type']} | {r['card']} | {r['chosen_n']} | {r['chosen_wr']}% | "
            f"{r['declined_n']} | {r['declined_wr']}% | {r['delta_pp']:+.2f}pp | "
            f"{'yes' if r['disjoint'] else 'no'} |")
    (OUT_DIR / "iono_fragile_transition.md").write_text(
        "\n".join(x for x in lines if x is not None), encoding="utf-8")

    print("\n".join(x for x in lines if x is not None)[:6000])
    print(f"\nWrote {OUT_DIR / 'iono_fragile_transition.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
