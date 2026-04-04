---
phase: 08-signal-scoring
plan: "01"
subsystem: engine
tags: [signal-scoring, dataclass, pure-function, tdd, nifty, banknifty, rsi, supertrend, vix]

# Dependency graph
requires:
  - phase: 07-backtest-engine
    provides: BacktestDayResult.signals dict shape and direction/conviction fields consumed by scorer
  - phase: 06-technical-signals
    provides: signals dict keys (rsi, supertrend, vix_regime, oi_sentiment) and value formats
provides:
  - SignalScorer.score() — pure static method combining 60% sentiment + 40% technical alignment into 0-100 float
  - ScoreResult dataclass — score, tier, direction, contributing_factors, suggested_instrument
  - Tier labels: >70 strong, >=50 moderate, <50 skip
  - Instrument mapping: NIFTY/BANKNIFTY + direction family → CE/PE/NONE
affects:
  - 08-02-integration (calls SignalScorer.score() and attaches ScoreResult to API responses)
  - 09-backtest-dashboard (displays tier, score, suggested_instrument from ScoreResult)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pure function module — no DB, no network, no app.config imports; tested in complete isolation
    - @dataclass for result types at engine layer (not Pydantic — no HTTP boundary)
    - TDD: test file committed RED before implementation; 24 tests cover all formula branches

key-files:
  created:
    - gods-eye/backend/app/engine/signal_scorer.py
    - gods-eye/backend/tests/test_signal_scorer.py
  modified: []

key-decisions:
  - "SignalScorer.score() is a pure static method — no instance state, no side effects; makes it trivially testable and safe to call from any context"
  - "HOLD direction always produces 0 sentiment score regardless of conviction — max score 40 (technicals only), always tier=skip unless 3+ technicals align"
  - "Unknown direction strings treated as HOLD (safe default) so caller errors degrade gracefully rather than crash"
  - "Instrument param is case-insensitive to tolerate caller inconsistency"
  - "contributing_factors always includes agent conviction entry so consumers can surface the LLM signal even when no technicals aligned"

patterns-established:
  - "Pure engine layer: modules in app/engine/ that are not BacktestEngine itself should have zero I/O dependencies — import only stdlib and typing"
  - "TDD for pure functions: write all assertions against specified formula first, implement to pass — formula math locked in tests prevents silent regression"

requirements-completed: [SIG-01, SIG-02, SIG-03]

# Metrics
duration: 2min
completed: 2026-03-31
---

# Phase 8 Plan 01: SignalScorer Summary

**Pure 0-100 signal scorer using 60% agent sentiment + 40% technical alignment, with tier labels and NIFTY/BANKNIFTY instrument mapping, backed by 24 TDD tests**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T22:10:39Z
- **Completed:** 2026-03-30T22:12:39Z
- **Tasks:** 2 (RED + GREEN TDD phases)
- **Files modified:** 2

## Accomplishments

- `SignalScorer.score()` pure static method implementing the exact formula from CONTEXT.md: direction multiplier (1.0/0.85/0.0) * conviction * 0.60 + aligned_technicals * 25 * 0.40
- `ScoreResult` dataclass with score, tier, direction, contributing_factors, suggested_instrument — zero Pydantic dependency
- Instrument mapping covers NIFTY and BANKNIFTY for all 5 direction values (BUY/SELL/STRONG_BUY/STRONG_SELL/HOLD)
- 24 TDD tests locked formula math, tier boundaries, contributing_factors content, clamp behaviour, and edge cases (empty signals, absent OI, unknown direction, case-insensitive instrument)

## Task Commits

Each task was committed atomically:

1. **RED — Failing tests** - `e19d79e` (test)
2. **GREEN — Implementation** - `25a4a24` (feat)

_TDD plan: test commit before implementation commit._

## Files Created/Modified

- `gods-eye/backend/app/engine/signal_scorer.py` - SignalScorer class + ScoreResult dataclass; pure function, no I/O
- `gods-eye/backend/tests/test_signal_scorer.py` - 24 TDD tests; formula math, tier boundaries, instrument mapping, edge cases

## Decisions Made

- `SignalScorer.score()` is a `@staticmethod` — no instance needed, no state to initialise; simplest correct design for a pure function
- `ScoreResult` uses `@dataclass` not Pydantic `BaseModel` — there is no HTTP serialisation boundary here; dataclass is lighter and appropriate for engine-layer value objects
- HOLD direction: sentiment multiplier = 0.0, so conviction is irrelevant; max reachable score is 40 (4 aligned technicals), which is always tier=skip
- `contributing_factors` always appends the agent conviction entry last — consumers can surface the LLM signal even if zero technicals fired

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `signal_scorer.py` is ready for Plan 08-02 integration which will call `SignalScorer.score()` and attach `ScoreResult` to backtest and live-simulate API responses
- ScoreResult fields map directly to the Phase 9 dashboard requirements (tier for color-coding, score for bar chart, suggested_instrument for option type label)

---
*Phase: 08-signal-scoring*
*Completed: 2026-03-31*

## Self-Check: PASSED
