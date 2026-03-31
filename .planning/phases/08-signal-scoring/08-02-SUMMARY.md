---
phase: 08-signal-scoring
plan: "02"
subsystem: backend/signal-integration
tags: [signal-scoring, backtest-engine, api, integration, tdd]
dependency_graph:
  requires:
    - 08-01  # SignalScorer module created in plan 01
    - 07-02  # BacktestEngine with BacktestDayResult
  provides:
    - signal_score field on every BacktestDayResult and API response
  affects:
    - GET /api/backtest/results/{run_id}
    - POST /api/simulate
tech_stack:
  added: []
  patterns:
    - vars(dataclass_instance) to convert ScoreResult to plain dict at engine boundary
    - Optional[SignalScoreSchema] = None on BacktestDayResponse for graceful null on pre-Phase-8 persisted runs
    - Inline VIX classify + PCR-to-OI-sentiment helpers in route handler (no separate module needed)
key_files:
  created: []
  modified:
    - gods-eye/backend/app/engine/backtest_engine.py
    - gods-eye/backend/app/api/schemas.py
    - gods-eye/backend/app/api/routes.py
    - gods-eye/backend/tests/test_backtest_engine.py
    - gods-eye/backend/tests/test_routes.py
decisions:
  - "vars(score_result) to convert ScoreResult dataclass to plain dict — consistent with asdict() pattern used elsewhere in engine; JSON-serializable with no extra import"
  - "signal_score on BacktestDayResponse is Optional[SignalScoreSchema] = None so pre-Phase-8 persisted runs (no signal_score in stored JSON) deserialise gracefully without 422"
  - "Live simulate uses inline VIX/PCR helpers in routes.py — no new helper module; helpers are 3 lines each and only needed in one place"
  - "SignalScorer.score() called in run_backtest() after signals = TechnicalSignals.compute_signals_for_date(...), before BacktestDayResult construction — same signals dict reused, zero extra computation"
metrics:
  duration: "6m (wall clock)"
  completed: "2026-03-31"
  tasks: 2
  files_modified: 5
---

# Phase 08 Plan 02: Signal Scorer Integration Summary

Wire SignalScorer into BacktestEngine and live simulate endpoint so both response paths emit a `signal_score` object (score, tier, direction, contributing_factors, suggested_instrument).

## Tasks Completed

### Task 1: Add signal_score to BacktestDayResult and wire engine
- Added `signal_score: Optional[Dict] = field(default=None)` to `BacktestDayResult` dataclass
- Imported `SignalScorer` in `backtest_engine.py`
- Called `SignalScorer.score()` after `TechnicalSignals.compute_signals_for_date()`, before `BacktestDayResult` construction
- Passed `signal_score=vars(score_result)` into the dataclass constructor
- Added 4 tests: field existence, dict assignment, tier validity, full integration roundtrip

### Task 2: Expose signal_score in API schemas and live simulate route
- Added `SignalScoreSchema` Pydantic model to `schemas.py`
- Added `signal_score: Optional[SignalScoreSchema] = None` to `BacktestDayResponse`
- Imported `SignalScorer` in `routes.py`
- Wired signal_score computation into POST `/api/simulate` handler with inline VIX/PCR helpers
- Updated `_serialize_backtest_result()` to propagate `signal_score` from `BacktestDayResult` to `BacktestDayResponse`
- Added 2 tests confirming signal_score present in simulate response and tier is valid

## Verification Results

```
======================== 81 passed, 7 warnings in 0.23s ========================
```

All 81 tests passed. Zero regressions.

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

1. `vars(score_result)` to convert `ScoreResult` dataclass to plain dict at engine boundary — consistent with the `asdict()` pattern used elsewhere; JSON-serializable without extra imports.
2. `Optional[SignalScoreSchema] = None` on `BacktestDayResponse` ensures pre-Phase-8 persisted runs (no `signal_score` in stored JSON) deserialise gracefully without 422 errors.
3. Inline VIX classify and PCR-to-OI-sentiment helpers kept in `routes.py` — only 3 lines each and only needed in one place; a separate helper module would add indirection without benefit.
4. `SignalScorer.score()` is called after `TechnicalSignals.compute_signals_for_date()` with the same `signals` dict — zero extra computation, natural integration point.

## Self-Check: PASSED

Files confirmed present:
- gods-eye/backend/app/engine/backtest_engine.py (modified)
- gods-eye/backend/app/api/schemas.py (modified)
- gods-eye/backend/app/api/routes.py (modified)
- gods-eye/backend/tests/test_backtest_engine.py (modified)
- gods-eye/backend/tests/test_routes.py (modified)

Commits confirmed:
- c810378: feat(08-02): add signal_score to BacktestDayResult and wire SignalScorer
- eed4953: feat(08-02): expose signal_score in API schemas and live simulate route
