---
phase: 13-risk-management-rules
plan: "01"
subsystem: engine
tags: [risk-management, position-sizing, stop-loss, tdd, python, dataclass]

# Dependency graph
requires:
  - phase: 12-hybrid-scoring
    provides: HybridResult with tier, direction, conviction — inputs to RiskManager.compute()
provides:
  - RiskParams dataclass with lots, stop_distance, target_distance, stop_level, target_level, vix_used, risk_reward
  - RiskManager.compute(tier, direction, entry_close, vix) pure static method
  - Module constants STOP_MULTIPLIER=5.0 and RISK_REWARD_RATIO=1.5
affects:
  - 14-backtest-integration
  - route wiring (hybrid signal output)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pure static method engine (no instance state, no I/O, no app.* imports)
    - TDD RED->GREEN workflow with pytest
    - VIX-scaled stop formula as module-level constant

key-files:
  created:
    - gods-eye/backend/app/engine/risk_manager.py
    - gods-eye/backend/tests/test_risk_manager.py
  modified: []

key-decisions:
  - "RiskManager.compute() takes direction so one call returns complete RiskParams including directional stop/target levels"
  - "HOLD direction produces computed stop/target distances but levels stay at entry_close (no directional offset)"
  - "Unknown tier normalised to skip silently — avoids crashing on future tier additions"
  - "STOP_MULTIPLIER and RISK_REWARD_RATIO defined as module-level constants for future caller override"

patterns-established:
  - "Pure module pattern: risk_manager.py has zero app.* imports — only stdlib + dataclasses"
  - "Input validation raises ValueError with descriptive message (vix<=0, entry_close<=0)"

requirements-completed: [RISK-02, RISK-03, RISK-04]

# Metrics
duration: 2min
completed: 2026-04-01
---

# Phase 13 Plan 01: Risk Management Rules Summary

**VIX-scaled stop/target engine with tier-based lot sizing: RiskParams dataclass + RiskManager.compute() pure static method, 10 TDD tests all green**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-31T20:34:06Z
- **Completed:** 2026-04-01T00:00:00Z
- **Tasks:** 2 (RED + GREEN TDD phases)
- **Files modified:** 2

## Accomplishments

- RiskParams dataclass with 7 fields: lots, stop_distance, target_distance, stop_level, target_level, vix_used, risk_reward
- RiskManager.compute() pure static method — no I/O, no DB, no network, no app.* imports
- Position sizing: strong=2 lots, moderate=1 lot, skip=0 lots (all distances zero, levels at entry)
- Stop formula: VIX * 5.0 (VIX=20 -> 100pt stop, VIX=14 -> 70pt stop, VIX=25 -> 125pt stop)
- Target formula: stop_distance * 1.5 (100pt stop -> 150pt target)
- Directional levels: BUY subtracts stop/adds target; SELL adds stop/subtracts target; HOLD stays at entry_close
- 10 TDD tests covering all tiers, both directions, HOLD, edge cases (ValueError), risk_reward invariant

## Task Commits

Each task was committed atomically:

1. **RED phase: failing tests** - `e3d0a62` (test)
2. **GREEN phase: implementation** - `b25b837` (feat)

_TDD plan: two commits — test first, then implementation._

## Files Created/Modified

- `gods-eye/backend/app/engine/risk_manager.py` - RiskParams dataclass + RiskManager.compute() pure static method
- `gods-eye/backend/tests/test_risk_manager.py` - 10 TDD tests covering all sizing tiers, directions, edge cases

## Decisions Made

- RiskManager.compute() takes `direction` as a parameter so one call returns complete RiskParams including directional stop/target levels (plan spec: "Simplification: compute() takes direction too")
- HOLD direction produces computed stop/target distances but stop_level and target_level remain at entry_close — no directional offset since no trade is entered
- Unknown tier strings normalised to "skip" silently — avoids crashes when future tier labels are added upstream
- STOP_MULTIPLIER and RISK_REWARD_RATIO defined as module constants — callers can reference or override in future without changing formulas

## Deviations from Plan

None — plan executed exactly as written.

The test suite extends to 10 tests (plan required minimum 8). Two extra tests added (test_unknown_tier_treated_as_skip, test_negative_vix_raises_value_error) for complete coverage. Both pass.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- RiskManager ready for import: `from app.engine.risk_manager import RiskManager, RiskParams`
- Call pattern: `params = RiskManager.compute(hybrid_result.tier, hybrid_result.direction, entry_close, vix)`
- Phase 14 backtest integration can replace flat 3x leverage in backtest_engine.py._compute_pnl() with RiskManager.compute()
- Route wiring can append RiskParams to hybrid signal response payload

## Self-Check: PASSED

- FOUND: gods-eye/backend/app/engine/risk_manager.py
- FOUND: gods-eye/backend/tests/test_risk_manager.py
- FOUND: .planning/phases/13-risk-management-rules/13-01-SUMMARY.md
- FOUND commit: e3d0a62 (test RED phase)
- FOUND commit: b25b837 (feat GREEN phase)

---
*Phase: 13-risk-management-rules*
*Completed: 2026-04-01*
