# PROGRESS → see STATE.md

The 157 KB append-only log from Sessions 1–43 was **reset on 2026-06-22 (Session 44)**. It is
preserved in full at branch `graveyard/pre-reset-20260622`:

```bash
git show graveyard/pre-reset-20260622:PROGRESS.md   # full historical run log
```

Going forward there is **one** handoff/state file — [`STATE.md`](STATE.md) — not two parallel logs
(Ruling R10). The consolidated record of what every past session tried and why it failed now lives
in [`RULINGS.md`](RULINGS.md), which is far more useful than the chronological log it replaces.

**Where things went:**
- *What's true now + next action* → `STATE.md`
- *Ephemeral Cursor session* → `.cursor/SESSION.md`
- *What we tried + why (the 43-session synthesis)* → `RULINGS.md`
- *What we're building* → `ARCHITECTURE.md`
- *How to work here* → `AGENTS.md`

**Latest (2026-06-22, Session 44c):** Local Lucario field RL+MCTS stack committed (`251da2b`);
5-cycle CPU training running → `rl_mcts_field/lucarioex_v1/`. Next: finish train → package →
`gate_vs_public` → compare to SearchScorer 668 μ before any upload.
