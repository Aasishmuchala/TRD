---
phase: 11-agent-signal-rewrite
plan: 01
subsystem: api
tags: [llm, agents, prompt-engineering, fii, dii, retail-fno, promoter, rbi, signal]

# Dependency graph
requires:
  - phase: 10-quant-engine
    provides: MarketInput schema with all fields used in prompts (fii_flow_5d, dii_flow_5d, usd_inr, dxy, pcr_index, max_pain, dte, india_vix, context)
provides:
  - FII agent _build_prompt: single-pass directional prompt with USD/INR + DXY interpolated
  - DII agent _build_prompt: SIP absorption vs FII outflow framing
  - Retail F&O agent _build_prompt: contrarian PCR + max pain distance signal
  - Promoter agent _build_prompt: FII selling + VIX support/distribution signal
  - RBI agent _build_prompt: rupee/DXY rate-cut-bullish interpretation
affects: [12-validator-layer, 14-hybrid-backtest]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-pass agent prompt design: one focused directional question, JSON-only response, no round/other-agent context"
    - "Contrarian signal framing for retail F&O: PCR extremes as fade signals, not trend-following"
    - "Forex-gated conviction: RBI and FII prompts gate direction on USD/INR and DXY thresholds"

key-files:
  created: []
  modified:
    - gods-eye/backend/app/agents/fii_agent.py
    - gods-eye/backend/app/agents/dii_agent.py
    - gods-eye/backend/app/agents/retail_fno_agent.py
    - gods-eye/backend/app/agents/promoter_agent.py
    - gods-eye/backend/app/agents/rbi_policy_agent.py

key-decisions:
  - "New prompts ignore round_num and other_context parameters entirely — single-pass design means these are always 1 and empty; the parameters are kept in the signature for interface compatibility"
  - "Retail F&O prompt computes max_pain distance inline (abs diff + above/below label) so the LLM sees a concrete number rather than raw spot and max_pain to compare"
  - "All prompts cap at ~150 words and under 1300 characters — verified by assertion len(p) < 1500 in plan tests"
  - "Decision rules are written into the prompt body as explicit IF→THEN logic so the LLM has a concrete decision tree, not just a role persona"

patterns-established:
  - "Single-pass prompt pattern: short framing sentence + MARKET DATA block + DECISION RULES + JSON-only response block"
  - "No round_num or other_context interpolation in Phase 11+ prompts — kept in signature for backward compatibility only"

requirements-completed: [AGENT-01, AGENT-02, AGENT-03, AGENT-04]

# Metrics
duration: 15min
completed: 2026-03-31
---

# Phase 11 Plan 01: Agent Signal Rewrite Summary

**Five LLM agent prompts rewritten from 300-500-word persona essays to ~150-word single-pass directional signal prompts with explicit IF/THEN rules and JSON-only output**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-31T19:23:37Z
- **Completed:** 2026-03-31T19:38:31Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- FII agent: focused on USD/INR + DXY gating with 5-day flow trend, under 1100 chars
- DII agent: explicit absorption-vs-overwhelm framing with SIP floor as conviction modifier (not direction modifier)
- Retail F&O agent: contrarian PCR threshold rules (>1.4 STRONG_BUY through <0.6 STRONG_SELL), max pain distance computed inline
- Promoter agent: FII selling + VIX as proxies for promoter support/distribution behavior
- RBI agent: USD/INR and DXY thresholds for dovish/hawkish bias, conviction reduction for budget/election context
- All 5 prompts pass `len(p) < 1500` assertion and produce `"direction"` JSON key on import check

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite FII and DII agent prompts** - `75ae93c` (feat)
2. **Task 2: Rewrite Retail F&O, Promoter, and RBI agent prompts** - `14e48e1` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `gods-eye/backend/app/agents/fii_agent.py` - _build_prompt replaced: USD/INR + DXY + 5-day flow → single-pass directional question
- `gods-eye/backend/app/agents/dii_agent.py` - _build_prompt replaced: DII vs FII flow magnitude absorption framing
- `gods-eye/backend/app/agents/retail_fno_agent.py` - _build_prompt replaced: contrarian PCR thresholds + max pain distance calculation
- `gods-eye/backend/app/agents/promoter_agent.py` - _build_prompt replaced: FII selling + VIX support signal
- `gods-eye/backend/app/agents/rbi_policy_agent.py` - _build_prompt replaced: rupee/DXY constrained rate-cut signal

## Decisions Made

- New prompts ignore `round_num` and `other_context` parameters entirely — single-pass design means these are always 1 and empty; the parameters are kept in the signature for interface compatibility with the existing `analyze()` caller.
- Retail F&O max pain distance computed inline in Python before string interpolation (`abs(diff):.0f pts above/below`) so the LLM receives a concrete comparison rather than two raw numbers.
- Decision rules written as explicit IF→THEN logic in each prompt body — gives the LLM a concrete decision tree rather than a role description it must reason about implicitly.
- All prompts verified to be under 1500 characters (FII: 1016, DII: 1023, Retail: 1200, Promoter: 1122, RBI: 1193).

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — all 5 imports and prompt-build assertions passed on first run.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 5 LLM agents have single-pass signal prompts ready for Phase 11 parallel dispatch (all agents fired simultaneously in one round)
- Phase 12 (LLM validator) can now call any agent and receive a clean JSON block with `direction/conviction/key_triggers/reasoning` — no extra fields to strip
- No blockers — all agent `_parse_response`, `_consensus_direction`, `_fallback_response`, and `_call_llm` methods are unchanged and functional

---
*Phase: 11-agent-signal-rewrite*
*Completed: 2026-03-31*
