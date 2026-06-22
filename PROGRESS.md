# PROGRESS → see STATE.md

The 157 KB append-only log from Sessions 1–43 was **reset on 2026-06-22 (Session 44)**. It is
preserved in full at branch `graveyard/pre-reset-20260622`:

```bash
git show graveyard/pre-reset-20260622:PROGRESS.md   # full historical run log
```

Going forward there is **one** handoff/state file — [`STATE.md`](STATE.md) — not two parallel logs
(Ruling R10). The consolidated record of what every past session tried and why it failed now lives
in [`RULINGS.md`](RULINGS.md).

**Where things went:**
- *What's true now + next action* → `STATE.md`
- *Ephemeral Cursor session* → `.cursor/SESSION.md`
- *What we tried + why* → `RULINGS.md`
- *What we're building* → `ARCHITECTURE.md` (§ Per-deck template phases 1–3)
- *Build backlog* → `TASKS.md` (R1–R3 pilot rules)

**Latest (2026-06-22, Session 44d):** Standing order solidified — **(1) global rules per deck →
(2) per-opponent matchup levers → (3) field-mixture weighting**. Meta tracker is phase-3 input.
Lucario field RL train cycle 3+ in `metrics.csv`. Next: gate Lucario global rules baseline, then
first Abomasnow lever.
