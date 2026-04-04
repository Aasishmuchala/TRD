---
phase: 05-historical-data-backfill
plan: "02"
subsystem: api
tags: [fastapi, sqlite, dhan, historical-data, ohlcv, backfill]

# Dependency graph
requires:
  - phase: 05-01
    provides: HistoricalStore with get_ohlcv/get_vix_closes/backfill_all and DhanFetchError

provides:
  - GET /api/market/historical/{instrument} endpoint (nifty/banknifty/vix)
  - POST /api/market/historical/backfill endpoint for manual trigger
  - Startup hook in run.py that auto-backfills on fresh database (< 10 NIFTY rows)

affects:
  - 06-backtest-engine
  - 07-signal-engine
  - phase-06
  - phase-07

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DhanFetchError -> HTTP 502: Dhan API failures surface as explicit 502 (not 500, not silent empty)"
    - "Startup-safe backfill: threshold < 10 rows handles partial-backfill edge case; DhanFetchError caught so Railway deploy succeeds without Dhan credentials"
    - "Cache-first through API layer: routes delegate cache logic to HistoricalStore; no cache logic in routes.py"

key-files:
  created: []
  modified:
    - gods-eye/backend/app/api/routes.py
    - gods-eye/backend/run.py

key-decisions:
  - "DhanFetchError maps to HTTP 502 (not 500) to signal upstream dependency failure, consistent with REST conventions"
  - "Startup backfill uses < 10 row threshold (not == 0) to handle prior partial backfills"
  - "Startup backfill failure logs WARNING and continues app startup — Railway deploy must succeed even without Dhan credentials configured"

patterns-established:
  - "Historical endpoints: GET /api/market/historical/{instrument} pattern for all future instrument data endpoints"
  - "Startup hooks: import data layer modules inside startup_event function to avoid circular import risk at module load time"

requirements-completed: [HIST-01, HIST-02, HIST-03, HIST-04]

# Metrics
duration: 2min
completed: 2026-03-31
---

# Phase 05 Plan 02: Historical API Endpoints & Startup Backfill Summary

**Three HTTP endpoints exposing SQLite-cached Dhan historical data (NIFTY/BANKNIFTY/VIX) with automatic backfill on fresh database startup**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T20:36:17Z
- **Completed:** 2026-03-30T20:37:59Z
- **Tasks:** 3 (2 auto + 1 checkpoint auto-approved)
- **Files modified:** 2

## Accomplishments

- Added `GET /api/market/historical/{instrument}` endpoint — routes to `get_ohlcv()` for NIFTY/BANKNIFTY, `get_vix_closes()` for VIX; accepts optional `from_date`/`to_date` query params
- Added `POST /api/market/historical/backfill` endpoint — manually triggers `backfill_all()` for all 3 instruments
- Added startup hook in `run.py` — checks NIFTY row count on every startup and triggers `backfill_all()` automatically on fresh or near-empty database; Dhan failures during startup are caught and logged as warnings so Railway deploy succeeds

## Task Commits

Each task was committed atomically:

1. **Task 1: Add historical data endpoints to routes.py** - `2a7dbfe` (feat)
2. **Task 2: Add startup backfill hook in run.py** - `c1898c7` (feat)
3. **Task 3: Human verify (checkpoint)** - auto-approved in autonomous mode

**Plan metadata:** (pending final docs commit)

## Files Created/Modified

- `gods-eye/backend/app/api/routes.py` - Added `from app.data.historical_store import historical_store`, `from app.data.dhan_client import DhanFetchError`, and two new endpoint functions at end of file
- `gods-eye/backend/run.py` - Extended `startup_event()` with backfill check and call

## Decisions Made

- DhanFetchError maps to HTTP 502 (not 500) — explicitly signals upstream dependency failure, enabling callers to distinguish app bugs from Dhan outages
- Startup backfill uses `< 10` row threshold rather than `== 0` — handles case where a prior partial backfill left table with a few rows
- Startup failure is non-fatal — `DhanFetchError` caught and logged as WARNING; Railway deployment succeeds before Dhan credentials are set

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required beyond what was established in 05-01 (DHAN_ACCESS_TOKEN, DHAN_CLIENT_ID env vars).

## Next Phase Readiness

- All historical data infrastructure complete (Phase 5 fully done)
- `GET /api/market/historical/{instrument}` is ready for Phase 6 backtest engine to query OHLCV data
- `GET /api/market/historical/vix` provides VIX regime data for signal engine (Phase 7)
- Fresh Railway deploy will auto-populate historical DB on first startup

---
*Phase: 05-historical-data-backfill*
*Completed: 2026-03-31*

## Self-Check: PASSED

- gods-eye/backend/app/api/routes.py: FOUND
- gods-eye/backend/run.py: FOUND
- .planning/phases/05-historical-data-backfill/05-02-SUMMARY.md: FOUND
- Commit 2a7dbfe (Task 1): FOUND
- Commit c1898c7 (Task 2): FOUND
