# Track B RL Deck — Gate Failure Diagnosis (run 27)

**2026-06-19.** `best_deck.csv` Track B Learned gate FAILED (Learned 57/240 = 23.8%
vs Search 205/240 = 85.4%, SPRT accept_a). This is the root-cause analysis.

## Method
- `scripts/diag_teacher.py` — measure the MaskablePPO **teacher's** own win-rate.
- `scripts/diag_distill.py` — measure teacher→student top-1 agreement.

## Finding: TRAINING is broken, not distillation

**The teacher MaskablePPO itself only wins 18% (9/50) vs the benchmark suite** it
trained on. The distilled student (24%) is faithfully copying a losing teacher.

### Root cause: reward shaping dominates the win/loss signal
- `cabt_env.py:172` adds `0.01 * (board_value delta)` shaping every step, on top
  of the ±1 terminal win/loss reward.
- Measured **mean episode reward = +9.3 while losing 82% of games.** The agent is
  rewarded ~+9/episode for accumulating board value even as it loses.
- Accumulated shaping reaches ±tens (min −39, max +69), so the ±1 terminal
  outcome is **noise** in the return. The agent optimized board value, not wins —
  textbook reward misspecification / shaping domination.

### Note on the earlier (wrong) "83%" reading
A first pass classified wins by the **sign of accumulated reward** and reported
83%. That was wrong: shaping makes total reward positive even in losses. Reading
the engine's true terminal `result` flips it to 18%. (Caught in code review.)

## Recommended fixes (in priority order)
1. **Rebalance reward so winning dominates.** Options: drop shaping coeff from
   0.01 to ~0.001, OR scale terminal reward to ±10/±30, OR remove shaping and
   rely on terminal-only with more timesteps. Re-train and re-run `diag_teacher`
   before distilling.
2. **More timesteps** (200k–400k) once reward is fixed.
3. **Pragmatic alternative — skip Track B for this deck.** SearchScorer already
   pilots `best_deck.csv` to **85.4%** (the gate baseline). The deck is strong;
   RL Learned adds nothing here. Ship it as a Track A (Search) pilot instead.

## Next action
Decide: (a) fix reward + retrain (research path), or (b) ship `best_deck.csv`
with the Search pilot (Track A), which already clears 85%.

## RESOLUTION (run 29) — reward fixed, gate PASSED
Took path (a). Fixed two reward bugs in `cabt_env.py` (asymmetric our-move-only
shaping + opponent-perspective terminal Φ that rewarded losing). Same bad policy's
mean reward went +9.3 → −2.06. Retrained 100k with Kyogre held out:
- **Learned 198/240 = 82.5% vs pool** (was 23.8%), Search 202/240, SPRT accept_b → PASS.
- Held-out Kyogre ~55% @100k (heuristic loses this 37%).
The per-option distill was never the bottleneck; the teacher was. Track B Learned
is now viable for this deck. Package built (not submitted).
