"""Overnight deck + policy RL campaign (local training only).

GPU: policy on CUDA (4070 Ti SUPER class); cabt sim on CPU worker processes.
Checkpoints: frequent PPO saves + per-generation deck GA state for safe interrupt/resume.

Usage:
    python rl/train_deck_campaign.py --phase full --cycles 2
    python rl/train_deck_campaign.py --phase policy --timesteps 200000 --resume
    python rl/train_deck_campaign.py --phase deck --generations 30 --resume

Windows: scripts\\run_overnight_deck_rl.bat
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rl.deck_ga_checkpoint import (  # noqa: E402
    DECK_GA_PATH,
    genome_from_dict,
    load_deck_ga,
    save_deck_ga,
)
from rl.gpu_config import (  # noqa: E402
    CAMPAIGN_DIR,
    DECK_GA_JSON,
    POLICY_CKPT_DIR,
    POLICY_LATEST,
    apply_torch_safety,
    detect_hardware,
    load_campaign_state,
    migrate_campaign_state,
    policy_steps_for_cycle,
    save_campaign_state,
    set_policy_steps_for_cycle,
    training_defaults,
)

BEST_DECK = CAMPAIGN_DIR / "best_deck.csv"
POP_DIR = CAMPAIGN_DIR / "population"
LANE_ELITES_JSON = ROOT / "report" / "deck_rl" / "lane_elites.json"
LANE_ELITES_MD = ROOT / "report" / "deck_rl" / "lane_elites.md"

SEED_DECKS = [
    ROOT / "agent_decks" / "a2_kyogre_33_energy.csv",
    ROOT / "agent" / "deck.csv",
    ROOT / "agent_decks" / "a2_big_basic_29_energy.csv",
    ROOT / "agent_decks" / "a3_starmie_spread_33_energy.csv",
    ROOT / "agent_decks" / "pool_dragapult.csv",
    ROOT / "agent_decks" / "pool_crustle.csv",
]


def _load_pool_for_balance():
    from scripts.validate_deck import load_card_pool

    return load_card_pool()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _benchmark_opponent_decks() -> list[list[int]]:
    from rl.benchmark import load_suite

    return [d.load() for d in load_suite()]


def train_policy(
    timesteps: int,
    n_envs: int,
    device: str,
    deck_path: Path | None,
    checkpoint_freq: int,
    batch_size: int,
    n_steps: int,
    resume: bool,
    campaign_state: dict,
    cycle: int = 0,
) -> dict:
    """MaskablePPO vs benchmark opponents; GPU policy, CPU sim workers."""
    try:
        import numpy as np
        import torch
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
        from stable_baselines3.common.callbacks import CheckpointCallback
    except ImportError as exc:
        return {"status": "skipped", "reason": str(exc)}

    from rl.cabt_env import CabtEnv

    apply_torch_safety()
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    opp_decks = _benchmark_opponent_decks()
    deck = deck_path or (BEST_DECK if BEST_DECK.exists() else ROOT / "agent" / "deck.csv")
    POLICY_CKPT_DIR.mkdir(parents=True, exist_ok=True)

    def mask_fn(env):
        info = getattr(env.unwrapped, "_last_info", {})
        mask = info.get("action_mask") if isinstance(info, dict) else None
        return None if mask is None else np.asarray(mask, dtype=bool)

    class MaskedCabtEnv(CabtEnv):
        def reset(self, *, seed=None, options=None):
            obs, info = super().reset(seed=seed, options=options)
            self._last_info = info
            return obs, info

        def step(self, action):
            obs, reward, terminated, truncated, info = super().step(action)
            self._last_info = info
            return obs, reward, terminated, truncated, info

    def make_env(rank: int):
        def _thunk():
            env = MaskedCabtEnv(
                deck_path=deck,
                opponent_decks=opp_decks,
                seed=rank * 1000 + 7,
            )
            return ActionMasker(env, mask_fn)

        return _thunk

    model_stem = ROOT / "agent" / "models" / "rl_policy_campaign"
    can_resume = resume and (model_stem.with_suffix(".zip").exists() or POLICY_LATEST.exists())
    load_path = model_stem if model_stem.with_suffix(".zip").exists() else POLICY_LATEST.with_suffix("")

    already_done = policy_steps_for_cycle(campaign_state, cycle) if resume else 0
    remaining = max(0, timesteps - already_done)
    if remaining == 0 and can_resume and already_done >= timesteps:
        print(
            f"policy cycle {cycle + 1} already at {already_done}/{timesteps} timesteps; skipping",
            flush=True,
        )
        return {
            "status": "ok",
            "timesteps": 0,
            "timesteps_total": already_done,
            "device": device,
            "cycle": cycle,
            "skipped": True,
        }

    try:
        if n_envs > 1:
            from stable_baselines3.common.vec_env import SubprocVecEnv

            env = SubprocVecEnv([make_env(i) for i in range(n_envs)])
        else:
            env = make_env(0)()

        if can_resume and load_path.with_suffix(".zip").exists():
            model = MaskablePPO.load(str(load_path), env=env, device=device)
            model_steps = int(getattr(model, "num_timesteps", already_done))
            if model_steps > already_done:
                already_done = model_steps
                remaining = max(0, timesteps - already_done)
            print(
                f"resuming policy from {load_path}.zip "
                f"(cycle {cycle + 1}: {already_done}/{timesteps} steps)"
            )
        else:
            model = MaskablePPO(
                "MlpPolicy",
                env,
                verbose=1,
                n_steps=n_steps,
                batch_size=batch_size,
                n_epochs=4,
                learning_rate=3e-4,
                device=device,
            )

        if remaining == 0:
            set_policy_steps_for_cycle(campaign_state, cycle, already_done)
            by_cycle = campaign_state.get("policy_steps_by_cycle", {})
            campaign_state["policy_timesteps_done"] = sum(int(v) for v in by_cycle.values())
            save_campaign_state(campaign_state)
            return {
                "status": "ok",
                "timesteps": 0,
                "timesteps_total": already_done,
                "device": device,
                "cycle": cycle,
                "skipped": True,
            }

        ckpt_cb = CheckpointCallback(
            save_freq=max(1, checkpoint_freq // max(1, n_envs)),
            save_path=str(POLICY_CKPT_DIR),
            name_prefix="maskable_ppo",
            save_replay_buffer=False,
            save_vecnormalize=False,
        )

        t0 = time.time()
        model.learn(
            total_timesteps=remaining,
            reset_num_timesteps=not can_resume,
            callback=ckpt_cb,
            progress_bar=False,
        )
        model.save(str(model_stem))
        total_done = already_done + remaining
        set_policy_steps_for_cycle(campaign_state, cycle, total_done)
        by_cycle = campaign_state.get("policy_steps_by_cycle", {})
        campaign_state["policy_timesteps_done"] = sum(int(v) for v in by_cycle.values())
        campaign_state["policy_model"] = str(model_stem.with_suffix(".zip"))
        campaign_state["policy_updated_at"] = _now()
        save_campaign_state(campaign_state)

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        elapsed = time.time() - t0
        return {
            "status": "ok",
            "timesteps": remaining,
            "timesteps_total": total_done,
            "device": device,
            "n_envs": n_envs,
            "opponents": len(opp_decks),
            "model": str(model_stem.with_suffix(".zip")),
            "checkpoints": str(POLICY_CKPT_DIR),
            "elapsed_s": round(elapsed, 1),
        }
    except Exception as exc:
        campaign_state["policy_error"] = f"{type(exc).__name__}: {exc}"
        save_campaign_state(campaign_state)
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}


def _backfill_genome_lanes(pop: list, registry) -> None:
    from rl.deck_genome import DeckGenome

    for g in pop:
        if not isinstance(g, DeckGenome):
            continue
        if g.lane:
            g._with_lane_meta()
            continue
        lane = registry.lane_for_label(g.label)
        if lane:
            g.lane = lane
            g._with_lane_meta()


def _lane_elites_for_generation(pop, gen: int, lanes: list[str]) -> list[dict]:
    from rl.deck_genome import DeckGenome

    elites: dict[str, DeckGenome] = {}
    for g in pop:
        if not isinstance(g, DeckGenome) or not g.lane:
            continue
        if g.lane not in lanes:
            continue
        if g.meta.get("illegal"):
            continue
        prev = elites.get(g.lane)
        if prev is None or g.fitness > prev.fitness:
            elites[g.lane] = g

    rows: list[dict] = []
    for lane in lanes:
        g = elites.get(lane)
        if g is None:
            continue
        rows.append(
            {
                "gen": gen,
                "lane": lane,
                "label": g.label,
                "fitness": g.fitness,
                "composition": g.meta.get("composition", {}),
                "profile": g.meta.get("profile", ""),
            }
        )
    return rows


def _write_lane_elites(rows: list[dict], *, generation: int) -> None:
    LANE_ELITES_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generation": generation, "updated_at": _now(), "lanes": rows}
    LANE_ELITES_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Lane Elite Archive",
        "",
        f"Updated at generation {generation} (`{_now()}`).",
        "",
        "| Lane | Label | Fitness | Profile | E/P/T |",
        "|---|---|---:|---|---:|",
    ]
    for row in rows:
        comp = row.get("composition") or {}
        ept = f"{comp.get('energy', '?')}/{comp.get('pokemon', '?')}/{comp.get('trainers', '?')}"
        lines.append(
            f"| {row['lane']} | {row['label']} | {row['fitness']:.3f} | "
            f"{row.get('profile', '')} | {ept} |"
        )
    if not rows:
        lines.append("| (none) | — | — | — | — |")
    lines.append("")
    LANE_ELITES_MD.write_text("\n".join(lines), encoding="utf-8")


def _survivor_target(population: int, num_lanes: int) -> int:
    base = max(2, population // 2)
    return max(base, num_lanes)


def _select_survivors_by_lane(pop, lanes: list[str], target: int, rng: random.Random):
    from rl.deck_genome import DeckGenome

    by_lane: dict[str, list] = {lane: [] for lane in lanes}
    for g in pop:
        if not isinstance(g, DeckGenome) or not g.lane or g.lane not in by_lane:
            continue
        if g.meta.get("illegal"):
            continue
        by_lane[g.lane].append(g)

    min_per_lane = max(1, target // len(lanes)) if lanes else 1
    survivors: list = []
    seen_labels: set[str] = set()

    for lane in lanes:
        candidates = sorted(by_lane[lane], key=lambda x: x.fitness, reverse=True)
        for g in candidates[:min_per_lane]:
            if g.label not in seen_labels:
                survivors.append(g)
                seen_labels.add(g.label)

    if len(survivors) < target:
        rest = sorted(
            [g for g in pop if g.label not in seen_labels and not g.meta.get("illegal")],
            key=lambda x: x.fitness,
            reverse=True,
        )
        for g in rest:
            if len(survivors) >= target:
                break
            survivors.append(g)
            seen_labels.add(g.label)

    return survivors[:target]


def _inject_lane_seed(registry, lane: str, rng: random.Random, pool, *, fallback_survivors=None):
    from rl.deck_genome import DeckGenome

    paths = registry.lane_to_paths.get(lane, [])
    if paths:
        return DeckGenome.from_seed_path(rng.choice(paths), lane=lane)
    if fallback_survivors:
        return rng.choice(fallback_survivors).mutate(rng, pool)
    fallback = ROOT / "agent" / "deck.csv"
    return DeckGenome.from_seed_path(fallback, lane=lane)


def _ensure_lane_coverage(survivors, lanes: list[str], registry, rng: random.Random, pool):
    covered = {g.lane for g in survivors if g.lane}
    result = list(survivors)
    for lane in lanes:
        if lane not in covered:
            result.append(_inject_lane_seed(registry, lane, rng, pool, fallback_survivors=survivors or None))
            covered.add(lane)
    return result


def _breed_next_generation(
    survivors,
    population: int,
    lanes: list[str],
    rng: random.Random,
    pool,
    registry,
):
    from rl.deck_genome import DeckGenome

    next_pop = list(survivors)
    while len(next_pop) < population:
        lane = lanes[len(next_pop) % len(lanes)]
        lane_pool = [g for g in survivors if g.lane == lane]
        if not lane_pool:
            next_pop.append(_inject_lane_seed(registry, lane, rng, pool, fallback_survivors=survivors))
            continue
        if len(lane_pool) >= 2:
            a, b = rng.sample(lane_pool, 2)
        else:
            a = lane_pool[0]
            b = a
        next_pop.append(DeckGenome.crossover(a, b, rng).mutate(rng, pool))
    return next_pop[:population]


def _lane_survivor_counts(survivors, lanes: list[str]) -> dict[str, int]:
    counts = {lane: 0 for lane in lanes}
    for g in survivors:
        if g.lane in counts:
            counts[g.lane] += 1
    return counts


def evolve_decks(
    generations: int,
    population: int,
    games_eval: int,
    workers: int,
    scorer: str | None,
    rng_seed: int,
    resume: bool,
    campaign_state: dict,
    cycle: int = 0,
    *,
    registry_path: Path | None = None,
    lanes: list[str] | None = None,
) -> dict:
    """Genetic deck search with per-generation checkpoint."""
    from rl.benchmark import evaluate_deck_vs_benchmark
    from rl.deck_balance import (
        MATCHUP_COLLAPSE_FLOOR,
        balance_penalty,
        composition_of,
        infer_profile,
        matchup_collapse_penalty,
        summarize_deck,
    )
    from rl.deck_genome import DeckGenome
    from rl.deck_lane_registry import CANONICAL_LANES, LaneRegistry
    from scripts.validate_deck import validate_deck

    pool = _load_pool_for_balance()
    rng = random.Random(rng_seed)
    active_lanes = list(lanes or CANONICAL_LANES)
    fallback_seeds = [p for p in SEED_DECKS if p.exists()] or [ROOT / "agent" / "deck.csv"]
    registry = LaneRegistry.load(
        registry_path or (ROOT / "report" / "deck_rl" / "candidate_registry.csv"),
        lanes=active_lanes,
        fallback_paths=fallback_seeds,
    )
    if registry.is_empty():
        print("lane registry empty; falling back to hardcoded SEED_DECKS", flush=True)
    else:
        counts = {lane: len(registry.lane_to_paths.get(lane, [])) for lane in active_lanes}
        print(f"lane registry: {sum(counts.values())} seeds {counts}", flush=True)

    start_gen = 0
    pop: list[DeckGenome]
    if resume:
        ga = load_deck_ga(DECK_GA_JSON)
        if ga and ga.get("cycle", 0) == cycle:
            start_gen = int(ga.get("generation", 0))
            pop = [genome_from_dict(row) for row in ga.get("population", [])]
            _backfill_genome_lanes(pop, registry)
            pop = [g.repair(rng, pool, fallback=Counter(g.counts)) for g in pop]
            if len(pop) < population:
                pop = DeckGenome.seed_population_balanced(registry, population, rng, lanes=active_lanes)
            print(f"resuming deck GA cycle {cycle + 1} from generation {start_gen}", flush=True)
        else:
            pop = DeckGenome.seed_population_balanced(registry, population, rng, lanes=active_lanes)
            if ga and ga.get("cycle", 0) != cycle:
                print(f"deck GA checkpoint is cycle {ga.get('cycle')}; starting fresh for cycle {cycle}", flush=True)
    else:
        pop = DeckGenome.seed_population_balanced(registry, population, rng, lanes=active_lanes)

    best_fitness = float(campaign_state.get("best_fitness", -1.0))
    best_genome: DeckGenome | None = None
    history: list[dict] = []

    POP_DIR.mkdir(parents=True, exist_ok=True)

    est_eval_s = max(1, games_eval) * 10 * 0.35  # ~0.35s per game observed on Windows
    if population < 2 * len(active_lanes):
        print(
            f"warning: population={population} < 2*lanes={2 * len(active_lanes)}; "
            "lane-balanced selection may be tight",
            flush=True,
        )
    print(
        f"deck GA: gens {start_gen}..{generations - 1}, pop={population}, "
        f"lane selection=per-lane quotas, "
        f"collapse floor={MATCHUP_COLLAPSE_FLOOR:.2f}, "
        f"~{est_eval_s:.0f}s/deck, ~{est_eval_s * population / 60:.1f} min/gen",
        flush=True,
    )

    for gen in range(start_gen, generations):
        print(f"\ngen {gen} evaluating {population} decks...", flush=True)
        for i, g in enumerate(pop):
            deck_list = g.to_list(rng)
            deck_file = POP_DIR / f"gen{gen:03d}_ind{i:02d}.csv"
            deck_file.write_text("\n".join(str(c) for c in deck_list) + "\n", encoding="utf-8")
            deck_errors, _ = validate_deck(deck_list, pool)
            if deck_errors:
                g.fitness = 0.0
                g.meta = {
                    "gen": gen,
                    "lane": g.lane,
                    "illegal": deck_errors[0],
                    "composition": composition_of(g.counts, pool).as_dict(),
                    "profile": infer_profile(g.counts, pool).name,
                }
                print(
                    f"  gen {gen} ind {i}: fitness=0.000 ILLEGAL — {deck_errors[0]} "
                    f"({summarize_deck(g.counts, pool)})",
                    flush=True,
                )
                continue
            print(
                f"  gen {gen} ind {i}: simulating vs benchmark...",
                flush=True,
            )
            t_eval = time.time()
            result = evaluate_deck_vs_benchmark(
                deck_list,
                games_per_opponent=games_eval,
                workers=workers,
                scorer=scorer,
                deck_path=str(deck_file),
                seed=rng_seed + gen * 100 + i,
            )
            profile = infer_profile(g.counts, pool)
            comp = composition_of(g.counts, pool)
            balance_pen = balance_penalty(g.counts, pool, profile)
            collapse_pen, min_wr = matchup_collapse_penalty(result["opponents"])
            g.fitness = (
                result["fitness"]
                * (1.0 - 0.15 * balance_pen)
                * (1.0 - 0.25 * collapse_pen)
            )
            g.meta = {
                "gen": gen,
                "lane": g.lane,
                "raw_fitness": result["fitness"],
                "balance_penalty": balance_pen,
                "matchup_collapse_penalty": collapse_pen,
                "min_benchmark_win_rate": min_wr,
                "composition": comp.as_dict(),
                "profile": profile.name,
            }
            print(
                f"  gen {gen} ind {i}: fitness={g.fitness:.3f} raw={result['fitness']:.3f} "
                f"collapse={collapse_pen:.2f} min_wr={min_wr:.2f} lane={g.lane or '?'} "
                f"({time.time() - t_eval:.1f}s) {summarize_deck(g.counts, pool)}",
                flush=True,
            )

        pop.sort(key=lambda x: x.fitness, reverse=True)
        top = pop[0]
        history.append({"gen": gen, "best_fitness": top.fitness, "label": top.label, "lane": top.lane})
        print(f"gen {gen} best fitness={top.fitness:.3f} ({top.label}, lane={top.lane or '?'})", flush=True)

        lane_rows = _lane_elites_for_generation(pop, gen, active_lanes)
        for row in lane_rows:
            print(
                f"  lane elite {row['lane']}: fitness={row['fitness']:.3f} ({row['label']})",
                flush=True,
            )
        _write_lane_elites(lane_rows, generation=gen)

        if top.fitness > best_fitness:
            best_fitness = top.fitness
            best_genome = top
            BEST_DECK.parent.mkdir(parents=True, exist_ok=True)
            BEST_DECK.write_text("\n".join(str(c) for c in top.to_list(rng)) + "\n", encoding="utf-8")
            campaign_state["best_fitness"] = best_fitness
            campaign_state["best_label"] = top.label

        target = _survivor_target(population, len(active_lanes))
        survivors = _select_survivors_by_lane(pop, active_lanes, target, rng)
        survivors = _ensure_lane_coverage(survivors, active_lanes, registry, rng, pool)
        lane_counts = _lane_survivor_counts(survivors, active_lanes)
        print(
            "  lane survivors: "
            + " ".join(f"{lane}={lane_counts[lane]}" for lane in active_lanes),
            flush=True,
        )
        pop = _breed_next_generation(survivors, population, active_lanes, rng, pool, registry)

        campaign_state["deck_generation_done"] = gen + 1
        campaign_state["deck_ga_updated_at"] = _now()
        save_deck_ga(
            DECK_GA_JSON,
            generation=gen + 1,
            population=pop,
            rng_seed=rng_seed,
            cycle=cycle,
        )
        save_campaign_state(campaign_state)

    if best_genome:
        campaign_state["best_label"] = best_genome.label
    campaign_state["best_fitness"] = best_fitness
    save_campaign_state(campaign_state)

    return {
        "status": "ok",
        "generations": generations,
        "started_at_gen": start_gen,
        "best_fitness": best_fitness,
        "best_deck": str(BEST_DECK) if BEST_DECK.exists() else "",
        "history": history,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--phase", choices=("policy", "deck", "full"), default="full")
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--n-envs", type=int, default=None)
    parser.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    parser.add_argument("--generations", type=int, default=20)
    parser.add_argument("--population", type=int, default=12)
    parser.add_argument("--games-eval", type=int, default=6)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--scorer", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", action="store_true", help="Continue from checkpoint.json")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore checkpoint cycle counters (still loads policy/deck GA weights if present)",
    )
    parser.add_argument("--checkpoint-freq", type=int, default=None, help="PPO save every N steps")
    parser.add_argument(
        "--registry",
        default=str(ROOT / "report" / "deck_rl" / "candidate_registry.csv"),
        help="Archetype lane seed registry CSV from build_card_registry.py",
    )
    parser.add_argument(
        "--lanes",
        default="",
        help="Comma-separated search lanes (default: all four canonical lanes)",
    )
    args = parser.parse_args(argv)
    active_lanes = [s.strip() for s in args.lanes.split(",") if s.strip()] or None

    hw = detect_hardware()
    defaults = training_defaults(hw)
    n_envs = args.n_envs if args.n_envs is not None else defaults["n_envs"]
    workers = args.workers if args.workers is not None else defaults["deck_workers"]
    ckpt_freq = args.checkpoint_freq or defaults["checkpoint_freq"]
    device = args.device if args.device != "auto" else defaults["device"]

    CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    state = load_campaign_state()
    if not state:
        state = {
            "started_at": _now(),
            "policy_cycles_done": 0,
            "deck_cycles_done": 0,
            "best_fitness": -1.0,
            "history": [],
        }
    state = migrate_campaign_state(
        state,
        timesteps_per_cycle=args.timesteps,
        total_cycles=args.cycles if args.phase == "full" else 1,
    )
    state["config"] = vars(args)
    state["hardware"] = hw
    state["training_defaults"] = defaults
    state["phase"] = args.phase
    save_campaign_state(state)

    print("=== deck RL campaign ===")
    print(f"hardware: {json.dumps(hw)}")
    print(f"defaults: {defaults['notes']}")
    print(
        f"device={device} n_envs={n_envs} checkpoint_freq={ckpt_freq} "
        f"resume={args.resume} fresh={args.fresh}"
    )
    print(f"benchmark opponents: {len(_benchmark_opponent_decks())}")

    results: list[dict] = []
    use_resume = args.resume and not args.fresh
    policy_start = int(state.get("policy_cycles_done", 0)) if use_resume else 0
    deck_start = int(state.get("deck_cycles_done", 0)) if use_resume else 0
    total_cycles = args.cycles if args.phase == "full" else 1

    if args.phase in ("policy", "full"):
        if policy_start >= total_cycles:
            print(f"\npolicy: all {total_cycles} cycle(s) complete — skipping", flush=True)
        for c in range(policy_start, total_cycles):
            print(f"\n--- policy cycle {c + 1}/{total_cycles} ---", flush=True)
            deck_path = BEST_DECK if BEST_DECK.exists() else None
            r = train_policy(
                args.timesteps,
                n_envs,
                device,
                deck_path,
                ckpt_freq,
                defaults["batch_size"],
                defaults["n_steps"],
                args.resume,
                state,
                cycle=c,
            )
            results.append({"cycle": c, "policy": r})
            state.setdefault("history", []).append({"cycle": c, "policy": r})
            if r.get("status") == "ok" and (
                r.get("skipped") or int(r.get("timesteps_total", 0)) >= args.timesteps
            ):
                state["policy_cycles_done"] = max(int(state.get("policy_cycles_done", 0)), c + 1)
            save_campaign_state(state)
            if r.get("status") != "ok":
                print(f"policy phase ended: {r}")
                return 1

    if args.phase in ("deck", "full"):
        for c in range(deck_start, total_cycles):
            print(f"\n--- deck evolution cycle {c + 1}/{total_cycles} ---", flush=True)
            r = evolve_decks(
                args.generations,
                args.population,
                args.games_eval,
                workers,
                args.scorer,
                args.seed + c * 1000,
                args.resume,
                state,
                cycle=c,
                registry_path=Path(args.registry),
                lanes=active_lanes,
            )
            results.append({"cycle": c, "deck": r})
            if r.get("status") == "ok":
                state["deck_cycles_done"] = max(int(state.get("deck_cycles_done", 0)), c + 1)
            state["cycles_done"] = max(
                int(state.get("policy_cycles_done", 0)),
                int(state.get("deck_cycles_done", 0)),
            )
            state.setdefault("history", []).append({"cycle": c, "deck": r})
            save_campaign_state(state)

    state["last_results"] = results
    save_campaign_state(state)

    print(f"\n=== checkpoint: {CAMPAIGN_DIR / 'checkpoint.json'} ===")
    print(f"policy checkpoints: {POLICY_CKPT_DIR}")
    print(f"deck GA state: {DECK_GA_JSON}")
    if BEST_DECK.exists():
        print(f"best deck: {BEST_DECK} fitness={state.get('best_fitness', '?')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
