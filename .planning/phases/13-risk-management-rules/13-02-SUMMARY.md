---
phase: 13-risk-management-rules
plan: "02"
subsystem: api
tags: [risk-management, fastapi, pydantic, daily-loss-guard, position-sizing]

# Dependency graph
requires:
  - phase: 13-01-risk-management-rules
    provides: RiskManager.compute() with RiskParams dataclass, pure stdlib module

provides:
  - DailyLossGuard in-memory IST-aware session guard with module singleton
  - RISK_MAX_DAILY_LOSS and RISK_VIX_STOP_MULTIPLIER config fields (env-overridable)
  - RiskParamsSchema Pydantic model (7 fields)
  - HybridSignalResponse extended with risk_params, risk_blocked, risk_block_reason
  - POST /api/signal/hybrid response includes full risk block (lots, stops, targets, guard status)

affects:
  - 14-hybrid-backtest
  - any consumer of POST /api/signal/hybrid/{instrument}/{date}

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Module-level singleton initialised from config at import time (daily_loss_guard)
    - IST-aware daily reset via datetime.now(tz=IST).date() comparison
    - Risk guard check-only in signal route — record_loss reserved for Phase 14 accounting
    - Schema extension: new fields appended to existing Pydantic model without breaking existing fields

key-files:
  created:
    - gods-eye/backend/app/engine/daily_loss_guard.py
  modified:
    - gods-eye/backend/app/config.py
    - gods-eye/backend/app/api/schemas.py
    - gods-eye/backend/app/api/routes.py

key-decisions:
  - "DailyLossGuard uses IST timezone (UTC+5:30) for day boundary — matches Indian trading session"
  - "daily_loss_guard singleton reads config.RISK_MAX_DAILY_LOSS at import time — simple, no startup wiring needed"
  - "route calls is_blocked() only, not record_loss() — guard recording is Phase 14 backtest P&L accounting concern"
  - "entry_close = closes[-1] (already in scope as nifty_close) — reuses existing OHLCV fetch, no extra DB call"
  - "vix_val already loaded in Step 1 of route — passed directly to RiskManager, no re-fetch needed"

patterns-established:
  - "Risk guard singleton: initialised from config at module import, no dependency injection needed"
  - "Schema extension: append new fields to existing Pydantic response model with Optional for nullable fields"

requirements-completed: [RISK-01, RISK-02, RISK-03, RISK-04]

# Metrics
duration: 6min
completed: 2026-04-01
---

# Phase 13 Plan 02: Risk Management Wiring Summary

**DailyLossGuard IST-aware session guard, RiskParamsSchema Pydantic model, and full risk block wired into POST /api/signal/hybrid response**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-31T20:39:13Z
- **Completed:** 2026-03-31T20:44:37Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- Added `RISK_MAX_DAILY_LOSS=5000.0` and `RISK_VIX_STOP_MULTIPLIER=5.0` to Config dataclass, both env-overridable via `GODS_EYE_RISK_*` vars
- Created `DailyLossGuard` class with IST-aware auto-reset, `is_blocked()`, `record_loss()`, `cumulative_loss()`, `reset()`, and module-level singleton `daily_loss_guard`
- Added `RiskParamsSchema` Pydantic model and extended `HybridSignalResponse` with `risk_params`, `risk_blocked`, `risk_block_reason`
- Wired `RiskManager.compute()` and `daily_loss_guard.is_blocked()` into hybrid signal route — every response now carries position sizing, stop/target levels, and guard status

## Task Commits

Each task was committed atomically:

1. **Task 1: Config fields + DailyLossGuard module** - `5a1aec7` (feat)
2. **Task 2: Schema additions + hybrid route wiring** - `371a94f` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `gods-eye/backend/app/engine/daily_loss_guard.py` - DailyLossGuard class + daily_loss_guard singleton
- `gods-eye/backend/app/config.py` - Added RISK_MAX_DAILY_LOSS and RISK_VIX_STOP_MULTIPLIER fields
- `gods-eye/backend/app/api/schemas.py` - Added RiskParamsSchema; extended HybridSignalResponse with 3 new fields
- `gods-eye/backend/app/api/routes.py` - Imported RiskManager + daily_loss_guard; added Step 8 risk computation to hybrid route

## Decisions Made

- `daily_loss_guard` singleton reads `config.RISK_MAX_DAILY_LOSS` at module import time — simple, avoids startup wiring
- Route calls `is_blocked()` only, not `record_loss()` — recording paper losses is Phase 14 backtest P&L concern, not Phase 13
- `entry_close = closes[-1]` reuses the already-fetched OHLCV data in route scope — no extra DB call
- `vix_val` already loaded in Step 1 of route, passed directly to `RiskManager.compute()`
- IST timezone computed via `datetime.now(tz=timezone(timedelta(hours=5, minutes=30))).date()` — no pytz dependency

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Pre-existing test failure (unrelated to this plan):
- `tests/test_algo_agent_interaction_effects.py::test_high_vix_includes_volatility_regime_signal` — fails because AlgoQuantAgent's VIX-based `amplifies` logic doesn't include `"Volatility regime signals"`. Confirmed pre-existing by running suite before and after changes. Logged to deferred-items.

## Next Phase Readiness

- Phase 14 (hybrid backtest) can now call `daily_loss_guard.record_loss(loss_points)` to track cumulative P&L
- All risk fields on `HybridSignalResponse` are populated for every call — both tradeable and skip-tier signals
- `risk_blocked=True` path works: once cumulative loss >= 5000 pts, all subsequent signal responses will set `risk_blocked=True` and populate `risk_block_reason`

---
*Phase: 13-risk-management-rules*
*Completed: 2026-04-01*
