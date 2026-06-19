"""Periodic true-win-rate eval callback for MaskablePPO training.

Why this exists: train_rl previously ran verbose=0 with no eval, so a policy
that won only 18% of games looked "done". This logs the engine's TRUE terminal
win-rate (NOT reward sign — reward is shaped) every eval_freq steps, vs:
  - a sample of the TRAINING opponents (in-distribution progress), and
  - a HELD-OUT opponent (e.g. Kyogre) the policy never trains on
    (generalization / overfitting signal: train-WR up + holdout-WR flat = memorizing).

Runs eval envs in the training MAIN process (the cabt engine is a per-process
singleton; training envs live in subprocesses, so main is free).
"""

from __future__ import annotations

import json
from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback

ROOT = Path(__file__).resolve().parents[1]


def _terminal_result(base_env) -> int:
    """0=win for player 0, 1=loss, 2=draw, -1=unfinished."""
    cur = (getattr(base_env, "_obs", None) or {}).get("current") or {}
    return cur.get("result", -1)


def _unwrap(env):
    while hasattr(env, "env"):
        env = env.env
    return env


def play_winrate(model, env, n_games: int, seed_base: int, deterministic: bool = True) -> dict:
    """Play n_games with `model` in `env`; return true win/loss/draw counts."""
    base = _unwrap(env)
    wins = losses = draws = unfinished = 0
    for g in range(n_games):
        obs, info = env.reset(seed=seed_base + g)
        terminated = truncated = False
        while not (terminated or truncated):
            mask = info.get("action_mask")
            action, _ = model.predict(obs, action_masks=mask, deterministic=deterministic)
            obs, _r, terminated, truncated, info = env.step(int(action))
        res = _terminal_result(base)
        if res == 0:
            wins += 1
        elif res == 1:
            losses += 1
        elif res != -1:
            draws += 1
        else:
            unfinished += 1
    decided = wins + losses
    return {
        "win": wins, "loss": losses, "draw": draws, "unfinished": unfinished,
        "decided": decided, "win_rate": (wins / decided) if decided else float("nan"),
    }


class WinRateEvalCallback(BaseCallback):
    def __init__(
        self,
        deck_path,
        *,
        opponents: str = "benchmark",
        holdout: list[str] | None = None,
        eval_freq: int = 20_000,
        n_games: int = 20,
        seed: int = 12345,
        log_path: str | Path | None = None,
        verbose: int = 1,
    ) -> None:
        super().__init__(verbose)
        self._deck_path = deck_path
        self._opponents = opponents
        self._holdout = list(holdout or [])
        self._eval_freq = max(1, eval_freq)
        self._n_games = n_games
        self._seed = seed
        self._log_path = Path(log_path) if log_path else None
        self._train_env = None
        self._holdout_envs: dict[str, object] = {}
        self._history: list[dict] = []

    def _build_envs(self) -> None:
        from rl.env_factory import load_named_deck, make_masked_cabt_env

        # Train-opp probe: exclude the holdouts so this measures in-distribution.
        self._train_env = make_masked_cabt_env(
            self._deck_path, opponents=self._opponents,
            seed=self._seed, exclude=set(self._holdout),
        )
        for name in self._holdout:
            deck = load_named_deck(name, mode=self._opponents)
            self._holdout_envs[name] = make_masked_cabt_env(
                self._deck_path, opponents=self._opponents,
                seed=self._seed + 1, opp_decks=[deck],
            )

    def _on_training_start(self) -> None:
        self._build_envs()

    def _evaluate(self) -> dict:
        row = {"timesteps": int(self.num_timesteps)}
        train = play_winrate(self.model, self._train_env, self._n_games, self._seed)
        row["train"] = train
        for name, env in self._holdout_envs.items():
            row[f"holdout:{name}"] = play_winrate(
                self.model, env, self._n_games, self._seed + 99,
            )
        return row

    def _on_step(self) -> bool:
        if self.n_calls % self._eval_freq != 0:
            return True
        row = self._evaluate()
        self._history.append(row)
        if self.verbose:
            t = row["train"]
            msg = (f"[eval @ {row['timesteps']:>7} steps] "
                   f"train WR {t['win']}/{t['decided']}={t['win_rate']:.1%}")
            for name in self._holdout:
                h = row[f"holdout:{name}"]
                msg += f" | {name} WR {h['win']}/{h['decided']}={h['win_rate']:.1%}"
            print(msg, flush=True)
        if self._log_path is not None:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_path.write_text(json.dumps(self._history, indent=2), encoding="utf-8")
        return True

    def _on_training_end(self) -> None:
        # Do NOT call env.close() here. close() -> game.battle_finish() on an
        # already-finished battle native-crashes the C engine in the main process
        # (uncatchable by Python try/except; observed as a teardown exit-code crash
        # that prevented the final model.save()). Just drop refs; process exit
        # reclaims the engine. Per-eval reset() already pairs finish+start cleanly.
        self._train_env = None
        self._holdout_envs = {}
