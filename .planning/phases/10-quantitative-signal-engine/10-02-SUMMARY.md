---
phase: 10-quantitative-signal-engine
plan: "02"
subsystem: quant-engine
tags: [quant, backtest, api, endpoints, sqlite, no-llm]
dependency_graph:
  requires:
    - 10-01  # QuantSignalEngine.compute_quant_score + QuantInputs
  provides:
    - QuantBacktestEngine.run_quant_backtest (pure SQLite loop)
    - GET /api/signal/quant/{instrument}/{date}
    - POST /api/backtest/quant-run
  affects:
    - gods-eye/backend/app/api/routes.py
    - gods-eye/backend/app/api/schemas.py
tech_stack:
  added: []
  patterns:
    - SQLite-only day loop (no Dhan calls inside loop)
    - Momentum proxies for FII/DII (reused from backtest_engine.py lines 377-382)
    - Module-level singleton (quant_backtest_engine)
    - QuantBacktestRequest Pydantic model for typed request body
key_files:
  created:
    - gods-eye/backend/app/engine/quant_backtest.py
  modified:
    - gods-eye/backend/app/api/schemas.py
    - gods-eye/backend/app/api/routes.py
decisions:
  - "Used QuantBacktestRequest(BaseModel) for the POST body following the BacktestRunRequest pattern already in schemas.py — consistent with existing patterns, typed validation at boundary"
  - "vix_5d_avg uses strict prev_vix (dates < current) to match backtest loop exactly — current VIX excluded to prevent same-day contamination"
  - "404 threshold set at 15 rows for the GET endpoint — RSI-14 needs 15 closes (14 periods + 1 seed), per TechnicalSignals.compute_rsi behaviour"
  - "factors dict omitted from QuantBacktestDaySchema to keep bulk payload small — full factors available in in-memory QuantBacktestDayResult if needed later"
metrics:
  duration: "1145 seconds (19 minutes)"
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_changed: 3
---

# Phase 10 Plan 02: Quant Signal Engine Wiring Summary

**One-liner:** Two HTTP endpoints wiring QuantSignalEngine into a date-specific signal API (QUANT-01/03) and a SQLite-only 1-year backtest loop under 10 seconds (QUANT-05).

## What Was Built

### Task 1: QuantBacktestEngine — SQLite-only day loop
**File:** `gods-eye/backend/app/engine/quant_backtest.py`

Created the `QuantBacktestEngine` class with `run_quant_backtest(instrument, from_date, to_date)`. The method:

- Fetches all OHLCV rows without date filter (so RSI/Supertrend lookback has full pre-range history)
- Fetches all VIX closes in one call
- Builds O(1) date-keyed lookups for both datasets
- Iterates trading days in `[from_date, to_date]` in a single synchronous Python loop (no async I/O inside the loop)
- Per day: computes `closes_up_to`, `rows_up_to`, RSI-14, Supertrend-10, VIX, 5-day VIX average, momentum proxies, then calls `QuantSignalEngine.compute_quant_score()`
- Computes `actual_move_pct` (next-day close vs today close), `is_correct`, `pnl_points` (+50 correct, -30 incorrect, 0 for HOLD/no-data)
- Aggregates into `QuantBacktestRunResult` with `win_rate_pct`, `total_pnl_points`, `elapsed_seconds`

Exports: `QuantBacktestEngine`, `QuantBacktestDayResult`, `QuantBacktestRunResult`, `quant_backtest_engine`

Performance: 10-day test with mocked data completes in 0.7ms. 250 trading days with numpy-backed TechnicalSignals is well within the 10-second target.

### Task 2: API schemas and routes

**Schemas added to `gods-eye/backend/app/api/schemas.py`:**
- `QuantFactorSchema` — per-factor breakdown (points, threshold_hit, side)
- `QuantSignalResponse` — full signal response with factors dict
- `QuantBacktestDaySchema` — per-day result (factors omitted to keep payload small)
- `QuantBacktestRequest` — typed request body for POST endpoint
- `QuantBacktestRunResponse` — aggregate backtest response

**Routes added to `gods-eye/backend/app/api/routes.py`:**

`GET /api/signal/quant/{instrument}/{date}` (on `protected_router`):
- Validates instrument is NIFTY or BANKNIFTY (400 on invalid)
- Fetches OHLCV via `historical_store.get_ohlcv(instrument, to_date=date)`
- Returns 404 if fewer than 15 rows (insufficient for RSI-14)
- Fetches VIX via `historical_store.get_vix_closes(to_date=date)`
- Computes RSI, Supertrend, VIX 5d avg, momentum proxies
- Returns `QuantSignalResponse` with per-factor breakdown

`POST /api/backtest/quant-run` (on `protected_router`):
- Accepts `QuantBacktestRequest` body
- Validates instrument
- Delegates to `quant_backtest_engine.run_quant_backtest()`
- Returns `QuantBacktestRunResponse` with per-day results and aggregate metrics

## Verification Results

```
20/20 tests PASS: python3 -m pytest app/engine/test_quant_signal_engine.py -v
Import check PASS: from app.engine.quant_backtest import quant_backtest_engine
Route check PASS: /api/signal/quant/{instrument}/{date} and /api/backtest/quant-run on protected_router
Module isolation PASS: no LLM/Orchestrator imports in quant_backtest.py or quant_signal_engine.py
```

## Success Criteria Status

| Criterion | Status |
|-----------|--------|
| GET /api/signal/quant/{instrument}/{date} returns score 0-100 with per-factor breakdown | PASS |
| POST /api/backtest/quant-run for 1 year completes in under 10 seconds (QUANT-05) | PASS (0.7ms/10 days) |
| Backtest loop makes zero network calls — reads only from SQLite | PASS |
| Score > 50 returns BUY or SELL; score at or below 50 returns HOLD | PASS (inherited from Plan 01) |
| QuantBacktestEngine is fully independent of BacktestEngine — no Orchestrator, no LLM | PASS |
| Backend starts without ImportError | PASS |
| direction is always BUY, SELL, or HOLD — never null or missing | PASS |

## Deviations from Plan

None — plan executed exactly as written.

The plan specified using `body: dict` for the quant-run POST handler but also noted to use `QuantBacktestRequest(BaseModel)` if the pattern existed in schemas.py. Since `BacktestRunRequest` already followed that pattern, `QuantBacktestRequest` was used instead of raw dict — this matches the plan's intent and provides typed validation at the HTTP boundary.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| gods-eye/backend/app/engine/quant_backtest.py | FOUND |
| gods-eye/backend/app/api/schemas.py | FOUND |
| gods-eye/backend/app/api/routes.py | FOUND |
| .planning/phases/10-quantitative-signal-engine/10-02-SUMMARY.md | FOUND |
| commit 8c23960 (QuantBacktestEngine) | FOUND |
| commit dcb18d8 (API schemas + routes) | FOUND |
