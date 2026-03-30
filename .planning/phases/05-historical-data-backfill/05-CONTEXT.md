# Phase 5: Historical Data Backfill - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase)

<domain>
## Phase Boundary

System has 1+ year of daily OHLCV data for Nifty 50 and Bank Nifty, plus daily VIX closes, all fetched from Dhan API and stored in SQLite. Data refreshes daily during market hours. Dhan failure raises explicit error — no fallback to mock data.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
Infrastructure phase. Key requirements:
- HIST-01: Fetch and store Nifty 50 daily OHLCV from Dhan (1yr minimum)
- HIST-02: Fetch and store Bank Nifty daily OHLCV from Dhan (1yr minimum)
- HIST-03: Fetch and store India VIX daily close values
- HIST-04: Cache in SQLite, refresh daily during market hours

Dhan historical data API: Use /charts/historical endpoint with daily candles.
Store in a new `historical_prices` table in the existing SQLite database.
Add a CLI command or startup hook to trigger initial backfill.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- app/data/dhan_client.py — Dhan API client (needs historical endpoint methods)
- app/config.py — DATABASE_PATH for SQLite location
- app/data/cache.py — in-memory cache layer
- alembic/ — migration framework already set up

### Established Patterns
- Async httpx for API calls
- SQLite via sqlite3 (prediction_tracker.py pattern)
- Dhan auth headers: access-token + client-id

### Integration Points
- New table: historical_prices (date, instrument, open, high, low, close, volume)
- New table: historical_vix (date, close)
- Dhan endpoint: POST /charts/historical with exchangeSegment, instrument, interval, fromDate, toDate

</code_context>

<specifics>
## Specific Ideas

- Dhan charts/historical returns OHLCV candles. Use "DAY" interval.
- Nifty 50 security ID on Dhan: "13", Bank Nifty: "25"
- Rate limit Dhan calls conservatively (1 request per second)
- Backfill on first run, then daily incremental refresh

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
