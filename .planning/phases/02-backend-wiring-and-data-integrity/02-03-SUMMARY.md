---
phase: 02-backend-wiring-and-data-integrity
plan: "03"
subsystem: api, ui
tags: [fastapi, react, tailwind, nse, fallback, data-source, banner]

# Dependency graph
requires:
  - phase: 02-backend-wiring-and-data-integrity
    provides: live NSE market data with fallback tracking (market_data.py already sets data_source field)

provides:
  - simulate API response always includes top-level data_source field ("nse_live" or "fallback")
  - Dashboard amber "DATA: FALLBACK" banner renders when result.data_source === "fallback"
  - Banner is dismissible per-result with auto-reset on new simulation

affects: [frontend-ui, backend-api, data-integrity, phase-03, phase-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "data_source propagation: snapshot.get('data_source') fetched from get_live_snapshot() and attached to every simulate response"
    - "live_data_source initialized at top of try block to 'fallback' to prevent NameError across all code paths"
    - "React fallback banner pattern: result?.data_source optional chaining, dismissedFallback state reset via useEffect([result])"

key-files:
  created: []
  modified:
    - TRD/gods-eye/backend/app/api/routes.py
    - TRD/gods-eye/frontend/src/pages/Dashboard.jsx

key-decisions:
  - "For source=live path: call get_live_snapshot() separately to extract data_source — build_market_input() strips non-underscore snapshot fields into mi_fields but does not preserve data_source separately"
  - "For non-live paths (scenario, manual, flat fields): always set data_source='fallback' — no NSE fetch occurs"
  - "live_data_source initialized before the if/elif branches (not inside them) to satisfy all exit paths without NameError"
  - "Banner placed above toast notification inside main content div — not in TopNav (per plan spec)"

patterns-established:
  - "Simulation response contract: every /api/simulate response now has a top-level data_source field"
  - "Frontend trust signal: amber banner is the canonical UI affordance for fallback data state"

requirements-completed: [BACK-03]

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 02 Plan 03: NSE Fallback Visibility Summary

**Simulate API now exposes data_source ("nse_live" or "fallback") in every response; Dashboard renders a dismissible amber "DATA: FALLBACK" banner when mock market data was used**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-30T12:47:24Z
- **Completed:** 2026-03-30T12:49:01Z
- **Tasks:** 2 auto + 1 checkpoint (auto-approved)
- **Files modified:** 2

## Accomplishments

- Backend routes.py: `live_data_source` initialized to `"fallback"` as a safe default, overridden to the snapshot value for source=live runs; attached to every simulate response
- Backend routes.py: for non-live simulations (scenario or manual), always sets `data_source="fallback"` since no NSE fetch occurs
- Frontend Dashboard.jsx: imports `useEffect` alongside `useState`; adds `dismissedFallback` state; resets on each new result; renders amber banner with `role="alert"` and accessible dismiss button

## Task Commits

Each task was committed atomically:

1. **Task 1: Expose data_source in simulate API response** - `4db29ab` (feat)
2. **Task 2: Render amber fallback banner in Dashboard.jsx** - `5880647` (feat)
3. **Task 3: checkpoint:human-verify** — Auto-approved (autonomous mode)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `TRD/gods-eye/backend/app/api/routes.py` - Added live_data_source initialization, snapshot fetch for source=live, and data_source attachment in both live and non-live response paths
- `TRD/gods-eye/frontend/src/pages/Dashboard.jsx` - Added useEffect import, dismissedFallback state with auto-reset, and amber fallback banner JSX

## Decisions Made

- Called `get_live_snapshot()` separately in the source=live branch (instead of extracting data_source from live_extras) because `build_market_input()` only copies underscore-prefixed keys to live_extras — data_source is not underscore-prefixed so it never reaches live_extras.
- `live_data_source = "fallback"` initialized at top of try block before all branching — prevents NameError if code reaches the response assembly section via any path.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Outer TRD workspace git repo treats `TRD/` as untracked (gods-eye has its own `.git`). Commits were made to the gods-eye sub-repo directly as intended.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The simulate API data_source contract is now stable and documented
- Any future phase that adds live ticker display or market status indicators can rely on `result.data_source` as the canonical trust signal
- No blockers

---
*Phase: 02-backend-wiring-and-data-integrity*
*Completed: 2026-03-30*
