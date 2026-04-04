---
phase: "09"
plan: "03"
subsystem: frontend
tags: [recharts, equity-curve, modal, drill-down, backtest-dashboard]
dependency_graph:
  requires: ["09-01", "09-02"]
  provides: ["EquityCurve component", "DayDetailModal component", "day drill-down flow"]
  affects: ["gods-eye/frontend/src/pages/Backtest.jsx"]
tech_stack:
  added: []
  patterns:
    - "Recharts LineChart with dynamic line color (bull/bear based on final P&L)"
    - "Per-dot color mapping from daily pnl_points"
    - "Portal-free fixed overlay modal with backdrop click-to-close"
    - "ReferenceLine at y=0 for breakeven visualization"
key_files:
  created:
    - gods-eye/frontend/src/components/EquityCurve.jsx
    - gods-eye/frontend/src/components/DayDetailModal.jsx
  modified:
    - gods-eye/frontend/src/pages/Backtest.jsx
decisions:
  - "onDayClick wired at LineChart level (not Line level) — chart-level onClick provides activePayload reliably"
  - "Per-dot color uses renderDot/renderActiveDot functions — Recharts dot prop accepts a render function for custom per-point styling"
  - "DayDetailModal placed before closing Layout tag — ensures z-50 fixed overlay sits above sidebar and scrollable content"
  - "dirColor/dirLabel imported directly in Backtest.jsx for day list table — avoids prop-drilling through EquityCurve"
metrics:
  duration: "192s"
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_changed: 3
---

# Phase 09 Plan 03: Equity Curve and Day Detail Modal Summary

**One-liner:** Recharts equity curve with dynamic bull/bear line color and per-dot P&L coloring, plus full-detail day drill-down modal showing prediction, outcome, agent directions, and signal score.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create EquityCurve.jsx using Recharts | 62cc9ce | `EquityCurve.jsx` (created) |
| 2 | Create DayDetailModal.jsx and wire into Backtest.jsx | 04e5d6d | `DayDetailModal.jsx` (created), `Backtest.jsx` (modified) |

## What Was Built

### EquityCurve.jsx
- Recharts LineChart with `ResponsiveContainer`, `ReferenceLine` at y=0 (breakeven), and `CartesianGrid`
- Transforms `days` array to `{ date: "MM-DD", cumPnl, rawDay }` for compact X labels
- Line color adapts dynamically: `#00E676` (bull) when final cumPnl > 0, `#FF1744` (bear) when negative, `#00D4E0` default
- Custom `renderDot` and `renderActiveDot` color each dot green/red/neutral based on that day's `pnl_points`
- `onDayClick` wired via `LineChart onClick` extracting `activePayload[0].payload.rawDay`
- Empty state: "NO DATA YET" centered mono text
- Tooltip follows AccuracyChart style (dark bg, primary border, JetBrains Mono)

### DayDetailModal.jsx
- Renders `null` when `day` prop is null (no DOM cost when closed)
- Fixed fullscreen overlay `bg-black/60` with `z-50`; clicking backdrop calls `onClose`
- Modal card stops propagation with `e.stopPropagation()`
- Sections in order:
  1. Header: date + next_date + close button (X)
  2. Prediction vs Actual: 2-col grid with direction badge, conviction %, actual move %, CORRECT/INCORRECT/HELD badge
  3. P&L row: day P&L + cumulative P&L (bull/bear colored)
  4. Agent Directions: 3-col grid of 6 agents with direction badges
  5. Signal Score (conditional): score number, tier badge, direction, suggested instrument, contributing factors list
  6. Nifty prices: `close → next_close` in font-mono
- `TierBadge` inline helper applies tier-specific Tailwind colors (strong/moderate/skip)
- Uses `dirColor`/`dirLabel` from `../utils/format`

### Backtest.jsx Updates
- Added imports: `EquityCurve`, `DayDetailModal`, `{ dirColor, dirLabel }`
- Added `selectedDay` state initialized to `null`
- Results section now renders (after Plan 02's BacktestSummary/StatsPanel/AgentAccuracyTable):
  - `<EquityCurve days={result.days} onDayClick={setSelectedDay} />`
  - Day-by-Day Results table with clickable rows (date, prediction, actual %, P&L pts, WIN/LOSS/HELD)
- `<DayDetailModal>` placed just before `</Layout>` for correct z-index stacking

## Deviations from Plan

None — plan executed exactly as written.

The only non-trivial decision was discovering Plan 02's components (BacktestSummary, StatsPanel, AgentAccuracyTable) were already imported in Backtest.jsx from a prior execution but not committed to git. The results section already had the Plan 02 layout stub. Plan 03 additions were written into the correct section below without conflict.

## Verification

All success criteria met:
- EquityCurve renders Recharts LineChart with cumulative P&L, date X axis, breakeven ReferenceLine, dynamic bull/bear color
- Clicking chart data point calls `onDayClick` with the day object
- DayDetailModal renders null when `day=null`; renders full overlay with all sections when a day is passed
- Backtest.jsx day list table renders all days as clickable rows
- Clicking any row opens DayDetailModal with that day's data
- `npm run build` completes without errors (866 modules, 2.69s)

## Self-Check: PASSED

- `gods-eye/frontend/src/components/EquityCurve.jsx` — FOUND
- `gods-eye/frontend/src/components/DayDetailModal.jsx` — FOUND
- Commits `62cc9ce` and `04e5d6d` — FOUND
