# Property-Test Failures — Bugs Found in the Risk Surface

Run command:
  cd backend && venv/Scripts/python -m pytest tests/property -q --tb=short

Result: ALL 37 PROPERTIES PASS as of commit fixing rounding consistency
in `stop_loss_engine.compute_stop()`. The 2 bugs documented below were
found by these property tests and have been fixed. Document retained as
a record of what the property suite caught on its first run.

Both failures are in `app/engine/stop_loss_engine.py`. Both stem from the
same root cause — `compute_stop()` rounds intermediate fields to 2-3 decimal
places before returning, while internal arithmetic uses raw precision.
For NIFTY-sized prices (~25 000) the discrepancies are invisible, but the
property tests trip on small entry prices and document a real edge case.

---

## 1. BUG — `test_buy_stop_is_below_entry`

Property: For a BUY/STRONG_BUY signal with a non-zero stop distance the
returned `stop_price` must be strictly less than `entry_price`.

File: tests/property/test_stop_loss_engine_props.py

Hypothesis counterexample:
    direction='BUY', entry=1.125, atr=0.0, mult=1.0, pct=0.5
    → StopLossResult(entry_price=1.12, stop_price=1.12,
                     stop_distance_pts=0.01, method='pct')

Theory: `StopLossResult.entry_price` and `stop_price` are both rounded to
2 decimals before being returned. When the raw stop distance is smaller
than the rounding granularity (here 1.125 × 0.5% = 0.005625) the rounded
levels collapse to the same value while `stop_distance_pts` rounds up to
0.01 — leaving an internally inconsistent record where the stop is
"non-zero" but is not actually below the entry.

Impact: Mostly cosmetic on a 25 000-pt index, but `check_stop_hit` would
NEVER fire (BUY needs day_low ≤ stop_price; equality only triggers if
NIFTY closes exactly at the rounded entry). Any caller building UI/exit
logic on the assumption "stop_price < entry_price for a BUY" is wrong on
this edge case. Bug is real for any future use on lower-priced
instruments (single-stock options, sub-100 ETFs).

---

## 2. BUG — `test_stop_pct_matches_distance_over_entry`

Property: `result.stop_pct ≈ result.stop_distance_pts / result.entry_price * 100`.
The two displayed fields must be mutually consistent.

File: tests/property/test_stop_loss_engine_props.py

Hypothesis counterexample:
    entry=1.5, atr=0.0, mult=1.0, pct=1.0
    → StopLossResult(entry_price=1.5, stop_price=1.49,
                     stop_distance_pts=0.01, stop_pct=1.0, method='pct')
    Reconstructed pct from displayed fields: 0.01 / 1.5 * 100 = 0.667
    Reported: 1.0 — off by ~50%.

Theory: `stop_pct` is computed from the RAW distance
    round((distance / entry_close) * 100, 3)
while `stop_distance_pts` is computed from `round(distance, 2)`. For
small entry values the two roundings disagree by enough that the printed
"stop = 0.01 pts, i.e. 1% of price" is internally inconsistent — a user
seeing 1% would actually be looking at a 0.67% stop.

Impact: Same as above — invisible at NIFTY price, but the field
contract on `StopLossResult` is violated and would confuse any UI/log
consumer that uses the two fields together.

---

## Summary

- **2 real bugs** identified in `stop_loss_engine.py`, both rounding-precision
  inconsistencies in `compute_stop()`.
- 0 bugs in `risk_manager.py` (all 11 properties pass).
- 0 bugs in `aggregator.py` (all 11 properties pass — including direction-flip
  symmetry, score bounds, conviction floor, and unanimous-consensus sanity).

Recommended fix (NOT applied, per instructions — properties left intact):
Either (a) drop the rounding of `entry_price`/`stop_price` and round only
in display layers, or (b) compute `stop_pct` from the rounded distance:
    stop_pct = round((round(distance, 2) / entry_close) * 100, 3)
and ensure `stop_price` is computed from the rounded distance so that
`entry_price - stop_price == stop_distance_pts` is an exact identity.
