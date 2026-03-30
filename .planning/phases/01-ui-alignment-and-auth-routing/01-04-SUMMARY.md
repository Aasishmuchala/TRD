---
phase: 01-ui-alignment-and-auth-routing
plan: "04"
subsystem: frontend-ui
tags: [graduation-criteria, paper-trading, scenario-modal, flow-data, ui-alignment]
dependency_graph:
  requires: [01-01]
  provides: [correct-graduation-criteria, flow-data-inputs]
  affects: [PaperTrading.jsx, ScenarioModal.jsx, Dashboard.jsx]
tech_stack:
  added: []
  patterns: [plan-spec-thresholds, editable-flow-data-inputs, iife-computed-criteria]
key_files:
  created: []
  modified:
    - TRD/gods-eye/frontend/src/pages/PaperTrading.jsx
    - TRD/gods-eye/frontend/src/components/ScenarioModal.jsx
    - TRD/gods-eye/frontend/src/pages/Dashboard.jsx
decisions:
  - "Graduation criteria computed with IIFEs inline — avoids separate useMemo, keeps each criterion self-contained"
  - "flowData passed as argument to onConfirm; Dashboard merges as flow_data key in simulation payload — backward-compatible"
  - "Session list card simplified to single-line format: date · direction conviction% (removes separate direction column)"
metrics:
  duration_minutes: 2
  completed_date: "2026-03-30"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
---

# Phase 01 Plan 04: Graduation Criteria Fix and ScenarioModal Flow Data Summary

**One-liner:** Replace 4 wrong operational metrics with plan-spec performance graduation criteria (6 thresholds) and add 6 editable flow data inputs to ScenarioModal.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace PaperTrading graduation criteria + fix session format | c9b3e86 | PaperTrading.jsx |
| 2 | Add missing flow data fields to ScenarioModal | b760ff6 | ScenarioModal.jsx, Dashboard.jsx |

## What Was Built

### Task 1: Graduation Criteria Replacement (PaperTrading.jsx)

The `criteria` array previously contained 4 operational metrics that measured system performance (simulations run, unique scenarios, feedback engine active, avg execution time). These were replaced with the 6 plan-spec performance-based graduation criteria:

1. **Directional Accuracy (1-day)** — `>= 57%` over 20 sessions (reads `outcome_accuracy_1d` from history)
2. **Directional Accuracy (1-week)** — `>= 60%` over 4 weeks (reads `outcome_accuracy_1w`)
3. **Calibration Error** — `< 15%` (reads `calibration_error`)
4. **Quant-LLM Agreement** — `>= 70%` when both agree (reads `aggregator_result.quant_llm_agreement`)
5. **No Catastrophic Miss** — no >3% move missed with high-confidence wrong call (reads `catastrophic_miss` flag)
6. **Internal Consistency** — `>= 75%` across 3 samples (reads `internal_consistency`)

Each criterion uses IIFEs to compute `current` and `passed` from history. Shows `'N/A'` when API fields are absent (which they all currently are — criteria will populate as backend adds these fields).

Session list format changed from `"29 Mar, HH:MM"` to `"Mar 29 · BEAR 65%"` (date · direction conviction%) per plan spec. The separate right-aligned direction column was removed; direction and conviction are now inline with the date.

### Task 2: ScenarioModal Flow Data (ScenarioModal.jsx + Dashboard.jsx)

ScenarioModal previously showed only scenario name/description and CANCEL/EXECUTE buttons. Added:

- `useState` import and `flowData` state with 6 keys
- "Flow Data" section with 2-column grid of editable inputs:
  - FII Net (Today), FII 5-Day Avg, FII Futures OI Delta
  - DII Net (Today), DII 5-Day Avg, SIP Inflow
- `handleConfirm` now calls `onConfirm(flowData)` passing data back to parent

Dashboard.jsx `handleConfirm` updated to accept `flowData` argument and merge it as `flow_data` key in the simulation payload before calling `simulate()`. Change is backward-compatible — if flowData is empty object, simulation proceeds as before.

## Decisions Made

- **Inline IIFEs for computed criteria:** Each criterion uses `(() => { ... })()` for both `current` and `passed` fields. This keeps each criterion object self-contained and avoids pulling useMemo into the component just for this. Acceptable at this scale.
- **flowData forwarded as `flow_data` key:** Dashboard merges `flow_data: flowData` into the scenario payload. Backend may or may not use it immediately — the hook and API client will pass it through without breaking.
- **Session card simplified:** Removed the separate right-column direction display. Single line `"Mar 29 · BEAR 65%"` is more compact and matches plan spec format.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files Exist
- `TRD/gods-eye/frontend/src/pages/PaperTrading.jsx` — FOUND
- `TRD/gods-eye/frontend/src/components/ScenarioModal.jsx` — FOUND
- `TRD/gods-eye/frontend/src/pages/Dashboard.jsx` — FOUND

### Commits Exist
- `c9b3e86` — Task 1 commit
- `b760ff6` — Task 2 commit

## Self-Check: PASSED
