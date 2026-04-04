# Phase 13: Risk Management Rules - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase)

<domain>
## Phase Boundary

Position sizing, daily max-loss guard, VIX-scaled stop loss, and 1.5x target exit — all applied after signal generation. Pure rules, no LLM.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- RISK-01: Max loss per day = 5000 pts default (configurable). Once hit, no new signals for the day.
- RISK-02: Position sizing: score > 70 (strong) = 2 lots, 50-70 (moderate) = 1 lot, < 50 = skip
- RISK-03: Stop loss = VIX * multiplier. VIX 14 → ~70pt stop. VIX 25 → ~125pt stop. Formula: stop_points = VIX * 5
- RISK-04: Target = stop_points * 1.5 (risk:reward = 1:1.5)

New module: app/engine/risk_manager.py (pure, no I/O)
Integrates into hybrid signal output and backtest P&L calculation.

</decisions>

<code_context>
## Existing Code Insights

### Reusable
- app/engine/hybrid_scorer.py — HybridResult has direction, hybrid_score, tier
- app/engine/backtest_engine.py — _compute_pnl() uses flat 3x leverage (will be replaced)
- app/config.py — add RISK_MAX_DAILY_LOSS, RISK_VIX_STOP_MULTIPLIER

</code_context>

<specifics>
No specific requirements beyond success criteria.
</specifics>

<deferred>
None.
</deferred>
