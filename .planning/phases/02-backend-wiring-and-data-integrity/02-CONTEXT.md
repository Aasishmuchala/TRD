# Phase 2: Backend Wiring and Data Integrity - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Learned skills actively reach agent prompts during simulation, SkillStore writes succeed under container non-root users, and users always know whether market data is live or fallback. Agent interaction_effects fields are populated with real amplifies/dampened_by data.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key areas:
- BACK-01: Wire skill injection into agent prompts via ProfileGenerator (framework exists at app/learning/skill_store.py)
- BACK-02: Make SkillStore path configurable via env var GODS_EYE_LEARNING_SKILL_DIR
- BACK-03: Add data freshness indicator when NSE falls back to mock data (visible in API response)
- BACK-04: Populate interaction_effects in agent responses (amplifies/dampened_by)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- app/learning/skill_store.py — SkillStore with build_skill_context() method
- app/engine/orchestrator.py — ProfileGenerator builds enriched context
- app/data/market_data.py — NSE fetcher with fallback mock data
- app/agents/base_agent.py — AgentResponse includes interaction_effects field

### Established Patterns
- FastAPI async endpoints
- Config via app/config.py module-level singleton
- httpx for external API calls
- Pydantic schemas at app/api/schemas.py

### Integration Points
- ProfileGenerator.build_context() — where skill context should be injected
- MarketDataFetcher — where fallback detection should add freshness metadata
- Agent analyze() methods — where interaction_effects should be populated

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
