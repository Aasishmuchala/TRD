---
phase: 12-hybrid-scoring-and-llm-validator
plan: "02"
subsystem: api
tags: [hybrid-scoring, llm-validator, fastapi, pydantic, direction-lock, api-endpoint]

# Dependency graph
requires:
  - phase: 12-01
    provides: HybridScorer.fuse(), HybridResult, ValidatorVerdict — consumed by route handler and LLMValidator
  - phase: 10-quant-signal-engine
    provides: QuantInputs, QuantSignalEngine.compute_quant_score() — called in route to build quant half
  - phase: 11-agent-signal-prompts
    provides: Orchestrator.run_simulation(), AgentResponse — agent outputs fed into HybridScorer.fuse()

provides:
  - LLMValidator class in hybrid_scorer.py with call_validator() async method
  - HybridSignalResponse Pydantic schema in schemas.py
  - AgentBreakdownEntrySchema Pydantic schema in schemas.py
  - POST /api/signal/hybrid/{instrument}/{date} route on protected_router

affects:
  - 13  # Risk rules phase will consume HybridSignalResponse.tradeable and conviction fields
  - 14  # Hybrid backtest will call HybridScorer.fuse() and LLMValidator in replay loop

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Placeholder verdict pattern: fuse() called twice — once with placeholder to build prompt, once with real verdict
    - Confirm-fallback pattern: any LLM exception returns confirm verdict, never 500
    - Async classmethod validator: LLMValidator.call_validator() imports LLMClient inline to avoid circular deps
    - Agent breakdown serialization: dataclass AgentBreakdownEntry converted to Pydantic AgentBreakdownEntrySchema at API boundary

key-files:
  created: []
  modified:
    - gods-eye/backend/app/engine/hybrid_scorer.py
    - gods-eye/backend/app/api/schemas.py
    - gods-eye/backend/app/api/routes.py

key-decisions:
  - "LLMValidator is an async classmethod — keeps it co-located with HybridScorer in the engine module while being the only async component in the file"
  - "Placeholder verdict pattern: preliminary HybridResult built first so LLMValidator prompt gets real hybrid_score and tier values before making the LLM call"
  - "Validator failure (any exception including RuntimeError, timeout) falls back to confirm — trade signal is never blocked by a validator timeout"
  - "AgentBreakdownEntry dataclasses converted to AgentBreakdownEntrySchema at the API boundary — engine stays dataclass, HTTP response is Pydantic"

patterns-established:
  - "Confirm-fallback wraps the entire validator call in try/except — a single guard handles all failure modes uniformly"
  - "Route builds QuantInputs with the same RSI/supertrend/VIX/momentum pattern as GET /signal/quant — one consistent data assembly path for both endpoints"

requirements-completed: [HYB-02, HYB-03, HYB-04]

# Metrics
duration: 698s
completed: 2026-04-01
---

# Phase 12 Plan 02: LLMValidator + Hybrid Signal API Summary

**LLMValidator class, HybridSignalResponse schema, and POST /api/signal/hybrid/{instrument}/{date} endpoint wiring the complete hybrid engine with single LLM validator call and confirm-fallback on failure**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-04-01
- **Tasks:** 2 (Task 1: LLMValidator + schema; Task 2: route handler)
- **Files modified:** 3

## Accomplishments

- Added `LLMValidator` class to `hybrid_scorer.py` with structured prompt template, JSON parsing, and confirm-fallback on parse error
- Added `HybridSignalResponse` and `AgentBreakdownEntrySchema` Pydantic models to `schemas.py`
- Wired `POST /api/signal/hybrid/{instrument}/{date}` on `protected_router` with full 8-step pipeline:
  1. Load OHLCV + VIX from historical_store
  2. Build QuantInputs using same RSI/supertrend/momentum pattern as GET /signal/quant
  3. Run QuantSignalEngine.compute_quant_score()
  4. Run Orchestrator.run_simulation() for agent consensus
  5. Build preliminary HybridResult with placeholder verdict (so LLM prompt has real scores)
  6. Call LLMValidator.call_validator() — single LLM call
  7. Final HybridScorer.fuse() with real verdict
  8. Serialize to HybridSignalResponse and return
- Direction lock enforced at engine layer (HybridScorer.fuse) — validator cannot flip direction
- All 8 Plan 01 tests still pass after Task 1 additions

## Task Commits

1. **Task 1: LLMValidator + HybridSignalResponse** - `a7591da` (feat)
2. **Task 2: Wire hybrid signal route** - `426191f` (feat)

## Files Created/Modified

- `gods-eye/backend/app/engine/hybrid_scorer.py` — LLMValidator class appended: prompt template, _build_quant_factors_text, _build_agent_calls_text, _parse_verdict_response, call_validator
- `gods-eye/backend/app/api/schemas.py` — AgentBreakdownEntrySchema and HybridSignalResponse added at bottom
- `gods-eye/backend/app/api/routes.py` — HybridScorer/LLMValidator/ValidatorVerdict imports added; POST /api/signal/hybrid/{instrument}/{date} handler added

## Decisions Made

- `LLMValidator` is an async classmethod — keeps it co-located with `HybridScorer` in the engine module while being the only async component in the file
- Placeholder verdict pattern: preliminary `HybridResult` built first so `LLMValidator` prompt gets real `hybrid_score` and `tier` values before making the LLM call
- Validator failure (any exception including RuntimeError, timeout) falls back to confirm — trade signal is never blocked by a validator timeout
- `AgentBreakdownEntry` dataclasses converted to `AgentBreakdownEntrySchema` at the API boundary — engine stays dataclass, HTTP response is Pydantic

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- `POST /api/signal/hybrid/{instrument}/{date}` ready for Phase 13 risk rules
- `HybridSignalResponse.tradeable` and `conviction` fields available for Phase 13 position sizing gate
- `LLMValidator.call_validator()` ready for Phase 14 hybrid backtest (replay loop)

---
*Phase: 12-hybrid-scoring-and-llm-validator*
*Completed: 2026-04-01*

## Self-Check: PASSED

- FOUND: gods-eye/backend/app/engine/hybrid_scorer.py
- FOUND: gods-eye/backend/app/api/schemas.py
- FOUND: gods-eye/backend/app/api/routes.py
- FOUND: .planning/phases/12-hybrid-scoring-and-llm-validator/12-02-SUMMARY.md
- FOUND commit: a7591da feat(12-02): add LLMValidator class and HybridSignalResponse schema
- FOUND commit: 426191f feat(12-02): wire POST /api/signal/hybrid/{instrument}/{date} route
- All 10 VALIDATOR_PROMPT_TEMPLATE interpolation fields verified present
- Route /api/signal/hybrid/{instrument}/{date} verified on protected_router
- All 8 Plan 01 tests still passing (8 passed, 0 failed)
