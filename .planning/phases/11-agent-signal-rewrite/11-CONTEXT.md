# Phase 11: Agent Signal Rewrite - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated

<domain>
## Phase Boundary

All 6 agent prompts rewritten to produce directional trading signals (not just qualitative commentary). FII agent focuses on flows + forex, DII on SIP absorption, Retail on PCR/OI contrarian, Algo is pure quant (no LLM). All agents run in parallel, single round, ~5 seconds total.

</domain>

<decisions>
## Implementation Decisions

### Agent Rewrites
- AGENT-01: All prompts must end with a clear BUY/SELL/HOLD + conviction + 2-sentence rationale
- AGENT-02: FII agent prompt: "Given FII net flow of X, USD/INR at Y, DXY at Z — are FIIs likely to buy or sell tomorrow?"
- AGENT-03: DII agent prompt: "Given SIP inflows of X and FII outflow of Y — can DIIs absorb the selling?"
- AGENT-04: Retail F&O agent prompt: "PCR is X, max pain at Y, OI buildup at Z — what is retail positioning telling us?"
- AGENT-05: Algo agent becomes PURE QUANT — uses QuantSignalEngine from Phase 10, no LLM call
- AGENT-06: All 5 LLM agents dispatched with asyncio.gather, Algo computed inline

### Prompt Design Principles
- Short, focused prompts (not 500-word essays about being a DII manager)
- Direct question → direct answer (JSON with direction + conviction + reasoning)
- Each agent sees ONLY the data relevant to their expertise
- No "interaction rounds" — single pass, parallel

</decisions>

<code_context>
## Existing Code Insights

### Files to Modify
- app/agents/fii_agent.py — rewrite prompt, keep structure
- app/agents/dii_agent.py — rewrite prompt
- app/agents/retail_fno_agent.py — rewrite prompt
- app/agents/promoter_agent.py — rewrite prompt
- app/agents/rbi_policy_agent.py — rewrite prompt
- app/agents/algo_agent.py — replace LLM with QuantSignalEngine

### Reusable
- app/agents/base_agent.py — BaseAgent class, _parse_response, _consensus_direction
- app/engine/quant_signal_engine.py — QuantSignalEngine (Phase 10)
- app/auth/llm_client.py — LLM client for the 5 LLM agents

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond success criteria.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
