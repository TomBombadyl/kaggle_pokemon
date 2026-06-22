# Kaggle Simulation competitions — CLI workflow

Reference for **The Pokémon Company - PTCG AI Battle Challenge Simulation**
(`pokemon-tcg-ai-battle`). Strategy track is separate (`pokemon-tcg-ai-battle-challenge-strategy`).

Related: [`SUBMISSION_PLAYBOOK.md`](SUBMISSION_PLAYBOOK.md), [`COMPETITION_SCORING.md`](COMPETITION_SCORING.md),
[`fetch_agent_logs.py`](../scripts/fetch_agent_logs.py), [`track_ladder.py`](../scripts/track_ladder.py).

---

## 1. Find and inspect

```bash
kaggle competitions list -s simulation
kaggle competitions pages pokemon-tcg-ai-battle
kaggle competitions pages pokemon-tcg-ai-battle --content
kaggle competitions topics list pokemon-tcg-ai-battle -s top --page-size 10
kaggle competitions topics show pokemon-tcg-ai-battle <topic_id>
```

---

## 2. Join and download

Accept rules on the Kaggle website first.

```bash
kaggle competitions list --group entered
kaggle competitions download pokemon-tcg-ai-battle -p data/kaggle_ref/simulation
```

Local engine copy: `python scripts/fetch_sim_engine.py` → `data/sim/sample_submission/cg/`.

---

## 3. Submit an agent

Our agents are packaged tarballs with `main.py` at root (see `scripts/package_submission.py`).

```bash
python scripts/package_submission.py --name <candidate> --scorer learned|search|lucario_mcts --deck <path> [--model <path>]

kaggle competitions submit pokemon-tcg-ai-battle \
  -f dist/candidates/<candidate>.tar.gz \
  -m "description"
```

Notebook-backed submit (optional):

```bash
kaggle competitions submit pokemon-tcg-ai-battle \
  -k YOUR_USERNAME/your-kernel -f dist/candidates/<candidate>.tar.gz -v 1 -m "msg"
```

**Limits:** 5 uploads/team/day; **2 Final Submissions** for judging (select manually on Kaggle).

---

## 4. Monitor submissions

```bash
kaggle competitions submissions pokemon-tcg-ai-battle
kaggle competitions submissions pokemon-tcg-ai-battle -v
python scripts/track_ladder.py
```

Note the submission **ref** (ID) for episodes/logs.

---

## 5. Episodes, replays, agent logs

```bash
# List episodes for a submission ref
kaggle competitions episodes <submission_ref>
kaggle competitions episodes <submission_ref> -v

# Episode replay JSON
kaggle competitions replay <episode_id>
kaggle competitions replay <episode_id> -p report/replays

# Agent debug logs (agent_index is 0-based)
kaggle competitions logs <episode_id> 0
kaggle competitions logs <episode_id> 1 -p report/agent_logs
```

Local wrapper (READ ONLY): `python scripts/fetch_agent_logs.py --ref <submission_ref>`.

---

## 6. Leaderboard scouting

```bash
kaggle competitions leaderboard pokemon-tcg-ai-battle -s
kaggle competitions team-submissions <team_id>
kaggle competitions episodes <best_submission_ref>
```

Use replays/logs on top teams to study tempo, bench usage, and prize sequencing.

---

## 7. Typical iteration loop

1. Local gate: `scripts/gate_track_b.py`, `scripts/gate_track_a.py`, or `scripts/gate_vs_public.py`
2. Package dry-run: `python scripts/package_submission.py --name … --gate` (runs L0+L1)
3. Submit (user OK): `kaggle competitions submit …`
4. Wait ~40+ min for ladder μ to stabilize after COMPLETE
5. **Episode analysis:** `python scripts/analyze_submission.py --ref <ref>`
6. Fix policy from `report/submission_stats/{ref}_stats.csv` (win_rate, avg_turns, fast_loss_pct)

---

## 8. Local JSON replay (offline debugging)

Record agent-vs-agent battles locally without Kaggle:

```bash
python scripts/record_local_battle.py --agent-a lucario --agent-b search \
  --deck-a agent_decks/real_mega_lucario_ex.csv --games 20 --seed 42
```

Output: `report/local_replays/<name>_seed<seed>.json` with per-game:
- `turn_count`, `result_reason` (`prize`, `deck_out`, `no_active`, `card_effect`)
- `win_rate`, `avg_turns`, `fast_loss_pct` summary

Add `--full-steps` to capture every `(observation, action)` step for golden tests.

---

## 9. Episode analysis (per submission ref)

μ alone hides *how* an agent wins or loses. Pull episode stats after COMPLETE:

```bash
python scripts/analyze_submission.py --ref 53886522
python scripts/analyze_submission.py --ref 53869254 --agent-index 0
```

Pipeline:
1. `fetch_agent_logs.py --ref <ref>` (episode list)
2. Downloads replay JSON → `report/replays/<episode_id>.json`
3. Writes `report/submission_stats/{ref}_stats.csv`
4. Updates `report/submission_log.csv` with win_rate, avg_turns, fast_loss_pct, top_loss_reason

**Pass criteria (L4):** `avg_turns > 15`, `fast_loss_pct < 20%`, top loss reason ≠ `no_active`.

See [`EVAL_PROTOCOL.md`](EVAL_PROTOCOL.md) and [`COMPETITION_SCORING.md`](COMPETITION_SCORING.md).

---

## 10. Project-specific commands

| Task | Command |
|------|---------|
| Lucario field RL+MCTS (local) | `python scripts/train_lucario_field_mcts.py --device cpu --cycles 5` then package `--scorer lucario_mcts` |
| Dragapult gate | `python scripts/gate_dragapult.py --games 30` |
| Ladder sync | `python scripts/track_ladder.py --fetch-logs` |
