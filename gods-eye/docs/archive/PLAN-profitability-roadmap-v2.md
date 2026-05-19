# God's Eye — Profitability Roadmap v2
## Stop Losses + Real Data + VIX Filter + Re-Backtest

**Goal:** Make the system safe and signal-accurate enough for real capital.
**Prerequisite:** v1 roadmap (Phases 0-3) completed. This plan finishes the wire-up, adds stop losses, and re-backtests.

**Date created:** 2026-04-01
**Based on:** Discovery subagent audit of full codebase (verified against actual file/line numbers)

---

## Phase 0: Documentation Discovery (COMPLETE)

Findings locked from subagent audit. All API names, signatures, and line references below are verified against source.

### Verified Allowed APIs

| API | File:Line | Signature |
|-----|-----------|-----------|
| `fetch_fii_dii_activity()` | `app/data/nse_fii_dii.py:96` | `async def fetch_fii_dii_activity() -> Dict` → keys: `fii_net_value`, `dii_net_value` (crores) |
| `FiiDiiStore.get_fii_dii_for_quant()` | `app/data/fii_dii_store.py:237` | `get_fii_dii_for_quant(store, date_str)` → `{"fii_net_cr", "dii_net_cr"}` |
| `FiiDiiStore.get_5d_sum()` | `app/data/fii_dii_store.py:137` | `get_5d_sum(date_str) -> Dict` → `{"fii_5d_net", "dii_5d_net", "days_found"}` |
| `FiiDiiStore.store_daily()` | `app/data/fii_dii_store.py:65` | `store_daily(date_str, fii_net_cr, dii_net_cr, ...)` |
| `PCRStore.get_pcr()` | `app/data/pcr_store.py:108` | `get_pcr(date: str) -> Optional[float]` |
| `PCRStore.store_pcr()` | `app/data/pcr_store.py:69` | `store_pcr(date, pcr, total_call_oi, total_put_oi, max_pain, ...)` |
| `VixStore.get_range()` | `app/data/vix_store.py:148` | `get_range(from_date, to_date) -> List[Dict]` → keys: `date, open, high, low, close, source` |
| `VixStore.get_close()` | `app/data/vix_store.py:127` | `get_close(date: str) -> Optional[float]` |
| `HistoricalStore.get_ohlcv()` | `app/data/historical_store.py:211` | `async get_ohlcv(instrument, from_date, to_date) -> List[Dict]` → keys: `date, open, high, low, close, volume` |
| `TechnicalSignals.classify_vix_regime()` | `app/data/technical_signals.py:140` | `classify_vix_regime(india_vix: float) -> str` → `"low" / "normal" / "elevated" / "high"` |
| `QuantSignalEngine.compute_quant_score()` | `app/engine/quant_signal_engine.py:94` | `compute_quant_score(inputs: QuantInputs, instrument: str) -> QuantSignalResult` |
| `global fii_dii_store` | `app/data/fii_dii_store.py:266` | Singleton — import directly, do not instantiate |
| `global pcr_store` | `app/data/pcr_store.py:191` | Singleton — import directly, do not instantiate |

### Verified Existing Wiring

| Component | Status |
|-----------|--------|
| `pcr_collector.start()` | ✅ Called in `run.py:238` on FastAPI startup |
| `fii_dii_collector.start()` | ✅ Called in `run.py:242` on FastAPI startup |
| Live market PCR fallback to `pcr_store.get_latest()` | ✅ `app/data/market_data.py:257-263` |
| Backtest FII/DII proxy (`momentum * 1500`) | ❌ `app/engine/backtest_engine.py:404` — NOT using real store |
| Backtest PCR proxy (RSI-derived) | ❌ `app/engine/backtest_engine.py:409, 434` — NOT using real store |
| VIX filter in algo_agent | ⚠️ `app/agents/algo_agent.py:77-87` — EXISTS but too soft (0.75/0.85 multiplier, NOT HOLD) |
| Stop loss anywhere | ❌ Does not exist |
| Unit mismatch risk | ⚠️ `algo_agent.py:47` assumes USD millions and multiplies by 8.35 — market_data path may already be in crores |

### Anti-Patterns to Avoid

- **DO NOT** use `fii_net_cr` as key when calling `fetch_fii_dii_activity()` — it returns `fii_net_value` / `dii_net_value`
- **DO NOT** use `GET` for Dhan RenewToken with `POST` — confirmed broken anti-pattern
- **DO NOT** use `accessToken` field from RenewToken — it's `token`
- **DO NOT** set `vix_5d_avg = india_vix` — makes VIX buy condition structurally impossible
- **DO NOT** call `FiiDiiStore()` as a constructor — use the global singleton `fii_dii_store` from `app/data/fii_dii_store.py:266`
- **DO NOT** add component libraries (shadcn, MUI) to frontend
- **DO NOT** use `"low_fear"` / `"high_fear"` VIX regime strings — `classify_vix_regime()` returns `"low"/"normal"/"elevated"/"high"`
- **DO NOT** instantiate a new `HistoricalStore` — use the existing `historical_store` singleton from `run.py` or import from module

---

## Phase 1: Real FII/DII Wire-Up into Backtest + Unit Fix

**Estimated time:** 3-4 hours
**Dependencies:** None (fii_dii_store and fii_dii_collector already built and running)
**Impact:** Replaces 35 pts of circular proxy scoring with real predictive signal

### Context

The `FiiDiiStore` (`app/data/fii_dii_store.py`) is fully implemented with a `get_fii_dii_for_quant(store, date_str)` helper at line 237 that returns `{"fii_net_cr", "dii_net_cr"}` directly — exactly what the backtest needs. The only gap is that `backtest_engine.py:404` still generates a proxy instead of calling this.

Additionally, `algo_agent.py:47` has a potential unit mismatch: it applies `* 8.35` assuming USD millions, but the live `market_data` path may already deliver values in INR crores. This must be audited and fixed.

### Tasks

**1.1 — Fix unit mismatch in algo_agent.py**

Read `app/data/market_data.py` lines 300-380 to find where `fii_flow_5d` is set.
- If it's already in crores → remove `* _USD_M_TO_CR` from `algo_agent.py:47`
- If it's in USD millions → keep the conversion but add a docstring to both files confirming units
- Either way: add a unit assertion comment at `algo_agent.py:46` specifying expected unit

**1.2 — Wire backtest_engine.py to use real FII/DII**

File: `app/engine/backtest_engine.py` lines 380-450

Replace the proxy block:
```python
# CURRENT (lines 404-405): DELETE THIS
fii_flow_proxy = momentum_5d_pct * 1500
dii_flow_proxy = -momentum_5d_pct * 800
```

With real store lookup:
```python
# REPLACEMENT: use fii_dii_store singleton
from app.data.fii_dii_store import fii_dii_store as _fii_dii_store
fii_dii_data = get_fii_dii_for_quant(_fii_dii_store, current_date_str)
fii_flow_real = fii_dii_data["fii_net_cr"]   # already in crores
dii_flow_real = fii_dii_data["dii_net_cr"]   # already in crores
```

Pattern to copy: `app/data/fii_dii_store.py:237-262` (`get_fii_dii_for_quant` shows exactly how to call)

Fallback: if `fii_dii_data["fii_net_cr"]` is 0 AND `fii_dii_data["dii_net_cr"]` is 0 (meaning no data for that date), fall back to `momentum_5d_pct * 1500` with a `logger.warning()` so we know when proxy is still active.

**1.3 — Seed historical FII/DII data**

Run `scripts/seed_fii_dii.py` to populate the store for the backtest date range (Apr 2024 → Mar 2026).
- If script doesn't exist: create it following the pattern in `app/data/fii_dii_store.py:65` (store_daily)
- NSE API: `GET https://www.nseindia.com/api/fiidiiActivity/category` (daily, needs session headers)
- NSE CSV archive: `https://www.nseindia.com/reports/fii-dii` for historical bulk download
- Target: ≥400 rows in `fii_dii_daily` table for the 474-day backtest window

### Verification Checklist
- [ ] `grep -n "momentum.*1500" app/engine/backtest_engine.py` → 0 results
- [ ] `python -c "from app.data.fii_dii_store import fii_dii_store; print(fii_dii_store.count_rows())"` → ≥400 rows
- [ ] `python -c "from app.data.fii_dii_store import fii_dii_store, get_fii_dii_for_quant; print(get_fii_dii_for_quant(fii_dii_store, '2025-03-15'))"` → non-zero values
- [ ] `python -c "from app.engine.backtest_engine import BacktestEngine; print('import ok')"` → no errors
- [ ] Unit of `fii_flow_5d` in `market_data.py` confirmed and documented

### Regression Guards
- Existing tests that mock FII data must still pass — do not remove fallback logic, only deprioritize it
- The `fii_dii_store.get_fii_dii_for_quant()` returns `{"fii_net_cr": 0.0, "dii_net_cr": 0.0}` when no data, not None — check for zeros, not None
- Do not change the `MarketInput` schema — the downstream algo_agent reads `fii_flow_5d` from it, which is set in market_data, not backtest

---

## Phase 2: PCR Real Data + VIX Filter Tighten

**Estimated time:** 2-3 hours
**Dependencies:** Phase 1 complete (so both fixes land in same backtest run)
**Impact:** PCR factor (+25 pts) now uses real or near-real data; VIX filter prevents capital destruction in high-volatility regimes

### Context

**PCR:** `pcr_store.py` and `pcr_collector.py` exist and start on FastAPI startup. The live path already has a `pcr_store.get_latest()` fallback at `market_data.py:257-263`. The backtest (`backtest_engine.py:409, 434`) still uses an RSI-derived proxy. Since PCR collection is forward-only (Dhan doesn't provide historical option chain), the backtest will use real PCR only for dates where data exists, with graceful fallback to `1.0` for older dates.

**VIX Filter:** The implementation at `algo_agent.py:77-87` is too soft. Current: `VIX≥30 → 0.75 multiplier`. Plan spec: `VIX≥30 → force HOLD (0.0 multiplier)`. The backtest showed high-VIX trades losing ₹5K-22K avg — softening doesn't eliminate those losses.

**VIX 5-day average:** `algo_agent.py:55` uses `vix * 0.8 + 17.0 * 0.2` as a proxy. `vix_store.get_range()` exists and can compute a real 5-day trailing average.

### Tasks

**2.1 — Wire backtest_engine.py to use real PCR**

File: `app/engine/backtest_engine.py` lines 409, 434

Replace:
```python
# CURRENT (line 409): DELETE
pcr_proxy = 0.6 + (rsi_val / 100) * 0.8
# CURRENT (line 434): DELETE
pcr_index=round(pcr_proxy, 2),
```

With:
```python
# REPLACEMENT: use pcr_store singleton with fallback
from app.data.pcr_store import pcr_store as _pcr_store
real_pcr = _pcr_store.get_pcr(current_date_str) or 1.0
# Wire: pcr_index=real_pcr,
```

Pattern to copy: `app/data/market_data.py:254-265` (exact fallback chain)

Fallback: `pcr_store.get_pcr()` returns `Optional[float]`. Use `or 1.0` directly (PCR of 1.0 = neutral, no scoring effect — safe default).

**2.2 — Tighten VIX filter in algo_agent.py**

File: `app/agents/algo_agent.py` lines 77-87

Replace the current soft multipliers:
```python
# CURRENT (too soft): DELETE
if vix_regime == "high":
    conviction_multiplier = 0.75
elif vix_regime == "elevated":
    conviction_multiplier = 0.85
```

With the plan-spec values:
```python
# REPLACEMENT (matches profitability plan spec)
if vix_regime == "high":          # VIX >= 30: hard filter — destroy conviction
    direction = "HOLD"
    conviction_multiplier = 0.0
elif vix_regime == "elevated":    # 20 <= VIX < 30: soft filter — 40% penalty
    conviction_multiplier = config.VIX_ELEVATED_CONVICTION_MULTIPLIER  # = 0.6
```

Note: `config.VIX_ELEVATED_CONVICTION_MULTIPLIER` is already 0.6 (confirmed in config.py). Do not hardcode — read from config.

Also fix the reasoning string at line 113: when `direction` is overridden to HOLD, the log should say `"HOLD forced"` not just `"High VIX reduces conviction"`.

**2.3 — Compute real VIX 5-day average**

File: `app/agents/algo_agent.py` line 52-55

Replace proxy estimate:
```python
# CURRENT (line 55): DELETE
vix_5d_avg = vix * 0.8 + 17.0 * 0.2
```

With real vix_store lookup:
```python
# REPLACEMENT
from app.data.vix_store import vix_store as _vix_store
from datetime import datetime, timedelta

# Get 5-day trailing VIX closes ending on market_data date
end_date = market_data.timestamp.strftime("%Y-%m-%d") if market_data.timestamp else datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
vix_rows = _vix_store.get_range(start_date, end_date)  # List[Dict] with 'close' key
vix_closes = [r["close"] for r in vix_rows if r.get("close")][-5:]
vix_5d_avg = sum(vix_closes) / len(vix_closes) if len(vix_closes) >= 3 else vix  # fallback to spot if <3 days
```

Pattern to copy: `app/data/vix_store.py:148` (`get_range` signature confirmed)

Edge case: If vix_store is empty (first run, no historical data), fall back to `vix_5d_avg = vix` with a log warning. This is safe — VIX buy signals just won't fire, which is conservative.

**2.4 — Add backtest variants V6 and V7**

File: `app/engine/backtest_engine.py` — the variants config section

V6: V3 threshold (>20) + hard VIX filter (skip all trades when `india_vix > 20`)
V7: V3 threshold (>20) + soft VIX filter (0.6 conviction when VIX 20-30, skip when VIX >30)

These should be separate `BacktestVariant` entries, not code changes to the main loop.

### Verification Checklist
- [ ] `grep -n "pcr_proxy" app/engine/backtest_engine.py` → 0 results
- [ ] `grep -n "0\.75\|0\.85" app/agents/algo_agent.py` → 0 results (multipliers removed)
- [ ] `grep -n "conviction_multiplier = 0.0\|direction = .HOLD" app/agents/algo_agent.py` → lines present
- [ ] `python -c "from app.data.technical_signals import TechnicalSignals; print(TechnicalSignals.classify_vix_regime(32))"` → `high`
- [ ] VIX 5-day average falls back gracefully when vix_store is empty — test with empty store
- [ ] All existing module imports still clean: `python -c "from app.agents.algo_agent import AlgoQuantAgent; print('ok')"`

### Regression Guards
- `classify_vix_regime()` returns `"low"/"normal"/"elevated"/"high"` — NOT `"low_vix"/"high_vix"`. The orchestrator (`app/engine/orchestrator.py`) uses `_classify_vix_regime()` which returns `"low_vix"/"normal_vix"` etc. These are different functions — do NOT merge them.
- When `direction = "HOLD"` is forced, `adjusted_conviction = 0.0`. Make sure `AgentResponse.conviction = 0.0` is valid in the schema (it is — float with no min validator).

---

## Phase 3: Stop Loss Engine

**Estimated time:** 4-5 hours
**Dependencies:** None (standalone new module, wired into existing backtest and simulation)
**Impact:** Caps maximum loss per trade; prevents a single bad day from wiping cumulative P&L

### Context

Currently there is **no stop loss anywhere in the codebase**. The backtest simulates each day as a 1-day hold with exit at next close. For an options trader on Dalal Street, this is unrealistic — intraday adverse moves will stop you out long before EOD. The stop loss engine must:

1. Compute stop levels before simulated entry
2. Apply stop in backtest if intraday range crosses the level
3. Surface stop levels in live simulation UI so the trader knows where to place their stop

For NIFTY ATM options specifically:
- Delta ≈ 0.5 → 1% NIFTY move ≈ 0.5% option premium move
- A 1.5% adverse move in NIFTY → option loses ~50% of premium (practical stop for retail)
- ATR-based: 1.5× ATR(14) of NIFTY daily range

### New File: `app/engine/stop_loss_engine.py`

Copy the class structure from `app/engine/quant_signal_engine.py:1-50` (similar dataclass + staticmethod pattern).

```python
"""Stop Loss Engine — computes ATR-based and percentage stop levels for NIFTY options."""

import math
from typing import Optional, List, Dict
from dataclasses import dataclass

ATR_PERIOD = 14
DEFAULT_ATR_MULTIPLIER = 1.5    # 1.5× ATR = stop distance in points
DEFAULT_PCT_STOP = 1.5          # 1.5% adverse move in underlying = stop trigger


@dataclass
class StopLossResult:
    direction: str           # BUY or SELL (the signal direction, not the stop)
    entry_price: float       # NIFTY close on signal day
    stop_price: float        # NIFTY level that triggers exit
    stop_distance_pts: float # stop_price distance from entry in points
    stop_pct: float          # stop distance as % of entry
    atr_14: float            # ATR(14) used for calculation
    method: str              # "atr" or "pct" — whichever was tighter


class StopLossEngine:
    """Computes stop loss levels using ATR and percentage methods, takes the tighter of the two."""

    @staticmethod
    def compute_atr(ohlcv_rows: List[Dict], period: int = ATR_PERIOD) -> float:
        """
        Compute ATR(period) from OHLCV rows.
        Pattern: uses True Range = max(high-low, |high-prev_close|, |low-prev_close|)
        Input: List[Dict] with keys 'open', 'high', 'low', 'close' — from HistoricalStore.get_ohlcv()
        Returns: float ATR value or 0.0 if insufficient data
        """
        if len(ohlcv_rows) < period + 1:
            return 0.0
        true_ranges = []
        for i in range(1, len(ohlcv_rows)):
            high = ohlcv_rows[i]["high"]
            low = ohlcv_rows[i]["low"]
            prev_close = ohlcv_rows[i - 1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        # Simple moving average of last `period` true ranges
        return sum(true_ranges[-period:]) / period

    @staticmethod
    def compute_stop(
        direction: str,
        entry_close: float,
        atr_14: float,
        atr_multiplier: float = DEFAULT_ATR_MULTIPLIER,
        pct_stop: float = DEFAULT_PCT_STOP,
    ) -> StopLossResult:
        """
        Compute stop loss level. Takes the TIGHTER of ATR-based and percentage-based stops.

        For BUY: stop is BELOW entry. Tighter = higher stop price (less room to fall).
        For SELL: stop is ABOVE entry. Tighter = lower stop price (less room to rise).
        """
        atr_distance = atr_14 * atr_multiplier
        pct_distance = entry_close * (pct_stop / 100.0)

        # Tighter stop = smaller distance from entry
        distance = min(atr_distance, pct_distance) if atr_14 > 0 else pct_distance
        method = "atr" if (atr_14 > 0 and atr_distance < pct_distance) else "pct"

        if direction == "BUY":
            stop_price = entry_close - distance
        else:  # SELL
            stop_price = entry_close + distance

        return StopLossResult(
            direction=direction,
            entry_price=entry_close,
            stop_price=round(stop_price, 2),
            stop_distance_pts=round(distance, 2),
            stop_pct=round((distance / entry_close) * 100, 3),
            atr_14=round(atr_14, 2),
            method=method,
        )

    @staticmethod
    def check_stop_hit(
        direction: str,
        stop_price: float,
        day_low: float,
        day_high: float,
    ) -> bool:
        """
        Check if stop was hit during the day using the day's high/low.
        For BUY: hit if day_low <= stop_price (NIFTY fell through stop)
        For SELL: hit if day_high >= stop_price (NIFTY rose through stop)
        """
        if direction == "BUY":
            return day_low <= stop_price
        elif direction == "SELL":
            return day_high >= stop_price
        return False

    @staticmethod
    def compute_stopped_pnl(
        direction: str,
        entry_close: float,
        stop_price: float,
        option_leverage: float = 3.0,
    ) -> float:
        """
        P&L when stop is hit. Uses same leverage model as backtest_engine._compute_pnl().
        stop_pnl_points = (stop_price - entry_close) / entry_close * 100 * option_leverage * (entry_close / 100)
        For BUY: negative (loss). For SELL: negative (loss). Always a loss when stop hits.
        """
        move_pct = (stop_price - entry_close) / entry_close * 100
        if direction == "SELL":
            move_pct = -move_pct  # Invert: stop hit means price went against short
        return move_pct * option_leverage * (entry_close / 100)
```

### Config additions (app/config.py)

Add to the Config dataclass `__post_init__`:
```python
self.STOP_LOSS_ENABLED: bool = os.getenv("GODS_EYE_STOP_LOSS_ENABLED", "true").lower() in ("true", "1", "yes")
self.STOP_LOSS_ATR_MULTIPLIER: float = float(os.getenv("GODS_EYE_STOP_LOSS_ATR_MULTIPLIER", "1.5"))
self.STOP_LOSS_PCT: float = float(os.getenv("GODS_EYE_STOP_LOSS_PCT", "1.5"))
self.STOP_LOSS_ATR_PERIOD: int = int(os.getenv("GODS_EYE_STOP_LOSS_ATR_PERIOD", "14"))
```

### Wire stop loss into backtest_engine.py

The backtest simulates 1-day trades. With stop loss:
1. Before entry on day D, compute `StopLossEngine.compute_atr()` from the prior 20 OHLCV rows
2. Compute `StopLossEngine.compute_stop(direction, entry_close, atr)`
3. On day D+1 (the "holding" day), check `StopLossEngine.check_stop_hit(direction, stop_price, day_low, day_high)` using the NEXT day's OHLCV
4. If stop hit: use `compute_stopped_pnl()` instead of the full-day P&L
5. If stop not hit: use existing `_compute_pnl()` (unchanged)

Note: `historical_store.get_ohlcv()` is async. The backtest already loads a `days` list from it. Pre-load the rolling 20-day window into a lookup dict keyed by date before the main loop — do not call get_ohlcv() inside the loop.

Add to `BacktestDayResult`:
```python
stop_loss_hit: bool = False
stop_price: Optional[float] = None
stop_distance_pts: Optional[float] = None
```

### Wire stop loss level into simulation result UI

In `app/api/schemas.py`, add to `AggregatorResult` (or create a `RiskLevels` sub-schema):
```python
stop_loss_price: Optional[float] = None     # NIFTY level to place stop
stop_loss_pct: Optional[float] = None       # as % from current price
stop_loss_method: Optional[str] = None      # "atr" or "pct"
atr_14: Optional[float] = None             # ATR(14) for context
```

In the orchestrator (`app/engine/orchestrator.py`), after aggregation, compute the stop level and attach it to the result. ATR can be pre-computed from `historical_store` during orchestrator initialization.

### Frontend: Display Stop Level on Simulation Result

File: `frontend/src/pages/Simulation.jsx` (or equivalent results page)

Add a "Risk Levels" section below the consensus card:
```
STOP LOSS   22,847   (-1.2%  |  ATR method)
```

Display in red with a downward arrow for BUY signals, upward for SELL. Use existing terminal-card styling.

### Verification Checklist
- [ ] `python -c "from app.engine.stop_loss_engine import StopLossEngine; print('import ok')"`
- [ ] `python -c "from app.engine.stop_loss_engine import StopLossEngine; r = StopLossEngine.compute_stop('BUY', 22000, 150, 1.5, 1.5); assert r.stop_price < 22000; print(r)"`
- [ ] `python -c "from app.engine.stop_loss_engine import StopLossEngine; assert StopLossEngine.check_stop_hit('BUY', 21800, 21750, 22100) == True"`
- [ ] `grep -n "stop_loss_hit\|stop_price" app/engine/backtest_engine.py` → lines present
- [ ] `grep -n "STOP_LOSS_ENABLED" app/config.py` → line present
- [ ] With `STOP_LOSS_ENABLED=false`, backtest P&L matches pre-stop-loss baseline

### Regression Guards
- `_compute_pnl()` must be unchanged — stop loss uses it as a fallback
- ATR computation requires ≥15 rows of OHLCV. Backtest days before row 15 should disable stop loss (use full-day P&L)
- `StopLossResult` must handle `direction="HOLD"` gracefully — return a no-op result with `stop_price=None`
- Pre-loading OHLCV window as dict: use `{row["date"]: row for row in ohlcv_rows}` — date strings are `YYYY-MM-DD`, confirm format matches backtest loop's `current_date_str`

---

## Phase 4: Re-Backtest + Comparison Report

**Estimated time:** 2-3 hours
**Dependencies:** Phases 1, 2, 3 complete + FII/DII store seeded with ≥400 rows
**Impact:** Quantifies improvement from each fix; confirms whether edge exists before paper trading

### Context

Backtest currently runs 5 variants (V1-V5 by conviction threshold). After Phases 1-3, add V6 and V7 (VIX-filtered) and compare all 7 with and without stop losses. The backtest infrastructure already exists in `app/engine/backtest_engine.py` — only the input data and variant configs change.

### Tasks

**4.1 — Run comprehensive backtest**

```bash
cd backend
python -c "
import asyncio
from app.engine.backtest_engine import BacktestEngine

async def run():
    engine = BacktestEngine()
    results = await engine.run_backtest(
        instrument='NIFTY',
        from_date='2024-04-01',
        to_date='2026-03-31',
    )
    print(f'Variants run: {len(results)}')
    for r in results:
        print(f'{r.variant_name}: hit_rate={r.hit_rate_pct:.1f}% sharpe={r.sharpe_ratio:.2f} pnl={r.total_pnl_points:.0f}pts')

asyncio.run(run())
"
```

**4.2 — Verify no proxy data leaking**

```bash
# These must all return 0 matches after Phases 1+2:
grep -n "momentum.*1500" app/engine/backtest_engine.py
grep -n "pcr_proxy" app/engine/backtest_engine.py
grep -n "pcr_stock=1\.0" app/engine/backtest_engine.py
```

**4.3 — Before/after comparison table**

Generate a simple table comparing:
```
Variant | Old Hit Rate | New Hit Rate | Old P&L | New P&L | Stop Loss P&L | Sharpe
V3 (threshold>20) | 53.1% | ? | -4.8% | ? | ? | ?
V6 (VIX hard filter) | N/A | ? | N/A | ? | ? | ?
V7 (VIX soft filter) | N/A | ? | N/A | ? | ? | ?
```

Save to `backtest_results_v2.json` in the backend root (same pattern as `backtest_results.json`).

**4.4 — Decide next step based on results**

After Phase 4 results:
- If any variant shows Sharpe > 0.5 AND hit rate > 55% → proceed to Railway deployment (paper trade live)
- If no variant shows edge → diagnose: is FII/DII data actually improving signal? Check per-date examples where old proxy fired vs new real data
- If specific regime shows edge only → build regime-specific signal (only trade when VIX < 20)

### Verification Checklist
- [ ] `fii_dii_store.count_rows()` ≥ 400 before running backtest
- [ ] No proxy greps return matches (see 4.2)
- [ ] V6 and V7 show fewer total trades than V3 (VIX filter removes some days)
- [ ] Stop loss variants show lower max drawdown than non-stop variants
- [ ] `backtest_results_v2.json` written and parseable

### Regression Guards
- Backtest date range must match FII/DII seed range — if store only has 300 rows, the remaining 174 days will use the fallback proxy; log a count of proxy-fallback days
- PCR store likely has 0 rows for historical dates (forward-collect only since today). Log count of PCR-from-store vs PCR-fallback days. If 0 real PCR rows, the PCR factor contributes nothing new — note this in the comparison report

---

## Phase 5: Deploy to Railway (Paper Trade Live)

**Estimated time:** 2-3 hours
**Dependencies:** Phase 4 re-backtest shows at least one variant with positive P&L after stop losses
**Impact:** 24/7 signal generation, PCR data starts accumulating from today, track record begins

### Pre-Deployment Gate

**Do NOT deploy until:**
- [ ] At least one backtest variant shows positive P&L (even marginal) after stop losses
- [ ] `grep -n "allow_origins.*\*" app` → 0 results in production CORS config
- [ ] Stop loss levels display correctly in frontend simulation result
- [ ] FII/DII data confirmed non-zero for recent 30 trading days

### Railway Deployment

Follow ARCHITECTURE.md Railway section. Key env vars to set:
```bash
railway variables set GODS_EYE_DB_PATH=/app/data/gods_eye.db
railway variables set GODS_EYE_LEARNING_SKILL_DIR=/app/skills
railway variables set GODS_EYE_VIX_FILTER_ENABLED=true
railway variables set GODS_EYE_STOP_LOSS_ENABLED=true
railway variables set GODS_EYE_CORS_ORIGINS=https://your-app.vercel.app
railway variables set LLM_API_KEY=<anthropic_key>
```

Mount Railway volume at `/app/data` (not `/data` — confirmed in ARCHITECTURE.md).

Gunicorn start command: `gunicorn run:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 180 --bind 0.0.0.0:$PORT`

### Vercel Frontend Deployment

```bash
cd frontend
vercel --prod
vercel env add VITE_API_BASE production
# Value: https://your-railway-app.railway.app
```

---

## Execution Order

```
Phase 1 (FII/DII Wire-Up)     ─┐
Phase 2 (PCR + VIX Tighten)   ─┤── Phase 4 (Re-Backtest) → Phase 5 (Deploy)
Phase 3 (Stop Loss Engine)    ─┘
```

Phases 1-3 are independent and can run in parallel or any order.
Phase 4 requires all three.
Phase 5 requires Phase 4 results to show positive edge.

**Recommended execution order in a single session:** Phase 3 → Phase 2 → Phase 1 → Phase 4 → Phase 5

Rationale: Phase 3 is pure new code (stop_loss_engine.py), zero regression risk. Phase 2 fixes one multiplier in algo_agent + one line in backtest. Phase 1 requires FII/DII seeding which may need network access and is most likely to hit issues.

---

## Known Risks and Edge Cases

| Risk | Mitigation |
|------|------------|
| NSE API blocks seeding script (bot detection) | Add session cookies + random delay between requests; fallback to NSDL CSV manual download |
| PCR store empty for all backtest dates | Expected — log a warning, do not treat as error. PCR real data only accumulates going forward |
| vix_store empty when computing 5-day avg | `if len(vix_closes) >= 3` fallback in Phase 2.3 handles this gracefully |
| Backtest OHLCV missing some dates (holidays) | `historical_store.get_ohlcv()` returns only existing rows — rolling window pre-computation handles gaps |
| `classify_vix_regime()` and orchestrator `_classify_vix_regime()` both exist with different return strings | DO NOT merge — they are used by different systems. Note in code comments |
| Unit mismatch fii_flow_5d (USD M vs INR Cr) | Phase 1.1 resolves this — must be done before Phase 1.2 |
| Stop loss changes total P&L significantly, making all variants worse | Still correct — max loss per trade is capped. Sharpe often improves even when P&L drops |
| Workers > 1 on Railway | Config singleton mutation issue per ARCHITECTURE.md — keep `--workers 1` |

---

*Plan created: 2026-04-01*
*Discovery subagents confirmed all file paths, line numbers, and method signatures*
*Supersedes: PLAN-profitability-roadmap.md (v1)*
