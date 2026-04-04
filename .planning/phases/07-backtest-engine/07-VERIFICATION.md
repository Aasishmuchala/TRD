---
phase: 07-backtest-engine
verified: 2026-03-31T00:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 07: Backtest Engine Verification Report

**Phase Goal:** Replay any date range through agents, compare predicted direction vs actual next-day move, accumulate accuracy and P&L.
**Verified:** 2026-03-31
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | BacktestEngine.run_backtest() iterates trading days with mock/LLM mode | VERIFIED | Full day-loop in `backtest_engine.py` lines 196–301; config.MOCK_MODE saved/restored via try/finally |
| 2 | Each day runs Orchestrator.run_simulation() (3-round debate) | VERIFIED | `sim_result = await self.orchestrator.run_simulation(market_input)` at line 226; `round_history` captured from result |
| 3 | Compares prediction vs actual next-day move with 0.1% threshold | VERIFIED | `_is_correct()` method lines 390–405; `_CORRECT_THRESHOLD = 0.1`; BUY family requires `> 0.1`, SELL family requires `< -0.1` |
| 4 | Per-agent accuracy and overall win rate computed | VERIFIED | `_compute_per_agent_accuracy()` lines 423–461; `overall_accuracy` computed at lines 275–277; both surfaced in `BacktestRunSummary` via `win_rate_pct` field |
| 5 | P&L computed with ATM option proxy (3x leverage) | VERIFIED | `_compute_pnl()` lines 407–421; `_OPTION_LEVERAGE = 3.0`; formula: `actual_move_pct * 3.0 * (close / 100)` |
| 6 | POST /api/backtest/run and GET /api/backtest/results/{run_id} endpoints | VERIFIED | Both routes on `protected_router`; confirmed by runtime check: `['/api/backtest/run', '/api/backtest/results/{run_id}']` |
| 7 | SQLite backtest_runs table for persistence | VERIFIED | `_init_schema()` creates table on `__init__`; confirmed table exists at `config.DATABASE_PATH`; all 10 required columns and 2 named indexes present |

**Score:** 7/7 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `gods-eye/backend/app/engine/backtest_engine.py` | BacktestEngine class with run_backtest() async method | VERIFIED | 507 lines; exports BacktestEngine, BacktestDayResult, BacktestRunResult; all methods implemented |
| `gods-eye/backend/app/api/routes.py` | POST /api/backtest/run and GET /api/backtest/results/{run_id} | VERIFIED | Endpoints at lines 913–959; backtest_engine singleton at line 50 |
| `gods-eye/backend/app/api/schemas.py` | BacktestRunRequest, BacktestRunResponse Pydantic models | VERIFIED | 4 models added under Phase 7 section (lines 159–207); BacktestRunRequest.mock_mode defaults to True |
| `gods-eye/backend/tests/test_backtest_engine.py` | Unit tests for engine logic | VERIFIED | 18 tests; all pass (confirmed by pytest run) |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| BacktestEngine.run_backtest() | HistoricalStore.get_ohlcv() | `historical_store.get_ohlcv(instrument)` | WIRED | Line 172; full dataset fetched then filtered to signal range |
| BacktestEngine._build_market_input() | Orchestrator.run_simulation() | `self.orchestrator.run_simulation(market_input)` | WIRED | MarketInput constructed at line 222; awaited at line 226 |
| BacktestEngine._compute_pnl() | next-day OHLCV close | `actual_move_pct` derived from nifty_next_close (line 219); passed to _compute_pnl() | WIRED | Line 245; result stored in BacktestDayResult.pnl_points |
| POST /api/backtest/run | BacktestEngine.run_backtest() | `result = await backtest_engine.run_backtest(...)` | WIRED | Lines 922–928; parameters forwarded from BacktestRunRequest |
| BacktestRunResponse | BacktestRunResult dataclass | `_serialize_backtest_result()` with per-day cumulative accumulation | WIRED | Lines 962–1000; dataclass fields mapped to Pydantic fields; cumulative_pnl_points computed in API layer |
| config.MOCK_MODE flag | Agents (all 6) using MockResponseGenerator | Agents check `if config.MOCK_MODE:` and call MockResponseGenerator.generate() | WIRED | Confirmed in fii_agent.py, dii_agent.py, retail_fno_agent.py, promoter_agent.py, rbi_policy_agent.py, algo_agent.py |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| BT-01 | 07-01 | System can replay a date range through agents using historical data as input | SATISFIED | run_backtest() fetches OHLCV, filters to range, iterates signal rows |
| BT-02 | 07-01 | Each backtest day runs a full 3-round simulation with historical market conditions | SATISFIED | orchestrator.run_simulation() called per day; MarketInput built from historical row |
| BT-03 | 07-01 | System compares agent prediction against actual next-day move | SATISFIED | _is_correct() with 0.1% threshold; direction_correct stored per day |
| BT-04 | 07-02 | System tracks per-agent accuracy, overall accuracy, conviction calibration | SATISFIED | _compute_per_agent_accuracy() + overall_accuracy; both in BacktestRunSummary |
| BT-05 | 07-01, 07-02 | System computes P&L assuming ATM CE/PE option strategy | SATISFIED | _compute_pnl() with 3x leverage; cumulative_pnl_points in API response |

All 5 requirements satisfied. REQUIREMENTS.md tracking table marks all BT-01 through BT-05 as complete for Phase 7.

---

## Anti-Patterns Found

No anti-patterns detected in phase files.

| File | Scan Result |
|------|-------------|
| gods-eye/backend/app/engine/backtest_engine.py | No TODO/FIXME/placeholder/stub patterns |
| gods-eye/backend/app/api/routes.py (backtest section) | No TODO/FIXME/placeholder patterns |
| gods-eye/backend/app/api/schemas.py (backtest section) | No TODO/FIXME/placeholder patterns |
| gods-eye/backend/tests/test_backtest_engine.py | No TODO/FIXME/placeholder patterns |

---

## Human Verification Required

### 1. End-to-end mock backtest via HTTP

**Test:** Start backend with `uvicorn app.main:app --reload --port 8000`, then POST to `/api/backtest/run` with a 10-day range within historical data (e.g., 2024-01-15 to 2024-01-26, mock_mode=true)
**Expected:** Response contains `summary.day_count` matching trading days in range, `summary.per_agent_accuracy` with 6 agents, `days[].direction_correct` booleans, `days[-1].cumulative_pnl_points` equal to `summary.total_pnl_points`
**Why human:** Cannot fire an authenticated HTTP request in this verification context; requires running backend + API key

### 2. GET retrieval by run_id

**Test:** Copy `run_id` from POST response, call `GET /api/backtest/results/{run_id}` with same API key
**Expected:** Returns identical data to the original POST response
**Why human:** Requires a live SQLite write from a completed backtest run to test the re-hydration path

---

## Verification Notes

**Mock mode chain confirmed:** BacktestEngine sets `config.MOCK_MODE = mock_mode` before the day loop and restores via `try/finally`. Each of the 6 agents checks `config.MOCK_MODE` at call time and branches to `MockResponseGenerator.generate()` when True. The chain is complete — no LLM API key is needed for mock backtests.

**SQLite confirmed live:** The `backtest_runs` table already exists in the database at `config.DATABASE_PATH` (`/Users/aasish/gods_eye.db`), with all 10 required columns and both named indexes (`idx_br_instrument_dates`, `idx_br_created`).

**All 3 documented commits verified:** `34fdb0d` (engine core + tests), `b7d3232` (schemas), `321c2a8` (routes) all exist in the git repository.

**Test suite:** 18/18 unit tests pass covering dataclass instantiation, `_is_correct()` semantics (including threshold boundary conditions), `_compute_pnl()` formula (BUY, SELL, HOLD, STRONG_BUY), and `_compute_consensus()` majority vote logic.

---

_Verified: 2026-03-31_
_Verifier: Claude (gsd-verifier)_
