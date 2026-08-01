"""INTEL: bench a public/extracted agent as a full-game delegate on a given suite.

Answers the intel question "is there a public agent stronger than sample_75wr as
the Iono delegate?" by running each candidate's own `agent(obs)` as the hero brain
against the local field registry, on OUR hero deck (what a delegate actually plays).

  python scripts/intel_delegate_bench.py --candidate sample_archaludon_75wr --opponents real_iono --games 40

Candidates are directory names under extracted_agents/ (or an absolute path to a
dir holding main.py). Prints a POOLED-parseable `overall` line so Shard-Gate.ps1
can pool N independent shards.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ENGINE_DIR = ROOT / "data" / "sim" / "sample_submission"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

CAND_DIR = ROOT / "extracted_agents"

from eval.field_registry import opponents_for_suite  # noqa: E402
from eval.harness import DEFAULT_ARCHALUDON_DECK, load_deck, run_suite  # noqa: E402
from eval.gates import print_harness_summary  # noqa: E402


def load_candidate(name: str):
    """Import <candidate>/main.py as its own module; return its `agent` callable."""
    d = Path(name)
    if not d.is_absolute():
        d = CAND_DIR / name
    main_py = (d / "main.py").resolve()
    if not main_py.exists():
        raise FileNotFoundError(f"no main.py under {d}")
    cwd = os.getcwd()
    os.chdir(main_py.parent)  # module-level open("deck.csv") must resolve
    sys.path.insert(0, str(main_py.parent))
    try:
        spec = importlib.util.spec_from_file_location(f"cand_{uuid.uuid4().hex}", main_py)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
        try:
            sys.path.remove(str(main_py.parent))
        except ValueError:
            pass
    fn = getattr(mod, "agent", None)
    if fn is None:
        raise AttributeError(f"{main_py} exposes no `agent`")
    return fn


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", required=True, help="extracted_agents/<name> or abs dir")
    ap.add_argument("--games", type=int, default=40, help="games per opponent (seat-swapped)")
    ap.add_argument("--suite", default="", help="registry suite (alt to --opponents)")
    ap.add_argument("--opponents", nargs="*", default=None)
    ap.add_argument("--hero-deck", default=None,
                    help="deck CSV the delegate plays (default: our archaludon deck)")
    ap.add_argument("--own-deck", action="store_true",
                    help="use the candidate's bundled deck.csv instead of the hero deck")
    ap.add_argument("--handshake", action="store_true",
                    help="replay Kaggle's deck-selection call agent({'select': None}) before "
                         "playing. Many public agents pick their route/specialist there and "
                         "otherwise fall back to a stub policy. Implies --own-deck using the "
                         "60 card ids the handshake returns (unless --hero-deck is given).")
    args = ap.parse_args(argv)

    opponents = args.opponents or (opponents_for_suite(args.suite) if args.suite else ["real_iono"])
    brain = load_candidate(args.candidate)

    handshake_deck = None
    if args.handshake:
        try:
            picked = brain({"select": None})
        except Exception as exc:  # noqa: BLE001 - report, don't crash the shard
            print(f"[warn] handshake raised {exc!r}; continuing without it", flush=True)
            picked = None
        if isinstance(picked, list) and len(picked) == 60 and all(isinstance(v, int) for v in picked):
            tmp = ROOT / "recordings" / "intel" / f"handshake_{Path(args.candidate).name}.deck"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text("\n".join(str(v) for v in picked))
            handshake_deck = str(tmp)
            print(f"[handshake] agent selected a 60-card deck -> {tmp.name}", flush=True)
        else:
            print(f"[handshake] agent returned {type(picked).__name__} "
                  f"len={len(picked) if isinstance(picked, list) else 'n/a'}; "
                  "no deck adopted", flush=True)

    if args.hero_deck:
        deck = str(args.hero_deck)
    elif handshake_deck:
        deck = handshake_deck
    elif args.own_deck:
        own = (CAND_DIR / args.candidate / "deck.csv")
        if not own.exists():
            print(f"[warn] {own} missing; falling back to hero deck", flush=True)
            deck = str(DEFAULT_ARCHALUDON_DECK)
        else:
            deck = str(own)
    else:
        deck = str(DEFAULT_ARCHALUDON_DECK)

    label = Path(args.candidate).name
    print(f"candidate={label} deck={Path(deck).name} opponents={opponents} games={args.games}",
          flush=True)

    # sanity: the deck must load before we burn engine time
    load_deck(deck)

    result = run_suite(
        brain, deck, opponents,
        games_per_opp=args.games,
        hero_brain_label=f"intel:{label}",
    )
    if not result.matchups:
        print("No opponents gated.")
        return 1
    print_harness_summary(result)
    # Shard-Gate parseable line
    print(f"overall wr={result.overall_wr_pct:.1f}% "
          f"({result.overall_wins}/{result.overall_games}) "
          f"ci95=[{result.overall_ci_low_pct:.1f},{result.overall_ci_high_pct:.1f}]", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
