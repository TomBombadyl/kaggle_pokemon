"""Track A gate: SPRT SearchScorer vs HeuristicScorer vs meta pool; package if pass."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.agent import Agent, HeuristicScorer  # noqa: E402
from agent.search_policy import SearchScorer  # noqa: E402
from scripts.arena import play_matchup, pool_decks  # noqa: E402
from scripts.stats_utils import sprt_test  # noqa: E402

REPORT = ROOT / "report" / "track_a_gate.md"

SCORERS = {
    "search": SearchScorer,
    "heuristic": HeuristicScorer,
}


def eval_scorer(scorer_name: str, deck: list[int], opponents: dict[str, list[int]], games: int) -> tuple[int, int]:
    wins = losses = 0
    deck_path = str(ROOT / "agent" / "deck.csv")
    for name, opp_deck in opponents.items():
        row = play_matchup(
            scorer_name, deck, name, opp_deck, games, 6000,
            workers=1, scorer_a=scorer_name, deck_path_a=deck_path,
        )
        wins += row["a_wins"]
        losses += row["b_wins"]
    return wins, wins + losses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=8)
    parser.add_argument("--p1", type=float, default=0.52, help="SPRT null win rate")
    parser.add_argument("--p2", type=float, default=0.58, help="SPRT alt win rate")
    args = parser.parse_args(argv)

    deck = [int(x) for x in (ROOT / "agent" / "deck.csv").read_text().splitlines() if x.strip()]
    opponents = pool_decks()
    if not opponents:
        print("no pool decks; run scripts/validate_deck.py first")
        return 1

    s_wins, s_total = eval_scorer("search", deck, opponents, args.games)
    h_wins, h_total = eval_scorer("heuristic", deck, opponents, args.games)

    sprt = sprt_test(s_wins, s_total, p0=args.p1, p1=args.p2)
    passed = sprt.decision == "accept_b" or (s_wins / max(1, s_total) > h_wins / max(1, h_total) + 0.02)

    package_path = ""
    submit_cmd = ""
    if passed:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "package_submission.py"),
             "--name", "track_a_search", "--agent-module", "agent.agent"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        package_path = str(ROOT / "dist" / "candidates" / "track_a_search.tar.gz")
        submit_cmd = (
            f"kaggle competitions submit -c pokemon-tcg-ai-battle "
            f"-f {package_path} -m \"Track A SearchScorer probe (user approval required)\""
        )
        gate_note = proc.stdout.strip() or proc.stderr.strip()
    else:
        gate_note = "gate not passed; no package built"

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "\n".join([
            "# Track A gate report",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## SPRT (SearchScorer vs pool)",
            f"- Search wins: {s_wins}/{s_total} ({100*s_wins/max(1,s_total):.1f}%)",
            f"- Heuristic wins: {h_wins}/{h_total} ({100*h_wins/max(1,h_total):.1f}%)",
            f"- SPRT decision: **{sprt.decision}** (log_ratio={sprt.log_ratio:.3f})",
            f"- Gate passed: **{passed}**",
            "",
            "## Packaging",
            f"- Package: `{package_path}`" if package_path else "- Package: (not built)",
            "",
            "## Suggested submit command (DO NOT run automatically)",
            "```",
            submit_cmd or "(none — gate failed)",
            "```",
            "",
            "## Notes",
            gate_note,
            "",
            "Wire SearchScorer in submission by replacing default agent factory:",
            "```python",
            "from agent.search_policy import SearchScorer",
            "from agent.agent import build_agent",
            "_AGENT = build_agent(scorer=SearchScorer())",
            "```",
        ]) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {REPORT}; gate passed={passed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
