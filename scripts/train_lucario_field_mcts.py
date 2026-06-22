"""Local field-opponent RL+MCTS training for Mega Lucario ex (fresh start).

Trains from scratch on the real Lucario deck vs 10 mined field opponents.
CPU-first (simulator-bound). No resume from old Snorlax-era checkpoints.

  python scripts/train_lucario_field_mcts.py --device cpu

Outputs: rl_mcts_field/lucarioex_v1/model{cycle}.pth, model_best.pth, metrics.csv, run_meta.json
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import lucario_mcts_runtime as rt  # noqa: E402

DEFAULT_OPPONENTS = [
    "real_mega_lucario_ex",
    "real_dragapult_ex",
    "real_mega_abomasnow_ex",
    "real_iono",
    "top_mined_alakazam",
    "top_mined_trevenant",
    "top_mined_dragapult_ex",
    "top_mined_iono",
    "top_mined_mega_abomasnow_ex",
    "top_mined_mega_lucario_ex",
]


def load_deck(path: Path) -> list[int]:
    ids = [int(line.strip()) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(ids) != 60:
        raise ValueError(f"{path} has {len(ids)} cards, expected 60")
    return ids


def discover_opponents(decks_dir: Path, names: list[str] | None) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    wanted = set(names or DEFAULT_OPPONENTS)
    for csv_path in sorted(decks_dir.glob("*.csv")):
        stem = csv_path.stem
        if names is not None and stem not in wanted:
            continue
        out[stem] = load_deck(csv_path)
    missing = wanted - set(out)
    if missing:
        raise FileNotFoundError(f"missing opponent decks in {decks_dir}: {sorted(missing)}")
    return out


def make_opponent(kind: str, deck_path: str, opp_deck: list[int]):
    if kind == "random":
        return rt.random_agent
    if kind == "lucario":
        from agent.agent import build_agent
        from agent.lucario_policy import LucarioScorer

        agent = build_agent(deck_path=deck_path, scorer=LucarioScorer(deck_path=deck_path))
        return lambda obs: agent.act(obs)
    raise ValueError(f"unknown opponent kind: {kind}")


def collect_vs_opponent(deck, opp_deck, opp_move, model, n_games: int) -> list:
    out: list = []
    for g in range(n_games):
        your_index = g % 2
        decks = (deck, opp_deck) if your_index == 0 else (opp_deck, deck)
        obs, start = rt.battle_start(*decks)
        if start.errorPlayer >= 0:
            raise ValueError(f"deck error type={start.errorType}")
        mine, ply = [], 0
        while obs["current"]["result"] < 0:
            if obs["current"]["yourIndex"] == your_index:
                temp = 1.0 if ply < rt.TEMP_PLIES else 0.0
                selected, sample = rt.mcts_agent(
                    obs, deck, model, opp_deck=opp_deck, add_noise=True, temperature=temp,
                )
                mine.append(sample)
            else:
                selected = opp_move(obs)
            obs = rt.battle_select(selected)
            ply += 1
        rt.battle_finish()
        rt.label_samples(mine, obs["current"]["result"], your_index, out)
    return out


def eval_matchup(deck, opp_deck, opp_move, model, games: int) -> tuple[int, int, int]:
    wins = losses = draws = 0
    model.eval()
    with torch.inference_mode():
        for i in range(games):
            your_index = i % 2
            decks = (deck, opp_deck) if your_index == 0 else (opp_deck, deck)
            obs, start = rt.battle_start(*decks)
            if start.errorPlayer >= 0:
                raise ValueError(f"deck error type={start.errorType}")
            while obs["current"]["result"] < 0:
                if obs["current"]["yourIndex"] == your_index:
                    selected, _ = rt.mcts_agent(obs, deck, model, opp_deck=opp_deck)
                else:
                    selected = opp_move(obs)
                obs = rt.battle_select(selected)
            rt.battle_finish()
            r = obs["current"]["result"]
            if r == 2:
                draws += 1
            elif r == your_index:
                wins += 1
            else:
                losses += 1
    return wins, losses, draws


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-deck", default="agent_decks/real_mega_lucario_ex.csv")
    ap.add_argument("--decks-dir", default="agent_decks")
    ap.add_argument("--opponents", default="", help="Comma-separated stems; default = 10 field decks")
    ap.add_argument("--cycles", type=int, default=5)
    ap.add_argument("--games-per-opponent", type=int, default=20)
    ap.add_argument("--selfplay-games", type=int, default=40)
    ap.add_argument("--eval-games", type=int, default=20)
    ap.add_argument("--opponent-brain", default="random", choices=("random", "lucario"))
    ap.add_argument("--eval-opponent", default="random", choices=("random", "lucario"))
    ap.add_argument("--search-count", type=int, default=12)
    ap.add_argument("--gate-games", type=int, default=20)
    ap.add_argument("--gate-winrate", type=float, default=0.55)
    ap.add_argument("--replay-iters", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda", "auto"))
    ap.add_argument("--work", default="rl_mcts_field/lucarioex_v1")
    ap.add_argument("--time-budget-sec", type=float, default=0.0, help="0 = no limit")
    ap.add_argument("--smoke", action="store_true", help="1 cycle, 2 games/opponent")
    args = ap.parse_args(argv)

    if args.smoke:
        args.cycles = 1
        args.games_per_opponent = 2
        args.selfplay_games = 4
        args.eval_games = 2
        args.gate_games = 4

    rt.SEARCH_COUNT = args.search_count
    rt.GATE_GAMES = args.gate_games
    rt.GATE_WINRATE = args.gate_winrate
    rt.REPLAY_ITERS = args.replay_iters
    rt.BATCH_SIZE = args.batch_size
    rt.LR = args.lr
    rt.SELFPLAY_GAMES = args.selfplay_games
    rt.EVAL_GAMES = args.eval_games

    random.seed(rt.SEED)
    torch.manual_seed(rt.SEED)

    train_deck_path = ROOT / args.train_deck
    deck = load_deck(train_deck_path)
    decks_dir = ROOT / args.decks_dir
    opp_names = [s.strip() for s in args.opponents.split(",") if s.strip()] or None
    opponents = discover_opponents(decks_dir, opp_names)

    work = ROOT / args.work
    work.mkdir(parents=True, exist_ok=True)

    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)

    print(
        f"device={device} search={rt.SEARCH_COUNT} cycles={args.cycles} "
        f"opponents={len(opponents)} work={work}",
        flush=True,
    )

    model = rt.MyModel(rt.D_MODEL, rt.NUM_HEADS, rt.D_FF, rt.ENC_LAYERS, rt.DEC_LAYERS).to(device)
    champion = rt.MyModel(rt.D_MODEL, rt.NUM_HEADS, rt.D_FF, rt.ENC_LAYERS, rt.DEC_LAYERS).to(device)
    champion.load_state_dict(model.state_dict())

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max(1, args.cycles * len(opponents)),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    loss_fn_enc = torch.nn.HuberLoss(delta=0.2)
    loss_fn_dec = torch.nn.HuberLoss(reduction="none", delta=0.1)

    metrics_path = work / "metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow([
            "cycle", "opponent", "phase", "wins", "losses", "draws", "wr_pct",
            "n_samples", "loss", "promoted", "elapsed_s",
        ])

    replay: list[list] = []
    t0 = time.time()

    for cycle in range(args.cycles):
        if args.time_budget_sec > 0 and time.time() - t0 > args.time_budget_sec:
            print(f"time budget reached before cycle {cycle}", flush=True)
            break

        torch.save(model.state_dict(), work / f"model{cycle}.pth")
        eval_summary: dict[str, float] = {}

        for opp_name, opp_deck in opponents.items():
            opp_move = make_opponent(
                args.eval_opponent, str(decks_dir / f"{opp_name}.csv"), opp_deck,
            )
            w, l, d = eval_matchup(deck, opp_deck, opp_move, champion, args.eval_games)
            wr = 100.0 * w / max(1, w + l)
            eval_summary[opp_name] = wr
            print(f"[cycle {cycle}] eval {opp_name}: {wr:.1f}% (W{w}/L{l}/D{d})", flush=True)
            with metrics_path.open("a", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow([
                    cycle, opp_name, "eval", w, l, d, round(wr, 1), 0, "", 0, round(time.time() - t0, 1),
                ])

        cycle_samples: list = []
        for _ in rt.progress(args.selfplay_games, f"[cycle {cycle}] mirror "):
            cycle_samples.extend(rt.selfplay_game(model, deck))

        for opp_name, opp_deck in opponents.items():
            opp_move = make_opponent(
                args.opponent_brain, str(decks_dir / f"{opp_name}.csv"), opp_deck,
            )
            got = collect_vs_opponent(deck, opp_deck, opp_move, model, args.games_per_opponent)
            cycle_samples.extend(got)
            print(f"[cycle {cycle}] +{len(got)} samples vs {opp_name}", flush=True)

        replay.append(cycle_samples)
        if len(replay) > args.replay_iters:
            replay.pop(0)
        train_pool = [s for chunk in replay for s in chunk]

        loss = rt.train_on_samples(
            model, optimizer, scheduler, scaler, device, loss_fn_enc, loss_fn_dec, train_pool,
        )
        gate_wr = rt.eval_vs_model(model, champion, deck, args.gate_games)
        promoted = gate_wr >= args.gate_winrate
        if promoted:
            champion.load_state_dict(model.state_dict())

        torch.save(model.state_dict(), work / "model_latest.pth")
        if promoted:
            torch.save(champion.state_dict(), work / "model_best.pth")

        mean_wr = sum(eval_summary.values()) / max(1, len(eval_summary))
        print(
            f"[cycle {cycle}] loss={loss:.4f} gate={gate_wr:.3f} promoted={int(promoted)} "
            f"mean_eval_wr={mean_wr:.1f}% samples={len(train_pool)}",
            flush=True,
        )
        with metrics_path.open("a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow([
                cycle, "ALL", "train", "", "", "", round(mean_wr, 1),
                len(train_pool), round(loss, 5), int(promoted), round(time.time() - t0, 1),
            ])

    if not (work / "model_best.pth").exists():
        torch.save(champion.state_dict(), work / "model_best.pth")

    meta = {
        "train_deck": str(train_deck_path.relative_to(ROOT)),
        "opponents": list(opponents.keys()),
        "cycles": args.cycles,
        "source_checkpoint": None,
        "config": {
            "LUC_D_MODEL": rt.D_MODEL,
            "LUC_HEADS": rt.NUM_HEADS,
            "LUC_D_FF": rt.D_FF,
            "LUC_ENC_LAYERS": rt.ENC_LAYERS,
            "LUC_DEC_LAYERS": rt.DEC_LAYERS,
            "LUC_SEARCH_COUNT": rt.SEARCH_COUNT,
            "opponent_brain": args.opponent_brain,
            "eval_opponent": args.eval_opponent,
        },
    }
    with (work / "run_meta.json").open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    print(f"DONE -> {work}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
