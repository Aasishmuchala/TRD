---
phase: 01-ui-alignment-and-auth-routing
plan: "03"
subsystem: frontend-ui
tags: [sidebar, settings, welcome, constants, agent-labels, quant-llm]
dependency_graph:
  requires: [01-01]
  provides: [UI-04, UI-05, UI-06, UI-07]
  affects: [Sidebar.jsx, Settings.jsx, Welcome.jsx]
tech_stack:
  added: []
  patterns:
    - Import canonical constants instead of local hardcoded maps
    - Quant/LLM balance persisted as decimal (0.45) to API, displayed as integer (45%)
key_files:
  modified:
    - TRD/gods-eye/frontend/src/components/Sidebar.jsx
    - TRD/gods-eye/frontend/src/pages/Settings.jsx
    - TRD/gods-eye/frontend/src/pages/Welcome.jsx
decisions:
  - "Sidebar nav labels aligned to plan spec: Dashboard/Agents/History/Paper Trading/Settings"
  - "Settings drives agent weight sliders from AGENT_ORDER (canonical order) via constants import"
  - "Quant/LLM default 45/55 per plan spec; stored as decimal in API payload"
  - "Welcome mini-nodes use agent.shortLabel and agent.color from AGENTS constant — no local data"
metrics:
  duration: "2 minutes 20 seconds"
  completed_date: "2026-03-30"
  tasks_completed: 3
  files_modified: 3
---

# Phase 01 Plan 03: UI Label Alignment, Quant/LLM Slider, Welcome Agent Nodes Summary

**One-liner:** Sidebar labels renamed to plan spec (Dashboard/Agents/History/Settings), Settings adds Quant/LLM slider defaulting to 45/55 with constants import, Welcome mini-nodes use canonical shortLabels from AGENTS constant.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix Sidebar labels to match plan spec | 7c89b91 | Sidebar.jsx |
| 2 | Add Quant/LLM slider to Settings, import from constants | 94982c9 | Settings.jsx |
| 3 | Fix Welcome agent mini-nodes to use canonical short labels | 83eccce | Welcome.jsx |

## What Was Built

### Task 1 — Sidebar Labels
Renamed 4 of 5 nav labels in `menuItems` to match plan spec exactly:
- `'Command Center'` → `'Dashboard'`
- `'Agent Intel'` → `'Agents'`
- `'Trade Log'` → `'History'`
- `'Config'` → `'Settings'`
- `'Paper Trading'` unchanged (already correct)

Verified no out-of-scope elements (Portfolio, Execute Trade, Markets, Secure Node, Terminal V2, user profile) existed in Sidebar.jsx.

### Task 2 — Settings Page
- Replaced local `agentLabels` and `agentColors` objects with imports from `constants/agents`:
  `import { AGENT_ORDER, AGENT_DISPLAY_NAMES, AGENT_COLORS, AGENT_WEIGHTS } from '../constants/agents'`
- Changed `agentWeights` initial state from hardcoded values to `{ ...AGENT_WEIGHTS }`
- Updated `handleReset` to use `AGENT_WEIGHTS` and reset `quantLlmBalance` to 45
- Switched agent weight slider loop from `Object.entries(agentWeights)` to `AGENT_ORDER.map()` for canonical ordering
- Added `quantLlmBalance` state (default: 45)
- Added "Quant / LLM Balance" section between Agent Weights and Simulation Parameters
- `handleSave` now includes `quant_llm_balance: quantLlmBalance / 100` in the API payload
- `fetchSettings` restores `quantLlmBalance` from API response (`data.quant_llm_balance * 100`)

### Task 3 — Welcome Agent Mini-Nodes
- Added `import { AGENTS } from '../constants/agents'`
- Replaced hardcoded inline array (6 objects with ad-hoc labels/colors) with `AGENTS.map()`
- Corrected `'RTL'` → `'RET'` (RETAIL_FNO canonical shortLabel per plan spec)
- All hardcoded hex colors removed — colors now driven by `agent.color` from constants
- `handleSubmit`, `handleMockMode`, localStorage logic unchanged

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

All acceptance criteria passed:

- `grep "label: 'Dashboard'\|label: 'Agents'\|label: 'History'\|label: 'Settings'" Sidebar.jsx` — 4 matches
- Old labels `'Command Center'|'Agent Intel'|'Trade Log'|'Config'` — 0 matches
- `grep -c "quantLlmBalance" Settings.jsx` — 4 matches (state, display, onChange, save payload)
- `grep "useState(45)" Settings.jsx` — 1 match
- `grep "import.*constants/agents" Settings.jsx Welcome.jsx` — 2 matches (one per file)
- `grep "shortLabel" Welcome.jsx` — 1 match
- Hardcoded hex colors in Welcome.jsx — 0 matches

## Self-Check: PASSED

All 3 modified files exist on disk. All 3 task commits verified in git history.
