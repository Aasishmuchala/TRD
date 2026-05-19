# God's Eye — Profitability Roadmap Plan

**Goal:** Make the QuantSignalEngine + multi-agent system generate positive alpha on NIFTY 50 options.

**Context:** Backtest across 474 trading days (Apr 2024 → Mar 2026) showed all 5 quant-only variants lose money. Best variant (V3, threshold >20) lost 4.8% vs buy-and-hold's -1.4%. Root causes: proxy FII/DII data, missing PCR, no regime filtering.

**Execution:** Each phase is self-contained and can be executed in a new chat context. Phases 1-3 are independent and can run in parallel. Phase 4 depends on all prior phases.

---

## Phase 0: Documentation Discovery (COMPLETE)

### Allowed APIs & Patterns
- **NSE FII/DII endpoint:** `GET https://www.nseindia.com/api/fiidiiActivity/category` — returns today's net flow
- **NSE historical archives:** `https://www.nseindia.com/reports/fii-dii` — CSV bulk downloads
- **Dhan option chain:** `POST https://api.dhan.co/v2/optionchain` — body: `{"UnderlyingScrip": 13, "UnderlyingSeg": "IDX_I"}`
- **Dhan token renewal:** `GET https://api.dhan.co/v2/RenewToken` — headers: access-token + dhanClientId
- **VIX regime classifier:** `TechnicalSignals.classify_vix_regime(vix)` in `app/data/technical_signals.py:154-165`
- **Quant engine:** `QuantSignalEngine.compute_quant_score(inputs)` in `app/engine/quant_signal_engine.py:94`

### Anti-Patterns to Avoid
- Do NOT use `POST` for RenewToken (it's `GET`)
- Do NOT use `IDX_I` segment for Dhan `/charts/historical` (only works for equities/F&O)
- Do NOT use `accessToken` response field from RenewToken (it's `token`)
- Do NOT set `vix_5d_avg = vix` (makes VIX buy condition impossible — known bug)
- Do NOT add component libraries (shadcn, MUI) — finish existing Tailwind components

---

## Phase 1: Real FII/DII Flow Data

**Impact:** Enables 35 pts of scoring (FII 25 + DII absorption 10) with actual predictive signal instead of circular price proxy.

### Tasks

**1.1 Create NSE FII/DII data fetcher**
- File: `app/data/nse_fii_dii.py` (NEW)
- Implement async fetcher that calls `https://www.nseindia.com/api/fiidiiActivity/category`
- Parse response: extract `category` ("FII/FPI" or "DII"), `netValue` (remove commas, parse float)
- Convert to crores (the API returns in INR crores)
- Add proper headers to bypass NSE bot detection (User-Agent, Referer: nseindia.com)
- Pattern to follow: existing `app/data/market_data.py:360-382` (_fetch_fii_dii method)

**1.2 Create historical FII/DII SQLite store**
- File: `app/data/fii_dii_store.py` (NEW)
- Table schema:
  ```sql
  CREATE TABLE fii_dii_daily (
    date TEXT PRIMARY KEY,          -- YYYY-MM-DD
    fii_net_cr REAL NOT NULL,       -- FII net in crores
    dii_net_cr REAL NOT NULL,       -- DII net in crores
    fii_buy_cr REAL DEFAULT 0,
    fii_sell_cr REAL DEFAULT 0,
    dii_buy_cr REAL DEFAULT 0,
    dii_sell_cr REAL DEFAULT 0,
    source TEXT DEFAULT 'nse_api',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  ```
- Methods: `store_daily(date, fii_net, dii_net, ...)`, `get_range(from_date, to_date)`, `get_5d_sum(date)`
- Use existing SQLite pattern from `app/data/historical_store.py`

**1.3 Seed historical data**
- Script: `scripts/seed_fii_dii.py` (NEW)
- Download last 2 years of FII/DII data from NSE archives
- Parse CSV (columns: Date, FII/FPI Buy, FII/FPI Sell, FII/FPI Net, DII Buy, DII Sell, DII Net)
- Insert into SQLite store
- Fallback: if NSE blocks scraping, use NSDL CSV from `https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx`

**1.4 Wire into QuantInputs**
- Modify: `app/agents/algo_agent.py` (lines 55-63)
- Replace proxy `fii_net_cr = momentum * 500` with real data from `fii_dii_store.get_latest()`
- Use `get_5d_sum(date)` for rolling window instead of crude `today * 2.5` estimate
- Update `app/api/schemas.py` fields if needed

**1.5 Update backtest to use real FII/DII**
- Modify: backtest script to load from `fii_dii_store.get_range()` instead of momentum proxy
- Align by date: match FII/DII date to NIFTY candle date

### Verification
- [ ] `seed_fii_dii.py` populates ≥400 rows for 2-year period
- [ ] `fii_dii_store.get_5d_sum("2025-03-15")` returns non-zero values
- [ ] Backtest with real FII/DII shows different signal distribution than proxy
- [ ] All 99 existing tests still pass

### Documentation References
- NSE API endpoint: `app/data/market_data.py:360` (existing pattern)
- SQLite pattern: `app/data/historical_store.py` (existing)
- QuantInputs: `app/engine/quant_signal_engine.py:50-63`

---

## Phase 2: Live PCR from Dhan Option Chain

**Impact:** Enables 15 pts PCR factor + 10 pts DII absorption (which requires negative FII, now possible with real data). Total: 25 additional scoring points.

### Tasks

**2.1 Create PCR historical store**
- File: `app/data/pcr_store.py` (NEW)
- Table schema:
  ```sql
  CREATE TABLE pcr_daily (
    date TEXT PRIMARY KEY,
    pcr REAL NOT NULL,
    total_call_oi INTEGER,
    total_put_oi INTEGER,
    max_pain REAL,
    nifty_close REAL,
    expiry_date TEXT,
    source TEXT DEFAULT 'dhan',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  ```
- Methods: `store_pcr(date, pcr, ...)`, `get_pcr(date)`, `get_range(from_date, to_date)`

**2.2 Create PCR collection background task**
- File: `app/tasks/pcr_collector.py` (NEW)
- Async task that runs at configurable interval (default: every 5 minutes during market hours 9:15-15:30 IST)
- Calls `DhanClient.fetch_options_summary()` to get live PCR
- Stores end-of-day PCR snapshot to `pcr_store` at 15:25 IST
- Add to FastAPI startup in `run.py` alongside existing Dhan token renewal task

**2.3 Wire live PCR into QuantInputs**
- Modify: `app/agents/algo_agent.py`
- Instead of hardcoding `pcr=1.0`, fetch from `DhanClient.fetch_options_summary()` for live runs
- For backtests: load from `pcr_store.get_pcr(date)`
- Fallback: if Dhan unavailable or market closed, use 1.0 (current behavior)

**2.4 Seed initial PCR data**
- Since Dhan doesn't provide historical option chain, this is forward-looking only
- Start collecting from today; PCR backtest data accumulates over time
- Alternative for backtest: use NSE option chain archives (if available) or synthetic PCR from VIX correlation

### Verification
- [ ] During market hours (9:15-15:30 IST), `fetch_options_summary()` returns PCR ≠ 1.0
- [ ] PCR value stored in SQLite after market close
- [ ] QuantInputs receives real PCR in live simulation
- [ ] Background task logs PCR every 5 minutes during market hours
- [ ] All 99 existing tests still pass

### Documentation References
- Dhan option chain endpoint: `app/data/dhan_client.py:118-151` (existing `get_option_chain`)
- PCR computation: `app/data/dhan_client.py:206-252` (existing `fetch_options_summary`)
- QuantInputs PCR rules: `app/engine/quant_signal_engine.py:146-157`
- Startup task pattern: `run.py:140-155` (existing token renewal startup)

---

## Phase 3: VIX Regime Filter

**Impact:** High VIX trades lost ₹5K-22K average per trade. Filtering saves ~₹50K-240K annually depending on variant. Quick win — half a day of work.

### Tasks

**3.1 Add regime filter to AlgoQuantAgent**
- Modify: `app/agents/algo_agent.py` (after line 65, after quant score computed)
- Import `TechnicalSignals.classify_vix_regime` from `app/data/technical_signals.py`
- Add filter logic:
  ```python
  vix_regime = TechnicalSignals.classify_vix_regime(market_data.india_vix)

  if vix_regime == "high":  # VIX >= 30
      # Hard filter: force HOLD
      result_direction = "HOLD"
      conviction_multiplier = 0.0
  elif vix_regime == "elevated":  # 20 <= VIX < 30
      # Soft filter: reduce conviction by 40%
      conviction_multiplier = 0.6
  else:
      conviction_multiplier = 1.0
  ```
- Apply multiplier to conviction before returning AgentResponse

**3.2 Add regime filter config**
- Modify: `app/config.py` or add to existing settings
- New settings:
  - `VIX_FILTER_ENABLED: bool = True`
  - `VIX_HIGH_THRESHOLD: float = 30.0` (hard filter above this)
  - `VIX_ELEVATED_THRESHOLD: float = 20.0` (soft filter above this)
  - `VIX_ELEVATED_CONVICTION_MULTIPLIER: float = 0.6`

**3.3 Fix vix_5d_avg bug**
- File: `app/agents/algo_agent.py` (line 50)
- Current: `vix_5d_avg = market_data.india_vix` (makes VIX buy condition impossible since vix == vix_5d_avg)
- Fix: Compute actual 5-day VIX average from historical data or pass it through MarketInput
- This enables the VIX buy signal (vix < 14 AND vix < vix_5d_avg) to actually fire

**3.4 Add backtest variants V6 and V7**
- V6: V3 + hard VIX filter (skip all trades when VIX > 20)
- V7: V3 + soft VIX filter (reduce position size by 40% when VIX 20-30, skip when VIX > 30)
- Run both and compare to V3 baseline

**3.5 Add unit tests**
- File: `tests/test_vix_regime_filter.py` (NEW)
- Test cases:
  - High VIX (35.0) → direction forced to HOLD
  - Elevated VIX (25.0) → conviction reduced by 40%
  - Normal VIX (16.0) → no change
  - Low VIX (12.0) → no change
  - Filter disabled → no change at any VIX level

### Verification
- [ ] V6 backtest shows fewer trades than V3 (High VIX trades removed)
- [ ] V7 backtest shows improved return vs V3
- [ ] All 99 existing tests pass + new VIX filter tests pass
- [ ] Grep for `classify_vix_regime` finds usage in algo_agent.py

### Documentation References
- VIX regime classifier: `app/data/technical_signals.py:154-165`
- AlgoQuantAgent: `app/agents/algo_agent.py:33-143`
- Backtest consensus: `app/engine/backtest_engine.py:417-470`
- Backtest regime data: `backtest_results.json` (High VIX losses)

---

## Phase 4: Re-Backtest with Real Data

**Depends on:** Phases 1, 2, 3 all complete.

### Tasks

**4.1 Run comprehensive backtest**
- Use real FII/DII data from SQLite store
- Use whatever PCR data has accumulated (may still be limited)
- Apply VIX regime filter (V6/V7 variants)
- Same 5 threshold variants + 2 new VIX-filtered variants = 7 total
- Compare all 7 against buy-and-hold benchmark

**4.2 Generate updated report**
- Interactive HTML report with before/after comparison
- Show impact of each improvement independently:
  - Real FII/DII vs proxy: how much did signal distribution change?
  - VIX filter: how much capital saved?
  - Combined: overall return improvement

**4.3 Decide next step**
- If quant-only shows edge → optimize thresholds, add more factors (OI change, delivery %)
- If quant-only still flat → proceed to hybrid LLM backtest (Phase 5, future plan)
- If specific regime shows edge → build regime-specific strategies

### Verification
- [ ] Backtest uses real FII/DII (grep for "momentum * 500" returns 0 matches)
- [ ] VIX-filtered variants (V6/V7) show improved metrics vs V3
- [ ] Report generated with before/after comparison
- [ ] No regressions: all tests pass

---

## Phase 5 (Future): Hybrid LLM Backtest

**Not in current plan scope.** Execute after Phase 4 results are analyzed.

- Run historical scenarios through actual Claude API calls (5 LLM agents)
- Measure incremental alpha from LLM layer over quant-only baseline
- Estimate API cost per simulation ($0.03-0.10 per scenario)
- Test if the 55% LLM weight in the hybrid model justifies the cost

---

## Execution Order

```
Phase 1 (FII/DII)  ─┐
Phase 2 (PCR)       ─┼── Phase 4 (Re-Backtest) → Phase 5 (Hybrid LLM)
Phase 3 (VIX Filter) ┘
```

Phases 1-3 are independent. Phase 4 requires all three. Start with Phase 3 (quickest win, half a day), then Phase 1 (biggest impact, 2 days), then Phase 2 (forward-looking, 1 day).

---

*Plan created: 1 Apr 2026*
*Based on: 474-day backtest across 5 QuantSignalEngine variants*
*Data sources: Yahoo Finance (NIFTY 50 + VIX), Dhan API (equities + option chain)*
