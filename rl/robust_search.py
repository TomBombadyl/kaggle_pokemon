"""Robust deck search (PSRO-lite).

Evolves a 60-card deck to maximise win rate against the *whole field*, not the
mean vs a fixed suite. Per generation:

  1. Evaluate each candidate vs the TRAIN gauntlet (+ self-play elites) with
     common-random-number seeds. With --surrogate, confident matchups are
     predicted (GPU) and only uncertain ones are simulated (CPU).
  2. Build the candidate x opponent payoff matrix and solve the zero-sum
     meta-game -> adversarial opponent weights y (the hardest field).
  3. Score each candidate with robust_score = alpha*mean + (1-alpha)*CVaR,
     using y-reweighted matchups (objective targets the hard field).
  4. Validate the best candidate on the HOLDOUT gauntlet (always simulated).
  5. Add the best candidate's deck to the self-elite opponent pool (co-evolution).
  6. Select + breed the next generation (DeckGenome crossover/mutate).

Deterministic RNG throughout. Writes checkpoints to report/robust_deck_rl/.
See report/robust_deck_optimization_design.md.
"""

from __future__ import annotations

import csv
import json
import random
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "report" / "robust_deck_rl"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def run_robust_search(
    *,
    generations: int = 20,
    population: int = 12,
    games_eval: int = 6,
    workers: int = 4,
    scorer: str | None = "heuristic",
    alpha: float = 0.5,
    cvar_q: float = 0.3,
    holdout_frac: float = 0.25,
    seed: int = 42,
    use_meta_solver: bool = True,
    use_surrogate: bool = False,
    surrogate_margin: float = 0.2,
    max_self_elites: int = 12,
    include_mined: bool = True,
    out_dir: Path = OUT_DIR,
) -> dict:
    from scripts.validate_deck import load_card_pool, validate_deck
    from rl.deck_genome import DeckGenome
    from rl.gauntlet import (
        Opponent, load_gauntlet, split_train_holdout, materialize_deck, winrate_vs,
    )
    from rl.robust_fitness import MatchupResult, robust_score, summarize
    from rl.meta_solver import adversarial_weights

    out_dir.mkdir(parents=True, exist_ok=True)
    cand_dir = out_dir / "_cand_decks"
    cand_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    pool = load_card_pool()

    surrogate = None
    surro_buffer: list[tuple[list[int], list[int], float]] = []
    if use_surrogate:
        from rl.winrate_surrogate import WinRateSurrogate
        surrogate = WinRateSurrogate(pool=pool, seed=seed)
        print(f"surrogate backend: {surrogate.backend}", flush=True)

    full = load_gauntlet(include_mined=include_mined)
    train, holdout = split_train_holdout(full, holdout_frac=holdout_frac, seed=seed)
    print(f"gauntlet: {len(full)} opponents -> train {len(train)} / holdout {len(holdout)}", flush=True)
    print(f"  train: {', '.join(o.name for o in train)}", flush=True)
    print(f"  holdout: {', '.join(o.name for o in holdout)}", flush=True)

    # Seed population from the real field (legal archetypes); mutate the clones.
    seeds = [DeckGenome.from_deck(o.deck, label=o.name) for o in full]
    pop: list[DeckGenome] = []
    for i in range(population):
        g = seeds[i % len(seeds)]
        clone = DeckGenome.from_deck(list(g.counts.elements()), label=g.label)
        pop.append(clone if i < len(seeds) else clone.mutate(rng, pool))

    self_elites: list[Opponent] = []
    metrics_path = out_dir / "metrics.csv"
    with metrics_path.open("w", newline="") as f:
        csv.writer(f).writerow(
            ["gen", "best_robust", "best_mean", "best_maximin", "best_worst",
             "holdout_robust", "holdout_maximin", "n_opponents", "games_simulated",
             "games_predicted", "elapsed_s"])

    best_overall = -1.0
    best_deck_list: list[int] = []
    best_card = None
    t0 = time.time()
    sim_counter = {"sim": 0, "pred": 0}

    def evaluate(cand, opps, base_seed, *, allow_surrogate, record):
        deck_list = cand.to_list(rng)
        errs, _ = validate_deck(deck_list, pool)
        if errs:
            return None, deck_list
        path = materialize_deck(deck_list, cand_dir / "cand.csv")
        rows = []
        for j, opp in enumerate(opps):
            pred = None
            if allow_surrogate and surrogate is not None and len(surro_buffer) >= 80:
                pred = surrogate.predict_pair(deck_list, opp.deck)
            if pred is not None and abs(pred - 0.5) > surrogate_margin:
                rows.append(MatchupResult(opp.name, float(pred), opp.weight, 0))
                sim_counter["pred"] += 1
            else:
                rate, gp = winrate_vs(deck_list, path, opp, games=games_eval,
                                      workers=workers, scorer=scorer, seed=base_seed + j * 7919)
                rows.append(MatchupResult(opp.name, rate, opp.weight, gp))
                sim_counter["sim"] += 1
                if record:
                    surro_buffer.append((deck_list, opp.deck, rate))
        return rows, deck_list

    for gen in range(generations):
        opps = train + self_elites
        if surrogate is not None and len(surro_buffer) >= 80:
            pairs = [(a, b) for a, b, _ in surro_buffer]
            labels = [r for _, _, r in surro_buffer]
            surrogate.fit(pairs, labels, epochs=300)

        payoff = np.full((len(pop), len(opps)), 0.5)
        cand_rows: list[list | None] = []
        cand_decks: list[list[int]] = []
        for ci, cand in enumerate(pop):
            rows, deck_list = evaluate(cand, opps, seed + gen * 100003 + ci * 131,
                                       allow_surrogate=True, record=True)
            cand_rows.append(rows)
            cand_decks.append(deck_list)
            if rows:
                for j, mr in enumerate(rows):
                    payoff[ci, j] = mr.win_rate

        adv = None
        if use_meta_solver and len(pop) >= 2 and len(opps) >= 2:
            try:
                adv = adversarial_weights(payoff, iters=4000)
            except Exception:
                adv = None

        scored = []
        for ci, cand in enumerate(pop):
            rows = cand_rows[ci]
            if not rows:
                cand.fitness = 0.0
                scored.append((0.0, ci))
                continue
            if adv is not None:
                a = adv / (adv.mean() + 1e-9)
                rows = [MatchupResult(mr.name, mr.win_rate, mr.weight * float(a[j]), mr.games)
                        for j, mr in enumerate(rows)]
            rs = robust_score(rows, alpha=alpha, cvar_q=cvar_q)
            cand.fitness = rs
            scored.append((rs, ci))

        scored.sort(reverse=True)
        best_rs, best_ci = scored[0]
        best_rows = cand_rows[best_ci]
        sc = summarize(best_rows, alpha=alpha, cvar_q=cvar_q) if best_rows else {}

        ho_robust = ho_mm = float("nan")
        if holdout and best_rows:
            ho_rows, _ = evaluate(pop[best_ci], holdout, seed + 555 + gen,
                                  allow_surrogate=False, record=False)
            if ho_rows:
                hs = summarize(ho_rows, alpha=alpha, cvar_q=cvar_q)
                ho_robust, ho_mm = hs["robust_score"], hs["maximin"]

        if best_rs > best_overall:
            best_overall = best_rs
            best_deck_list = cand_decks[best_ci]
            best_card = pop[best_ci]
            (out_dir / "best_deck.csv").write_text(
                "\n".join(str(c) for c in best_deck_list) + "\n", encoding="utf-8")

        if best_rows and len(best_deck_list) == 60:
            ep = materialize_deck(best_deck_list, out_dir / "_elites" / f"elite_gen{gen}.csv")
            self_elites.append(Opponent(f"selfelite_g{gen}", best_deck_list, ep, 1.3, "self"))
            if len(self_elites) > max_self_elites:
                self_elites.pop(0)

        elapsed = time.time() - t0
        with metrics_path.open("a", newline="") as f:
            csv.writer(f).writerow([
                gen, round(best_rs, 4), round(sc.get("mean", 0), 4),
                round(sc.get("maximin", 0), 4), str(sc.get("worst", "")),
                round(ho_robust, 4), round(ho_mm, 4), len(opps),
                sim_counter["sim"], sim_counter["pred"], round(elapsed, 1)])
        print(f"gen {gen}: robust={best_rs:.3f} mean={sc.get('mean',0):.3f} "
              f"maximin={sc.get('maximin',0):.3f} worst={sc.get('worst','')} "
              f"holdout_robust={ho_robust:.3f} elites={len(self_elites)} "
              f"sim={sim_counter['sim']} pred={sim_counter['pred']} ({elapsed/60:.1f}m)", flush=True)

        survivors = [pop[ci] for _, ci in scored[: max(2, population // 2)]]
        nxt = list(survivors)
        while len(nxt) < population:
            a, b = (rng.sample(survivors, 2) if len(survivors) >= 2 else (survivors[0], survivors[0]))
            nxt.append(DeckGenome.crossover(a, b, rng).mutate(rng, pool))
        pop = nxt

        (out_dir / "state.json").write_text(json.dumps({
            "updated_at": _now(), "gen_done": gen + 1, "best_robust": best_overall,
            "best_label": getattr(best_card, "label", ""),
            "config": {"generations": generations, "population": population,
                       "games_eval": games_eval, "alpha": alpha, "cvar_q": cvar_q,
                       "use_meta_solver": use_meta_solver, "use_surrogate": use_surrogate,
                       "seed": seed},
        }, indent=2), encoding="utf-8")

    return {
        "status": "ok", "generations": generations, "best_robust": best_overall,
        "best_deck": str(out_dir / "best_deck.csv") if best_deck_list else "",
        "gauntlet_size": len(full),
        "games_simulated": sim_counter["sim"], "games_predicted": sim_counter["pred"],
    }
