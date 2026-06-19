"""Track B gate: LearnedScorer vs SearchScorer vs meta pool (SPRT + packaging)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.arena import play_matchup, pool_decks  # noqa: E402
from scripts.stats_utils import sprt_test  # noqa: E402

REPORT = ROOT / "report" / "track_b_gate.md"
MODEL = ROOT / "agent" / "models" / "bc_v1.npz"


def eval_learned(deck: list[int], opponents: dict[str, list[int]], games: int) -> tuple[int, int]:
    wins = losses = 0
    deck_path = str(ROOT / "agent" / "deck.csv")
    for name, opp_deck in opponents.items():
        row = play_matchup(
            "learned", deck, name, opp_deck, games, 6000,
            workers=1, scorer_a="learned", deck_path_a=deck_path,
        )
        wins += row["a_wins"]
        losses += row["b_wins"]
    return wins, wins + losses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=8)
    args = parser.parse_args(argv)

    if not MODEL.exists():
        print(f"missing BC model: {MODEL}; run scripts/train_bc.py first")
        return 1

    deck = [int(x) for x in (ROOT / "agent" / "deck.csv").read_text().splitlines() if x.strip()]
    opponents = pool_decks()
    l_wins, l_total = eval_learned(deck, opponents, args.games)

    from scripts.gate_track_a import eval_scorer

    s_wins, s_total = eval_scorer("search", deck, opponents, args.games)
    sprt = sprt_test(l_wins, l_total)
    passed = l_wins >= s_wins or sprt.decision == "accept_b"

    package_note = ""
    if passed:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "package_submission.py"),
             "--name", "track_b_learned"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        package_note = proc.stdout.strip() or proc.stderr.strip()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "\n".join([
            "# Track B BC gate report",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            f"- Learned wins vs pool: {l_wins}/{l_total}",
            f"- Search baseline: {s_wins}/{s_total}",
            f"- SPRT: {sprt.decision}",
            f"- Gate passed: **{passed}**",
            "",
            package_note,
        ]) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {REPORT}; gate passed={passed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
