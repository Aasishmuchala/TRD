---
phase: 09-backtest-dashboard
plan: "01"
subsystem: frontend
tags: [react, routing, api-client, backtest, sidebar]
dependency_graph:
  requires: []
  provides:
    - gods-eye/frontend/src/pages/Backtest.jsx
    - apiClient.runBacktest
    - apiClient.getBacktestResult
    - /backtest route in App.jsx
    - Backtest sidebar nav item
  affects:
    - gods-eye/frontend/src/App.jsx
    - gods-eye/frontend/src/components/Sidebar.jsx
    - gods-eye/frontend/src/api/client.js
tech_stack:
  added: []
  patterns:
    - useState for form/loading/result/error (matches SimulationHistory.jsx pattern)
    - try/catch/finally setLoading(false) async handler
    - Layout wrapper + terminal-card content panels
key_files:
  created:
    - gods-eye/frontend/src/pages/Backtest.jsx
  modified:
    - gods-eye/frontend/src/api/client.js
    - gods-eye/frontend/src/App.jsx
    - gods-eye/frontend/src/components/Sidebar.jsx
decisions:
  - Backtest nav item placed between History and Skills per plan spec (maintains Dashboard > Agents > History > Backtest > Skills > Paper Trading > Settings order)
  - results area left as placeholder with comment for Plans 02/03 to inject display components
  - mock_mode defaulted to true so first-time users get a fast, cost-free run
metrics:
  duration: 337s
  completed_date: "2026-03-31"
  tasks_completed: 3
  files_modified: 4
---

# Phase 09 Plan 01: Backtest Page Foundation Summary

Wire up the Backtest page: API client extensions (runBacktest/getBacktestResult), /backtest route in App.jsx, Backtest sidebar nav item, and the form/run/progress/result UI that Plans 02 and 03 build on.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Extend API client with backtest methods | b449d4b | gods-eye/frontend/src/api/client.js |
| 2 | Add /backtest route and Backtest nav item | 122a8e0 | App.jsx, Sidebar.jsx |
| 3 | Create Backtest.jsx page | 6fd2c3e | gods-eye/frontend/src/pages/Backtest.jsx |

## What Was Built

**API client** (`client.js`): Two new methods appended after `getHealth`:
- `runBacktest(data)` — POST `/api/backtest/run` with JSON body `{instrument, from_date, to_date, mock_mode}`
- `getBacktestResult(runId)` — GET `/api/backtest/results/:runId`

**Routing** (`App.jsx`): Import and `<Route path="/backtest" element={<Backtest />} />` placed between `/history` and `/paper-trading` in the protected routes block.

**Sidebar** (`Sidebar.jsx`): Backtest nav item with bar-chart SVG icon inserted between History and Skills entries in the `menuItems` array.

**Backtest page** (`Backtest.jsx`): State-owning page component with:
- Form fields: instrument select (NIFTY/BANKNIFTY), from/to date pickers, mock mode toggle button
- `handleRun` async handler: calls `apiClient.runBacktest()`, manages loading/error/result state
- Loading panel: animated "RUNNING BACKTEST..." indicator with description text
- Error panel: bear-red left-border card showing readable error message
- Result panel: placeholder `terminal-card` showing `result.summary.day_count` days processed (Plans 02/03 inject child panels here)

## Verification

All 5 plan checks passed:
1. `runBacktest` and `getBacktestResult` present in client.js
2. `/backtest` route registered in App.jsx
3. Backtest nav item in Sidebar.jsx between History and Skills
4. `Backtest.jsx` file exists (148 lines)
5. `npm run build` completes without errors (63 modules, 2.32s)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `gods-eye/frontend/src/pages/Backtest.jsx` exists
- [x] `gods-eye/frontend/src/api/client.js` contains `runBacktest` and `getBacktestResult`
- [x] `gods-eye/frontend/src/App.jsx` contains `/backtest` route
- [x] `gods-eye/frontend/src/components/Sidebar.jsx` contains Backtest nav item
- [x] Commits b449d4b, 122a8e0, 6fd2c3e all exist
- [x] Build passes (vite build: 63 modules, no errors)
