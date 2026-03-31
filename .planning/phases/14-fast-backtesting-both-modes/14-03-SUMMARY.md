---
phase: 14-fast-backtesting-both-modes
plan: 03
subsystem: ui
tags: [react, tailwind, backtest, mode-comparison, api-client]

# Dependency graph
requires:
  - phase: 14-01
    provides: quant backtest engine + /api/backtest/quant-run endpoint
  - phase: 14-02
    provides: hybrid backtest engine + /api/backtest/hybrid-run endpoint
provides:
  - runQuantBacktest and runHybridBacktest API client methods
  - ModeCompare component with side-by-side delta comparison table
  - Updated Backtest page with RULES ONLY / HYBRID / AGENT (legacy) mode tabs
affects:
  - future-backtest-ui
  - dashboard

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mode tab pattern: activeMode state dispatches to different API methods and renders mode-specific result blocks"
    - "ModeCompare: receives both results (either may be null), renders '—' for missing side, delta column only when both present"
    - "Backend-computed stats pattern: ModeCompare reads sharpe_ratio/max_drawdown_pct from response root, not computed client-side"

key-files:
  created:
    - gods-eye/frontend/src/components/ModeCompare.jsx
  modified:
    - gods-eye/frontend/src/api/client.js
    - gods-eye/frontend/src/pages/Backtest.jsx

key-decisions:
  - "runQuantBacktest uses 60s timeout (fast rules engine); runHybridBacktest uses 600s timeout matching legacy runBacktest"
  - "Mock mode toggle rendered only in agent (legacy) tab — quant and hybrid modes have no mock equivalent"
  - "ModeCompare placed inside each mode's result block so both columns fill in as each mode runs, cross-tab"
  - "Delta color: green = hybrid better, red = hybrid worse; computed per-row with better:'higher'/'lower' annotation"

patterns-established:
  - "Mode tab dispatch pattern: single handleRun function checks activeMode and calls the corresponding API method"
  - "Partial compare table: ModeCompare renders a column as '—' when that mode's result is null; delta column absent until both results exist"

requirements-completed: [FBT-03, FBT-04]

# Metrics
duration: 3min
completed: 2026-04-01
---

# Phase 14 Plan 03: Backtest Mode Tabs and ModeCompare Summary

**Backtest page now has RULES ONLY / HYBRID / AGENT tabs each calling the correct API, with a ModeCompare component that shows a 7-metric side-by-side table with a colored delta column when both results exist**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-31T21:08:38Z
- **Completed:** 2026-04-01T21:11:xx Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `runQuantBacktest` (60s timeout) and `runHybridBacktest` (600s timeout) to api/client.js following existing runBacktest pattern
- Created ModeCompare.jsx: 7-row comparison table (Win Rate, P&L, Sharpe, Max Drawdown, Win/Loss Ratio, Tradeable Days, Elapsed) with delta column coloured green/red based on which mode wins each metric
- Updated Backtest.jsx: three mode tabs dispatch to the correct API, mock mode toggle only in agent tab, quant and hybrid result blocks each include ModeCompare so the compare panel fills in cross-tab as each mode runs

## Task Commits

Each task was committed atomically:

1. **Task 1: Add runQuantBacktest and runHybridBacktest to API client** - `cee114c` (feat)
2. **Task 2: Create ModeCompare component and update Backtest page** - `1078220` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `gods-eye/frontend/src/api/client.js` - Added runQuantBacktest and runHybridBacktest methods
- `gods-eye/frontend/src/components/ModeCompare.jsx` - New: side-by-side comparison table with delta row
- `gods-eye/frontend/src/pages/Backtest.jsx` - Mode tabs, dispatched handleRun, quant/hybrid result blocks, ModeCompare integration

## Decisions Made
- `runQuantBacktest` uses a 60-second timeout since the rules engine is fast; `runHybridBacktest` keeps the 600-second timeout like the legacy backtest
- Mock mode toggle is shown only in the AGENT (legacy) tab since quant and hybrid modes have no mock equivalent
- ModeCompare is placed inside each mode's result block (not outside) so both columns populate naturally as the user runs each mode, and the delta column appears automatically once both have been run
- Delta color logic: green = hybrid improves metric, red = hybrid degrades metric, using a per-row `better: 'higher'|'lower'` annotation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Frontend UI for both backtest modes is complete with mode tabs, mode-specific day tables, and side-by-side comparison
- Phase 14 plans 01-03 are all complete — the fast backtesting both-modes feature is fully delivered
- Both quant and hybrid result blocks correctly show 0 lots for skip-tier days (from backend data)

---
*Phase: 14-fast-backtesting-both-modes*
*Completed: 2026-04-01*
