---
phase: 05-historical-data-backfill
plan: 01
subsystem: database
tags: [sqlite, dhan-api, historical-data, ohlcv, cache, python]

# Dependency graph
requires: []
provides:
  - HistoricalStore class with SQLite schema (historical_prices, historical_vix tables)
  - DhanFetchError exception for strict Dhan API error handling
  - fetch_historical_candles method on DhanClient
  - Cache-first OHLCV fetch (same-day SQLite hit, Dhan fetch otherwise)
  - backfill_all() for sequentially fetching NIFTY, BANKNIFTY, VIX with rate-limiting
affects:
  - 06-signal-engine
  - 07-backtest-engine
  - 08-backtest-dashboard

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cache-first SQLite pattern: check fetched_at >= today before calling Dhan API"
    - "INSERT OR REPLACE for idempotent upserts in historical tables"
    - "Global singleton pattern: historical_store = HistoricalStore() mirrors dhan_client"
    - "DhanFetchError propagation: no silent fallback, raises on non-200 or empty response"

key-files:
  created:
    - gods-eye/backend/app/data/historical_store.py
  modified:
    - gods-eye/backend/app/data/dhan_client.py

key-decisions:
  - "DhanFetchError defined in dhan_client.py (not historical_store.py) so it can be raised at HTTP layer"
  - "BACKFILL_YEARS=2 ensures 252+ trading days across weekends/holidays"
  - "fetched_at column stores fetch timestamp not price date — enables same-day cache freshness check"
  - "asyncio.sleep(1.0) between instruments in backfill_all() is conservative rate-limit for Dhan API"

patterns-established:
  - "Historical data tables always use UNIQUE(instrument, date) constraint with INSERT OR REPLACE for upsert"
  - "Cache freshness is per-trading-day: fetched_at >= today.isoformat()"

requirements-completed: [HIST-01, HIST-02, HIST-03, HIST-04]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 05 Plan 01: Historical Data Backfill — Schema and Data Access Layer Summary

**SQLite-backed HistoricalStore with Dhan OHLCV/VIX fetch, cache-first reads, and DhanFetchError on any API failure**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T20:30:09Z
- **Completed:** 2026-03-30T20:33:22Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `DhanFetchError` exception and `fetch_historical_candles` async method to `DhanClient` — directly uses httpx client (not `_post` helper) so errors raise instead of returning None
- Created `HistoricalStore` class with `historical_prices` and `historical_vix` SQLite tables, composite indexes, and cache-first fetch logic
- All three public methods verified: `get_ohlcv("NIFTY")`, `get_ohlcv("BANKNIFTY")`, `get_vix_closes()` with optional date filters; `backfill_all()` with 1s inter-instrument delay

## Task Commits

1. **Task 1: Add fetch_historical_candles to DhanClient** - `8ed92b3` (feat)
2. **Task 2: Create HistoricalStore — schema, backfill, cache-first fetch** - `63e76e2` (feat)

## Files Created/Modified

- `gods-eye/backend/app/data/dhan_client.py` - Added `DhanFetchError` class and `fetch_historical_candles` async method (72 lines added)
- `gods-eye/backend/app/data/historical_store.py` - New file: `HistoricalStore` class with SQLite schema init, cache-check helpers, Dhan fetch+upsert, and public API (292 lines)

## Decisions Made

- `DhanFetchError` lives in `dhan_client.py` rather than a separate exceptions module — keeps the raise site and definition co-located; historical_store.py imports it from there
- `BACKFILL_YEARS = 2` chosen to guarantee 252+ trading days even accounting for Indian market holidays and weekends
- `fetched_at` column stores the UTC fetch timestamp (not the price date) — this is what the cache freshness check compares against `date.today().isoformat()`
- `fetch_historical_candles` bypasses the existing `_post` helper (which swallows exceptions via `logger.warning + return None`) and calls `client.post()` directly, raising `DhanFetchError` on non-200 or missing arrays

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The store reads `GODS_EYE_DB_PATH` from environment (already documented in `.env.example`). Dhan API credentials (`DHAN_ACCESS_TOKEN`, `DHAN_CLIENT_ID`) were already required and documented in v1.0.

## Next Phase Readiness

- `HistoricalStore` is ready for Phase 06 (signal engine) to call `get_ohlcv("NIFTY")` and `get_vix_closes()`
- Phase 07 (backtest engine) can call `get_ohlcv` with `from_date`/`to_date` filters for date-ranged replays
- Concern: Dhan API rate limits for `/charts/historical` are undocumented — `backfill_all()` uses 1s delay between instruments as a conservative guard; monitor on first production run

---
*Phase: 05-historical-data-backfill*
*Completed: 2026-03-31*

## Self-Check: PASSED

- FOUND: gods-eye/backend/app/data/historical_store.py
- FOUND: gods-eye/backend/app/data/dhan_client.py
- FOUND: .planning/phases/05-historical-data-backfill/05-01-SUMMARY.md
- FOUND commit: 8ed92b3 (Task 1)
- FOUND commit: 63e76e2 (Task 2)
