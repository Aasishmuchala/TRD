---
phase: 06-technical-signal-engine
plan: 01
subsystem: backend/data
tags: [technical-indicators, rsi, vwap, supertrend, vix, numpy, tdd]
dependency_graph:
  requires:
    - gods-eye/backend/app/data/historical_store.py   # get_ohlcv() row format
  provides:
    - gods-eye/backend/app/data/technical_signals.py  # TechnicalSignals class + singleton
  affects:
    - Phase 7 backtest engine (primary consumer)
    - Plan 06-02 signals API endpoint
tech_stack:
  added: []
  patterns:
    - Wilder EMA smoothing for RSI (seed=simple mean, then rolling)
    - ATR-based Supertrend with final_upper/final_lower band persistence
    - Date-string slice on List[Dict] for future-data leakage prevention
    - TDD: RED commit → GREEN commit pattern
key_files:
  created:
    - gods-eye/backend/app/data/technical_signals.py
    - TRD/gods-eye/backend/app/data/technical_signals.py
    - gods-eye/backend/app/data/test_technical_signals.py
  modified: []
decisions:
  - "technical_signals.py is a separate module from signal_engine.py — the existing module uses low_fear/high_fear labels for live simulation; new module uses low/normal/elevated/high for historical/backtest use. They coexist."
  - "compute_vwap_deviation falls back to arithmetic mean when all volumes are zero (returns 0.0 since close==vwap in single-row case); this avoids ZeroDivisionError without masking real data"
  - "classify_vix_regime raises ValueError on negative VIX (defensive: real VIX cannot be negative; makes bad data fail loudly)"
  - "compute_signals_for_date slices rows using string comparison (date format YYYY-MM-DD sorts correctly lexicographically)"
metrics:
  duration: "2 min"
  completed_date: "2026-03-31"
  tasks_completed: 1
  files_created: 3
  files_modified: 0
requirements_satisfied: [TECH-01, TECH-02, TECH-03, TECH-05]
---

# Phase 06 Plan 01: Technical Signals Module Summary

**One-liner:** Pure-numpy TechnicalSignals class with Wilder-smoothed RSI-14, VWAP deviation, ATR-10 Supertrend, and 4-tier VIX regime classifier — zero I/O, ready for Phase 7 backtest replay.

## What Was Built

`gods-eye/backend/app/data/technical_signals.py` — a pure-computation module with no async, no I/O, and no external data fetching. Accepts `List[Dict]` rows from `HistoricalStore.get_ohlcv()` and returns floating-point signals for any historical date slice.

### Methods

| Method | Input | Output | Notes |
|--------|-------|--------|-------|
| `compute_rsi(closes, period=14)` | `List[float]` | `float 0-100` | Returns 50.0 when `len < period+1`; Wilder EMA smoothing |
| `compute_vwap_deviation(rows)` | `List[Dict]` | `float` | `(close_last - vwap) / vwap * 100`; 0.0 on zero volume |
| `compute_supertrend(rows, period=10, multiplier=3.0)` | `List[Dict]` | `"bullish"\|"bearish"` | Returns "bullish" for `<11 rows`; never None |
| `classify_vix_regime(india_vix)` | `float` | `"low"\|"normal"\|"elevated"\|"high"` | Raises ValueError on negative |
| `compute_signals_for_date(rows, date_str)` | `List[Dict], str` | `Dict` | Slices to `date <= date_str`; prevents future data leakage |

### Singleton

```python
from app.data.technical_signals import TechnicalSignals, technical_signals
```

Follows the `dhan_client` / `historical_store` singleton pattern used throughout the codebase.

## Test Coverage

18 tests, all passing. Covers:
- RSI edge cases: all-gain (100.0), all-loss (0.0), insufficient data (50.0), exactly period+1
- VWAP: zero volume, empty rows, single row
- Supertrend: short series default, full series valid enum
- VIX regime: all four tier boundaries (exact: 13.9, 14.0, 19.99, 20.0, 29.99, 30.0), negative raises
- compute_signals_for_date: correct keys, future leakage prevention, no-data error

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `gods-eye/backend/app/data/technical_signals.py` exists
- [x] `TRD/gods-eye/backend/app/data/technical_signals.py` exists (second path)
- [x] `TechnicalSignals` and `technical_signals` importable
- [x] All 18 pytest assertions pass
- [x] All plan inline assertions pass (`All assertions passed.`)
- [x] Commits: `5524aad` (test RED), `d7e1658` (feat GREEN)
