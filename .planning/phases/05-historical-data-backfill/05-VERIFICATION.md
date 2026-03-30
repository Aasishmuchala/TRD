---
phase: 05-historical-data-backfill
verified: 2026-03-31T00:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Start backend with valid DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID, confirm startup logs show 'Backfill complete' with N > 200 per instrument"
    expected: "{'NIFTY': 252+, 'BANKNIFTY': 252+, 'VIX': 252+} in startup log; no crash"
    why_human: "Requires live Dhan API credentials and running backend — cannot mock a real HTTP response in static analysis"
  - test: "Call GET /api/market/historical/nifty twice in the same trading day; inspect server logs for absence of a second Dhan HTTP request"
    expected: "Second call returns data from SQLite (no Dhan request in logs)"
    why_human: "Cache behavior requires observing runtime logs, not inferrable from static code analysis alone"
  - test: "Unset DHAN_ACCESS_TOKEN, clear historical tables, call GET /api/market/historical/nifty"
    expected: "HTTP 502 with {'detail': 'Dhan API error: ...'} — not a silent empty list or 500"
    why_human: "Requires live server with deliberate Dhan misconfiguration to exercise the error path end-to-end"
---

# Phase 05: Historical Data Backfill Verification Report

**Phase Goal:** System has 1+ year of daily OHLCV data for Nifty 50 and Bank Nifty, plus daily VIX closes, all fetched from Dhan API and stored in SQLite. Data refreshes daily during market hours. Dhan failure raises explicit error.
**Verified:** 2026-03-31
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `DhanClient.fetch_historical_candles` exists, is async, and raises `DhanFetchError` (not returns None) on non-200 or missing OHLCV arrays | VERIFIED | `fetch_historical_candles` is a `coroutinefunction` on `DhanClient`; 3 explicit `raise DhanFetchError(...)` calls confirmed by AST; bypasses `_post` helper which would swallow errors |
| 2 | `historical_prices` table schema: `id, instrument, date, open, high, low, close, volume, fetched_at`, UNIQUE(instrument, date) | VERIFIED | `_init_schema` in `historical_store.py` lines 52-65 creates the table with all required columns; UNIQUE constraint present |
| 3 | `historical_vix` table schema: `id, date, close, fetched_at`, UNIQUE(date) | VERIFIED | `_init_schema` lines 67-74 creates the table with required columns; UNIQUE date constraint present |
| 4 | `get_ohlcv` returns cached data when `fetched_at >= today` — no new Dhan request within the same trading day | VERIFIED | `_is_cache_fresh` uses `WHERE fetched_at >= ? LIMIT 1` with `today = date.today().isoformat()`; `get_ohlcv` skips `_fetch_and_store` when `_is_cache_fresh` returns True |
| 5 | `backfill_all` fetches all 3 instruments (NIFTY, BANKNIFTY, VIX) sequentially | VERIFIED | `for instrument in ["NIFTY", "BANKNIFTY", "VIX"]` at line 284 of `historical_store.py`; `asyncio.sleep(1.0)` between requests |
| 6 | API endpoints `GET /api/market/historical/{instrument}` and `POST /api/market/historical/backfill` are registered | VERIFIED | `python3` import confirms both routes on `protected_router`: `('/api/market/historical/{instrument}', ['GET'])` and `('/api/market/historical/backfill', ['POST'])` |
| 7 | Startup hook triggers `backfill_all()` when `_count_rows("NIFTY") < 10`; Dhan failure logs warning and does not crash startup | VERIFIED | `run.py` lines 145-156: `if nifty_rows < 10` → `await historical_store.backfill_all()`; `except DhanFetchError as exc` logs WARNING without re-raising |

**Score:** 7/7 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `gods-eye/backend/app/data/dhan_client.py` | `DhanFetchError` class + `fetch_historical_candles` async method | VERIFIED | `DhanFetchError` is `Exception` subclass; `fetch_historical_candles` is `coroutinefunction`; 3 raise sites confirmed |
| `gods-eye/backend/app/data/historical_store.py` | `HistoricalStore` class with schema, backfill, cache-first fetch | VERIFIED | All 6 methods present (`get_ohlcv`, `get_vix_closes`, `backfill_all`, `_is_cache_fresh`, `_count_rows`, `_fetch_and_store`); `historical_store` singleton exported |
| `gods-eye/backend/app/api/routes.py` | Two new historical endpoints | VERIFIED | Both routes confirmed registered at runtime import; `DhanFetchError` maps to HTTP 502 |
| `gods-eye/backend/run.py` | Startup hook with `backfill_all` trigger | VERIFIED | All 4 required patterns present: `backfill_all`, `DhanFetchError`, `_count_rows`, `nifty_rows < 10` |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `historical_store.py` | `dhan_client.py` | `dhan_client.fetch_historical_candles()` | WIRED | `_fetch_and_store` calls `await dhan_client.fetch_historical_candles(security_id, from_date, to_date)` at line 159 |
| `historical_store.py` | SQLite DB | `sqlite3.connect(self.db_path)` | WIRED | Multiple `sqlite3.connect(self.db_path)` calls in `_init_schema`, `_is_cache_fresh`, `_count_rows`, `_fetch_and_store`, `get_ohlcv`, `get_vix_closes` |
| `routes.py` | `historical_store.py` | `historical_store.get_ohlcv()` / `get_vix_closes()` | WIRED | Imported via `from app.data.historical_store import historical_store`; called in `get_historical_data` endpoint body |
| `routes.py` | `dhan_client.py` | `DhanFetchError` exception catch | WIRED | Imported via `from app.data.dhan_client import DhanFetchError`; caught and re-raised as HTTP 502 in both historical endpoints |
| `run.py` | `historical_store.py` | `await historical_store.backfill_all()` | WIRED | `startup_event` imports `historical_store` locally and calls `backfill_all()` guarded by `< 10` row check |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HIST-01 | 05-01, 05-02 | Dhan API client fetches daily OHLCV candles for Nifty 50 and Bank Nifty | SATISFIED | `fetch_historical_candles` with `security_id` "13" (Nifty) and "25" (BankNifty); stored to `historical_prices` table |
| HIST-02 | 05-01, 05-02 | Dhan API client fetches daily VIX closes | SATISFIED | `fetch_historical_candles` with `security_id` "26" (VIX); stored to `historical_vix` table |
| HIST-03 | 05-01, 05-02 | SQLite stores 1+ year of daily history; cache-first read prevents redundant Dhan calls within same day | SATISFIED | `BACKFILL_YEARS = 2` (730 calendar days, ~504 trading days); `_is_cache_fresh` uses `fetched_at >= today` check |
| HIST-04 | 05-01, 05-02 | Dhan failure raises explicit error — no silent fallback to empty/mock data | SATISFIED | `DhanFetchError` raised on non-200, missing arrays, and zero candles; propagated through `routes.py` as HTTP 502 |

---

## Anti-Patterns Found

No anti-patterns detected across key files (`dhan_client.py`, `historical_store.py`, `routes.py`, `run.py`). No TODO/FIXME/placeholder comments, no stub implementations, no return-null handlers, no swallowed exceptions in the historical data path.

**One design note (not a blocker):** The `_post` helper on `DhanClient` (lines 72-81) still swallows exceptions via `return None`. This pre-existing behavior is intentional for live quote endpoints and is correctly bypassed by `fetch_historical_candles` which calls `client.post()` directly. The isolation is deliberate and documented.

---

## Human Verification Required

### 1. Live Startup Backfill

**Test:** Start backend fresh (`uvicorn run:app --reload`) with valid `DHAN_ACCESS_TOKEN` and `DHAN_CLIENT_ID` set. Read startup logs.
**Expected:** Log line "Historical DB is empty — triggering full backfill from Dhan..." followed by "Backfill complete: {'NIFTY': N, 'BANKNIFTY': N, 'VIX': N}" with N > 200 for each.
**Why human:** Requires live Dhan API credentials and a real HTTP response. Static analysis confirms the code path exists and is wired; actual 252+ row count requires a real API call.

### 2. Cache Hit Verification

**Test:** With a populated DB, call `GET /api/market/historical/nifty` twice in the same calendar day. Observe server logs for the second call.
**Expected:** Second call produces no Dhan HTTP request (only SQLite read). Log should NOT contain "Fetching historical data for NIFTY".
**Why human:** Cache behavior is runtime-observable; `_is_cache_fresh` logic is verified in code but the actual absence of a network call requires runtime log inspection.

### 3. Dhan Failure -> HTTP 502

**Test:** Unset `DHAN_ACCESS_TOKEN`, clear the `historical_prices` table, call `GET /api/market/historical/nifty`.
**Expected:** HTTP 502 with `{"detail": "Dhan API error: HTTP request failed for securityId=13: ..."}`. No 200 with empty list. No 500.
**Why human:** Requires deliberately misconfigured Dhan credentials and a running server. Code path confirmed present (3 raise sites + 502 catch in routes), but end-to-end behavior needs live validation.

---

## Gaps Summary

No gaps. All 7 observable truths are verified against the actual codebase. All 4 artifacts are present, substantive, and wired. All 4 requirements (HIST-01 through HIST-04) are satisfied by concrete implementation evidence.

The 3 human verification items are runtime behaviors that cannot be confirmed through static analysis alone. They are checkpoints, not blockers — the code implementing them is fully verified.

---

_Verified: 2026-03-31_
_Verifier: Claude (gsd-verifier)_
