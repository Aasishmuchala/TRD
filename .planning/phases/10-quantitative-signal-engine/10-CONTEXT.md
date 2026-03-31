# Phase 10: Quantitative Signal Engine - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase)

<domain>
## Phase Boundary

A deterministic rules engine that computes a 0-100 directional score from real market data (FII/DII flows, PCR, RSI-14, VIX level+direction, Supertrend) with zero LLM calls. Can backtest 1 year of data in under 10 seconds.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
Infrastructure phase. Key requirements:
- QUANT-01: Score 0-100 from FII/DII flows, PCR, RSI-14, VIX, Supertrend
- QUANT-02: Each factor has defined thresholds and point values
- QUANT-03: Score > 50 = tradeable signal, direction from higher-scoring side
- QUANT-04: Zero LLM calls, pure computation
- QUANT-05: 1 year backtest in <10 seconds

Signal scoring rules (from project discussion):

BUY signals (max 90 points):
- FII net today > +1000 Cr → +25
- DII net > FII outflow (absorption) → +10
- PCR > 1.2 (put heavy, contrarian bullish) → +15
- RSI < 30 (oversold) → +20
- VIX < 14 and falling → +10
- Supertrend bullish → +10

SELL signals (max 80 points):
- FII net today < -1000 Cr → +25
- PCR < 0.7 (call heavy, contrarian bearish) → +15
- RSI > 70 (overbought) → +20
- VIX > 20 and rising → +10
- Supertrend bearish → +10

Score > 50 = trade. Direction = whichever side higher.

New module: app/engine/quant_signal_engine.py
New API endpoint: GET /api/signal/quant/{instrument}/{date}
New fast backtest: POST /api/backtest/quant-run (rules only, no LLM)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- app/data/technical_signals.py — RSI, Supertrend, VIX regime already computed
- app/data/historical_store.py — OHLCV + OI snapshots stored
- app/engine/backtest_engine.py — existing backtest loop (can fork for quant-only)
- app/engine/signal_scorer.py — existing 60/40 scorer (will be replaced by hybrid in Phase 12)

### Integration Points
- New: app/engine/quant_signal_engine.py
- New API endpoints on protected_router
- Reads from HistoricalStore + TechnicalSignals (existing)

</code_context>

<specifics>
## Specific Ideas

- For backtesting, FII/DII flows need to be derived from price momentum (same as backtest_engine does)
- VIX "direction" = compare today's VIX to 5-day average
- The quant engine should be a pure function: input data → output score (no side effects)

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
