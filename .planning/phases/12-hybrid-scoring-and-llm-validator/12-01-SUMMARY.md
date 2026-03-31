---
phase: 12-hybrid-scoring-and-llm-validator
plan: "01"
subsystem: engine
tags: [hybrid-scoring, quant, agent-consensus, direction-lock, dataclass, tdd]

# Dependency graph
requires:
  - phase: 10-quant-signal-engine
    provides: QuantScoreResult, QuantSignalEngine — quant scoring output consumed by HybridScorer.fuse()
  - phase: 11-agent-signal-prompts
    provides: AgentResponse schema — agent outputs consumed to compute consensus

provides:
  - HybridScorer.fuse() pure static method combining quant (60%) + agent consensus (40%)
  - HybridResult dataclass with all 7 plan-spec fields + conviction, tradeable, tier
  - ValidatorVerdict dataclass with verdict/reasoning/adjustment_amount
  - AgentBreakdownEntry dataclass for per-agent snapshot in HybridResult.agent_breakdown
  - compute_agent_consensus() helper returning (score, direction) tuple

affects:
  - 12-02  # API layer will call HybridScorer.fuse() via plan 02
  - 12-03  # LLM validator plan will produce ValidatorVerdict consumed here
  - 14     # Hybrid backtest will call HybridScorer.fuse() in replay loop

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pure static method engine pattern (no instance state, no I/O, stdlib only)
    - TDD RED→GREEN commit sequence for engine modules
    - Direction-lock invariant: quant direction always wins over validator

key-files:
  created:
    - gods-eye/backend/app/engine/hybrid_scorer.py
    - gods-eye/backend/tests/test_hybrid_scorer.py
  modified: []

key-decisions:
  - "HybridScorer.fuse() is a pure static method — no instance state, no I/O; makes it trivially testable and safe to call from any context including backtests"
  - "Direction-lock is enforced unconditionally: quant_result.direction always becomes HybridResult.direction regardless of agent consensus or validator verdict"
  - "Conviction field equals hybrid_score after confirm verdict, reduced by adjustment_amount after adjust, set to 0 after skip — post-validation conviction is separate from hybrid_score"
  - "Instrument hint falls back to consensus-derived NIFTY_CE/PE only when quant direction is HOLD — prevents quant PE hint being overridden by bullish agents"

patterns-established:
  - "Engine dataclasses use @dataclass (not Pydantic BaseModel) — no HTTP boundary at engine layer; lighter and appropriate"
  - "Verdict constants defined as module-level strings (VERDICT_CONFIRM/ADJUST/SKIP) — avoids magic strings in fuse() logic"

requirements-completed: [HYB-01, HYB-03, HYB-04]

# Metrics
duration: 2min
completed: 2026-04-01
---

# Phase 12 Plan 01: HybridScorer Summary

**Pure fusion engine combining quant score (60%) + agent consensus (40%) with direction-lock invariant and validator verdict application — 8 TDD tests, all GREEN**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-31T19:56:17Z
- **Completed:** 2026-04-01T19:58:24Z
- **Tasks:** 2 (RED test phase + GREEN implementation)
- **Files modified:** 2

## Accomplishments

- Implemented `HybridScorer.fuse()` as a pure static method with zero I/O — safe to call from API layer and backtest replay loops
- Enforced direction-lock invariant at the data level: `HybridResult.direction` is always set from `quant_result.direction`, validator cannot override
- Applied all three validator verdict paths: confirm (conviction unchanged), adjust (conviction reduced by adjustment_amount), skip (conviction=0, tradeable=False, tier="skip")
- All 8 TDD tests pass: formula accuracy (66.0 = 70*0.6 + 60*0.4), clamp to 100, confirm/adjust/skip paths, direction-lock, HOLD wins, full field presence

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — write failing tests** - `03aaaa7` (test)
2. **Task 2: GREEN — implement hybrid_scorer.py** - `1231a39` (feat)

**Plan metadata:** [to be added by final commit]

_Note: TDD tasks have two commits (test → feat) as required by TDD execution flow_

## Files Created/Modified

- `gods-eye/backend/app/engine/hybrid_scorer.py` — HybridScorer, HybridResult, ValidatorVerdict, AgentBreakdownEntry; pure fusion engine with 60/40 formula and direction-lock
- `gods-eye/backend/tests/test_hybrid_scorer.py` — 8 TDD tests covering all plan-spec scenarios

## Decisions Made

- `HybridScorer.fuse()` is a pure static method — no instance state, no I/O; makes it trivially testable and safe to call from any context including backtests
- Direction-lock enforced unconditionally: `quant_result.direction` always becomes `HybridResult.direction` regardless of agent consensus or validator verdict
- `conviction` field equals `hybrid_score` after confirm verdict, reduced by `adjustment_amount` after adjust, set to 0 after skip — post-validation conviction is a separate field from `hybrid_score` so both values are inspectable
- Instrument hint falls back to consensus-derived hint only when quant direction is HOLD — prevents quant PE hint being overridden by bullish agents in mixed-signal scenarios

## Deviations from Plan

None — plan executed exactly as written. All 8 tests match the plan-specified test cases and pass without modification.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `HybridScorer.fuse()` is ready for Plan 02 (API layer integration)
- `ValidatorVerdict` dataclass is ready for Plan 03 (LLM validator call)
- All exports confirmed importable: `HybridScorer`, `HybridResult`, `ValidatorVerdict`
- No blockers for Plan 02 or 03

---
*Phase: 12-hybrid-scoring-and-llm-validator*
*Completed: 2026-04-01*

## Self-Check: PASSED

- FOUND: gods-eye/backend/app/engine/hybrid_scorer.py
- FOUND: gods-eye/backend/tests/test_hybrid_scorer.py
- FOUND: .planning/phases/12-hybrid-scoring-and-llm-validator/12-01-SUMMARY.md
- FOUND commit: 03aaaa7 test(12-01): add failing tests for HybridScorer
- FOUND commit: 1231a39 feat(12-01): implement HybridScorer pure fusion engine
