"""Diagnostic: teacher->student distillation fidelity.

Teacher (MaskablePPO) is strong but the distilled per-option LearnedScorer is
weak. Measure top-1 agreement: for each decision, does the student's argmax
option match the teacher's argmax? Low agreement => the tiny per-option scorer
cannot represent the teacher (capacity/feature problem), not an eval fluke.

    python scripts/diag_distill.py --deck report/rl_deck_campaign/best_deck.csv \
        --opponents benchmark --episodes 40
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL = ROOT / "agent" / "models" / "rl_policy.pt"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", required=True)
    parser.add_argument("--opponents", choices=("benchmark", "pool"), default="benchmark")
    parser.add_argument("--episodes", type=int, default=40)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--hidden", type=int, default=64)
    parser.add_argument("--student", default=str(ROOT / "agent" / "models" / "distilled_rl_deck_v1.npz"))
    args = parser.parse_args(argv)

    from scripts.distill_policy import (
        HIDDEN,
        IN_DIM,
        _load_teacher,
        collect_teacher_labels,
        train_student,
    )

    deck = ROOT / args.deck if not Path(args.deck).is_absolute() else Path(args.deck)
    model, env = _load_teacher(MODEL, deck, args.opponents)
    if model is None:
        print("teacher load failed")
        return 1
    print(f"collecting teacher labels ({args.episodes} eps)...")
    groups = collect_teacher_labels(model, env, args.episodes)
    env.close()
    print(f"decisions collected: {len(groups)}")

    # Distribution of option counts per decision (trivial 1-option decisions
    # inflate any agreement metric).
    n_opts = np.array([len(p) for _, p in groups])
    multi = n_opts > 1
    print(f"option-count: mean={n_opts.mean():.2f} max={n_opts.max()} "
          f"single-option(forced)={int((~multi).sum())}/{len(groups)}")

    # Existing distilled student
    data = np.load(args.student)
    w1, b1, w2, b2 = data["w1"], data["b1"], data["w2"].reshape(-1, 1), data["b2"]

    def student_scores(xs):
        h = np.tanh(xs @ w1 + b1)
        return (h @ w2 + b2).ravel()

    agree = agree_multi = total_multi = 0
    for xs, probs in groups:
        t_arg = int(np.argmax(probs))
        s_arg = int(np.argmax(student_scores(xs)))
        if t_arg == s_arg:
            agree += 1
        if len(probs) > 1:
            total_multi += 1
            if t_arg == s_arg:
                agree_multi += 1
    print("\n=== Existing distilled student (hidden=64, as shipped) ===")
    print(f"top-1 agreement (all):   {agree}/{len(groups)} = {agree/len(groups):.1%}")
    print(f"top-1 agreement (multi): {agree_multi}/{total_multi} = "
          f"{agree_multi/max(total_multi,1):.1%}")

    # Can a bigger / freshly-trained student do better on the SAME data?
    for hid in (args.hidden, 128, 256):
        import scripts.distill_policy as dp
        dp.HIDDEN = hid
        weights = train_student(groups, init=None, epochs=args.epochs)
        w1b = weights["w1"]; b1b = weights["b1"]
        w2b = weights["w2"].reshape(-1, 1); b2b = weights["b2"]

        def sc(xs, _w1=w1b, _b1=b1b, _w2=w2b, _b2=b2b):
            return (np.tanh(xs @ _w1 + _b1) @ _w2 + _b2).ravel()

        a = am = tm = 0
        for xs, probs in groups:
            t_arg = int(np.argmax(probs))
            s_arg = int(np.argmax(sc(xs)))
            a += t_arg == s_arg
            if len(probs) > 1:
                tm += 1
                am += t_arg == s_arg
        print(f"\n=== Fresh student hidden={hid}, epochs={args.epochs} (no BC init) ===")
        print(f"top-1 agreement (all):   {a}/{len(groups)} = {a/len(groups):.1%}")
        print(f"top-1 agreement (multi): {am}/{tm} = {am/max(tm,1):.1%}")
    dp.HIDDEN = HIDDEN
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
