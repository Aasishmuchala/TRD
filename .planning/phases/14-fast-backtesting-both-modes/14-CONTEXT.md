# Phase 14: Fast Backtesting Both Modes - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated

<domain>
## Phase Boundary

Rules-only backtest runs 1 year in <10 seconds. Hybrid backtest (rules + parallel agents) runs 1 month in <5 minutes. Dashboard shows both side by side with risk-adjusted metrics (Sharpe, drawdown, win/loss with position sizing).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- FBT-01: Rules-only backtest already exists from Phase 10 (quant_backtest.py). Verify it meets <10s target.
- FBT-02: Hybrid backtest = quant score + parallel agent calls + risk params per day. Rewrite backtest_engine.py to use hybrid_scorer + risk_manager.
- FBT-03: API returns both modes' results for same date range (or run separately, show side by side in dashboard)
- FBT-04: Add risk-adjusted P&L: apply position sizing (lots from RiskManager), stop loss exits, target exits. Sharpe + max drawdown already computed in frontend StatsPanel.

Key: The existing backtest_engine.py needs updating to use the new hybrid flow (quant + agents + risk) instead of the old 3-round orchestrator approach.

</decisions>

<code_context>
## Existing Code Insights

### Reusable
- app/engine/quant_backtest.py — rules-only fast loop (Phase 10)
- app/engine/backtest_engine.py — agent-based loop (needs rewrite for hybrid)
- app/engine/quant_signal_engine.py — pure quant scoring
- app/engine/hybrid_scorer.py — HybridScorer.fuse() + LLMValidator
- app/engine/risk_manager.py — RiskManager.compute()
- Frontend: StatsPanel already computes Sharpe/drawdown from days array

</code_context>

<specifics>
No specific requirements beyond success criteria.
</specifics>

<deferred>
None.
</deferred>
