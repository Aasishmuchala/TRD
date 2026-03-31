# Phase 12: Hybrid Scoring and LLM Validator - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated

<domain>
## Phase Boundary

Final signal = quant score (60%) + agent consensus score (40%). A single LLM validator call reviews the combined signal: confirm, adjust conviction, or skip — with plain-language explanation. Validator cannot flip direction.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- HYB-01: hybrid_score = quant_score * 0.60 + agent_consensus_score * 0.40, both visible
- HYB-02: Validator is 1 LLM call with a short prompt: "Quant says X, agents say Y — confirm/adjust/skip?"
- HYB-03: Validator can only: confirm (pass through), reduce conviction (e.g., 70→55), or skip (no trade). Cannot flip BUY→SELL
- HYB-04: Output dataclass: direction, hybrid_score, quant_breakdown, agent_breakdown, validator_verdict, validator_reasoning, instrument_hint

New module: app/engine/hybrid_scorer.py
New API: POST /api/signal/hybrid/{instrument}/{date}
Integrates: QuantSignalEngine (Phase 10) + Orchestrator agent consensus (Phase 11)

</decisions>

<code_context>
## Existing Code Insights

### Reusable
- app/engine/quant_signal_engine.py — QuantSignalEngine.compute_quant_score()
- app/engine/orchestrator.py — Orchestrator.run_simulation() returns agent consensus
- app/auth/llm_client.py — LLM client for validator call
- app/engine/signal_scorer.py — existing 60/40 scorer (will be replaced by this)

</code_context>

<specifics>
No specific requirements beyond success criteria.
</specifics>

<deferred>
None.
</deferred>
