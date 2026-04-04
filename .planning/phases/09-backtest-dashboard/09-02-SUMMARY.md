---
phase: 09-backtest-dashboard
plan: "02"
subsystem: frontend
tags: [react, components, backtest, metrics, table, statistics]
dependency_graph:
  requires:
    - gods-eye/frontend/src/pages/Backtest.jsx (Plan 01)
  provides:
    - gods-eye/frontend/src/components/BacktestSummary.jsx
    - gods-eye/frontend/src/components/StatsPanel.jsx
    - gods-eye/frontend/src/components/AgentAccuracyTable.jsx
  affects:
    - gods-eye/frontend/src/pages/Backtest.jsx
tech_stack:
  added: []
  patterns:
    - terminal-card + bg-surface-2 inner grid cards for metric panels
    - font-mono numbers with bull/bear/neutral color rules
    - useState(false) sort toggle for table column header
    - Inline stats computation (no external lib) for Sharpe/drawdown
key_files:
  created:
    - gods-eye/frontend/src/components/BacktestSummary.jsx
    - gods-eye/frontend/src/components/StatsPanel.jsx
    - gods-eye/frontend/src/components/AgentAccuracyTable.jsx
  modified:
    - gods-eye/frontend/src/pages/Backtest.jsx
decisions:
  - Inline AGENT_LABELS and AGENT_COLORS in AgentAccuracyTable to avoid dependency on constants file
  - Sample variance (n-1) for Sharpe stddev calculation to handle small backtests correctly
  - Sort defaults to descending (sortAsc=false) — highest accuracy shown first
  - N/A displayed when fewer than 2 active data points for Sharpe; null checks for avg win/loss
metrics:
  duration: 131s
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_modified: 4
---

# Phase 09 Plan 02: Backtest Data Display Panels Summary

Three analytical display components (BacktestSummary, StatsPanel, AgentAccuracyTable) wired into Backtest.jsx, delivering the core post-run readout with direction accuracy, P&L, drawdown, Sharpe ratio, and sortable per-agent accuracy.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create BacktestSummary.jsx and StatsPanel.jsx | 895db5a | BacktestSummary.jsx, StatsPanel.jsx |
| 2 | Create AgentAccuracyTable.jsx and wire all panels into Backtest.jsx | 9891106 | AgentAccuracyTable.jsx, Backtest.jsx |

## What Was Built

**BacktestSummary.jsx**: 4-stat grid panel reading from `summary` prop. Shows direction accuracy % (bull/bear colored), days analyzed (primary colored), total P&L with sign prefix (bull/bear colored), and instrument. MOCK MODE badge renders when `summary.mock_mode` is true. Date range shown at bottom.

**StatsPanel.jsx**: Computes 4 derived statistics from the `days` array:
- `maxDrawdown`: running peak - current cumulative, always shown in bear red
- `sharpeRatio`: `(mean / stddev) * sqrt(252)` on non-HOLD days only; N/A if < 2 data points; color by threshold (>0.5 bull, 0-0.5 neutral, negative bear)
- `avgWin`: mean of positive pnl_points with "+" prefix; N/A if no wins
- `avgLoss`: mean of absolute negative pnl_points with "-" prefix; N/A if no losses

**AgentAccuracyTable.jsx**: Sortable table with `useState(false)` for sort direction (descending default). Header "Accuracy" column has ▲/▼ indicator and click handler. Each row shows: colored circle dot (inline style backgroundColor from AGENT_COLORS), display name, thin progress bar (width = accuracy * 100%), accuracy % (bull >= 50%, bear < 50%). AGENT_LABELS map handles all 6 canonical agent keys.

**Backtest.jsx update**: Replaced the Plan 01 placeholder `<div>` with:
```jsx
<BacktestSummary summary={result.summary} />
<div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
  <StatsPanel days={result.days} />
  <AgentAccuracyTable perAgentAccuracy={result.summary.per_agent_accuracy} />
</div>
{/* EquityCurve and DayDetailModal added by Plan 03 */}
```
Three imports added at top. All existing form state and JSX unchanged.

## Verification

All plan checks passed:
1. All three component files exist in `gods-eye/frontend/src/components/`
2. Backtest.jsx contains 6 occurrences of the three component names (3 imports + 3 JSX uses)
3. `npm run build` passes: 66 modules transformed, no errors (2.37s)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `gods-eye/frontend/src/components/BacktestSummary.jsx` exists
- [x] `gods-eye/frontend/src/components/StatsPanel.jsx` exists
- [x] `gods-eye/frontend/src/components/AgentAccuracyTable.jsx` exists
- [x] `gods-eye/frontend/src/pages/Backtest.jsx` imports all three and renders them
- [x] Commit 895db5a exists (Task 1)
- [x] Commit 9891106 exists (Task 2)
- [x] Build passes: 66 modules, no errors
