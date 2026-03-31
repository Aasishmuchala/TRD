---
phase: 10-quantitative-signal-engine
plan: "01"
subsystem: engine
tags: [quant, signal-engine, tdd, pure-function, scoring]
dependency_graph:
  requires: []
  provides:
    - QuantSignalEngine.compute_quant_score
    - QuantInputs dataclass
    - QuantScoreResult dataclass
  affects:
    - gods-eye/backend/app/engine/quant_signal_engine.py
    - gods-eye/backend/app/engine/test_quant_signal_engine.py
tech_stack:
  added: []
  patterns:
    - Pure static method on class (no instance state)
    - dataclass for inputs and outputs (stdlib only)
    - TDD RED/GREEN cycle with pytest
key_files:
  created:
    - gods-eye/backend/app/engine/quant_signal_engine.py
    - gods-eye/backend/app/engine/test_quant_signal_engine.py
    - TRD/gods-eye/backend/app/engine/quant_signal_engine.py
    - TRD/gods-eye/backend/app/engine/test_quant_signal_engine.py
  modified: []
decisions:
  - "Bidirectional rules (fii_flow, pcr, rsi, vix, supertrend) use a single factor key — the side field (buy/sell) indicates which threshold fired; avoids double-keying and matches Plan 02's import contract"
  - "dii_absorption is buy-only and requires BOTH dii_net_cr > 0 AND fii_net_cr < 0 — confirmed correct per CONTEXT.md"
  - "factors dict built for EVERY evaluated rule (threshold_hit=False when rule did not fire) — downstream consumers can always inspect all 6 factors without KeyError"
  - "total_score = max(buy_points, sell_points) clamped to [0, 100] — mirrors plan spec exactly"
  - "Direction boundary: strictly > 50 required (50 == HOLD, 51 == tradeable) — confirms plan spec wording"
metrics:
  duration_seconds: 190
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_created: 4
  files_modified: 0
---

# Phase 10 Plan 01: QuantSignalEngine TDD Implementation Summary

**One-liner:** Pure Python rules engine mapping 7 market inputs (FII/DII flows, PCR, RSI, VIX, Supertrend) to a 0-100 directional score with per-factor breakdown via 11 scoring rules.

## What Was Built

`QuantSignalEngine.compute_quant_score` — a pure static method with zero LLM calls, zero I/O, and no app.* imports. Takes a `QuantInputs` dataclass and returns a `QuantScoreResult` with complete scoring breakdown for use by Phase 10 Plan 02 (fast backtest loop) and Phase 12 (hybrid scorer).

## Tasks Completed

| Task | Type | Commit | Result |
|------|------|--------|--------|
| Task 1 — Write failing tests (RED) | TDD RED | 12afeca | 20 tests, all fail with ImportError |
| Task 2 — Implement engine (GREEN) | TDD GREEN | 91e9ddb | 20/20 tests pass |

## Scoring Rules Implemented

| Factor | Side | Threshold | Points |
|--------|------|-----------|--------|
| fii_flow | BUY | fii_net_cr > +1000 Cr | +25 |
| dii_absorption | BUY | dii_net_cr > 0 AND fii_net_cr < 0 | +10 |
| pcr | BUY | pcr > 1.2 | +15 |
| rsi | BUY | rsi < 30 (oversold) | +20 |
| vix | BUY | vix < 14 AND vix < vix_5d_avg | +10 |
| supertrend | BUY | supertrend == "bullish" | +10 |
| fii_flow | SELL | fii_net_cr < -1000 Cr | +25 |
| pcr | SELL | pcr < 0.7 | +15 |
| rsi | SELL | rsi > 70 (overbought) | +20 |
| vix | SELL | vix > 20 AND vix > vix_5d_avg | +10 |
| supertrend | SELL | supertrend == "bearish" | +10 |

**BUY max: 90 pts | SELL max: 80 pts**

## Interface Contract (for Plan 02)

```python
from app.engine.quant_signal_engine import QuantInputs, QuantSignalEngine, QuantScoreResult

inp = QuantInputs(
    fii_net_cr=2000.0, dii_net_cr=500.0, pcr=1.5,
    rsi=25.0, vix=12.0, vix_5d_avg=13.0, supertrend="bullish"
)
result = QuantSignalEngine.compute_quant_score(inp, instrument="NIFTY")
# result.direction      → "BUY"
# result.total_score    → 80
# result.tier           → "strong"
# result.instrument_hint → "NIFTY_CE"
# result.factors["rsi"] → {"points": 20, "threshold_hit": True, "side": "buy"}
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `gods-eye/backend/app/engine/quant_signal_engine.py` — FOUND
- [x] `gods-eye/backend/app/engine/test_quant_signal_engine.py` — FOUND
- [x] `TRD/gods-eye/backend/app/engine/quant_signal_engine.py` — FOUND (working copy)
- [x] `TRD/gods-eye/backend/app/engine/test_quant_signal_engine.py` — FOUND (working copy)
- [x] Commit 12afeca (RED) — FOUND
- [x] Commit 91e9ddb (GREEN) — FOUND
- [x] 20/20 pytest tests pass
- [x] Zero app.* imports in quant_signal_engine.py

## Self-Check: PASSED
