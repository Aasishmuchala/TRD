---
phase: 03-frontend-polish-and-ux-completeness
plan: "02"
subsystem: market-ticker
tags: [bank-nifty, market-data, nse, frontend, ticker]
dependency_graph:
  requires: []
  provides: [bank-nifty-live-data, bank-nifty-ticker-display]
  affects: [MarketTicker, get_live_snapshot, /api/market/live]
tech_stack:
  added: []
  patterns: [nse-index-fetch, asyncio-gather-parallel, graceful-fallback]
key_files:
  created: []
  modified:
    - TRD/gods-eye/backend/app/data/market_data.py
    - TRD/gods-eye/frontend/src/components/MarketTicker.jsx
decisions:
  - "_fetch_bank_nifty uses equity-stockIndices?index=NIFTY%20BANK endpoint (same pattern as _fetch_nifty50) and is added to asyncio.gather() for zero latency overhead"
  - "Bank Nifty fallback returns zeroed dict (last=0, change=0, change_pct=0) — no exception propagated, no crash"
  - "Frontend falls back to '--' when bank_nifty_spot is 0/falsy; change indicator hidden entirely when spot is 0"
  - "npm install fixed pre-existing rollup native module issue (missing @rollup/rollup-darwin-arm64 optional dep)"
metrics:
  duration: 141s
  completed_date: "2026-03-30"
  tasks_completed: 2
  files_modified: 2
---

# Phase 03 Plan 02: Bank Nifty Live Ticker Summary

**One-liner:** Bank Nifty added to live market ticker — backend fetches from NSE NIFTY BANK endpoint in parallel with existing indices; MarketTicker.jsx displays BANK between NIFTY and VIX with bull/bear coloring and graceful '--' fallback.

## What Was Built

Added Bank Nifty (NIFTY BANK) as the second index in the dashboard header ticker, completing the FE-04 requirement that the ticker show live Nifty, Bank Nifty, AND India VIX.

**Ticker order after this plan:** LIVE indicator → NIFTY → BANK → VIX → FII → DII → PCR → A/D

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add _fetch_bank_nifty() to backend market_data.py | 384d1fd | backend/app/data/market_data.py |
| 2 | Add Bank Nifty section to MarketTicker.jsx | b52f3ae | frontend/src/components/MarketTicker.jsx |

## Task Details

### Task 1: Backend — _fetch_bank_nifty() and snapshot fields

Added `_fetch_bank_nifty()` method to `MarketDataService` using the NSE `equity-stockIndices?index=NIFTY%20BANK` endpoint, following the same pattern as `_fetch_nifty50()`. The method:
- Checks the `bank_nifty` cache key before making a network call
- Uses the `NSESession` shared client (cookies already set from NSE homepage hit)
- Parses `lastPrice`, `previousClose`, `change`, `pChange` from the response
- Returns zeroed fallback dict on any exception — no exception propagation

`get_live_snapshot()` updated:
- `bank_nifty_task = self._fetch_bank_nifty()` added before the gather
- `asyncio.gather()` extended to 5 concurrent tasks (was 4)
- `bank_nifty_spot`, `bank_nifty_change`, `bank_nifty_change_pct` added to snapshot dict after the Nifty 50 block

### Task 2: Frontend — Bank Nifty in MarketTicker.jsx

Added `bankNiftyUp` derived boolean and a Bank Nifty JSX block inserted between the existing Nifty 50 and VIX sections:
- Shows `BANK` label in `text-onSurfaceMuted`
- Shows spot price in bold `text-onSurface` with `formatNum(spot, 1)`
- Shows arrow + pct change in `text-bull` or `text-bear` via `pctClass(bankNiftyUp)`
- When `bank_nifty_spot` is 0 or falsy: spot shows `'--'`, change indicator hidden entirely (no crash)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing rollup native module missing (npm optional dep)**
- **Found during:** Task 2 verification (npm run build)
- **Issue:** `@rollup/rollup-darwin-arm64` optional dependency was missing from node_modules — `npm run build` failed with `Cannot find module @rollup/rollup-darwin-arm64`. Confirmed pre-existing (build failed before my changes too via git stash test).
- **Fix:** Ran `npm install --prefer-offline` in the frontend directory to restore the missing optional dependency. Build then succeeded in 1.71s.
- **Files modified:** node_modules (not tracked in git)
- **Commit:** N/A (dependency fix only)

## Verification Results

- Backend import check: PASSED — `_fetch_bank_nifty`, `bank_nifty_spot`, `bank_nifty_change_pct` all present
- Backend tests: PASSED — 33 passed, 7 warnings (all pre-existing deprecation warnings)
- Frontend content check: PASSED — `bank_nifty_spot`, `bankNiftyUp`, `BANK` label all present
- Frontend build: PASSED — `built in 1.71s`, no errors

## Self-Check: PASSED

Files verified:
- FOUND: /Users/aasish/Desktop/CLAUDE PROJECTS/TRD/TRD/gods-eye/backend/app/data/market_data.py
- FOUND: /Users/aasish/Desktop/CLAUDE PROJECTS/TRD/TRD/gods-eye/frontend/src/components/MarketTicker.jsx

Commits verified:
- FOUND: 384d1fd (feat(03-02): add _fetch_bank_nifty() and include in live snapshot)
- FOUND: b52f3ae (feat(03-02): add Bank Nifty section to MarketTicker between Nifty and VIX)
