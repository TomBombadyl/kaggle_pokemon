"""Wire the cabt engine into place on a Kaggle notebook (or any fresh clone).

Our code expects the engine at data/sim/sample_submission/cg/ (9 scripts hardcode
that path). The engine binary (Linux libcg.so) is NOT in git — it ships with the
*Simulation* competition `pokemon-tcg-ai-battle`. On a Kaggle notebook that
competition is mounted read-only under /kaggle/input/...; this copies the engine
(and EN_Card_Data.csv) into the repo so every script works unchanged.

Idempotent: if data/sim/sample_submission/cg already has the engine, it no-ops
(local dev machines that ran fetch_sim_engine.py are untouched).

    # On Kaggle, after attaching the 'pokemon-tcg-ai-battle' competition:
    python scripts/kaggle_setup.py
"""

from __future__ import annotations

import glob
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DST = ROOT / "data" / "sim" / "sample_submission"
CARDS_DST = ROOT / "data" / "EN_Card_Data.csv"


def _find_competition_root() -> Path | None:
    """Locate the mounted competition dir containing sample_submission/cg."""
    # Prefer the named mount, then any /kaggle/input match, then kagglehub cache.
    candidates = [
        "/kaggle/input/pokemon-tcg-ai-battle",
        "/kaggle/input/*pokemon*tcg*",
    ]
    for pat in candidates:
        for hit in sorted(glob.glob(pat)):
            if (Path(hit) / "sample_submission" / "cg").is_dir():
                return Path(hit)
    # Fallback: deep glob for the engine's sim.py anywhere under /kaggle/input.
    for hit in glob.glob("/kaggle/input/**/sample_submission/cg/sim.py", recursive=True):
        return Path(hit).parents[2]
    return None


def main() -> int:
    engine_ok = (ENGINE_DST / "cg" / "sim.py").exists() and (
        (ENGINE_DST / "cg" / "libcg.so").exists() or (ENGINE_DST / "cg" / "cg.dll").exists()
    )
    if engine_ok:
        print(f"[ok] engine already present at {ENGINE_DST / 'cg'} — nothing to do")
    else:
        comp = _find_competition_root()
        if comp is None:
            print("[ERROR] Could not find the cabt engine. On Kaggle, add the "
                  "'pokemon-tcg-ai-battle' competition via 'Add Input'. Locally, "
                  "run: python scripts/fetch_sim_engine.py")
            return 2
        print(f"[copy] competition root: {comp}")
        src_engine = comp / "sample_submission"
        ENGINE_DST.parent.mkdir(parents=True, exist_ok=True)
        if ENGINE_DST.exists():
            shutil.rmtree(ENGINE_DST)
        shutil.copytree(src_engine, ENGINE_DST)
        print(f"[copy] {src_engine} -> {ENGINE_DST}")
        src_cards = comp / "EN_Card_Data.csv"
        if src_cards.exists() and not CARDS_DST.exists():
            shutil.copy2(src_cards, CARDS_DST)
            print(f"[copy] {src_cards} -> {CARDS_DST}")

    # Verify the engine actually imports + starts a battle.
    sys.path.insert(0, str(ENGINE_DST))
    sys.path.insert(0, str(ROOT))
    try:
        from cg import game  # noqa: WPS433
        deck = [int(x) for x in (ENGINE_DST / "deck.csv").read_text().splitlines() if x.strip()]
        obs, start = game.battle_start(deck, deck)
        game.battle_finish()
        if obs is None:
            print(f"[ERROR] engine loaded but battle_start failed: {start.errorType}")
            return 3
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] engine import/start failed: {type(exc).__name__}: {exc}")
        return 4
    print("[ok] engine verified: import + battle_start OK")
    print("\nReady. Example training command:")
    print("  python scripts/train_track_b_deck.py --deck report/rl_deck_campaign/best_deck.csv \\")
    print("    --slug rl_deck --timesteps 100000 --n-envs 4 --opponents benchmark \\")
    print("    --holdout a2_kyogre --gate-games 40 --package --promote")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
