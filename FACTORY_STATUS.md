# PTCG AI Battle Challenge - 專案狀態記錄

**最後更新**：2026-07-31 ~01:41 local  
**策略**：Archaludon 75wr 殼 + Crustle lever · loop + CUDA MCTS  
**Canonical**：`E:\PTCG_AI_Battle_Challenge\kaggle_pokemon`  
**Supervisor**：`scripts/mainline_supervisor.py`（只保活 loop / focus / mcts / status；不 submit Dra/Alak）

---

## Live cycle 狀態表（主線 · 重啟後）

| Role | PID 模式 | Cycle | 備註 |
|------|----------|------:|------|
| mainline_supervisor | venv→sys 成對 | — | **01:39 重啟**（前一輪工人全滅後保活） |
| aggressive_loop | venv→sys | 1+ | Arch sprint；cap 5/5；sleep 300s when cap |
| continuous_focus_gates | venv→sys | 1+ | iono→majkel→flg→dual（director import 已修） |
| train_lucario_MCTS | venv→sys | 0 eval | CUDA 重載 champion |
| factory_cycle_status | 多實例 | 90s | 無害；status 寫入同一 md |
| factory_health_monitor | 背景 | 120s | **僅當 supervisor 死才重啟**；不殺工人 |
| ab_iono r14n/r14v | 背景 n200 | — | CPU A/B；default 仍 r14n |

venv launcher + sys worker 成對是正常現象，**勿用 dedupe 殺 sys**。

### Gates vs 目標

| Metric | Latest (post-restart) | Target | Gap | 瓶頸？ |
|--------|----------------------:|-------:|----:|--------|
| Arch sprint overall | **78.1%** (n32) | ≥85% | −6.9 | Iono + majkel 抖 |
| Iono | **30.0%** focus n40；pooled r14n **32.2%** | ≥55% | −25 | **#1 μ 瓶頸** |
| Crustle flg | ~87.5% | ≥89% | −1.5 | 抖 |
| Crustle majkel | **78–80%** 本輪 | ≥89% | −9 | **#2 抖動** |
| Dual overall | 待 focus 完成 | ≥95% | — | 跟 majkel |

### 本輪 μ 動作

1. **保活**：發現 loop/focus/MCTS/supervisor 全滅 → 只重啟 `mainline_supervisor`（未殺其他 session 的 n400 iono gate）
2. **r14v** lever 已入 `archaludon_agent`（`ARCH_IONO_LEVER=r14v`）：r14n 晚期 + 軟 pre-MD；A/B n200+guard 進行中
3. Default **仍 r14n**；僅 Δ≥+3pp 且 crustle guard 才切
4. Dra/Alak `every_n_cycles=9999`（下次 loop 進程重載生效）— 不再浪費 gate CPU
5. Pipeline 複刻：`report/PIPELINE_REPLICATION_20260731.md`（PPO retired；Arch=rules lever；MCTS=Lucario 副線）
6. **不自動提交** Dra/Alak；Arch 僅 ship floors 全清

### 政策

- **不自動提交 Dra/Alak**（`block_submit_ids`）
- Arch 僅在 iono floor≥55% + ship bar 才燒額度
- 官方 pipeline：Transformer+MCTS sample → 本地 `train_lucario_field_mcts`；episode catalog 供 BC/expert-iter 對手；Track B PPO **retired**

### 狀態檔

- 每 cycle 表：`report/aggressive/factory_cycle_status.md`
- monitor：`report/aggressive/factory_monitor.log`
- focus：`recordings/metrics/focus_latest.json`
- A/B：`report/aggressive/ab_r14v.out` · `recordings/metrics/iono_ab_latest.json`
