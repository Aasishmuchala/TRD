---
phase: 11-agent-signal-rewrite
plan: 02
subsystem: agents
tags: [quant, signal-engine, algo-agent, deterministic, fii-flow, pcr, rsi, vix]

# Dependency graph
requires:
  - phase: 10-quant-engine
    provides: QuantSignalEngine, QuantInputs, QuantScoreResult — the deterministic scoring rules engine
provides:
  - AlgoQuantAgent backed entirely by QuantSignalEngine — no LLM, no custom indicator math
  - USD-to-crore conversion constant at agent boundary
  - supertrend inference from RSI (RSI > 50 = bearish, else bullish) as fallback for missing field
affects:
  - 11-agent-signal-rewrite (other agent rewrites in this phase)
  - 12-llm-validator (validator receives AgentResponse from this agent)
  - 14-hybrid-backtest (uses AlgoQuantAgent in hybrid scoring loop)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Agent delegates entirely to engine: analyze() builds inputs struct, calls engine, maps result to AgentResponse"
    - "Unit conversion at agent boundary: USD millions -> INR crores with _USD_M_TO_CR=8.35 constant"
    - "Missing-field fallback pattern: vix_5d_avg=spot_vix, supertrend inferred from RSI threshold"

key-files:
  created: []
  modified:
    - gods-eye/backend/app/agents/algo_agent.py
    - TRD/gods-eye/backend/app/agents/algo_agent.py

key-decisions:
  - "supertrend inferred from RSI: RSI > 50 = bearish, else bullish — conservative fallback matching Phase 10 engine intent"
  - "vix_5d_avg falls back to spot VIX — no trend detection, prevents false VIX signals without historical data"
  - "conviction = QuantScoreResult.total_score (int cast to float, 0-100) — direct engine output, no rescaling"
  - "key_triggers capped at 5 items — avoids verbose AgentResponse payloads"

patterns-established:
  - "Pure engine delegation: agent analyze() is ~30 lines; all math lives in QuantSignalEngine"
  - "Both path copies kept in sync: gods-eye/backend and TRD/gods-eye/backend written simultaneously"

requirements-completed: [AGENT-05]

# Metrics
duration: 2min
completed: 2026-03-31
---

# Phase 11 Plan 02: Algo Agent QuantSignalEngine Rewrite Summary

**AlgoQuantAgent.analyze() replaced with single QuantSignalEngine.compute_quant_score() delegation — ~170 lines of hand-rolled RSI/BB/PCR/MACD math removed, deterministic engine-backed signal in <1ms**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-31T19:23:35Z
- **Completed:** 2026-03-31T19:25:10Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Removed all custom indicator computation: `_compute_rsi`, `_rsi_to_signal`, `_analyze_pcr`, `_compute_bb_position`, `_composite_to_direction`, `_build_interaction_effects`, `_build_reasoning` — all deleted
- `analyze()` shrunk from ~245 lines to ~90 lines; core logic is ~30 lines of QuantInputs construction + engine call
- BUY signal verified: FII +1500 USD-M + RSI 28 + PCR 1.3 → BUY conviction=70, elapsed=0.7ms
- SELL signal verified: FII -1500 USD-M + RSI 75 + PCR 0.65 + VIX 22 → SELL conviction=70
- Both path copies (`gods-eye/backend` and `TRD/gods-eye/backend`) updated identically

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace AlgoQuantAgent with QuantSignalEngine delegation** - `9100c78` (feat)

## Files Created/Modified
- `gods-eye/backend/app/agents/algo_agent.py` - Rewritten: imports QuantSignalEngine/QuantInputs, delegates analyze() to engine
- `TRD/gods-eye/backend/app/agents/algo_agent.py` - Mirror copy, identical content

## Decisions Made
- `supertrend` is not in `MarketInput` — inferred from RSI: `RSI > 50` = `"bearish"`, else `"bullish"`. Conservative proxy matching the spirit of the Phase 10 engine rule.
- `vix_5d_avg` is not in `MarketInput` — falls back to `india_vix` (spot VIX). This disables VIX trend detection but prevents false signals from missing data.
- `conviction = float(result.total_score)` — direct mapping from engine output, no rescaling. Score of 70 means 4 buy factors fired (FII + PCR + RSI + supertrend = 25+15+20+10).
- Both file paths written because the repo has two copies of the backend (`gods-eye/backend/` and `TRD/gods-eye/backend/`).

## Deviations from Plan

None — plan executed exactly as written. New file content matched the plan's specified implementation verbatim.

## Issues Encountered
- `python` command not found on this system — used `python3` for verification. Not a code issue.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- AlgoQuantAgent now produces deterministic signals consistent with Phase 10 quant backtest
- Ready for Phase 11 remaining agents (FII agent, DII agent, Retail agent etc.) to be similarly rewritten
- Phase 12 LLM validator can receive clean, fast AgentResponse from this agent without LLM latency

---
*Phase: 11-agent-signal-rewrite*
*Completed: 2026-03-31*
