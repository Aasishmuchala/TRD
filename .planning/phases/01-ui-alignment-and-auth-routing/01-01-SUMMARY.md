---
phase: 01-ui-alignment-and-auth-routing
plan: "01"
subsystem: ui
tags: [react, constants, agents, design-system]

# Dependency graph
requires: []
provides:
  - Canonical agent constants file with AGENTS array, AGENT_ORDER, AGENT_COLORS, AGENT_WEIGHTS, AGENT_DISPLAY_NAMES, AGENT_SHORT_LABELS
affects:
  - 01-02
  - 01-03
  - 01-04
  - all components that reference agent names, colors, or weights

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Import agent definitions from src/constants/agents.js — never hardcode agent names, colors, or weights in components"

key-files:
  created:
    - TRD/gods-eye/frontend/src/constants/agents.js
  modified: []

key-decisions:
  - "Plan spec is source of truth: AGENTS array uses plan-spec display names (FII Flows Analyst, DII Strategy Desk, Retail F&O Desk, Algo Trading Engine, Promoter Desk, RBI Policy Desk)"
  - "utils/colors.js left unmodified; downstream plans will migrate their imports independently"
  - "AGENT_ORDER canonical order follows plan spec: FII, DII, RETAIL_FNO, ALGO, PROMOTER, RBI (differs from SimulationStream.jsx which had ALGO first)"

patterns-established:
  - "Single source of truth: all agent data lives in src/constants/agents.js; components must import from here"
  - "Derived lookups (AGENT_COLORS, AGENT_WEIGHTS, etc.) computed via Object.fromEntries for zero duplication"

requirements-completed: [UI-01, UI-02]

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 01 Plan 01: Agent Constants — Single Source of Truth Summary

**ES module constants file exporting AGENTS array and 5 derived lookup objects with plan-spec names, colors, and weights for all 6 market agents**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-30T12:28:48Z
- **Completed:** 2026-03-30T12:30:30Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments

- Created `src/constants/agents.js` as the single source of truth for all agent definitions
- Exported `AGENTS` array (6 objects) plus 5 derived lookup maps covering colors, weights, display names, short labels, and canonical order
- Preserved exact hex colors from `utils/colors.js` while adding plan-spec display names and weights
- Left all existing files unmodified — downstream plans will migrate imports in their own tasks

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/constants/agents.js with canonical agent definitions** - `eae8360` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `TRD/gods-eye/frontend/src/constants/agents.js` — Canonical agent definitions: AGENTS array, AGENT_ORDER, AGENT_COLORS, AGENT_WEIGHTS, AGENT_DISPLAY_NAMES, AGENT_SHORT_LABELS

## Decisions Made

- Used plan-spec display names (e.g. "FII Flows Analyst", "Algo Trading Engine") which differ from the shorter labels in utils/colors.js ("FII Flows", "Algo Engine") — plan spec is authoritative
- AGENT_ORDER follows plan spec order (FII first), not SimulationStream.jsx order (ALGO first) — the new constants file is the canonical reference
- utils/colors.js not modified in this task; it still exports the `agents` and `agentLabels` objects for backward compat until downstream components update their imports

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- The project has a nested git repository structure (TRD/ is a separate repo containing gods-eye/ as another repo). The commit was made from within the gods-eye repo (`TRD/gods-eye/`) rather than the outer workspace repo. This is the correct behavior per the sub-repo structure noted in PROJECT.md.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `src/constants/agents.js` is ready for import by all Phase 1 plans (01-02, 01-03, 01-04)
- Plans updating components should replace inline `agentLabels`/`agentColors` objects and `utils/colors.js` `agents` imports with imports from `src/constants/agents.js`
- No blockers

---
*Phase: 01-ui-alignment-and-auth-routing*
*Completed: 2026-03-30*
