# Phase 9: Backtest Dashboard - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (frontend phase)

<domain>
## Phase Boundary

User can select a date range, run a backtest from the UI, and view comprehensive results: overall accuracy/win rate/P&L, per-agent accuracy breakdown, equity curve chart, max drawdown/Sharpe ratio, and drill into individual days to see agent reasoning vs actual outcome.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- DASH-01: Date range picker + Run button with progress indicator
- DASH-02: Summary panel: accuracy %, win rate %, total P&L
- DASH-03: Per-agent accuracy table sortable by performance
- DASH-04: Equity curve (Recharts line chart of cumulative P&L)
- DASH-05: Stats: max drawdown, Sharpe ratio, avg win/loss
- DASH-06: Click any day → detail view with agent reasoning vs actual

Frontend uses existing patterns: React, Tailwind, Recharts, apiClient.
New page: Backtest.jsx at /backtest route.
Add "Backtest" to Sidebar navigation.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- src/api/client.js — needs new methods for backtest endpoints
- src/components/Sidebar.jsx — add Backtest nav item
- src/App.jsx — add /backtest route
- Recharts already used for AccuracyChart — use same patterns
- Tailwind dark theme with terminal-card, surface-* colors

### API Endpoints (from Phase 7-8)
- POST /api/backtest/run → {run_id, summary, days}
- GET /api/backtest/results/{run_id} → same shape

### Integration Points
- New page: src/pages/Backtest.jsx
- New components: BacktestSummary, EquityCurve, AgentAccuracyTable, DayDetailModal
- API client extensions for backtest endpoints

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond success criteria.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
