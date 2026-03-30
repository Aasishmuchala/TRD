---
phase: 07-backtest-engine
plan: "02"
subsystem: api
tags: [fastapi, pydantic, backtest, sqlite, endpoints]

# Dependency graph
requires:
  - phase: 07-01
    provides: BacktestEngine.run_backtest(), BacktestRunResult dataclass, backtest_runs SQLite table

provides:
  - POST /api/backtest/run — runs backtest over a date range, stores result, returns BacktestRunResponse
  - GET /api/backtest/results/{run_id} — retrieves a stored backtest run by ID
  - BacktestRunRequest, BacktestRunResponse, BacktestRunSummary, BacktestDayResponse Pydantic models
  - _serialize_backtest_result() helper that computes cumulative_pnl_points in the API layer

affects:
  - 09-dashboard (consumes BacktestRunResponse shape for equity curve and per-agent accuracy charts)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "API layer computes cumulative_pnl_points from per-day pnl_points — engine stays pure, running total is presentation concern"
    - "Singleton backtest_engine at module level (same pattern as tracker = PredictionTracker())"
    - "Private _serialize_backtest_result() helper converts dataclass -> Pydantic (not a route)"
    - "GET retrieval re-hydrates BacktestDayResult from JSON via dataclasses.asdict() stored blob"

key-files:
  created: []
  modified:
    - gods-eye/backend/app/api/schemas.py
    - gods-eye/backend/app/api/routes.py

key-decisions:
  - "cumulative_pnl_points computed in API layer, not stored in engine — keeps BacktestEngine pure and lets API control equity curve shape"
  - "BacktestRunSummary.win_rate_pct is a convenience field (overall_accuracy * 100) for Phase 9 dashboard to avoid client-side multiplication"
  - "round_history omitted from BacktestDayResponse — heavy field, per-day round history not needed for dashboard equity curves"
  - "GET /backtest/results/{run_id} re-hydrates full BacktestRunResult from JSON blob rather than storing a separate parsed table"

patterns-established:
  - "Backtest API pattern: POST runs and stores, GET retrieves by ID — consistent with Phase 9 dashboard fetch pattern"
  - "Serialization helper (_serialize_backtest_result) as private function, not route — separation of HTTP handler from data transformation"

requirements-completed: [BT-04, BT-05]

# Metrics
duration: 40min
completed: 2026-03-31
---

# Phase 7 Plan 02: Backtest HTTP API Summary

**BacktestEngine wired to HTTP via POST /api/backtest/run and GET /api/backtest/results/{run_id} with 4 Pydantic schemas surfacing per-agent accuracy (BT-04) and cumulative P&L (BT-05)**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-03-30T21:18:35Z
- **Completed:** 2026-03-30T21:58:01Z
- **Tasks:** 2 (+ 1 auto-approved checkpoint)
- **Files modified:** 2

## Accomplishments

- Added 4 Pydantic models: `BacktestDayResponse`, `BacktestRunRequest`, `BacktestRunSummary`, `BacktestRunResponse`
- Wired `POST /api/backtest/run` and `GET /api/backtest/results/{run_id}` onto `protected_router`
- `cumulative_pnl_points` computed per-day in the API layer (not stored in engine) — equity curve ready for Phase 9 dashboard
- `win_rate_pct` convenience field (overall_accuracy * 100) in summary to spare Phase 9 client from multiplication
- All 18 existing backtest unit tests continue to pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Add BacktestRunRequest and BacktestRunResponse to schemas.py** - `b7d3232` (feat)
2. **Task 2: Add POST /api/backtest/run and GET /api/backtest/results/{run_id} to routes.py** - `321c2a8` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `gods-eye/backend/app/api/schemas.py` - Added BacktestDayResponse, BacktestRunRequest, BacktestRunSummary, BacktestRunResponse under Phase 7 section header
- `gods-eye/backend/app/api/routes.py` - Added BacktestEngine import + singleton, backtest schema imports, two endpoint handlers, _serialize_backtest_result() helper

## Decisions Made

- `cumulative_pnl_points` computed in the API layer so `BacktestEngine` stays pure (no running state); API owns the equity curve
- `win_rate_pct` added as convenience field — Phase 9 dashboard consumes it directly without client-side math
- `round_history` omitted from `BacktestDayResponse` — the field is heavy (full 3-round debate per day) and not needed for aggregate dashboard views
- GET retrieval reconstructs `BacktestRunResult` from the stored JSON blob via `BacktestDayResult(**d)` — avoids a second normalized table for backtest days

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. `python` binary not in PATH (macOS Homebrew Python 3.14 installs as `python3`); switched verification commands to `python3` — not a codebase issue.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

- FOUND: gods-eye/backend/app/api/schemas.py
- FOUND: gods-eye/backend/app/api/routes.py
- FOUND: .planning/phases/07-backtest-engine/07-02-SUMMARY.md
- FOUND commit b7d3232 (Task 1: schemas)
- FOUND commit 321c2a8 (Task 2: routes)

## Next Phase Readiness

- Both backtest endpoints are on `protected_router` and require `X-API-Key` auth (same as all other simulation endpoints)
- `mock_mode=True` default means Phase 9 dashboard can call `POST /api/backtest/run` with no LLM key for UI development
- Phase 9 (dashboard) can consume `BacktestRunResponse.days[].cumulative_pnl_points` directly for equity curve chart and `summary.per_agent_accuracy` for the agent accuracy bar chart
- No blockers

---
*Phase: 07-backtest-engine*
*Completed: 2026-03-31*
