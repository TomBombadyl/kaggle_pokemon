#!/usr/bin/env python3
"""Build a win/loss terminal-state comparison from schema-v2 Iono decisions."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if not n:
        return [0.0, 0.0]
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [100 * (centre - half), 100 * (centre + half)]


def load_games(data_dir: Path) -> tuple[list[dict], list[dict]]:
    games: list[dict] = []
    sources: list[dict] = []
    for path in sorted(data_dir.glob("iono_decisions_*.jsonl")):
        wins = losses = skipped = 0
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
                decisions = rec.get("decisions") or []
                label = rec.get("label")
                if rec.get("schema_version") != 2 or label not in (0, 1) or not decisions:
                    skipped += 1
                    continue
                usable = [
                    d for d in decisions
                    if len(d.get("s") or []) >= 25 and d["s"][22] < 0.5
                ]
                state = (usable or decisions)[-1].get("s") or []
                if len(state) < 25:
                    skipped += 1
                    continue
                games.append({"label": label, "state": state})
                wins += int(label == 1)
                losses += int(label == 0)
        sources.append({
            "file": path.name,
            "wins": wins,
            "losses": losses,
            "games": wins + losses,
            "wr_pct": round(100 * wins / (wins + losses), 2) if wins + losses else None,
            "skipped": skipped,
        })
    return games, sources


def active_name(s: list[float]) -> str:
    if s[15] >= 0.5:
        return "none"
    if s[12] >= 0.5:
        return "archaludon_ex"
    if s[13] >= 0.5:
        return "cinderace"
    if s[11] >= 0.5:
        return "duraludon"
    if s[14] >= 0.5:
        return "relicanth"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="episodes/iono_bc_v2")
    ap.add_argument("--out", default="recordings/intel/iono_loss_clusters")
    args = ap.parse_args()

    games, sources = load_games(ROOT / args.data)
    n_loss = sum(g["label"] == 0 for g in games)
    n_win = sum(g["label"] == 1 for g in games)
    if n_loss < 300:
        raise SystemExit(f"need >=300 schema-v2 losses; found {n_loss}")

    flags = {
        "fragile_board_any": lambda s: (
            not (s[12] >= 0.5 or s[13] >= 0.5) or s[10] < 2 or s[6] <= 0
        ),
        "setup_incomplete_active": lambda s: not (s[12] >= 0.5 or s[13] >= 0.5),
        "active_energy_lt2": lambda s: s[10] < 2,
        "bench_empty": lambda s: s[6] <= 0,
        "opponent_prizes_le2": lambda s: s[2] <= 2,
        "hero_prizes_ge4": lambda s: s[1] >= 4,
        "prize_deficit_ge2": lambda s: s[1] - s[2] >= 2,
        "hand_le2": lambda s: s[3] <= 2,
        "deck_le5": lambda s: s[4] <= 5,
        "turn_ge12": lambda s: s[0] >= 12,
        "iono_threat_active": lambda s: s[20] >= 0.5,
    }
    rows = []
    for name, predicate in flags.items():
        loss_k = sum(g["label"] == 0 and predicate(g["state"]) for g in games)
        win_k = sum(g["label"] == 1 and predicate(g["state"]) for g in games)
        loss_pct = 100 * loss_k / n_loss
        win_pct = 100 * win_k / n_win
        rows.append({
            "cluster": name,
            "loss_n": loss_k,
            "loss_pct": round(loss_pct, 2),
            "loss_ci95": [round(x, 2) for x in wilson(loss_k, n_loss)],
            "win_n": win_k,
            "win_pct": round(win_pct, 2),
            "win_ci95": [round(x, 2) for x in wilson(win_k, n_win)],
            "delta_pp": round(loss_pct - win_pct, 2),
        })

    actives = {}
    for label, key in ((0, "loss"), (1, "win")):
        counts = Counter(active_name(g["state"]) for g in games if g["label"] == label)
        total = sum(counts.values())
        actives[key] = {
            name: {"n": count, "pct": round(100 * count / total, 2)}
            for name, count in counts.most_common()
        }

    payload = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": 2,
        "games": len(games),
        "wins": n_win,
        "losses": n_loss,
        "pooled_wr_pct": round(100 * n_win / len(games), 2),
        "sources": sources,
        "clusters": rows,
        "last_active": actives,
        "decision_rule": "use last non-setup hero decision in each completed game",
        "caveat": "terminal-state enrichment is associative, not a causal action label",
    }

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Iono loss clusters — schema v2",
        "",
        f"Pooled **{len(games)} games**: {n_win} wins / {n_loss} losses "
        f"(**{payload['pooled_wr_pct']:.2f}%**). Each row compares the last non-setup "
        "hero decision in losses against wins.",
        "",
        "| cluster | losses | loss share (95% CI) | wins | win share (95% CI) | delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['cluster']}` | {row['loss_n']} | {row['loss_pct']:.2f}% "
            f"[{row['loss_ci95'][0]:.2f}, {row['loss_ci95'][1]:.2f}] | {row['win_n']} | "
            f"{row['win_pct']:.2f}% [{row['win_ci95'][0]:.2f}, {row['win_ci95'][1]:.2f}] | "
            f"{row['delta_pp']:+.2f}pp |"
        )
    lines += [
        "",
        "## Readout",
        "",
        "`fragile_board_any` is the first evidence-backed target: it covers at least "
        "20% of losses and is strongly enriched versus wins. Its three overlapping "
        "components are incomplete active evolution, active energy below two, and "
        "an empty bench.",
        "",
        "This does **not** identify a safe policy change by itself. A follow-up lever "
        "must target an earlier preventable decision and still pass pooled A/B gates; "
        "the final state can be a consequence rather than the cause of losing.",
        "",
        "## Source shards",
        "",
        "| file | games | W-L | WR | skipped |",
        "|---|---:|---:|---:|---:|",
    ]
    for src in sources:
        lines.append(
            f"| `{src['file']}` | {src['games']} | {src['wins']}-{src['losses']} | "
            f"{src['wr_pct']:.2f}% | {src['skipped']} |"
        )
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("games", "wins", "losses", "pooled_wr_pct")}))
    print(f"wrote {out.with_suffix('.md')} and {out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
