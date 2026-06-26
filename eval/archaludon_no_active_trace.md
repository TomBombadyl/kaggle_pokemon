# Archaludon no_active ladder trace (ref 54083197)

Two `no_active` losses from 42 public ladder games (76.2% WR).

## 82055480 — classic empty bench (turn 3)

| Field | Value |
|-------|-------|
| Opponent | kuma_jp |
| Turn | 3 |
| Setup | Never placed a basic on bench (`bench_count=0` entire game) |

**Failure chain (deck POV):**

1. **Turn 2 MAIN** — 6 options, hand 7, bench 0, active Duraludon (169). Agent did not PLAY a basic (`action=[]` in log).
2. **Turn 2** — picked option index 2 on 5-option MAIN (hand 7→6); active gained energy 0→1 → **attach before bench**.
3. Remainder of turn 2 — stuck on 2-option MAIN (likely END vs attack submenu), still bench 0.
4. Turn 3 — active KO with no bench → **`no_active`**.

**Root cause (pre-R7b ladder):** community v5 scored SETUP_BENCH `-10000` and Ultra Ball +300 beat END when bench empty; agent skipped setup bench and turn-2 bench.

**R7b fix in `archaludon_agent.py`:** `_empty_bench_basic_score`, MAIN END penalty, setup `_SETUP_BENCH_PRIORITY`, Ultra Ball `-5000` when bench empty.

---

## 82068759 — early empty bench + late TO_HAND stall (turn 15)

| Field | Value |
|-------|-------|
| Opponent | yomogi mochi |
| Turn | 15 |
| Terminal | bench 1 (Relicanth 57), active Archaludon ex (190) in last logged step |

**Early game (same class as 82055480):**

- Turn 2 MAIN 6 opts, bench 0 — no bench play.
- Turn 2 action `[2]` on 5 opts — attach/item before bench (hand 7→6, energy on active).

**Late game:**

- Turn 14 — repeated **TO_HAND** (context 7), 3 options, empty actions in deck log.
- Ladder labels loss **`no_active`** — terminal loser had **empty active slot** (Relicanth on bench but no promotion before loss).

**Hypothesis:** separate from empty-bench guard — mandatory **TO_ACTIVE** / promotion after active KO may have scored poorly vs TO_HAND effect, or deck log missed the promotion step. Lower priority than turn-2 bench; only 1 of 2 `no_active` games shows late-game bench present.

---

## Local A/B (agent scoring vs +packaged guard)

See [`archaludon_bench_guard_ab.md`](archaludon_bench_guard_ab.md).

| Variant | WR | n | no_active |
|---------|-----|---|-----------|
| Agent R7b only (`ARCHALUDON_BENCH_GUARD=0`) | 66.4% | 250 | **8** |
| + packaged guard | 68.0% | 250 | **5** |

Both include in-agent `_empty_bench_basic_score`. Guard still removes 3 `no_active` at +1.6 pp overall but **hurts vs `dragapult_ex_sample`** (-14 pp) — keep iterating in **`archaludon_agent.py`**, not guard-only overrides.

**Next in agent:** verify turn-2 MAIN always benches when PLAY basic legal; optional TO_ACTIVE boost when bench non-empty and active empty.
