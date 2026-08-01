"""Local field-opponent RL+MCTS training for Mega Lucario ex.

Trains our Lucario deck vs field opponents. **Default:** 9 decks in `agent_decks/`,
each with its own **official Kaggle rule pilot** (LucarioScorer / dragapult_agent /
iono_agent / abomasnow_agent). Mined Alakazam and Trevenant are excluded unless
`--include-random-opponents` (requires `--opponent-brain non_official`).

Before training:

  python scripts/verify_official_opponents.py
  powershell -File scripts/fetch_official_rule_samples.ps1
  python scripts/bootstrap_official_rule_agents.py

  python scripts/train_lucario_field_mcts.py --device cuda --cycles 25

Default: **no mirror** — train and promote only vs official field pilots (kiyotah rules).
Use --mirror-brain native only if you explicitly want same-deck mirror practice.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import lucario_mcts_runtime as rt  # noqa: E402
from agent.lucario_policy import is_lucario_deck  # noqa: E402
from agent.native_opponent import make_opponent_brain, native_brain_label  # noqa: E402
from agent.official_registry import (  # noqa: E402
    OFFICIAL_FIELD_DECK_STEMS,
    RANDOM_ONLY_DECK_STEMS,
    list_missing_official_samples,
    official_archetype_for_opponent,
)

OFFICIAL_FIELD_OPPONENTS = list(OFFICIAL_FIELD_DECK_STEMS)
RANDOM_ONLY_OPPONENTS = list(RANDOM_ONLY_DECK_STEMS)
DEFAULT_OPPONENTS = OFFICIAL_FIELD_OPPONENTS

METRICS_HEADER = [
    "cycle", "opponent", "phase", "wins", "losses", "draws", "wr_pct",
    "n_samples", "loss", "promoted", "elapsed_s",
]


def load_deck(path: Path) -> list[int]:
    ids = [int(line.strip()) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(ids) != 60:
        raise ValueError(f"{path} has {len(ids)} cards, expected 60")
    return ids


def discover_opponents(
    decks_dir: Path,
    names: list[str] | None,
    *,
    include_random: bool = False,
) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    wanted = set(names or DEFAULT_OPPONENTS)
    if include_random:
        wanted |= set(RANDOM_ONLY_OPPONENTS)
    for csv_path in sorted(decks_dir.glob("*.csv")):
        stem = csv_path.stem
        if stem not in wanted:
            continue
        out[stem] = load_deck(csv_path)
    missing = wanted - set(out)
    if missing:
        raise FileNotFoundError(f"missing opponent decks in {decks_dir}: {sorted(missing)}")
    return out


def games_for_opponent(opp_deck: list[int], base: int, lucario_mult: int) -> int:
    if lucario_mult > 1 and is_lucario_deck(opp_deck):
        return base * lucario_mult
    return base


def collect_vs_opponent(deck, opp_deck, opp_move, model, n_games: int, *, opp_name: str = "") -> list:
    out: list = []
    use_clock = rt.PLAYER_CLOCK_ENABLED
    for g in range(n_games):
        your_index = g % 2
        decks = (deck, opp_deck) if your_index == 0 else (opp_deck, deck)
        obs, start = rt.battle_start(*decks)
        if start.errorPlayer >= 0:
            raise ValueError(f"deck error type={start.errorType}")
        rt.set_training_opponent_context(opp_name, opp_deck)
        clock = rt.PlayerClock() if use_clock else None
        mine, ply = [], 0
        forfeit_result = None
        try:
            while obs["current"]["result"] < 0 and forfeit_result is None:
                yi = obs["current"]["yourIndex"]
                if yi == your_index:
                    temp = 1.0 if ply < rt.TEMP_PLIES else 0.0
                    if clock is not None:
                        selected, sample, forfeit_result = rt.timed_mcts(
                            rt.mcts_agent,
                            obs,
                            clock,
                            yi,
                            deck,
                            model,
                            opp_deck=opp_deck,
                            add_noise=True,
                            temperature=temp,
                        )
                    else:
                        selected, sample = rt.mcts_agent(
                            obs, deck, model, opp_deck=opp_deck, add_noise=True, temperature=temp,
                        )
                    mine.append(sample)
                else:
                    if clock is not None:
                        selected, forfeit_result = rt.timed_act(opp_move, obs, clock, yi)
                    else:
                        selected = opp_move(obs)
                if forfeit_result is None:
                    obs = rt.battle_select(selected)
                ply += 1
        finally:
            rt.clear_training_opponent_context()
        rt.battle_finish()
        result = forfeit_result if forfeit_result is not None else obs["current"]["result"]
        rt.label_samples(mine, result, your_index, out)
    return out


def eval_matchup(
    deck, opp_deck, opp_move, model, games: int, *, opp_name: str = "",
) -> tuple[int, int, int]:
    wins = losses = draws = 0
    model.eval()
    use_clock = rt.PLAYER_CLOCK_ENABLED
    with torch.inference_mode():
        for i in range(games):
            your_index = i % 2
            decks = (deck, opp_deck) if your_index == 0 else (opp_deck, deck)
            obs, start = rt.battle_start(*decks)
            if start.errorPlayer >= 0:
                raise ValueError(f"deck error type={start.errorType}")
            clock = rt.PlayerClock() if use_clock else None
            forfeit_result = None
            while obs["current"]["result"] < 0 and forfeit_result is None:
                yi = obs["current"]["yourIndex"]
                if yi == your_index:
                    if clock is not None:
                        selected, _, forfeit_result = rt.timed_mcts(
                            rt.mcts_agent, obs, clock, yi, deck, model, opp_deck=opp_deck,
                        )
                    else:
                        selected, _ = rt.mcts_agent(obs, deck, model, opp_deck=opp_deck)
                else:
                    if clock is not None:
                        selected, forfeit_result = rt.timed_act(opp_move, obs, clock, yi)
                    else:
                        selected = opp_move(obs)
                if forfeit_result is None:
                    obs = rt.battle_select(selected)
            rt.battle_finish()
            r = forfeit_result if forfeit_result is not None else obs["current"]["result"]
            if r == 2:
                draws += 1
            elif r == your_index:
                wins += 1
            else:
                losses += 1
    return wins, losses, draws


def _append_metrics_row(metrics_path: Path, row: list) -> None:
    with metrics_path.open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(row)
        fh.flush()


def opponents_without_official_sample(opponents: dict[str, list[int]]) -> set[str]:
    from agent.official_registry import official_archetype_for_opponent

    return {
        name for name, deck in opponents.items()
        if official_archetype_for_opponent(name, deck) is None
    }


def brain_kind(cli: str) -> str:
    """Map CLI brain flag to native_opponent kind."""
    if cli == "random":
        return "random"
    if cli == "non_official":
        return "non_official"
    return "native"


def preload_opponent_pilots(
    opponents: dict[str, list[int]],
    decks_dir: Path,
    args,
) -> dict[str, str]:
    """Build each opponent pilot once; fail fast if official sample missing."""
    resolved: dict[str, str] = {}
    for kind_attr in ("opponent_brain", "eval_opponent"):
        kind = brain_kind(getattr(args, kind_attr))
        for name, opp_deck in opponents.items():
            opp_path = str(decks_dir / f"{name}.csv")
            _, label = make_opponent_brain(
                kind,
                opp_path,
                opp_deck,
                opp_name=name,
                random_agent=rt.random_agent,
                non_official_brain=args.non_official_brain,
            )
            resolved[name] = label
    return resolved


def eval_field_mean(
    deck,
    opponents: dict[str, list[int]],
    decks_dir: Path,
    model,
    games: int,
    *,
    eval_opponent: str,
    non_official_brain: str,
) -> tuple[float, dict[str, float]]:
    """Mean win rate vs all field opponents using official pilots (native by default)."""
    summary: dict[str, float] = {}
    for opp_name, opp_deck in opponents.items():
        opp_path = str(decks_dir / f"{opp_name}.csv")
        opp_move, _ = make_opponent_brain(
            brain_kind(eval_opponent),
            opp_path,
            opp_deck,
            opp_name=opp_name,
            random_agent=rt.random_agent,
            non_official_brain=non_official_brain,
        )
        w, l, d = eval_matchup(deck, opp_deck, opp_move, model, games, opp_name=opp_name)
        summary[opp_name] = 100.0 * w / max(1, w + l)
    mean_wr = sum(summary.values()) / max(1, len(summary))
    return mean_wr, summary


def write_run_meta(
    work: Path,
    train_deck_path: Path,
    opponents: dict[str, list[int]],
    args,
    *,
    completed_cycles: int,
    source_checkpoint: str | None,
    opponent_brains: dict[str, str],
) -> None:
    meta = {
        "train_deck": str(train_deck_path.relative_to(ROOT)),
        "opponents": list(opponents.keys()),
        "cycles": args.cycles,
        "completed_cycles": completed_cycles,
        "source_checkpoint": source_checkpoint,
        "opponent_brains": opponent_brains,
        "config": {
            "LUC_D_MODEL": rt.D_MODEL,
            "LUC_HEADS": rt.NUM_HEADS,
            "LUC_D_FF": rt.D_FF,
            "LUC_ENC_LAYERS": rt.ENC_LAYERS,
            "LUC_DEC_LAYERS": rt.DEC_LAYERS,
            "LUC_SEARCH_COUNT": rt.SEARCH_COUNT,
            "LUC_DETERMINIZATIONS": rt.DETERMINIZATIONS,
            "LUC_PUCT_C": rt.PUCT_C,
            "LUC_PRIOR_BLEND": rt.PRIOR_BLEND,
            "LUC_POLICY_TARGET": rt.POLICY_TARGET,
            "opponent_brain": args.opponent_brain,
            "eval_opponent": args.eval_opponent,
            "mirror_brain": args.mirror_brain,
            "lucario_mirror_games": args.lucario_mirror_games,
            "gate_mode": args.gate_mode,
            "lucario_game_mult": args.lucario_game_mult,
            "lever_blend": args.lever_blend,
            "non_official_brain": args.non_official_brain,
            "player_clock_sec": rt.PLAYER_CLOCK_LIMIT_SEC,
            "player_clock_enabled": rt.PLAYER_CLOCK_ENABLED,
            "deck_scope_enabled": not args.no_deck_scope,
        },
    }
    with (work / "run_meta.json").open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_checkpoint(work: Path) -> dict | None:
    path = work / "checkpoint.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_checkpoint(
    work: Path,
    *,
    status: str,
    completed_cycles: int,
    next_cycle: int,
    total_cycles: int,
    args,
    source_checkpoint: str | None,
    interrupted: bool = False,
) -> None:
    payload = {
        "status": status,
        "completed_cycles": completed_cycles,
        "next_cycle": next_cycle,
        "total_cycles": total_cycles,
        "interrupted": interrupted,
        "updated_at": _utc_now(),
        "pid": os.getpid(),
        "work": str(work),
        "resume_from": "model_latest.pth",
        "champion_from": "model_best.pth",
        "source_checkpoint": source_checkpoint,
        "start_cycle_flag": f"--start-cycle {next_cycle}",
        "resume_flag": "--resume-from model_latest.pth",
        "config": {
            "opponent_brain": args.opponent_brain,
            "lever_blend": args.lever_blend,
            "cycles": total_cycles,
        },
    }
    tmp = work / "checkpoint.json.tmp"
    out = work / "checkpoint.json"
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(out)


# Set in main(); used by signal handler for crash-safe saves.
_SHUTDOWN_CTX: dict | None = None


def _emergency_checkpoint(reason: str) -> None:
    ctx = _SHUTDOWN_CTX
    if not ctx:
        return
    try:
        work: Path = ctx["work"]
        model = ctx["model"]
        champion = ctx["champion"]
        completed = int(ctx.get("completed_cycles", 0))
        next_c = int(ctx.get("current_cycle", completed))
        torch.save(model.state_dict(), work / "model_latest.pth")
        torch.save(champion.state_dict(), work / "model_best.pth")
        write_checkpoint(
            work,
            status="interrupted",
            completed_cycles=completed,
            next_cycle=next_c,
            total_cycles=ctx["total_cycles"],
            args=ctx["args"],
            source_checkpoint=ctx["source_checkpoint"],
            interrupted=True,
        )
        print(f"\nCHECKPOINT ({reason}) -> {work}/model_latest.pth", flush=True)
    except Exception as exc:
        print(f"\nCHECKPOINT FAILED ({reason}): {exc}", flush=True)


def _signal_handler(signum, frame) -> None:  # noqa: ARG001
    _emergency_checkpoint(f"signal {signum}")
    raise SystemExit(130)


def _install_signal_handlers() -> None:
    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_handler)


def _promote_candidate(
    args,
    deck,
    opponents: dict[str, list[int]],
    decks_dir: Path,
    model,
    champion,
    *,
    best_field_wr: float,
) -> tuple[bool, float, float, str]:
    """Return (promoted, gate_metric, champ_field_mean, gate_label)."""
    if args.gate_mode == "latest":
        return True, 100.0, best_field_wr, "latest"

    if args.gate_mode == "mirror":
        threshold = args.gate_winrate if args.gate_winrate > 0 else 0.55
        gate_wr = rt.eval_vs_model(model, champion, deck, args.gate_games)
        return gate_wr >= threshold, gate_wr * 100.0, best_field_wr, f"mirror_wr={gate_wr:.3f}"

    # field: promote when candidate beats champion on official pilots
    cand_mean, _ = eval_field_mean(
        deck,
        opponents,
        decks_dir,
        model,
        args.gate_games,
        eval_opponent=args.eval_opponent,
        non_official_brain=args.non_official_brain,
    )
    champ_mean, _ = eval_field_mean(
        deck,
        opponents,
        decks_dir,
        champion,
        args.gate_games,
        eval_opponent=args.eval_opponent,
        non_official_brain=args.non_official_brain,
    )
    min_wr = args.gate_winrate
    if min_wr > 0:
        promoted = cand_mean >= min_wr and cand_mean > champ_mean
    else:
        promoted = cand_mean > champ_mean
    return promoted, cand_mean, champ_mean, f"field_wr={cand_mean:.1f}% vs_champ={champ_mean:.1f}%"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-deck", default="agent_decks/real_mega_lucario_ex.csv")
    ap.add_argument("--decks-dir", default="agent_decks")
    ap.add_argument(
        "--include-random-opponents",
        action="store_true",
        help="Also train vs top_mined_alakazam/trevenant (random pilot — no official sample)",
    )
    ap.add_argument("--opponents", default="", help="Comma-separated stems; default = official field (9 decks)")
    ap.add_argument("--cycles", type=int, default=5)
    ap.add_argument("--start-cycle", type=int, default=0)
    ap.add_argument("--games-per-opponent", type=int, default=20)
    ap.add_argument(
        "--lucario-game-mult", type=int, default=1,
        help="Per-opponent game multiplier for Lucario-stem decks in the field list (1 = same as others)",
    )
    ap.add_argument(
        "--lucario-mirror-games", type=int, default=20,
        help="Games/cycle vs same train deck + official LucarioScorer (ladder mirror matchup; not MCTS self-play)",
    )
    ap.add_argument("--selfplay-games", type=int, default=40,
                    help="Only used when --mirror-brain is mcts/native/random (legacy bulk mirror)",
    )
    ap.add_argument("--eval-games", type=int, default=20)
    ap.add_argument(
        "--opponent-brain", default="native",
        choices=("native", "non_official", "random"),
        help="native=official Kaggle pilots only (default); non_official=+random for Alakazam/Trevenant",
    )
    ap.add_argument(
        "--eval-opponent", default="native",
        choices=("native", "non_official", "random"),
    )
    ap.add_argument(
        "--non-official-brain", default="random", choices=("random",),
        help="Pilot for decks with no official Kaggle sample (Alakazam, Trevenant)",
    )
    ap.add_argument(
        "--lever-blend", type=float, default=0.35,
        help="Matchup-lever bias on our MCTS root picks (0=off, LucarioScorer levers)",
    )
    ap.add_argument(
        "--mirror-brain", default="none",
        choices=("none", "native", "mcts", "random"),
        help="none=field opponents only (default). native/mcts/random = optional same-deck mirror phase",
    )
    ap.add_argument(
        "--gate-mode", default="field",
        choices=("field", "mirror", "latest"),
        help="field=promote on field WR vs official pilots; mirror=self-play gate; latest=always",
    )
    ap.add_argument("--search-count", type=int, default=12)
    ap.add_argument(
        "--determinizations", type=int, default=1,
        help="IS-MCTS-lite: independent search_begin samples per decision (1=legacy)",
    )
    ap.add_argument(
        "--puct-c", type=float, default=None,
        help="PUCT exploration scale (default: runtime LUC_PUCT_C / 0.4)",
    )
    ap.add_argument(
        "--prior-blend", type=float, default=0.0,
        help="Blend LucarioScorer one-hot into root NN prior (0=off, try 0.15–0.35)",
    )
    ap.add_argument(
        "--policy-target", choices=("value", "visits"), default="value",
        help="LearnSample policy: value=legacy relative Q; visits=AlphaZero N^{1/t}",
    )
    ap.add_argument("--gate-games", type=int, default=20,
                    help="Games per opponent for field gate eval (gate-mode=field)")
    ap.add_argument(
        "--gate-winrate", type=float, default=0.0,
        help="Min mean field WR %% to promote (0 = only require beating champion field mean)",
    )
    ap.add_argument("--replay-iters", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda", "auto"))
    ap.add_argument("--work", default="rl_mcts_field/lucarioex_v2")
    ap.add_argument("--resume-from", default="", help="Load model weights from .pth before training")
    ap.add_argument(
        "--auto-resume",
        action="store_true",
        help="Resume from work/checkpoint.json + model_latest.pth if present",
    )
    ap.add_argument(
        "--no-auto-resume",
        action="store_true",
        help="Ignore checkpoint.json even if present (fresh weights unless --resume-from)",
    )
    ap.add_argument("--append-metrics", action="store_true",
                    help="Append to existing metrics.csv instead of overwriting")
    ap.add_argument("--time-budget-sec", type=float, default=0.0, help="0 = no limit")
    ap.add_argument(
        "--no-player-clock",
        action="store_true",
        help="Disable 9:59 cumulative think-time forfeit (not recommended)",
    )
    ap.add_argument(
        "--no-deck-scope",
        action="store_true",
        help="Disable deck-scoped soft masking on matchup levers",
    )
    ap.add_argument("--smoke", action="store_true", help="1 cycle, 2 games/opponent")
    args = ap.parse_args(argv)

    if args.smoke:
        args.cycles = 1
        args.games_per_opponent = 2
        args.selfplay_games = 4
        args.eval_games = 2
        args.gate_games = 4
        args.lucario_game_mult = 1
        args.lucario_mirror_games = 2

    rt.SEARCH_COUNT = args.search_count
    rt.DETERMINIZATIONS = max(1, int(args.determinizations))
    if args.puct_c is not None:
        rt.PUCT_C = float(args.puct_c)
    rt.PRIOR_BLEND = max(0.0, min(1.0, float(args.prior_blend)))
    rt.POLICY_TARGET = str(args.policy_target).strip().lower()
    rt.GATE_GAMES = args.gate_games
    rt.GATE_WINRATE = args.gate_winrate
    rt.REPLAY_ITERS = args.replay_iters
    rt.BATCH_SIZE = args.batch_size
    rt.LR = args.lr
    rt.SELFPLAY_GAMES = args.selfplay_games
    rt.EVAL_GAMES = args.eval_games

    random.seed(rt.SEED)
    torch.manual_seed(rt.SEED)

    work = ROOT / args.work
    work.mkdir(parents=True, exist_ok=True)

    if args.auto_resume and not args.no_auto_resume:
        ck = load_checkpoint(work)
        if ck and ck.get("status") != "done":
            next_c = int(ck.get("next_cycle", 0))
            total = int(ck.get("total_cycles", args.cycles))
            if 0 < next_c < total:
                args.start_cycle = next_c
                if not args.resume_from.strip():
                    args.resume_from = str(work / "model_latest.pth")
                print(
                    f"auto-resume: start_cycle={args.start_cycle} from {args.resume_from}",
                    flush=True,
                )

    train_deck_path = ROOT / args.train_deck
    deck = load_deck(train_deck_path)
    decks_dir = ROOT / args.decks_dir
    opp_names = [s.strip() for s in args.opponents.split(",") if s.strip()] or None
    opponents = discover_opponents(decks_dir, opp_names, include_random=args.include_random_opponents)

    if args.include_random_opponents and args.opponent_brain == "native":
        print(
            "ERROR: --include-random-opponents requires --opponent-brain non_official "
            "(Alakazam/Trevenant have no official Kaggle sample).",
            flush=True,
        )
        return 2

    if args.opponent_brain == "native" and args.eval_opponent == "native":
        allow_non_official = set()
    elif args.opponent_brain == "random" and args.eval_opponent == "random":
        allow_non_official = set(opponents.keys())
    else:
        allow_non_official = opponents_without_official_sample(opponents)

    missing = list_missing_official_samples(opponents, allow_non_official=allow_non_official)
    if missing:
        print(
            "ERROR: no official Kaggle rule sample for: " + ", ".join(sorted(missing)),
            flush=True,
        )
        print(
            "Fetch kernels: powershell -File scripts/fetch_official_rule_samples.ps1",
            flush=True,
        )
        print(
            "Or use --opponent-brain non_official (random only for Alakazam/Trevenant).",
            flush=True,
        )
        return 2

    try:
        opponent_brains = preload_opponent_pilots(opponents, decks_dir, args)
    except (FileNotFoundError, ModuleNotFoundError, ValueError) as exc:
        print(f"ERROR: cannot load official opponent pilot: {exc}", flush=True)
        print("Run: powershell -File scripts/fetch_official_rule_samples.ps1", flush=True)
        print("     python scripts/bootstrap_official_rule_agents.py", flush=True)
        return 2

    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)

    rt.set_field_training_flags(
        player_clock=not args.no_player_clock,
        deck_scope=not args.no_deck_scope,
    )
    train_deck_str = str(train_deck_path)
    rt.set_lucario_lever_teaching(train_deck_str, blend=args.lever_blend)
    print(
        f"lever_blend={args.lever_blend} clock={rt.PLAYER_CLOCK_LIMIT_SEC}s "
        f"(enabled={rt.PLAYER_CLOCK_ENABLED}) deck_scope={not args.no_deck_scope}",
        flush=True,
    )

    print(
        f"device={device} search={rt.SEARCH_COUNT} cycles={args.cycles} "
        f"start_cycle={args.start_cycle} opponents={len(opponents)} "
        f"brain={args.opponent_brain} work={work}",
        flush=True,
    )
    for name, label in sorted(opponent_brains.items()):
        arch = official_archetype_for_opponent(name, opponents[name])
        note = "official" if arch else "NON-OFFICIAL"
        print(f"  {name:32} pilot={label:22} ({note})", flush=True)
    n_opp = len(opponents)
    g_base = args.games_per_opponent
    g_field = sum(
        games_for_opponent(d, g_base, args.lucario_game_mult) for d in opponents.values()
    )
    g_legacy_mirror = args.selfplay_games if args.mirror_brain != "none" else 0
    g_lucario_mirror = args.lucario_mirror_games
    parts = [f"field={g_field} ({n_opp} official pilots, {g_base}g base)"]
    if g_lucario_mirror:
        parts.append(f"lucario_mirror={g_lucario_mirror} (same deck + LucarioScorer)")
    if g_legacy_mirror:
        parts.append(f"legacy_mirror={g_legacy_mirror}")
    print(f"  training games/cycle: {', '.join(parts)}", flush=True)
    print(f"  gate_mode={args.gate_mode} opponent_brain={args.opponent_brain}", flush=True)

    model = rt.MyModel(rt.D_MODEL, rt.NUM_HEADS, rt.D_FF, rt.ENC_LAYERS, rt.DEC_LAYERS).to(device)
    champion = rt.MyModel(rt.D_MODEL, rt.NUM_HEADS, rt.D_FF, rt.ENC_LAYERS, rt.DEC_LAYERS).to(device)

    source_checkpoint: str | None = None
    resume_path = args.resume_from.strip()
    if resume_path:
        ckpt = ROOT / resume_path if not Path(resume_path).is_absolute() else Path(resume_path)
        model.load_state_dict(torch.load(ckpt, map_location=device, weights_only=True))
        source_checkpoint = str(ckpt.relative_to(ROOT)) if ckpt.is_relative_to(ROOT) else str(ckpt)
        print(f"resumed weights from {ckpt}", flush=True)

    best_path = work / "model_best.pth"
    if best_path.exists():
        champion.load_state_dict(torch.load(best_path, map_location=device, weights_only=True))
        print(f"loaded champion from {best_path}", flush=True)
    else:
        champion.load_state_dict(model.state_dict())

    _install_signal_handlers()
    global _SHUTDOWN_CTX
    _SHUTDOWN_CTX = {
        "work": work,
        "model": model,
        "champion": champion,
        "completed_cycles": args.start_cycle,
        "current_cycle": args.start_cycle,
        "total_cycles": args.cycles,
        "args": args,
        "source_checkpoint": source_checkpoint,
    }
    (work / "train.pid").write_text(str(os.getpid()), encoding="utf-8")
    write_checkpoint(
        work,
        status="running",
        completed_cycles=args.start_cycle,
        next_cycle=args.start_cycle,
        total_cycles=args.cycles,
        args=args,
        source_checkpoint=source_checkpoint,
    )

    lucario_mirror_move = None
    if args.lucario_mirror_games > 0:
        lucario_mirror_move, lucario_mirror_label = make_opponent_brain(
            "native",
            train_deck_str,
            deck,
            opp_name="lucario_mirror",
            random_agent=rt.random_agent,
            non_official_brain=args.non_official_brain,
        )
        print(
            f"  lucario mirror pilot: {lucario_mirror_label} ({args.lucario_mirror_games}g/cycle)",
            flush=True,
        )

    mirror_move = None
    if args.mirror_brain == "native":
        mirror_move, _ = make_opponent_brain(
            "native",
            train_deck_str,
            deck,
            opp_name="mirror",
            random_agent=rt.random_agent,
            non_official_brain=args.non_official_brain,
        )
    elif args.mirror_brain == "random":
        mirror_move = rt.random_agent

    best_field_wr = 0.0
    if best_path.exists():
        # Champion already loaded; field baseline unknown until cycle eval
        pass

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    remaining = max(1, (args.cycles - args.start_cycle) * len(opponents))
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=remaining)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    loss_fn_enc = torch.nn.HuberLoss(delta=0.2)
    loss_fn_dec = torch.nn.HuberLoss(reduction="none", delta=0.1)

    metrics_path = work / "metrics.csv"
    if args.append_metrics and metrics_path.exists():
        pass
    else:
        with metrics_path.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(METRICS_HEADER)

    replay: list[list] = []
    t0 = time.time()
    completed_cycles = args.start_cycle
    interrupted = False

    try:
        for cycle in range(args.start_cycle, args.cycles):
            _SHUTDOWN_CTX["current_cycle"] = cycle
            if args.time_budget_sec > 0 and time.time() - t0 > args.time_budget_sec:
                print(f"time budget reached before cycle {cycle}", flush=True)
                break

            torch.save(model.state_dict(), work / f"model{cycle}.pth")
            eval_summary: dict[str, float] = {}

            for opp_name, opp_deck in opponents.items():
                opp_path = str(decks_dir / f"{opp_name}.csv")
                opp_move, brain = make_opponent_brain(
                    brain_kind(args.eval_opponent),
                    opp_path,
                    opp_deck,
                    opp_name=opp_name,
                    random_agent=rt.random_agent,
                    non_official_brain=args.non_official_brain,
                )
                w, l, d = eval_matchup(
                    deck, opp_deck, opp_move, champion, args.eval_games, opp_name=opp_name,
                )
                wr = 100.0 * w / max(1, w + l)
                eval_summary[opp_name] = wr
                print(
                    f"[cycle {cycle}] eval {opp_name} ({brain}): {wr:.1f}% (W{w}/L{l}/D{d})",
                    flush=True,
                )
                _append_metrics_row(metrics_path, [
                    cycle, opp_name, "eval", w, l, d, round(wr, 1), 0, "", 0,
                    round(time.time() - t0, 1),
                ])

            cycle_samples: list = []
            if args.lucario_mirror_games > 0 and lucario_mirror_move is not None:
                got = collect_vs_opponent(
                    deck,
                    deck,
                    lucario_mirror_move,
                    model,
                    args.lucario_mirror_games,
                    opp_name="lucario_mirror",
                )
                cycle_samples.extend(got)
                print(
                    f"[cycle {cycle}] +{len(got)} samples lucario mirror "
                    f"(same deck + LucarioScorer, {args.lucario_mirror_games}g)",
                    flush=True,
                )

            if args.mirror_brain == "mcts":
                for _ in rt.progress(args.selfplay_games, f"[cycle {cycle}] mirror mcts"):
                    cycle_samples.extend(rt.selfplay_game(model, deck))
            elif args.mirror_brain == "native" and mirror_move is not None:
                for _ in rt.progress(args.selfplay_games, f"[cycle {cycle}] mirror vs rules"):
                    got = collect_vs_opponent(
                        deck, deck, mirror_move, model, 1, opp_name="mirror_lucario",
                    )
                    cycle_samples.extend(got)
            elif args.mirror_brain == "random":
                for _ in rt.progress(args.selfplay_games, f"[cycle {cycle}] mirror vs random"):
                    got = collect_vs_opponent(deck, deck, rt.random_agent, model, 1)
                    cycle_samples.extend(got)

            for opp_name, opp_deck in opponents.items():
                opp_path = str(decks_dir / f"{opp_name}.csv")
                opp_move, brain = make_opponent_brain(
                    brain_kind(args.opponent_brain),
                    opp_path,
                    opp_deck,
                    opp_name=opp_name,
                    random_agent=rt.random_agent,
                    non_official_brain=args.non_official_brain,
                )
                n_games = games_for_opponent(opp_deck, args.games_per_opponent, args.lucario_game_mult)
                got = collect_vs_opponent(
                    deck, opp_deck, opp_move, model, n_games, opp_name=opp_name,
                )
                cycle_samples.extend(got)
                print(
                    f"[cycle {cycle}] +{len(got)} samples vs {opp_name} ({brain}, {n_games}g)",
                    flush=True,
                )

            replay.append(cycle_samples)
            if len(replay) > args.replay_iters:
                replay.pop(0)
            train_pool = [s for chunk in replay for s in chunk]

            loss = rt.train_on_samples(
                model, optimizer, scheduler, scaler, device, loss_fn_enc, loss_fn_dec, train_pool,
            )
            promoted, gate_metric, champ_field, gate_label = _promote_candidate(
                args, deck, opponents, decks_dir, model, champion, best_field_wr=best_field_wr,
            )
            if promoted:
                champion.load_state_dict(model.state_dict())
                if args.gate_mode == "field" and gate_metric > best_field_wr:
                    best_field_wr = gate_metric

            torch.save(model.state_dict(), work / "model_latest.pth")
            if promoted:
                torch.save(champion.state_dict(), work / "model_best.pth")

            mean_wr = sum(eval_summary.values()) / max(1, len(eval_summary))
            completed_cycles = cycle + 1
            _SHUTDOWN_CTX["completed_cycles"] = completed_cycles
            write_checkpoint(
                work,
                status="running",
                completed_cycles=completed_cycles,
                next_cycle=cycle + 1,
                total_cycles=args.cycles,
                args=args,
                source_checkpoint=source_checkpoint,
            )
            print(
                f"[cycle {cycle}] loss={loss:.4f} {gate_label} promoted={int(promoted)} "
                f"champ_eval={mean_wr:.1f}% best_field={best_field_wr:.1f}% samples={len(train_pool)}",
                flush=True,
            )
            _append_metrics_row(metrics_path, [
                cycle, "ALL", "train", "", "", "", round(mean_wr, 1),
                len(train_pool), round(loss, 5), int(promoted), round(time.time() - t0, 1),
            ])

            write_run_meta(
                work, train_deck_path, opponents, args,
                completed_cycles=completed_cycles,
                source_checkpoint=source_checkpoint,
                opponent_brains=opponent_brains,
            )
    except KeyboardInterrupt:
        interrupted = True
        _emergency_checkpoint("keyboard")
        write_run_meta(
            work, train_deck_path, opponents, args,
            completed_cycles=completed_cycles,
            source_checkpoint=source_checkpoint,
            opponent_brains=opponent_brains,
        )
        print(f"\nINTERRUPTED at completed_cycles={completed_cycles} -> saved latest", flush=True)
        return 130
    except Exception:
        _emergency_checkpoint("error")
        raise

    if not (work / "model_best.pth").exists():
        torch.save(champion.state_dict(), work / "model_best.pth")

    write_checkpoint(
        work,
        status="done",
        completed_cycles=completed_cycles,
        next_cycle=args.cycles,
        total_cycles=args.cycles,
        args=args,
        source_checkpoint=source_checkpoint,
    )

    write_run_meta(
        work, train_deck_path, opponents, args,
        completed_cycles=completed_cycles,
        source_checkpoint=source_checkpoint,
        opponent_brains=opponent_brains,
    )

    print(f"DONE -> {work}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
