# Deck RL — launch prep (extend cycles)

Ready to continue the deck + policy campaign on your GPU box. Keeps all prior
progress; adds new cycles.

---

## Current checkpoint (where you'll resume from)

- `best_fitness` **0.864**, `best_label` Kyogre/big-basic hybrid.
- `policy_cycles_done` **2**, `deck_cycles_done` **2**, deck GA **gen 20**.
- Policy steps done **~300k**; model `agent/models/rl_policy_campaign.zip`.

A plain `--resume --cycles 2` **no-ops** (all 2 cycles done). The launcher is now
set to **`--cycles 4`** so it runs the new cycles 3–4.

---

## Run it

**Easiest (Windows):**

```bat
scripts\run_overnight_deck_rl.bat
```

**Equivalent explicit command:**

```bat
python rl\train_deck_campaign.py --phase full --cycles 4 --timesteps 100000 ^
  --device auto --resume --generations 20 --population 12 --games-eval 6 --scorer heuristic
```

- `--resume` keeps prior policy + deck-GA weights; runs only cycles 3–4.
- Each deck cycle runs `--generations 20` more GA generations seeded from the saved
  lane elites.

---

## Before you launch — dependencies

GPU stack is **not** in `requirements.txt` by default (it's dev-only). The `.bat`
auto-installs if missing, but to be safe on your CUDA box:

```bat
python -m pip install torch gymnasium stable-baselines3 sb3-contrib
```

- Use a **CUDA** torch build (match your driver) so policy PPO runs on the 4070 Ti.
- `gymnasium`, `stable-baselines3`, `sb3-contrib` are already pinned in `requirements.txt`.
- Sanity check before the long run:
  ```bat
  python -c "import torch;print('cuda',torch.cuda.is_available())"
  ```
  Must print `cuda True`. If `False`, you'll train policy on CPU (slow).

---

## Safe to interrupt

Checkpoints are frequent and resume is idempotent:

- `report\rl_deck_campaign\checkpoint.json` — cycle counters + best.
- `report\rl_deck_campaign\deck_ga.json` — GA population.
- `report\rl_deck_campaign\policy_checkpoints\` — PPO saves.
- `report\rl_deck_campaign\best_deck.csv` — current best deck.

Ctrl-C any time, then re-run the same command (still `--resume`) to continue.

---

## What good looks like

- `best_fitness` in `checkpoint.json` climbs above **0.864**.
- All 4 lanes stay alive in `report\deck_rl\lane_elites.json` (no lane collapse).
- New `best_deck.csv` validates legal (60 cards) — confirm with
  `python scripts\validate_deck.py report\rl_deck_campaign\best_deck.csv`.

---

## When it's done

Paste me the final `best_fitness` + the new `best_deck.csv`, and I'll validate the
deck, diff it against the current Kyogre baseline, and tell you whether it's worth a
benchmark gate before any ladder probe.

---

*Verified (CPU sandbox): deck-GA fitness path runs end-to-end against the 10-opponent
benchmark suite; modules import cleanly with torch lazy-loaded. Policy/full phase needs
your CUDA box — the sandbox is CPU-only and would also clobber the shared checkpoint,
so it was not run here.*
