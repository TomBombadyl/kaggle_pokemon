# Evaluation & testing protocol

Professional workflow for this repo. **Local gates filter; Kaggle ladder validates.**

**Proven floor:** SearchScorer × real Mega Lucario ex **≈ 668 μ** (RULINGS Part 1). Any new brain —
including Lucario field RL+MCTS — must beat that on the **real-field gate** before upload (Ruling R3).

Related: [`SUBMISSION_PLAYBOOK.md`](SUBMISSION_PLAYBOOK.md), [`RULINGS.md`](../RULINGS.md) R1–R3,
[`META_NOTES.md`](META_NOTES.md).

---

## 1. Optimization loops (current vs retired)

| Loop | What moves | Training | Submission brain | Status |
|------|------------|----------|------------------|--------|
| **A — Rules + search** | Heuristic logic; `search_*` on key contexts | None | `SearchScorer` / `HeuristicScorer` | **KEEP — floor** |
| **D — Lucario field RL+MCTS** | Transformer policy + MCTS on fixed Lucario list | `scripts/train_lucario_field_mcts.py` vs real field decks | `lucario_mcts` + `model_best.pth` | **EXPERIMENTAL — R3 gated** |
| **Per-deck rule pilot** | Official sample logic + safety wrapper | None | e.g. `dragapult` custom agent module | **Active probes** |
| **B — Policy RL (PPO+distill)** | MaskablePPO per deck | `rl/train_rl.py` (graveyard) | `LearnedScorer` | **RETIRED** — best 585 μ |
| **C — Deck GA** | 60-card list | `rl/train_deck_campaign.py` (graveyard) | pair with A/B | **RETIRED** |

**Invariant:** gate on **real mined decks + public agents** (`agent_decks/{real_*,top_mined_*}`,
`data/kaggle_ref/opponents/`). Never `pool_*` proxies or mirror-only training (Ruling R2).

---

## 2. Real-field opponent set

**Canonical lists (today):** `agent_decks/real_*.csv`, `agent_decks/top_mined_*.csv` (10 decks used
by `train_lucario_field_mcts.py`).

**Public agents:** `python scripts/extract_public_agents.py` → `data/kaggle_ref/opponents/`.

**Future:** migrate to `field/decks/` + `field/registry.json` when `eval/harness.py` lands (TASKS F2).

**Retired as gate opponents:** `agent_decks/pool_*.csv`, random, mirror-only self-play.

---

## 3. Test pyramid (run in order)

### L0 — Legality (every change)

```bash
python scripts/smoke_test.py              # agent contract
python scripts/smoke_replay.py            # bench-guard golden fixtures
python scripts/smoke_cg_engine.py         # cg.dll battle_start (MCTS / field train)
python scripts/validate_deck.py           # deck CSV legality
```

### L1 — Real-field gate (N≈30/opp, Wilson CI)

```bash
python scripts/gate_vs_public.py --games 30    # spine / packaged candidates
python scripts/gate_dragapult.py --games 30    # Dragapult ex probe
```

Record: wins/total/draws, opponents, seeds, deck, brain name.

### L2 — SPRT vs champion

Compare candidate vs SearchScorer floor on the same opponent set and game count. Promote only if
Wilson lower bound beats champion or SPRT accepts.

### L3 — Package dry-run

```bash
# Rules/search
python scripts/package_submission.py --name <candidate> --scorer search --deck <path>

# Lucario field RL+MCTS (after train completes)
python scripts/package_submission.py \
  --name track_d_lucarioex_field_v1 \
  --scorer lucario_mcts \
  --deck agent_decks/real_mega_lucario_ex.csv \
  --model rl_mcts_field/lucarioex_v1/model_best.pth \
  --meta rl_mcts_field/lucarioex_v1/run_meta.json

python scripts/verify_archive.py dist/candidates/<name>.tar.gz --games 50
```

### L4 — Episode analysis (post-ladder)

```bash
python scripts/analyze_submission.py --ref <submission_ref>
python scripts/track_ladder.py --fetch-logs
```

**Pass criteria:** `avg_turns > 15`, `fast_loss_pct < 20%`, top loss reason ≠ `no_active`.

### L5 — Kaggle ladder (truth)

See [`SUBMISSION_PLAYBOOK.md`](SUBMISSION_PLAYBOOK.md). **≥2 μ readings ≥40 min apart** (Ruling R1).
Max **5 uploads/day**; **2 Final Submissions** selected manually.

---

## 4. Lucario field RL+MCTS workflow (Loop D)

```powershell
python scripts/bootstrap_lucario_mcts_runtime.py   # after official sample changes
python scripts/smoke_cg_engine.py
python scripts/train_lucario_field_mcts.py --device cpu --cycles 5
# outputs: rl_mcts_field/lucarioex_v1/{model_best.pth, metrics.csv, run_meta.json}
```

**Training rules:**
- Opponents = real field decks only (see `run_meta.json` `opponents` list).
- Opponent deck passed into `search_begin` (not Snorlax stub).
- Draw terminal label = 0.0 in training.
- Inference: `LucarioScorer` fallback if model missing; `LUC_SUBMIT_SEARCH_COUNT` modest (default 12).

**Ship criteria:** L0–L2 on real field, then L5 with stable μ **≥ SearchScorer 668** (user OK).

---

## 5. Per-deck rule pilot workflow

Example: Dragapult ex (`agent/dragapult_agent.py`, `agent_decks/dragapult_ex_sample.csv`).

```bash
python scripts/gate_dragapult.py --games 30
python scripts/package_dragapult.py   # if packaging script present
```

Improve via matchup levers on visible board (Boss timing, bench depth) — one change at a time, re-gate.

---

## 6. Artifacts map (live)

| Artifact | Path |
|----------|------|
| Search/heuristic package | `dist/candidates/*.tar.gz` |
| Lucario MCTS weights | `rl_mcts_field/lucarioex_v1/model_best.pth` (gitignored) |
| Train metrics | `rl_mcts_field/lucarioex_v1/metrics.csv` |
| Ladder history | `report/ladder_history.csv`, `report/submission_log.csv` |
| Future unified log | `eval/ladder_log.csv` (scaffold) |
| Replays / logs | `report/replays/`, `report/agent_logs/` |

**Graveyard:** Track B/C artifacts under `graveyard/pre-reset-20260622` — do not resurrect without
addressing RULINGS 2C.

---

## 7. Quick command reference

```bash
# Spine gate
python scripts/gate_vs_public.py --games 30

# Lucario field train (CPU default)
python scripts/train_lucario_field_mcts.py --device cpu --cycles 5

# Package Lucario MCTS
python scripts/package_submission.py --name track_d_lucarioex_field_v1 \
  --scorer lucario_mcts --deck agent_decks/real_mega_lucario_ex.csv \
  --model rl_mcts_field/lucarioex_v1/model_best.pth \
  --meta rl_mcts_field/lucarioex_v1/run_meta.json

# Ladder
python scripts/track_ladder.py --fetch-logs
```

---

## 8. Historical decision log (pre-reset)

See `RULINGS.md` Part 1 for the full μ scoreboard. Key takeaway: Learned/MCTS/GA paths never beat
hand-tuned rules/search on the ladder; the rebuild gates all new ML against that evidence.
