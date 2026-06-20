# Checkpoint Sweep Execution Guide (Option B)

**For:** User decision to run P2 (checkpoint sweeping)  
**Status:** Ready to execute on Kaggle  
**Estimated time:** 30–60 min (Kaggle GPU) + 5–10 min (download/import)  
**Expected outcome:** Best intermediate checkpoint, likely beats 100k candidate (210/240)

---

## What the Checkpoint Sweep Does

**Problem it solves:**  
The 100k, 1M, and 3M runs all used final-only policy packaging. This threw away stronger intermediate checkpoints saved during training. The 1M and 3M training curves show the best raw eval was around 400k–500k steps, but only the final policy was distilled and gated.

**Solution:**  
Checkpoint sweep trains in chunks, saves every checkpoint, distills + gates each checkpoint, re-distills the best two candidates with more teacher episodes (800 vs 300), and packages only the best gated result.

**Expected improvement:**  
- Historical data from the 1M/3M curves suggests 400k–500k beats final 1M/3M and likely beats 100k
- Estimated gate: 215–225/240 (vs 100k at 210/240)
- Estimated ladder: 550–650 μ (vs 100k at ~520–600 estimated)

---

## Step-by-Step Execution

### **1. Prepare Kaggle Session (5 min)**

1. Open **Kaggle → Notebooks → Create → Notebook**
2. Enable **GPU Accelerator** (T4 or better)
3. Set runtime to **No time limit** (may run 30–60 min)
4. Paste the entire cell from: **`report/kaggle_notebook_jobs/sweep_track_b_cell.md`**

### **2. Configure Sweep Parameters (2 min)**

In the cell, adjust these knobs at the top:

```python
# ---- knobs ----
CHUNKS = 5                    # Quick run: ~30–40 min. Set to 7 for ~50–60 min.
TIMESTEPS_PER_CHUNK = 100_000
N_ENVS = 4
GATE_GAMES = 40               # Initial gate threshold
FINALIST_GATE_GAMES = 80      # Re-gate best finalists at higher threshold
DISTILL_EPISODES = 300        # Teacher episodes per checkpoint
FINALIST_DISTILL_EPISODES = 800  # Higher distillation for finalists
FINALIST_DISTILL_EPOCHS = 50
```

**Recommendation:** Start with `CHUNKS=5` (30–40 min). If it finishes quickly and you want stronger results, run `CHUNKS=7` afterward.

### **3. Run the Cell (30–60 min)**

Click **Run All** or execute cell-by-cell:

1. **Clone repo** and pull latest code (~2 min)
2. **Install deps** (`gymnasium`, `stable-baselines3`, `sb3-contrib`) (~3 min)
3. **Verify CUDA** — expect output: `cuda True, device_count 2 or 1, Tesla T4`
4. **Fetch engine** from the Simulation dataset (~1 min)
5. **Run checkpoint sweep** (~20–45 min depending on `CHUNKS`)

**Checkpoint sweep does:**
- Train MaskablePPO in 100k-step chunks
- Save `rl_policy.zip` checkpoint after each chunk
- Distill each checkpoint with 300 teacher episodes
- Gate each distilled checkpoint at 40 games
- Re-distill the best two checkpoints with 800 episodes
- Re-gate best finalists at 80 games
- Package only the best gate winner

### **4. Download Results (5–10 min)**

When complete, download:

```
/kaggle/working/track_b_sweep_outputs.zip
```

Extract locally into:

```
report/kaggle_notebook_jobs/sweep_outputs_<date>/
```

### **5. Import and Analyze (10 min)**

Extract the zip and examine:

1. **`best_gate.json`** — which checkpoint won best gate score
2. **`checkpoint_<timesteps>_gate.md`** files — gate reports for all checkpoints
3. **`track_b_learned_sweep_best.tar.gz`** — the packaged best candidate (ready to submit)
4. **`sweep_progress.json`** — full training curve and selection logic

**Example analysis:**
```bash
# Extract
unzip /kaggle/working/track_b_sweep_outputs.zip -d report/kaggle_notebook_jobs/sweep_outputs_20260620/

# Check best winner
cat report/kaggle_notebook_jobs/sweep_outputs_20260620/best_gate.json
# Output: e.g., {"checkpoint": 400000, "gate_score": 218, "gate_total": 240, "margin": 0.025}

# List all gate reports
ls report/kaggle_notebook_jobs/sweep_outputs_20260620/checkpoint_*_gate.md
```

### **6. Decide: Submit or Rerun (10 min)**

Compare best checkpoint gate to 100k baseline (210/240):

| Outcome | Decision |
|---|---|
| Best gate ≥ 215/240 | **Package ready for submission** (`track_b_learned_sweep_best.tar.gz`). Proceed with P1 (submit) next run. |
| Best gate 210–214/240 | **Tie or marginal win.** Consider `CHUNKS=7` rerun, or submit 100k for faster ladder proof. |
| Best gate < 210/240 | **100k is still best.** Proceed with submitting 100k as Plan A instead. |

---

## Troubleshooting

### **CUDA not available**
- **Error:** `cuda False` in GPU check
- **Fix:** Set Kaggle Accelerator to GPU (Settings → Session → GPU T4 or V100), restart session, re-run cell

### **Git clone fails**
- **Error:** `git clone` timeout or network error
- **Fix:** Cell has automatic fallback to zip download. Should succeed on second attempt.

### **Pip install hangs**
- **Error:** `pip install -q gymnasium` takes >5 min
- **Fix:** Expected on first run (torch wheel is large). Wait. If truly hung, restart session and re-run.

### **Training hangs or OOMs**
- **Error:** GPU memory full or process seems stuck
- **Fix:** Reduce `N_ENVS` from 4 to 2, or `CHUNKS` from 5 to 3

### **Output zip not created**
- **Error:** `/kaggle/working/track_b_sweep_outputs.zip` doesn't exist
- **Fix:** Check cell output for errors. If training completed (prints "DONE"), zip should exist. Try cell output: `python -c "import zipfile; z = zipfile.ZipFile('/kaggle/working/track_b_sweep_outputs.zip'); print(z.namelist())"`

---

## Expected Output Files

```
track_b_sweep_outputs.zip (6–10 MB)
├── best_gate.json
├── sweep_progress.json
├── checkpoint_100000_gate.md
├── checkpoint_200000_gate.md
├── checkpoint_300000_gate.md
├── checkpoint_400000_gate.md
├── checkpoint_500000_gate.md
├── (optional checkpoint_600000_gate.md, checkpoint_700000_gate.md if CHUNKS=7)
├── track_b_learned_sweep_best.tar.gz (best gate winner, ready to submit)
├── finalist_distill_300k.npz (finalist 1, if applicable)
├── finalist_distill_400k.npz (finalist 2, if applicable)
└── finalists_regatings.json (re-gate scores at 80 games)
```

---

## Success Criteria

✅ **Run is successful if:**
- Cell prints "DONE" at the end
- GPU was used (`cuda True` at start)
- All 8 checkpoint gate files exist (for `CHUNKS=5`; 7 for `CHUNKS=7`)
- `track_b_learned_sweep_best.tar.gz` exists and is > 3 MB
- `best_gate.json` has a `checkpoint` field with a valid timestep

---

## Next Run (After Checkpoint Sweep Completes)

1. **Download** `/kaggle/working/track_b_sweep_outputs.zip` from Kaggle
2. **Extract** to `report/kaggle_notebook_jobs/sweep_outputs_<date>/`
3. **Read** `best_gate.json` to identify the winning checkpoint
4. **Compare** best gate vs 100k baseline (210/240)
5. **If better:** prepare `track_b_learned_sweep_best.tar.gz` for submission
6. **If tie/worse:** submit 100k candidate instead
7. **Update** ladder history and PROGRESS.md with decision

---

## Files Referenced

- **Cell to run:** `report/kaggle_notebook_jobs/sweep_track_b_cell.md`
- **Script being called:** `scripts/sweep_track_b_checkpoints.py`
- **Comparison baseline:** `report/track_b_gates/track_b_learned_rl_deck_kaggle_20260619_gate.md` (100k, 210/240)
- **Improvement plan:** `report/competition_improvement_plan_20260620.md` (full diagnosis)

---

**Prepared by:** Autonomous bot (Run 36)  
**Date:** 2026-06-20  
**Status:** Ready for execution

