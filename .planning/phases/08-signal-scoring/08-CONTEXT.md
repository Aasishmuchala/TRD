# Phase 8: Signal Scoring - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase)

<domain>
## Phase Boundary

System produces a combined 0-100 score merging agent sentiment conviction with technical signal alignment. Scores map to strong (>70), moderate (50-70), or skip (<50) tiers. Output includes direction, strength, contributing factors, and suggested instrument.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- SIG-01: Combined score 0-100 from sentiment + technicals
- SIG-02: Tier mapping: >70 strong, 50-70 moderate, <50 skip
- SIG-03: Output includes direction, strength, factors, suggested instrument (Nifty CE/PE or BankNifty CE/PE)

Scoring formula:
- Agent sentiment component (60% weight): conviction% normalized to 0-100
- Technical alignment component (40% weight): how many technicals agree with agent direction
  - RSI alignment: RSI < 30 supports BUY, > 70 supports SELL
  - Supertrend alignment: bullish supports BUY, bearish supports SELL
  - VIX regime: low supports BUY (complacency risk), high supports SELL (fear)
  - OI sentiment: bullish supports BUY, bearish supports SELL

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- app/engine/backtest_engine.py — BacktestDayResult has consensus_direction + consensus_conviction
- app/data/technical_signals.py — TechnicalSignals with RSI, VWAP, Supertrend, VIX
- app/data/historical_store.py — OI snapshots

### Integration Points
- New module: app/engine/signal_scorer.py
- Integrate into backtest_engine.py (add signal_score to each day result)
- Integrate into live simulate endpoint (add signal_score to response)

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond ROADMAP success criteria.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
