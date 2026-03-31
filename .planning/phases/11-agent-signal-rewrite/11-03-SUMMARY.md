---
phase: 11-agent-signal-rewrite
plan: "03"
subsystem: api
tags: [asyncio, orchestrator, streaming, agents, parallel-dispatch]

# Dependency graph
requires:
  - phase: 11-01
    provides: Rewritten agent prompts for signal-oriented analysis
  - phase: 11-02
    provides: AlgoQuantAgent sync rewrite (pure QUANT, no LLM)

provides:
  - Single-round parallel Orchestrator.run_simulation() with asyncio.gather
  - Single-round streaming StreamingOrchestrator.stream_simulation() with asyncio.wait
  - Backward-compatible return dict shape (round2/round3=None)
  - Event sequence reduced from 3-round to 1-round (11 events total)

affects:
  - phase 12 (LLM validator layer — consumes orchestrator output)
  - phase 14 (hybrid backtest — uses orchestrator for agent dispatch)
  - WebSocket handler (streaming_orchestrator consumer)
  - API routes (orchestrator consumer)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - QUANT agent awaited inline before asyncio.gather for LLM agents
    - asyncio.wait(FIRST_COMPLETED) for streaming per-agent events as they arrive
    - _check_direction_changes kept as static stub for backward compatibility; no longer called

key-files:
  created: []
  modified:
    - gods-eye/backend/app/engine/orchestrator.py
    - gods-eye/backend/app/engine/streaming_orchestrator.py
    - gods-eye/backend/app/agents/profile_generator.py

key-decisions:
  - "Single-round design: no direction-change check, no conditional round 2/3 — all 6 agents dispatched once"
  - "QUANT agent awaited inline (not in gather) because it is synchronous/instant; keeps it separate from LLM network I/O"
  - "round2 and round3 keys set to None (not removed) to preserve backward compatibility with existing consumers"
  - "asyncio.wait(FIRST_COMPLETED) used in streaming path so agent_result events are emitted as each LLM finishes, not all at end"
  - "_stream_round removed — logic inlined in stream_simulation; _check_direction_changes kept as static stub"

patterns-established:
  - "Orchestrator pattern: QUANT first (inline await), then LLM batch via asyncio.gather"
  - "Streaming pattern: QUANT yields immediately, LLM tasks tracked in dict, asyncio.wait loop yields each on completion"

requirements-completed: [AGENT-06]

# Metrics
duration: 5min
completed: 2026-04-01
---

# Phase 11 Plan 03: Orchestrator Single-Round Parallel Dispatch Summary

**Both orchestrators collapsed from 3-round sequential loops to single-round parallel dispatch — all 6 agents fire simultaneously (QUANT inline, 5 LLM via asyncio.gather/wait), completing in under 100ms in MOCK_MODE.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-01T09:41:06Z
- **Completed:** 2026-04-01T09:46:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Orchestrator.run_simulation() collapsed from 3-round sequential loop to single _run_single_round() call using asyncio.gather for 5 LLM agents
- StreamingOrchestrator.stream_simulation() rewritten: QUANT yields first, then LLM agents dispatched in parallel with asyncio.wait(FIRST_COMPLETED) so events stream as each finishes
- Return dict shape preserved (round1=outputs, round2=None, round3=None, final_outputs, round_history, execution_time_ms, tuned_weights, feedback_active, learning_enabled)
- Event sequence reduced from up to 24 events (3 rounds x 8) to exactly 11: simulation_start, round_start, 6x agent_result, round_complete, aggregation, simulation_end
- Both orchestrators verified at 42-67ms in MOCK_MODE (well under 2s and 3s targets)

## Task Commits

1. **Task 1: Rewrite Orchestrator for single-round parallel dispatch** - `615ddf6` (feat)
2. **Task 2: Rewrite StreamingOrchestrator for single-round parallel dispatch** - `a68d10b` (feat)

## Files Created/Modified

- `gods-eye/backend/app/engine/orchestrator.py` — Replaced _run_round (3-round) with _run_single_round; asyncio.gather for LLM agents; round2/round3=None
- `gods-eye/backend/app/engine/streaming_orchestrator.py` — Replaced _stream_round with inline single-round logic; asyncio.wait for streaming; total_rounds=1
- `gods-eye/backend/app/agents/profile_generator.py` — Bug fix: guarded max_pain arithmetic against None (auto-fix, Rule 1)

## Decisions Made

- QUANT agent awaited inline (not in gather): AlgoQuantAgent is pure computation with no network I/O; keeping it separate avoids exception-handling complexity inside gather
- round2/round3 keys set to None rather than removed: any consumer doing dict.get("round2") or checking result["round2"] continues to work without KeyError
- asyncio.wait(FIRST_COMPLETED) in streaming path instead of gather: allows yielding each agent_result as it arrives, giving the WebSocket client real-time progress feedback

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed NoneType arithmetic in profile_generator.py when max_pain is None**
- **Found during:** Task 1 (Orchestrator verification)
- **Issue:** `profile_generator.py` line 209 computed `distance = spot - max_pain` without a None guard; test MarketInput omits max_pain (Optional field), causing `TypeError: unsupported operand type(s) for -: 'float' and 'NoneType'`
- **Fix:** Wrapped max_pain block in `if max_pain is not None` guard; added fallback `Max Pain: N/A` line
- **Files modified:** gods-eye/backend/app/agents/profile_generator.py
- **Verification:** Orchestrator test passed after fix (6 agents, 67ms)
- **Committed in:** 615ddf6 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug)
**Impact on plan:** Necessary correctness fix for optional field. No scope creep.

## Issues Encountered

- `python` command not found on this macOS; used `python3` for all verification. No code impact.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both orchestrators are single-round parallel — Phase 12 (LLM validator) can add a single post-aggregation call without touching dispatch logic
- Backward-compatible output shape means WebSocket handler and API routes require no changes
- MOCK_MODE wall-clock: ~65ms. Live mode wall-clock target: under 8 seconds — gated by slowest LLM agent response

---
*Phase: 11-agent-signal-rewrite*
*Completed: 2026-04-01*
