# Plan: Backtest Latency Fix

## Problem

The backtest uses **T's close as the entry price**, but in reality:
- Signal runs after market close on day T (3:30 PM IST)
- Trade enters at **T+1's open** (9:15 AM IST)
- Trade exits at **T+1's close** (3:30 PM IST)

The gap between T's close and T+1's open is unaccounted for. On trending days
this is 0.3–0.8%. On overnight-news days it can be 1–2%. This inflates P&L on
BUY gap-up days and understates losses on BUY gap-down days.

## Files to Modify

- `backend/app/engine/backtest_engine.py` — main fix
- `backend/app/api/schemas.py` — add `entry_price` field to response
- `backend/app/api/routes.py` — serialize new field
- `frontend/src/components/BacktestSummary.jsx` — display avg open gap stat

## Tasks

### Task 1 — Pass next_row to P&L and stop loss

In `backtest_engine.py`, find the per-day loop (around line 255–320).

Currently:
```python
market_input = self._build_market_input(row, vix_map, all_ohlcv)
...
pnl_points = self._compute_pnl(predicted_direction, actual_move_pct, nifty_close)
```

Change the P&L calculation to use T+1 open as entry:

```python
entry_price = next_row["open"]   # T+1 open — actual execution price
exit_price  = nifty_next_close   # T+1 close — EOD exit

# Overnight gap (T close → T+1 open): not captured by signal, purely noise/luck
overnight_gap_pct = (entry_price - nifty_close) / nifty_close * 100

# Move from our actual entry to exit
entry_to_exit_pct = (exit_price - entry_price) / entry_price * 100

actual_move_pct = entry_to_exit_pct  # override: this is what we actually capture
pnl_points = self._compute_pnl(predicted_direction, actual_move_pct, entry_price)
```

Also pass `entry_price` (instead of `nifty_close`) to stop loss engine:
```python
sl_result = StopLossEngine.compute_stop_for_day(
    direction=predicted_direction,
    entry_close=entry_price,   # was nifty_close
    ohlcv_window=ohlcv_window,
    ...
)
```

And add gap-open immediate stop check:
```python
# If gap-open already past stop level, stop hit at open — no intraday needed
if sl_result.stop_price is not None:
    gap_stop_hit = StopLossEngine.check_stop_hit(
        predicted_direction, sl_result.stop_price,
        day_low=entry_price, day_high=entry_price  # treat open as both H and L
    )
    if gap_stop_hit:
        stop_hit = True
```

### Task 2 — Add `entry_price` and `overnight_gap_pct` to BacktestDayResult

In `backtest_engine.py` dataclass `BacktestDayResult`, add:
```python
entry_price: float = 0.0           # T+1 open — actual trade entry
overnight_gap_pct: float = 0.0     # T close → T+1 open gap (%)
```

Store them in the day result construction.

### Task 3 — Add overnight gap stat to BacktestRunResult

Add:
```python
avg_overnight_gap_pct: float = 0.0   # mean |gap| across all trading days
```

Compute it in the aggregation block:
```python
all_gaps = [abs(d.overnight_gap_pct) for d in days if d.predicted_direction != "HOLD"]
avg_overnight_gap_pct = sum(all_gaps) / len(all_gaps) if all_gaps else 0.0
```

### Task 4 — Update schemas.py

Add to `BacktestDayResponse`:
```python
entry_price: float = 0.0
overnight_gap_pct: float = 0.0
```

Add to `BacktestRunSummary`:
```python
avg_overnight_gap_pct: float = 0.0
```

### Task 5 — Update routes.py serializer

Add to the day response dict:
```python
"entry_price": getattr(day, 'entry_price', 0.0),
"overnight_gap_pct": getattr(day, 'overnight_gap_pct', 0.0),
```

Add to summary dict:
```python
"avg_overnight_gap_pct": getattr(result, 'avg_overnight_gap_pct', 0.0),
```

### Task 6 — Update run_backtest.py script output

Print overnight gap stat in Phase 4 runner:
```python
logger.info(f"Avg overnight gap   : {result.avg_overnight_gap_pct:.2f}% (abs mean)")
```

### Task 7 — Re-run backtest and compare

Run:
```
python -m scripts.run_backtest --from 2024-04-01 --to 2025-03-31 --instrument NIFTY
python -m scripts.run_backtest --from 2025-04-01 --to 2026-03-30 --instrument NIFTY
```

Compare new P&L vs old (+9,861 / +13,303 pts). Report:
- New total P&L
- Avg overnight gap
- Whether strategy remains profitable

## Verification

After Task 7:
- New backtest P&L still positive (may be lower — that's expected and correct)
- `entry_price` values in results are T+1 open prices (not T close)
- `overnight_gap_pct` values are non-zero and vary across days
