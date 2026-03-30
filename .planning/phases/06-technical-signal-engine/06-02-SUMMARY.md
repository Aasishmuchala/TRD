---
phase: 06-technical-signal-engine
plan: 02
subsystem: api, database
tags: [sqlite, fastapi, technical-signals, oi, options, historical-data]

# Dependency graph
requires:
  - phase: 06-01
    provides: TechnicalSignals class with compute_signals_for_date, classify_vix_regime, and technical_signals singleton
  - phase: 05
    provides: HistoricalStore with get_ohlcv(), get_vix_closes(), SQLite historical_prices and historical_vix tables
provides:
  - oi_snapshots SQLite table with store_oi_snapshot() and get_oi_snapshot() sync methods on HistoricalStore
  - GET /api/market/signals/{instrument}/{date} endpoint returning rsi, vwap_deviation_pct, supertrend, vix_regime, vix_close, and oi
  - POST /api/market/oi/capture endpoint for live OI snapshot capture from Dhan
affects: [07-backtest-engine, signal-scoring, backtest-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sync methods (store_oi_snapshot, get_oi_snapshot) on HistoricalStore alongside existing async methods"
    - "PCR-to-sentiment derivation: >1.2 = bullish, <0.8 = bearish, else neutral"
    - "VIX fallback to nearest-prior date when exact date missing — non-fatal for signal assembly"
    - "OI data is nullable in signal response — historical dates before capture return oi: null"

key-files:
  created: []
  modified:
    - gods-eye/backend/app/data/historical_store.py
    - gods-eye/backend/app/api/routes.py

key-decisions:
  - "store_oi_snapshot and get_oi_snapshot are sync methods — OI capture is not latency-sensitive, no async needed"
  - "Signal endpoint returns oi: null (not 404) when OI snapshot missing — historical dates before capture are valid"
  - "VIX regime falls back to nearest-prior VIX row when exact date missing — preserves response shape, avoids 404"
  - "No rate limit on GET /market/signals/{instrument}/{date} — called in tight loops by Phase 7 backtest engine"
  - "capture_oi_snapshot uses fetch_options_summary() for NIFTY and get_option_chain('25') for BANKNIFTY — mirrors Dhan API capability split"

patterns-established:
  - "PCR-based OI sentiment: >1.2 = bullish (contrarian put-heavy), <0.8 = bearish (call-heavy), 0.8-1.2 = neutral"
  - "Signal assembly pattern: OHLCV-based signals + VIX regime + OI snapshot → unified response dict"

requirements-completed: [TECH-04, TECH-01, TECH-02, TECH-03, TECH-05]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 06 Plan 02: Technical Signal Engine — Signals API Summary

**OI snapshot storage with SQLite oi_snapshots table and GET /api/market/signals/{instrument}/{date} assembling RSI, VWAP deviation, Supertrend, VIX regime, and nullable OI for Phase 7 backtest engine**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-30T20:55:46Z
- **Completed:** 2026-03-31T21:01:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Extended HistoricalStore with oi_snapshots SQLite table (UNIQUE on instrument+date), store_oi_snapshot(), and get_oi_snapshot() sync methods with PCR-derived net_sentiment
- Wired GET /api/market/signals/{instrument}/{date} assembling all five technical dimensions (RSI, VWAP deviation, Supertrend, VIX regime, OI) into a single response
- Added POST /api/market/oi/capture endpoint to snapshot live OI from Dhan for both NIFTY and BANKNIFTY

## Task Commits

Each task was committed atomically:

1. **Task 1: Add oi_snapshots table and OI store/fetch methods to HistoricalStore** - `43e73ee` (feat)
2. **Task 2: Add signals endpoint and OI capture endpoint to routes.py** - `051705c` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `gods-eye/backend/app/data/historical_store.py` - Added oi_snapshots table in _init_schema(), store_oi_snapshot() and get_oi_snapshot() sync methods
- `gods-eye/backend/app/api/routes.py` - Added TechnicalSignals import, GET /market/signals/{instrument}/{date} and POST /market/oi/capture endpoints

## Decisions Made
- store_oi_snapshot and get_oi_snapshot are synchronous — no Dhan API call inside, SQLite only, no async overhead needed
- Signal endpoint returns `oi: null` rather than HTTP 404 for missing OI snapshot — historical dates predate OI capture
- VIX regime resolution uses nearest-prior VIX row (not exact match) with graceful DhanFetchError pass — VIX absence is a data gap not a crash
- No rate limit decorator on signals endpoint per plan spec — Phase 7 backtest engine calls it in tight date loops
- BANKNIFTY OI uses get_option_chain("25") + manual CE/PE aggregation since fetch_options_summary() only covers NIFTY

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 7 (backtest engine) has a clean single HTTP call to retrieve all technical context for any stored date via GET /api/market/signals/{instrument}/{date}
- OI history builds via POST /api/market/oi/capture called after market close; historical dates before capture return oi: null gracefully
- All TECH-01 through TECH-05 requirements addressed: RSI (TECH-01), VWAP deviation (TECH-02), Supertrend (TECH-03), OI change (TECH-04), VIX regime (TECH-05)

---
*Phase: 06-technical-signal-engine*
*Completed: 2026-03-31*
