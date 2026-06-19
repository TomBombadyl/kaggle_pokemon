# Sample Agents & Meta — Reusable Patterns (T6)

Sources (community, read 2026-06-19; reconfirm specifics against the official
sample notebooks once data is downloaded):
- Official docs random agent (matsuoinstitute.github.io/cabt) — the only
  *official* code reference here.
- github.com/wmh/ptcg-abc — 3 rule-based ladder agents + meta write-up.
- Kaggle notebook "A Sample Rule-Based Agent — Iono's Deck" (kiyotah).

## Agent engineering patterns (adopt)
1. **Never-crash scaffold.** Wrap decision logic in try/except and always fall
   back to a legal selection. Mirrors the wmh `_legal_fallback` pattern; ours is
   implemented in `agent/agent.py`. A single crash forfeits the game.
2. **`normalize_selection`.** Coerce the returned indices to satisfy
   `minCount/maxCount`, dedupe, and clamp to range *before* returning. We do this
   in `_take_min` / `_legal_fallback`.
3. **Per-SelectContext handlers.** The cleanest agents branch on
   `select.context` (49 values), not just `select.type`. Roadmap for T7: a
   dispatch table {context -> scorer}. Highest-value contexts to handle first:
   MAIN, ATTACK, SETUP_ACTIVE/BENCH_POKEMON, ATTACH_TO, EVOLVE, SWITCH, DISCARD,
   MULLIGAN/IS_FIRST (yes/no), DRAW_COUNT.
4. **Static MAIN priority is a strong baseline.** attack > evolve > attach
   energy > ability > play > retreat > end. Already in `MAIN_PRIORITY`. Refine in
   T7 with board reads (only attack if it KOs or is net-positive on prize trade).
5. **Lookahead via `search_*` API.** `search_begin/step/end` enables 1-ply (or
   shallow) rollouts to compare candidate moves. Use sparingly — 10-min/player
   time budget; a rule-based agent piloting a *simple* deck cleanly beats a
   complex agent that times out or misplays.

## Meta / deck-design lessons (wmh ladder data)
- **Deck choice dominates** rule-based agent quality — pick a deck a simple
  policy can pilot well.
- **Simplicity wins for rule-based pilots.** wmh's simplest deck (Iono's
  Bellibolt ex, Lightning, Elo 836) beat their "stronger" Stage-2 combo decks,
  because heuristics execute a linear gameplan cleanly.
- **Meta shifts fast & has rock-paper-scissors structure.** At the time of their
  write-up, *Crustle* (immune to ex / mega-ex attacks) ballooned to ~50% of the
  field → **non-ex attackers** and counter-decks gained value (e.g. Kilowattrel).
- **Local sims mispredict ladder rank.** Both a ctypes harness and the official
  `cabt` env disagreed with real-ladder results. Treat offline win-rate as a
  *sanity filter*, not ground truth; the Simulation ladder is the real judge.
- **Single-prize aggro is a live archetype.** Alakazam + Dudunsparce: "Powerful
  Hand" = 20 dmg x cards-in-hand; a Dudunsparce draw engine builds a 15-20 card
  hand for 300-400 damage, all single-prize (denies opponent 2-prize swings).

## Implications for our build (feeds T7/T8)
- Start from a **simple, consistent Lightning/aggro line** the heuristic pilots
  cleanly; keep deck list short on combo pieces.
- Build the **context-dispatch scorer** before chasing a fancy deck.
- Plan a **non-ex attacker** as anti-Crustle insurance in deck design (T8).
- Keep everything **seeded/deterministic** so nightly win-rate deltas are real.
