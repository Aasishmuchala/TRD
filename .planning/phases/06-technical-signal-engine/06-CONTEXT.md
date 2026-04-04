# Phase 6: Technical Signal Engine - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase)

<domain>
## Phase Boundary

RSI (14-period), VWAP deviation, Supertrend, OI change tracking, and VIX regime classification are computable for any historical date with stored data. All indicators read from the HistoricalStore (Phase 5) and produce signals usable by the backtest engine (Phase 7).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
Infrastructure phase. Key requirements:
- TECH-01: RSI 14-period for Nifty and Bank Nifty
- TECH-02: VWAP deviation as percentage from rolling reference
- TECH-03: Supertrend (ATR-based) for trend direction
- TECH-04: OI change from Dhan options chain for sentiment shift
- TECH-05: VIX regime classification (low <14, normal 14-20, elevated 20-30, high >30)

Existing signal_engine.py has basic RSI/MACD/Bollinger. Extend or create new module.
All indicators should work on historical data arrays (not just live snapshots).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- app/data/signal_engine.py — has basic RSI, MACD, Bollinger (live snapshot only)
- app/data/historical_store.py — get_ohlcv() returns date-sorted OHLCV rows
- app/agents/algo_agent.py — already uses VIX regime classification
- numpy is available

### Integration Points
- New module: app/data/technical_signals.py (or extend signal_engine.py)
- Input: OHLCV arrays from HistoricalStore
- Output: dict of signals per date for backtest engine consumption

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond ROADMAP success criteria.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
