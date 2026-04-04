---
phase: 14-fast-backtesting-both-modes
plan: "02"
subsystem: hybrid-backtest-engine
tags: [backtest, hybrid, orchestrator, risk-manager, llm-validator, api]
dependency_graph:
  requires:
    - app/engine/hybrid_scorer.py (HybridScorer, LLMValidator, ValidatorVerdict)
    - app/engine/quant_signal_engine.py (QuantSignalEngine, QuantInputs)
    - app/engine/orchestrator.py (Orchestrator.run_simulation — Phase 11 parallel)
    - app/engine/risk_manager.py (RiskManager.compute)
    - app/data/historical_store.py (get_ohlcv, get_vix_closes)
    - app/data/technical_signals.py (TechnicalSignals)
    - app/api/schemas.py (MarketInput, existing schemas)
  provides:
    - HybridBacktestEngine.run_hybrid_backtest
    - POST /api/backtest/hybrid-run
    - HybridBacktestRunResult, HybridBacktestDayResult
    - HybridBacktestRunResponse, HybridBacktestRequest, HybridBacktestDaySchema
  affects:
    - gods-eye/backend/app/api/routes.py (new protected route)
    - gods-eye/backend/app/api/schemas.py (3 new models)
tech_stack:
  added: []
  patterns:
    - orchestrator-singleton: Orchestrator instantiated once in HybridBacktestEngine.__init__ to reuse connection pools across all backtest days
    - placeholder-then-real-verdict: HybridScorer.fuse() called twice per day — placeholder for LLM prompt build, then real verdict for final result
    - try-except-fallback: Both agent simulation and LLM validator wrapped in try/except with confirm/empty fallback — backtest never crashes on LLM failure
    - risk-adjusted-pnl: pnl = actual_move_pts * lots * NIFTY_LOT(25) — weak signals (tier=skip, direction=HOLD) produce 0.0
key_files:
  created:
    - gods-eye/backend/app/engine/hybrid_backtest.py
  modified:
    - gods-eye/backend/app/api/schemas.py
    - gods-eye/backend/app/api/routes.py
decisions:
  - "Orchestrator singleton in __init__: reuse connection pools across 22 days instead of instantiating per-day"
  - "try/except around both orchestrator.run_simulation and LLMValidator.call_validator: backtest completes even under partial LLM failures"
  - "Sharpe ratio uses sample stdev (n-1) over tradeable days — matches Phase 9 convention for small backtests"
  - "Max drawdown computed on peak-to-trough of cumulative P&L curve, returned as 0.0 when peak <= 0"
  - "Win/loss ratio: avg winning P&L / abs(avg losing P&L) — None when either wins or losses are empty"
metrics:
  duration_seconds: 582
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 14 Plan 02: Hybrid Backtest Engine Summary

## One-liner

Full hybrid per-day pipeline (quant + 6 parallel agents + HybridScorer + LLMValidator + RiskManager) wired to POST /api/backtest/hybrid-run with risk-adjusted P&L and Sharpe/drawdown/win-loss metrics.

## What Was Built

### Task 1: hybrid_backtest.py

New engine file at `gods-eye/backend/app/engine/hybrid_backtest.py`.

Per-day loop logic:
1. Loads all OHLCV + VIX once (no date filter for full lookback history)
2. For each date in range: computes RSI, Supertrend, VIX, vix_5d_avg, momentum_5d
3. Builds QuantInputs (same proxy formula as quant_backtest.py)
4. Calls QuantSignalEngine.compute_quant_score()
5. Builds MarketInput and calls Orchestrator.run_simulation() — 6 parallel agents (Phase 11)
6. Placeholder fuse + LLMValidator.call_validator() + final fuse (two-pass pattern from Phase 12)
7. RiskManager.compute() for lots/stop/target — weak signals get lots=0, pnl=0
8. Appends HybridBacktestDayResult

Aggregate metrics: win_rate_pct, total_pnl_points, sharpe_ratio (sample stdev), max_drawdown_pct, win_loss_ratio.

Module-level singleton: `hybrid_backtest_engine = HybridBacktestEngine()`

### Task 2: schemas.py + routes.py

**schemas.py additions (Phase 14 section):**
- `HybridBacktestDaySchema` — per-day response model
- `HybridBacktestRequest` — instrument, from_date, to_date
- `HybridBacktestRunResponse` — aggregate + days list with sharpe, drawdown, win_loss

**routes.py additions:**
- Import: `hybrid_backtest_engine` + 3 new schema classes
- `POST /api/backtest/hybrid-run` registered on `protected_router`
- Validates instrument, handles ValueError (400) and generic Exception (500)
- Serializes HybridBacktestDayResult → HybridBacktestDaySchema for each day

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files exist:

- [x] `gods-eye/backend/app/engine/hybrid_backtest.py`
- [x] `gods-eye/backend/app/api/schemas.py` (modified)
- [x] `gods-eye/backend/app/api/routes.py` (modified)

### Commits exist:

- [x] a6d0f10 — feat(14-02): create HybridBacktestEngine with full per-day pipeline
- [x] 039c45b — feat(14-02): add HybridBacktestRunResponse schema and POST /api/backtest/hybrid-run route

### Verification results:

- [x] `python3 -c "from app.engine.hybrid_backtest import HybridBacktestEngine, hybrid_backtest_engine, HybridBacktestRunResult, HybridBacktestDayResult; print('import OK')"` → import OK
- [x] `python3 -c "from app.api.schemas import HybridBacktestRunResponse, HybridBacktestRequest, HybridBacktestDaySchema; from app.api.routes import protected_router; routes = [r.path for r in protected_router.routes]; assert any('hybrid-run' in r for r in routes); print('OK')"` → OK — route and schemas present
- [x] Schema instantiation test (empty response) → NIFTY instrument, no crash

## Self-Check: PASSED
