# Mega Lucario ex — RL + MCTS trainer

Hardened fork of the official PTCG *Reinforcement Learning and MCTS sample code*,
with the sample deck swapped for **Mega Lucario ex** and a robust, checkpoint-gated
GPU training loop.

## Files

- `lucario_rl_mcts.ipynb` — the Kaggle notebook (run this).
- `lucario_rl_mcts.py` — same trainer as a plain script (`python lucario_rl_mcts.py`).
- `kernel-metadata.json` — push config (GPU + competition data attached).

## Run on Kaggle

1. Push or upload the notebook:
   ```bash
   kaggle kernels push -p notebooks/lucario
   ```
   (or New Notebook → upload `.ipynb`). Set your own username in `kernel-metadata.json`.
2. Confirm **Accelerator = GPU** and the **competition data is attached** (it provides
   `cg-lib`, which the notebook auto-locates under `/kaggle/input/**/cg-lib`).
3. Run all cells. Order: `0 setup → 1 config → 2 defs → 3 main() → 4 inspect`.
4. Download artifacts when done:
   ```bash
   kaggle kernels output tobin/ptcg-lucario-rl-mcts -p report/kaggle_notebook_jobs/lucario/
   ```

## Dependencies (accelerated training)

Kaggle's GPU image already provides everything this trainer needs:

- **CUDA-enabled PyTorch** + cuDNN (the trainer uses `torch.autocast` AMP — no extra libs).
- `numpy`, `pandas` (preinstalled; `pandas` only used in the inspect cell).

Cell 0 verifies the GPU is live (`nvidia-smi`, `torch.cuda.is_available()`) and asserts
if GPU is off. No `pip install` is required on Kaggle. Off-Kaggle, a CUDA PyTorch build
is the only requirement.

## What was improved vs the sample

| Area | Sample | This trainer |
|---|---|---|
| Deck | generic sample_deck | **Mega Lucario ex** (60 cards) |
| MCTS sims / move | 10 | **48** (`LUC_SEARCH_COUNT`) |
| Model | d128 / 2h / 256ff / 1+1 layers | **d256 / 4h / 512ff / 2+2** |
| Iterations | 5 | **40** + wall-clock `TIME_BUDGET` |
| Checkpoint pick | overwrites every iter | **champion-gating** (keep strongest) |
| Training data | current iter only | **replay buffer** (last 3 iters) |
| Exploration | none | **Dirichlet root noise + temperature** (self-play only) |
| Stability/speed | plain AdamW | **seeded, grad-clip, cosine LR, AMP** |
| Logging | stdout win-rate | `metrics.csv`, `run_meta.json`, per-iter snapshots |

The champion-gating change is the most important: it directly fixes the project's
known "final-only packaging throws away a stronger earlier checkpoint" problem — a new
net only becomes `model_best.pth` if it beats the incumbent ≥ `LUC_GATE_WINRATE`.

## Knobs (set in cell 1, or as env vars)

`LUC_ITERS`, `LUC_SEARCH_COUNT`, `LUC_SELFPLAY_GAMES`, `LUC_EVAL_GAMES`,
`LUC_GATE_GAMES`, `LUC_GATE_WINRATE`, `LUC_TIME_BUDGET_SEC`, `LUC_D_MODEL`,
`LUC_HEADS`, `LUC_D_FF`, `LUC_ENC_LAYERS`, `LUC_DEC_LAYERS`, `LUC_REPLAY_ITERS`,
`LUC_DIR_ALPHA`, `LUC_DIR_FRAC`, `LUC_TEMP_PLIES`, `LUC_SEED`.

## Outputs (`/kaggle/working/lucario_rl/`)

- `model_best.pth` — champion weights → **use this for inference**.
- `model_latest.pth`, `model_iter{N}.pth` — snapshots.
- `metrics.csv` — `iter, vs_random, gate_winrate, promoted, n_samples, loss, elapsed_s`.
- `run_meta.json` — final summary + config.

## Verification (after a run)

1. `metrics.csv` → `vs_random` should trend up (sample reached ~0.76).
2. `promoted` is `1` on iters where `gate_winrate ≥ LUC_GATE_WINRATE`.
3. Reload `model_best.pth`, eval ≥100 games vs random → win rate well above the
   ~0.50 random-vs-random baseline.

## Package Locally After Download

After `kaggle kernels output ... -p report/kaggle_notebook_jobs/lucario/`, build
the local candidate archive without submitting:

```bash
python scripts/import_lucario_rl_outputs.py --source report/kaggle_notebook_jobs/lucario --name track_d_lucario_rl_mcts --gate-games 4
```

This copies `model_best.pth`, packages it with the dedicated `lucario_mcts`
wrapper, dry-runs import/deck selection, and optionally runs the public-agent
gate. Submit only after the public gate clears our current baselines.

## Local note

The engine integration (deck legality + Search/Battle API) was smoke-tested against the
repo's `data/sim/sample_submission/cg` engine: deck is legal, `search_begin/step/end`
work, and full games complete. The transformer/MCTS math is unchanged from the official
sample. A full GPU training pass must run on Kaggle (the sandbox is CPU-only and can't
fit the CUDA PyTorch build).
