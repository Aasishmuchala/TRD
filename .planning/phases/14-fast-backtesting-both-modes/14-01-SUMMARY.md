---
phase: 14-fast-backtesting-both-modes
plan: "01"
subsystem: engine
tags: [backtest, risk-management, quant, sharpe, drawdown, pnl, nifty]

# Dependency graph
requires:
  - phase: 13-risk-management-rules
    provides: RiskManager.compute() static method with lot sizing per tier
  - phase: 10-quant-signal-engine
    provides: QuantBacktestEngine, QuantBacktestDayResult, QuantBacktestRunResult
provides:
  - QuantBacktestDayResult with lots field (RiskManager-derived lot count per trade)
  - QuantBacktestRunResult with sharpe_ratio, max_drawdown_pct, win_loss_ratio
  - QuantBacktestRunResponse schema with all three risk metrics exposed in API response
  - 15 unit tests covering P&L formula, Sharpe, max drawdown, and win/loss ratio
affects:
  - 14-fast-backtesting-both-modes (plan 02 hybrid backtest may reference same metrics)
  - frontend backtest dashboard (plan 09+) consuming QuantBacktestRunResponse

# Tech tracking
tech-stack:
  added: []
  patterns:
    - RiskManager.compute called per-day inside backtest loop (O(1) pure math, zero I/O)
    - itertools.accumulate for equity curve construction
    - statistics.mean + statistics.stdev (n-1) for Sharpe ratio
    - Optional[float] risk metrics default to None in dataclasses and Pydantic models

key-files:
  created:
    - gods-eye/backend/app/engine/test_quant_backtest_risk.py
  modified:
    - gods-eye/backend/app/engine/quant_backtest.py
    - gods-eye/backend/app/api/schemas.py
    - gods-eye/backend/app/api/routes.py

key-decisions:
  - "RiskManager.compute called inside per-day loop only when tier != skip and direction != HOLD — skip tier always pnl=0"
  - "NIFTY_LOT=25 hardcoded as constant inside engine — standard Nifty lot size"
  - "vix fallback to 15.0 when vix <= 0 inside loop — prevents ValueError from RiskManager"
  - "Sharpe uses sample stdev (n-1) and returns None when stdev=0 to avoid div-by-zero"
  - "max_drawdown_pct returns None when equity curve has no positive peak — prevents misleading 0% on all-loss runs"
  - "win_loss_ratio returns None when no losing days — avoids false infinity/zero reporting"
  - "New schema fields use Optional[float] = None default — backward-compatible with existing API consumers"

patterns-established:
  - "Risk metrics (sharpe, drawdown, win_loss) computed in engine, not API layer — engine owns full P&L accounting"
  - "TDD RED→GREEN on structural tests (dataclass fields) catches missing fields before implementation"

requirements-completed:
  - FBT-01
  - FBT-04

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 14 Plan 01: Fast Backtesting Both Modes Summary

**Risk-adjusted P&L via RiskManager lot sizing (replacing flat +50/-30) plus Sharpe ratio, max drawdown, and win/loss ratio in QuantBacktestRunResponse**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T20:56:47Z
- **Completed:** 2026-03-31T21:00:25Z
- **Tasks:** 2
- **Files modified:** 4 (1 created + 3 modified)

## Accomplishments

- Replaced flat +50/-30 P&L with lots-scaled formula: `actual_move_pts * lots * 25` per trade direction
- Added `lots: int = 0` to `QuantBacktestDayResult` dataclass and API schema
- Added `sharpe_ratio`, `max_drawdown_pct`, `win_loss_ratio` to both engine result and API response
- 15 unit tests covering all P&L cases, Sharpe edge cases, drawdown scenarios, and win/loss ratio

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for risk-adjusted P&L and risk metrics** - `787c223` (test)
2. **Task 1 (GREEN): Risk-adjusted P&L and risk metrics in QuantBacktestEngine** - `0052294` (feat)
3. **Task 2: Expose lots and risk metrics in QuantBacktestRunResponse schema** - `0d81a10` (feat)

_Note: TDD task had separate test and implementation commits_

## Files Created/Modified

- `gods-eye/backend/app/engine/test_quant_backtest_risk.py` - 15 unit tests for P&L formula, Sharpe, drawdown, win/loss ratio
- `gods-eye/backend/app/engine/quant_backtest.py` - RiskManager integration, lots field, three risk metric computations post-loop
- `gods-eye/backend/app/api/schemas.py` - `lots` on QuantBacktestDaySchema; sharpe/drawdown/win_loss on QuantBacktestRunResponse
- `gods-eye/backend/app/api/routes.py` - Pass `lots=d.lots` and three risk metric fields through to response

## Decisions Made

- **RiskManager call only when `tier != "skip"`**: The skip branch already guarantees lots=0 and pnl=0.0 — calling RiskManager would be wasted work and redundant.
- **vix fallback 15.0 inside loop**: RiskManager raises `ValueError` if vix <= 0; historical VIX data could have gaps; fallback to moderate-fear default (15.0) preserves run continuity.
- **sample stdev (n-1) for Sharpe**: Consistent with Phase 09 decision (backtests are samples, not populations).
- **`max_drawdown_pct` returns None when no positive peak**: Prevents reporting 0% drawdown on all-loss runs which would be misleading.
- **Schema fields default to `None`**: Ensures existing API consumers that don't read these fields are unaffected (backward-compatible Pydantic addition).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `QuantBacktestRunResponse` now carries full risk metrics: FBT-04 requirement fulfilled
- FBT-01 (1-year <10s) unaffected: `RiskManager.compute` is pure math, O(1), no I/O added to the loop
- Plan 14-02 (hybrid backtest) can use the same risk metrics pattern for its per-day results

## Self-Check: PASSED

- FOUND: gods-eye/backend/app/engine/quant_backtest.py
- FOUND: gods-eye/backend/app/engine/test_quant_backtest_risk.py
- FOUND: gods-eye/backend/app/api/schemas.py
- FOUND: gods-eye/backend/app/api/routes.py
- FOUND: .planning/phases/14-fast-backtesting-both-modes/14-01-SUMMARY.md
- FOUND commit: 787c223 (test RED phase)
- FOUND commit: 0052294 (feat GREEN phase)
- FOUND commit: 0d81a10 (feat schema/routes)

---
*Phase: 14-fast-backtesting-both-modes*
*Completed: 2026-03-31*
