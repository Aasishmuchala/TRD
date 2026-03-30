---
phase: 07-backtest-engine
plan: "01"
subsystem: backend/engine
tags: [backtest, engine, sqlite, tdd, dataclass]
dependency_graph:
  requires:
    - app.engine.orchestrator.Orchestrator
    - app.data.historical_store.historical_store
    - app.data.technical_signals.TechnicalSignals
    - app.api.schemas.MarketInput
    - app.config.config
  provides:
    - BacktestEngine
    - BacktestDayResult
    - BacktestRunResult
  affects:
    - Phase 07 Plan 02 (API endpoints consume BacktestEngine.run_backtest())
tech_stack:
  added: []
  patterns:
    - TDD (RED-GREEN cycle per task)
    - Dataclass-based result models with asdict() serialization
    - mock_mode toggle via config.MOCK_MODE flag save/restore
    - SQLite persistence using same DATABASE_PATH as rest of app
key_files:
  created:
    - gods-eye/backend/app/engine/backtest_engine.py
    - gods-eye/backend/tests/test_backtest_engine.py
  modified: []
decisions:
  - "mock_mode saves/restores config.MOCK_MODE via try/finally — clean even on exception"
  - "Consensus uses majority vote by direction count; ties broken by absolute DIRECTION_WEIGHT magnitude"
  - "direction_correct threshold is 0.1% — moves smaller than that are noise not signal"
  - "Per-agent accuracy excludes HOLD predictions from denominator — only eligible days counted"
  - "backtest_runs table stored in same SQLite file as rest of app (config.DATABASE_PATH)"
  - "historical_prices capped at last 60 closes to keep MarketInput context manageable"
  - "Next trading day looked up from full dataset (not range-filtered) to avoid skipping last signal day"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
  tests_added: 18
  tests_passing: 18
---

# Phase 07 Plan 01: Backtest Engine Core Summary

**One-liner:** BacktestDayResult/BacktestRunResult dataclasses + BacktestEngine with majority-vote consensus, ATM option P&L proxy, SQLite persistence, and 18 passing unit tests.

## What Was Built

The core backtest replay engine for God's Eye v2.0.

`BacktestEngine.run_backtest()` accepts an instrument and date range, fetches all historical OHLCV + VIX rows from `historical_store`, then iterates each signal day in the range. For each day:

1. Constructs `MarketInput` from historical row using neutral proxies for unavailable fields (FII/DII flows, USD/INR, DXY, PCR)
2. Sets `config.MOCK_MODE` to requested value (restored via `try/finally`)
3. Calls `await orchestrator.run_simulation(market_input)` for the full 3-round agent debate
4. Computes consensus direction + conviction via majority vote across `final_outputs`
5. Computes `actual_move_pct`, `direction_correct`, and `pnl_points` (ATM option proxy)
6. Accumulates per-agent accuracy stats

After the loop, `overall_accuracy` and `per_agent_accuracy` are computed and the full `BacktestRunResult` is persisted as JSON to `backtest_runs` SQLite table.

## Tasks Completed

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1 | Define BacktestDayResult and BacktestRunResult dataclasses | Complete | 34fdb0d |
| 2 | Implement BacktestEngine.run_backtest() with full day-loop logic | Complete | 34fdb0d |

## Test Coverage

18 unit tests in `tests/test_backtest_engine.py`:

- Dataclass instantiation (both `BacktestDayResult` and `BacktestRunResult`)
- `_is_correct()` semantics: BUY+positive, BUY+negative, HOLD=None, SELL+negative, threshold boundary conditions
- `_compute_pnl()`: BUY, SELL, HOLD, STRONG_BUY identity with BUY
- `_compute_consensus()`: majority BUY wins, majority SELL wins, all HOLD returns HOLD

## Deviations from Plan

None — plan executed exactly as written.

## Key Decisions Made

| Decision | Rationale |
|----------|-----------|
| Tasks 1+2 committed together | Both tasks are in the same file; separating them would produce an incomplete commit with non-importable code |
| `try/finally` for mock_mode restore | Guarantees config is restored even if simulation raises an exception mid-loop |
| Next-day lookup from full dataset | Using only signal rows would cause the last signal day to always be skipped (no next row) — instead we find the day's position in the full historical dataset |
| historical_prices capped at 60 | Agent context window; diminishing returns beyond 60 closes for RSI/trend analysis |
| backtest_runs in same SQLite file | Avoids a second database file; Plan 02 API retrieves runs from same connection path |

## Self-Check: PASSED

- `gods-eye/backend/app/engine/backtest_engine.py` — FOUND
- `gods-eye/backend/tests/test_backtest_engine.py` — FOUND
- Commit `34fdb0d` — FOUND
- 18/18 tests passing — VERIFIED
