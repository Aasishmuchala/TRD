---
phase: 15-dashboard-updates
plan: "01"
subsystem: frontend-signal-page
tags: [signal, hybrid-engine, dashboard, react, api-client]
dependency_graph:
  requires:
    - Phase 12 hybrid scoring endpoint (POST /api/signal/hybrid/{instrument}/{date})
    - Phase 13 risk params in HybridSignalResponse
  provides:
    - Signal page at /signal with 4-section hybrid signal layout
    - getHybridSignal and getQuantSignal methods on apiClient
  affects:
    - gods-eye/frontend/src/api/client.js
    - gods-eye/frontend/src/App.jsx
    - gods-eye/frontend/src/components/Sidebar.jsx
tech_stack:
  added: []
  patterns:
    - terminal-card sections with font-mono styling (consistent with Backtest.jsx)
    - Instrument toggle tabs (NIFTY/BANKNIFTY) following Backtest mode-tab pattern
    - ProgressBar component for quant score and agent conviction bars
    - DirectionTag component for color-coded BUY/SELL/HOLD badges
key_files:
  created:
    - gods-eye/frontend/src/pages/Signal.jsx
  modified:
    - gods-eye/frontend/src/api/client.js
    - gods-eye/frontend/src/App.jsx
    - gods-eye/frontend/src/components/Sidebar.jsx
decisions:
  - Signal nav item placed between Backtest and Performance (not between Backtest and Skills as originally spec'd) because a pre-existing Performance entry was already inserted between Backtest and Skills
  - AGENT_DISPLAY_NAMES imported from constants/agents.js for agent label mapping — avoids inline duplication
  - ProgressBar and DirectionTag defined as local components in Signal.jsx — lightweight helpers not worth extracting to shared components at this stage
metrics:
  duration_seconds: 281
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_modified: 4
---

# Phase 15 Plan 01: Signal Page Summary

**One-liner:** Signal page at /signal showing hybrid signal output — quant score breakdown table, per-agent direction+conviction bars, validator verdict badge, and risk-parameterised trade recommendation — driven by a single POST to /api/signal/hybrid.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add API client methods + create Signal.jsx page | 869e865 | client.js (+2 methods), Signal.jsx (363 lines, created) |
| 2 | Wire /signal route in App.jsx + Sidebar nav item | 1d1e7ae | App.jsx (+import+route), Sidebar.jsx (+Signal entry) |

## What Was Built

### Signal.jsx (363 lines)

Full-page React component with Layout wrapper containing:

- **Control bar** — NIFTY/BANKNIFTY instrument toggle (tab style matching Backtest.jsx) + date input defaulting to today + RUN SIGNAL button
- **Section 1: Quant Score** — large score badge, direction tag, score progress bar (0-100), factor table with columns Factor / Threshold Hit / Side / Points
- **Section 2: Agent Consensus** — per-agent rows with direction tag, conviction% progress bar (1px height, direction-colored), rationale text with title hover for full text
- **Section 3: Validator Verdict** — verdict badge (confirm=bull/green, adjust=neutral, skip=bear/red), reasoning text below
- **Section 4: Recommended Trade** — tradeable badge, 6-cell 2-column grid (instrument, tier, lots, stop, target, VIX), skip overlay when tier=skip
- Empty / loading / error states all handled

### API Client Methods

```js
getHybridSignal: (instrument, date) => request(
  `${API_BASE}/signal/hybrid/${instrument}/${date}`,
  { method: 'POST', headers: {...}, body: JSON.stringify({}) },
  0, 30000  // 0 retries, 30s timeout
)

getQuantSignal: (instrument, date) => request(
  `${API_BASE}/signal/quant/${instrument}/${date}`,
  {}, 0, 10000  // 0 retries, 10s timeout
)
```

## Deviations from Plan

### Minor Position Adjustment

**Signal nav item placement:** Plan spec says "between Backtest and Skills". Pre-existing (unrelated) work had already inserted a Performance entry between Backtest and Skills in Sidebar.jsx. The Signal entry was placed between Backtest and Performance — this keeps Signal adjacent to Backtest (as intended in plan) and preserves existing sidebar order.

No other deviations — plan executed as written.

## Self-Check: PASSED

- `/Users/aasish/Desktop/CLAUDE PROJECTS/TRD/gods-eye/frontend/src/pages/Signal.jsx` — FOUND (363 lines)
- `/Users/aasish/Desktop/CLAUDE PROJECTS/TRD/gods-eye/frontend/src/api/client.js` — getHybridSignal + getQuantSignal at lines 143/149
- App.jsx `/signal` route — FOUND at line 32
- Sidebar.jsx `/signal` entry — FOUND at line 39
- Commit 869e865 — Task 1
- Commit 1d1e7ae — Task 2
- Vite build: 869 modules, 0 errors
