# Phase 7: Backtest Engine - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase)

<domain>
## Phase Boundary

System can replay any date range through the 6-agent simulation using historical data as input. Each backtest day runs a full 3-round simulation, compares predicted direction against actual next-day move, tracks per-agent and overall accuracy, and computes simulated P&L using a simple ATM option strategy.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- BT-01: Replay date range — iterate trading days, build MarketInput from HistoricalStore data for each day
- BT-02: Each day runs full 3-round simulation (use existing Orchestrator, not streaming)
- BT-03: Compare prediction vs actual next-day move direction (up/down/flat threshold ~0.1%)
- BT-04: Track per-agent accuracy, overall accuracy, conviction calibration
- BT-05: P&L: BUY signal → buy ATM CE, SELL → buy ATM PE, HOLD → skip. Use next-day Nifty/BankNifty % move as proxy for option P&L.

Key consideration from STATE.md blockers: "Backtest replays full 3-round LLM simulation per day — date ranges over ~30 days may be slow or costly; may need batching or a lighter replay mode."

Solution: Support both modes:
1. Full LLM mode (real agent calls — slow, costly, accurate)
2. Mock mode (uses mock_responses.py — fast, free, for testing the engine)

Default to mock mode for backtests unless user explicitly requests LLM mode.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- app/engine/orchestrator.py — Orchestrator.run_simulation(market_data) returns SimulationResult
- app/agents/mock_responses.py — scenario-aware mock data (fast, no LLM calls)
- app/data/historical_store.py — get_ohlcv() for historical data
- app/data/technical_signals.py — compute_signals_for_date()
- app/api/schemas.py — MarketInput, SimulationResult pydantic models

### Integration Points
- New module: app/engine/backtest_engine.py
- New API endpoints: POST /api/backtest/run, GET /api/backtest/results/{id}
- Uses Orchestrator for each simulated day
- Stores results in SQLite (new backtest_results table)

</code_context>

<specifics>
## Specific Ideas

- Each backtest day: build MarketInput from historical OHLCV + VIX + technical signals → run simulation → store result with actual next-day move
- "Actual move" = (next_day_close - current_day_close) / current_day_close * 100
- Direction correct if: prediction BUY and actual > 0.1%, or SELL and actual < -0.1%
- P&L proxy: conviction% * actual_move% (scaled to represent option leverage ~3-5x)
- Store all backtest runs with ID for retrieval by dashboard (Phase 9)

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
