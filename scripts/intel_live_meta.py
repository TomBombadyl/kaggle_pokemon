"""INTEL: live top-band archetype distribution from freshly pulled replays.

`field/weights.json` is still sourced from `deck_by_mu_band_2026-06-26.json`, whose
archetype shares came from **47** parsed replays, most of them in the
`unmanifested_recent` bucket rather than a mu band. This recomputes the field
mixture from `recordings/episodes_high_value/replays/*.json` -- the top-N public
episodes pulled today -- and counts every deck actually seen on both sides, not
just the puller's own representative deck.

Output:
  recordings/intel/live_meta_<date>.json   machine-readable shares + Wilson CIs
  report/OPPONENT_DECK_DISTRIBUTION_live.md   human table + weights_v2 proposal

Diagnostic only: it does NOT write field/weights.json. The delta is a proposal for
director/arch, because changing the mixture moves every weighted gate at once.

  python scripts/intel_live_meta.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.extract_deck_from_episode import (  # noqa: E402
    classify_archetype,
    extract_decks_from_file,
    load_card_table,
)
from scripts.stats_utils import wilson_ci  # noqa: E402

HV_ROOT = ROOT / "recordings" / "episodes_high_value"
OUT_JSON_DIR = ROOT / "recordings" / "intel"
OUT_MD = ROOT / "report" / "OPPONENT_DECK_DISTRIBUTION_live.md"

# Archetype key used by field/weights.json + agent/matchup_levers.py.
KEY_MAP = {
    "marnie_grimmsnarl_ex": "marnie_grimmsnarl_ex",
    "mega_kangaskhan_ogerpon": "mega_kangaskhan_ogerpon",
    "crustle_iwapalace": "crustle_iwapalace",
    "dragapult_ex": "dragapult_psychic",
    "mega_lucario_ex": "lucario_mirror",
    "alakazam": "alakazam_psychic",
    "iono": "iono_lightning",
    "kyogre": "kyogre_water",
    "mega_abomasnow_ex": "abomasnow_water",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replays", default=str(HV_ROOT / "replays"))
    ap.add_argument(
        "--exclude-ids",
        default=None,
        help="JSON file with {'ids': [...]}; those episodes are skipped. Use a "
             "pre-pull snapshot here to read ONLY the freshly pulled episodes, "
             "which makes the resulting mixture an independent second sample "
             "rather than a re-read of the same replays.",
    )
    ap.add_argument("--tag", default="", help="suffix for the output filenames")
    args = ap.parse_args()

    replay_dir = Path(args.replays)
    files = sorted(replay_dir.glob("ep*.json"))
    excluded = 0
    if args.exclude_ids:
        skip = set(json.loads(Path(args.exclude_ids).read_text(encoding="utf-8"))["ids"])
        keep = [f for f in files if "".join(c for c in f.stem if c.isdigit()) not in skip]
        excluded = len(files) - len(keep)
        files = keep
    if not files:
        print(f"[error] no replays under {replay_dir} (excluded {excluded})")
        return 1

    idx_path = HV_ROOT / "index.json"
    ep_owner: dict[str, dict] = {}
    if idx_path.exists():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        for e in idx.get("episodes", []):
            ep_owner[str(e.get("episode_id"))] = e

    cards = load_card_table()
    total = Counter()
    wins = Counter()
    decided = Counter()
    by_team: dict[str, Counter] = defaultdict(Counter)
    n_decks = 0

    for f in files:
        eid = "".join(ch for ch in f.stem if ch.isdigit())
        owner = ep_owner.get(eid, {})
        for rec in extract_decks_from_file(f):
            deck = rec.get("deck") or rec.get("deck_ids")
            if not deck or len(deck) != 60:
                continue
            arch = classify_archetype(list(deck), cards).get("primary_archetype") or "unknown"
            key = KEY_MAP.get(arch, arch)
            total[key] += 1
            n_decks += 1
            team = rec.get("team_name") or rec.get("team") or owner.get("team") or "?"
            by_team[str(team)][key] += 1
            reward = rec.get("reward")
            if reward is not None:
                decided[key] += 1
                if float(reward) > 0:
                    wins[key] += 1

    known = Counter({k: v for k, v in total.items() if k != "unknown"})
    known_n = sum(known.values()) or 1

    rows = []
    for key, cnt in known.most_common():
        share = cnt / known_n
        lo, hi = wilson_ci(cnt, known_n)
        wr = (100.0 * wins[key] / decided[key]) if decided[key] else None
        rows.append({
            "archetype": key,
            "decks_seen": cnt,
            "share": round(share, 4),
            "share_ci95": [round(lo, 4), round(hi, 4)],
            "decided_games": decided[key],
            "win_rate_pct": round(wr, 1) if wr is not None else None,
        })

    old = json.loads((ROOT / "field" / "weights.json").read_text(encoding="utf-8"))
    old_w = old.get("opponent_archetype_weights", {})

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d") + args.tag
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_replays": len(files),
        "excluded_replays": excluded,
        "decks_classified": n_decks,
        "unknown_decks": total.get("unknown", 0),
        "known_decks": known_n,
        "rows": rows,
        "proposed_weights_v2": {r["archetype"]: r["share"] for r in rows},
        "current_weights_v1": old_w,
        "current_weights_source": old.get("source"),
        "current_weights_updated": old.get("updated"),
    }
    OUT_JSON_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUT_JSON_DIR / f"live_meta_{stamp}.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    out_md = OUT_MD if not args.tag else OUT_MD.with_name(f"{OUT_MD.stem}{args.tag}.md")
    lines = [
        f"# Live top-band opponent distribution — {stamp}",
        "",
        f"- Replays parsed: **{len(files)}** (top public episodes pulled today"
        + (f", **{excluded} excluded** as already-seen → independent sample)" if excluded else ")"),
        f"- Decks classified: **{n_decks}** (unknown {total.get('unknown', 0)}, "
        f"known {known_n})",
        f"- Current `field/weights.json`: updated **{old.get('updated')}**, "
        f"source `{old.get('source')}`",
        "",
        "| Archetype | Decks seen | Live share | 95% CI | weights.json v1 | Δ |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for r in rows:
        v1 = old_w.get(r["archetype"])
        v1s = f"{v1:.3f}" if v1 is not None else "**absent**"
        delta = f"{r['share'] - v1:+.3f}" if v1 is not None else f"+{r['share']:.3f}"
        lines.append(
            f"| `{r['archetype']}` | {r['decks_seen']} | {r['share']:.3f} | "
            f"[{r['share_ci95'][0]:.3f}, {r['share_ci95'][1]:.3f}] | {v1s} | {delta} |"
        )
    dropped = [k for k in old_w if k not in {r["archetype"] for r in rows}]
    for k in dropped:
        lines.append(f"| `{k}` | 0 | 0.000 | [0.000, 0.043] | {old_w[k]:.3f} | -{old_w[k]:.3f} |")
    lines += [
        "",
        "Unknown decks are excluded from the share denominator; they are a real",
        "share of the field, so every number above is an upper bound on its archetype.",
        "",
        "This file is a proposal. `field/weights.json` is unchanged.",
    ]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print(f"\n[intel] wrote {out_json}")
    print(f"[intel] wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
