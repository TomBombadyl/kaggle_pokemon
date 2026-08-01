# STATE — PTCG AI Battle Aggressive Ladder Climb

> **Mode:** NEVER-STOP aggressive parallel loop (rules-locked 2026-07-30)  
> **Workspace:** `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon`  
> **Goal:** Simulation ladder as high as possible; prep Strategy top-8  
> **Auto-approve:** ALL train / eval / package / file / Kaggle API  
> **Auto-submit:** strongest only · legal+finish · WR≥60.0% · max 5/day · board keeps latest 2  
> **Clock:** 600s/player → prefer `speed_class=fast` brains  

---

## Live status (2026-07-31T07:25:39)

| Item | Status |
|------|--------|
| Loop | **RUNNING** |
| Token | OK |
| Engine cg/ | OK |
| Card pool | OK |
| Offline smoke | OK |
| Today submits | 5 / 5 (soft quality ≤2) |
| Last gate | archaludon wr=85.4 ok=True legal=True fin=True |
| Last submit | daily_cap 5/5 |
| Best local | archaludon=85.4 |
| Cycle | 60 |
| Blocker | none |

### Competition rules (active)
1. Max **5** submits/day; only **latest 2** stay on board → submit strongest, not spray.
2. **10 min** battle clock → inference speed first; heavy MCTS trains locally, ships only if time-safe.
3. **Official card pool only** (`validate_deck` + EN_Card_Data).
4. Almost **no competition training compute** → local self-play + MCTS on this machine.
5. Pre-submit gate: **no illegal** + **games finish** + **WR >> random** (≥60.0%).
6. **Parallel local** gates/train; submit path is serial + capped.
7. **Daily episodes** refresh for deck/meta adjustment.

### Auto rules
1. Never ask for confirmation on train/eval/package/Kaggle API.
2. Parallel gates → rank by WR → package **one** strongest → `auto_submit.py` (retry once).
3. Daily hard cap 5; soft quality slots 2 unless clear upgrade.
4. API fail ×2 → package stays in `dist/candidates/`; STATE logs MANUAL.
5. Loop never exits except SIGINT / --once.

## Loop design

```
while True:
  ensure_token
  fetch_engine + official card pool
  daily episode refresh (once/day)
  offline_smoke
  PARALLEL gates [Archaludon, Dragapult, Alakazam, ...]
  rank by WR (prefer fast brains)
  if strongest passes legal+finish+WR:
    validate official deck → package → auto_submit (≤5/day, soft ≤2)
  if idle / slots full: local self-play + optional MCTS train
  update STATE.md
  sleep (adaptive)
```



## Auto-submit log
### Auto-submit 2026-07-31T08:20:08
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\arch_v5_r7.tar.gz`
- status: **SKIPPED_DIRECTOR_GATE**
- message: Strongest reroll #3: Archaludon v5 R7 historical champion ref 54083197 mu 1196.1
- local_gate: 85.4
- strength_note: User-directed strongest-score reroll; verified SHA256 651686cde25100aacb1cd86c3094ac072c97f088cdaf3581c10f2483424c1154
- submits_today: 2/5 (board keeps latest 2)
- api_output: ```iono 50.625 < 55.0; crustle_min 83.3375 < 89.0```

### Auto-submit 2026-07-31T08:17:20
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\arch_v5_r7.tar.gz`
- status: **SKIPPED_DIRECTOR_GATE**
- message: SSOT guard self-test - must not submit
- local_gate: 95.0
- strength_note: read-only policy guard test
- submits_today: 2/5 (board keeps latest 2)
- api_output: ```iono 49.375 < 55.0; crustle_min 84.175 < 89.0```

### Auto-submit 2026-07-31T08:07:13
- file: `dist\candidates\arch_v5_r7.tar.gz`
- status: **OK**
- message: Final lock-in #2: Archaludon v5 R7 historical champion ref 54083197 mu 1196.1
- local_gate: 85.4
- strength_note: User-directed final lock-in of verified historical champion; SHA256 651686cde25100aacb1cd86c3094ac072c97f088cdaf3581c10f2483424c1154
- submits_today: 2/5 (board keeps latest 2)
- api_output: ```3 submissions remaining today.
Successfully submitted to The Pokémon Company - PTCG AI Battle Challenge Simulation
  0%|          | 0.00/1.89M [00:00<?, ?B/s]
  1%|          | 16.0k/1.89M [00:00<00:58, 33.4kB/s]
 16%|█▌        | 304k/1.89M [00:00<00:03, 462kB/s]  
 19%|█▉        | 368k/1.89M [00:00<00:03, 448kB/s]
 22%|██▏       | 432k/1.89M [00:01<00:03, 437kB/s]
 37%|███▋      | 720k/1.89M [00:01<00:01, 835kB/s]
 62%|██████▏   | 1.17M/1.89M [00:01<00:00, 1.48MB/s]
100%|██████████| 1.89M/1.89M ```

### Auto-submit 2026-07-31T08:07:04
- file: `dist\candidates\arch_v5_r7.tar.gz`
- status: **OK**
- message: Final lock-in #1: Archaludon v5 R7 historical champion ref 54083197 mu 1196.1
- local_gate: 85.4
- strength_note: User-directed final lock-in of verified historical champion; SHA256 651686cde25100aacb1cd86c3094ac072c97f088cdaf3581c10f2483424c1154
- submits_today: 1/5 (board keeps latest 2)
- api_output: ```4 submissions remaining today.
Successfully submitted to The Pokémon Company - PTCG AI Battle Challenge Simulation
  0%|          | 0.00/1.89M [00:00<?, ?B/s]
  1%|          | 16.0k/1.89M [00:00<00:33, 58.2kB/s]
 35%|███▍      | 672k/1.89M [00:00<00:00, 1.93MB/s] 
 48%|████▊     | 928k/1.89M [00:00<00:00, 1.33MB/s]
 60%|██████    | 1.14M/1.89M [00:00<00:00, 1.41MB/s]
 87%|████████▋ | 1.64M/1.89M [00:01<00:00, 1.93MB/s]
100%|██████████| 1.89M/1.89M [00:01<00:00, 1.12MB/s]
```

### Auto-submit 2026-07-31T07:28:28
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\arch_v5_r7.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: dryrun
- local_gate: 95.0
- strength_note: 
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:59:57
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 65.0
- strength_note: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:59:19
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 65.0
- strength_note: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:59:09
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 65.0
- strength_note: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:57:46
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 65.0
- strength_note: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:56:32
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 81.8
- strength_note: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:55:46
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 65.0
- strength_note: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:54:32
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 81.8
- strength_note: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:53:46
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 65.0
- strength_note: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:52:32
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 82.5
- strength_note: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:51:46
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 65.0
- strength_note: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:50:32
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 82.5
- strength_note: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:49:45
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 65.0
- strength_note: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:48:32
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 82.5
- strength_note: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:47:45
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 65.0
- strength_note: Crustle MissingNo #1 day-flip #1 鈥?chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

### Auto-submit 2026-07-31T01:46:32
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\crustle_MissingNo_v1.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 81.1
- strength_note: Crustle MissingNo #1 day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```


### Auto-submit 2026-07-30T09:19:34
- file: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\archaludon.tar.gz`
- status: **SKIPPED_DAILY_CAP**
- message: Archaludon R7 PRIMARY day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- local_gate: 87.5
- strength_note: Archaludon R7 PRIMARY day-flip #1 — chase pin 1196 / top 1198+ (live~793.7)
- submits_today: 5/5 (board keeps latest 2)
- api_output: ```cap 5```

## Episode RL

### Episode RL pipeline 2026-07-31T00:05:20
- days: []
- top extract teams: 10
- decks mined to field: 19
- trajectories: 140
- paths: `episodes/raw`, `recordings/metrics`, `data/rl_from_episodes`
- focus: Grimmsnarl/Alakazam matchups for Archaludon


### Episode RL pipeline 2026-07-31T00:26:41
- days: ['2026-07-29', '2026-07-28']
- top extract teams: 0
- decks mined to field: 69
- trajectories: 150
- paths: `episodes/raw`, `recordings/metrics`, `data/rl_from_episodes`
- focus: Grimmsnarl/Alakazam matchups for Archaludon

### Episode RL pipeline 2026-07-31T00:59:17
- days: ['2026-07-29', '2026-07-28']
- top extract teams: 0
- decks mined to field: 69
- trajectories: 150
- paths: `episodes/raw`, `recordings/metrics`, `data/rl_from_episodes`
- focus: Grimmsnarl/Alakazam matchups for Archaludon

---

## Quota reset ship monitor
### Quota monitor 2026-07-31T01:55:12
- **Quota ship monitor STARTED** thresholds: overall≥83.0 crustle≥89.0 iono≥55.0
- package: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\archaludon.tar.gz`


### Quota monitor 2026-07-31T01:53:44
- **Quota ship monitor STARTED** thresholds: overall≥83.0 crustle≥89.0 iono≥55.0
- package: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\archaludon.tar.gz`


### Quota monitor 2026-07-31T01:53:17
- **Quota ship monitor STARTED** thresholds: overall≥83.0 crustle≥89.0 iono≥55.0
- package: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\archaludon.tar.gz`


### Quota monitor 2026-07-31T01:41:16
- **Quota ship monitor STARTED** thresholds: overall≥83.0 crustle≥89.0 iono≥55.0
- package: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\archaludon.tar.gz`


### Quota monitor 2026-07-31T01:39:17
- **Quota ship monitor STARTED** thresholds: overall≥83.0 crustle≥89.0 iono≥55.0
- package: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\archaludon.tar.gz`



### Quota monitor 2026-07-31T01:37:43
- **Quota ship monitor STARTED** thresholds: overall≥83.0 crustle≥89.0 iono≥55.0
- package: `E:\PTCG_AI_Battle_Challenge\kaggle_pokemon\dist\candidates\archaludon.tar.gz`

