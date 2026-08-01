# Director decision 2026-07-31T02:00:06.2570923+08:00
UTC: 2026-07-30T18:00:06.2581150Z
until_midnight_s: 21594

## CRITICAL FIX
- crustle_MissingNo_v1/v2 packages had agent/deck.csv = ARCHALUDON (169/190/666). Root deck.csv was Crustle.
- REPACKAGED v1 with agent/deck.csv == Crustle MissingNo (344/345/117/756/1182). package_submission.py now overwrites agent/deck.csv.
- Broken archives renamed zz_broken_* out of wait glob.

## PROCESS
- KILL: duplicate wait_and_submit (had archaludon_only queue + race)
- KEEP/START: single wait_and_submit_crustle PID=119828 crustle_only queue
- aggressive_loop restarted with block_submit_ids += archaludon (no auto Arch/Dra/Alak)
- CAP 5/5 until UTC 2026-07-31 00:00:00

## SHIP PLAN (UTC dayroll)
1. FIRST: dist/candidates/crustle_MissingNo_v1.tar.gz ONLY (fixed deck)
2. SECOND: only if clear Crustle upgrade (WR +3pp) — else HOLD
3. NEVER auto: Arch / Dra / Alak

## HOLD
- Do not ship Arch until Iono floor >=55% AND human overrides block
- Do not burn more CAP today

## MONITOR
- wait sleep_s=120 until midnight; then submit + log
