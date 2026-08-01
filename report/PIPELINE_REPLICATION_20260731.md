# Training pipeline replication (local μ path) — 2026-07-31

## Official / community stacks that actually move μ

| Stack | Source | Local map | Ladder evidence |
|-------|--------|-----------|-----------------|
| **Rules + matchup levers** | sample Arch 75wr / our R7 | `agent/archaludon_agent.py` + 75wr deck | **1196.1 μ** champion |
| **Transformer + MCTS self-play** | official sample notebook | `train_lucario_field_mcts.py` CUDA | Lucario peak ~651 μ (v5 regressed 580) |
| **PPO → distill** | public discussions / Track B | **RETIRED** (`data/EVAL_PROTOCOL.md`) | best **585 μ** |
| **Linear selector / GPU meta** | metal_gpu_v28 extracted | not ship default | contender research |
| **Episode mine → BC/expert-iter opponents** | `episode_rl_pipeline.py` | decks + traj stubs in `data/rl_from_episodes/` | feeds gates, not brain yet |

## Locked local policy (this factory)

```
episodes (daily) ──► mine decks / traj stubs
        │
        ▼
Arch rules single-lever A/B ──► focus gates (iono/flg/majkel/dual)
        │                         │
        │                         ▼
        │                    director_gate floors
        │                    (iono≥55, arch≥83, crustle≥89)
        ▼
CUDA field MCTS (Lucario) ──► secondary research only
        │
        ▼
NO auto-submit Dra/Alak · Arch only when ship floors clear · cap 5/day
```

**Do not** re-open full Track B PPO. **Do not** put MCTS/SearchScorer on Arch list (ruled out, ladder regressions).

## Expert-iteration loop that raises Arch local WR

1. **Diagnose** with focus n=40–80 + pooled n≥400 before accepting a lever.
2. **One lever** via `ARCH_IONO_LEVER` (never stack until n≥400 KEEP).
3. **Guard** Crustle flg/majkel ≥85 after any iono change.
4. **Promote** only if iono Δ ≥ +3pp vs r14n pooled and dual holds ≥95 rolling.

### Current lever ledger (iono @ real_iono)

| Lever | n | WR% | Decision |
|-------|--:|----:|----------|
| none | 800 | 29.8 | baseline |
| r14n | 2400 | 32.2 | **KEEP default** |
| r14m / r14u / r14o / r14q / r14s / r14k | various | ≤31 or crash | REJECT |
| **r14v** | A/B running | ? | r14n + soft pre-MD engine |

## Commands

```powershell
# Focus (already running via supervisor)
python -u scripts/continuous_focus_gates.py

# Iono A/B (CPU; does not touch CUDA MCTS)
$env:ARCH_IONO_LEVER='r14n'; python -u scripts/ab_iono_lever.py --levers r14n r14v --games 200 --guard

# Episode refresh (no submit)
python -u scripts/episode_rl_pipeline.py --days 2 --top 10

# MCTS (already running)
python -u scripts/train_lucario_field_mcts.py --device cuda --auto-resume
```
