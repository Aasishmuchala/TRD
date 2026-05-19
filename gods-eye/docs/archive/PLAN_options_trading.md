# God's Eye — Options Trading Plan
**Capital: ₹10,000 | Target: 10–100%+ monthly | Hold: 1–5 days | Instruments: NIFTY + Stock Options**

_Generated: 2026-04-03 | Status: Ready to execute_

---

## Context & Constraints

| Constraint | Detail |
|---|---|
| Capital | ₹10,000 starting |
| Instruments | NIFTY weekly options, NIFTY50 stock options |
| Hold period | 1–5 days (positional, not intraday) |
| Target return | 10–100%+ per month on capital deployed |
| Selectivity target | 25–35% of days traded (3–6 trades/month) |
| Win rate target | >55% |
| Max risk/trade | ₹1,500–2,000 (15–20% of capital) |

### NIFTY Options Capital Reality
- NIFTY lot size: 25 units
- ATM weekly CE/PE premium: ₹80–200 = ₹2,000–5,000/lot
- ₹10k budget → 1 lot at ≤₹400/unit premium max
- OTM strikes (1–2 strikes out) = ₹50–150/unit = ₹1,250–3,750/lot → affordable
- Weekly expiry every Thursday → natural 1–5 day hold alignment

### Stock Options Capital Reality
- Stocks with lot size 200–400 units can have premiums ₹5–25/unit = ₹1,000–10,000/lot
- Best targets: mid-cap NIFTY50 stocks with active weekly options
- Avoid: Bank Nifty (lot size 15, but premium >₹5k/lot typically)

---

## Current State (as of session end)

### What's done
- ✅ Conviction filter fix applied to `backtest_engine.py` (lines 629–634)
- ✅ `GODS_EYE_CONVICTION_FLOOR=70` set in `backend/.env`
- ✅ `GODS_EYE_HOLD_BAND=20` set in `backend/.env`
- ✅ Historical data seeded in SQLite (`/tmp/gods_eye_local.db` — 757 NIFTY rows, 752 VIX rows)
- ✅ Dhan token renewed and auto-renewal cron running
- ✅ April 2024 diagnosis: 100% selectivity bug identified (threshold=0.25, bull market always clears it)

### What's broken / pending
- ❌ Mock backtest not yet run to verify conviction filter fix
- ❌ P&L is in "points" — no rupee conversion, no lot size, no premium cost
- ❌ No stock options qualitative agent
- ❌ No IV rank / theta awareness
- ❌ Full FY2024–25 backtest not run

---

## Phase 0 — Architecture Reference (DONE)

_Findings from codebase exploration — reference for all phases._

### Key Files
```
backend/app/
├── agents/base_agent.py          — ABC: async analyze(market_data, round_num, other_agents_output, enriched_context) -> AgentResponse
├── agents/algo_agent.py          — QUANT agent, zero LLM calls, delegates to QuantSignalEngine
├── agents/fii_agent.py           — LLM agent, weight=0.30
├── agents/dii_agent.py           — LLM agent, weight=0.25
├── agents/retail_fno_agent.py    — LLM agent, weight=0.15, tracks dte/max_pain
├── agents/promoter_agent.py      — LLM agent, weight=0.05
├── agents/rbi_policy_agent.py    — LLM agent, weight=0.05
├── engine/backtest_engine.py     — _compute_consensus() at line 564, fix at line 629
├── engine/aggregator.py          — conviction floor at line 58, _score_to_direction() at line 221
├── engine/quant_signal_engine.py — QuantInputs → QuantScoreResult, instrument_hint (NIFTY_CE/PE)
├── api/schemas.py                — MarketInput (lines 8–41), AgentResponse, AggregatorResult
└── config.py                     — CONVICTION_FLOOR, HOLD_BAND, AGENT_WEIGHTS, VIX thresholds
```

### AgentResponse fields (exact)
```python
agent_name, agent_type, direction, conviction (0–100),
reasoning, key_triggers: List[str],
time_horizon, views: dict, interaction_effects: dict,
internal_consistency (0–1), reproducible (bool), sample_variance (float)
```

### MarketInput fields with options data (exact, from schemas.py lines 8–41)
```python
nifty_spot, nifty_open, nifty_high, nifty_low, nifty_close, india_vix,
fii_flow_5d, dii_flow_5d, usd_inr, dxy,
pcr_index, pcr_stock, max_pain, dte,
rsi_14, macd_signal,
context: str   # free-text description
```

### AGENT_WEIGHTS (from config.py)
```python
FII=0.30, DII=0.25, ALGO=0.20, RETAIL_FNO=0.15, PROMOTER=0.05, RBI=0.05
```

### Conviction filter fix location
```python
# backtest_engine.py lines 629–635 (ALREADY APPLIED)
if winning_direction != "HOLD" and conviction < config.CONVICTION_FLOOR:
    winning_direction = "HOLD"
    conviction = 50.0
return (winning_direction, conviction)
```

---

## Phase 1 — Validate Conviction Filter Fix (Mock Backtest)

**Goal:** Confirm selectivity drops from 100% → ~30% for April 2024 without running live LLM calls.
**Duration:** ~2 minutes. No internet needed. No Railway.

### Tasks

**1.1 — Set MOCK=true temporarily and run April 2024 backtest**

```bash
cd /path/to/gods-eye/backend
export $(grep -v '^#' .env | xargs)
export GODS_EYE_MOCK=true
python3 /tmp/run_backtest.py   # already written from prior session
```

**1.2 — Re-run_backtest.py with correct mock flag**

The script at `/tmp/run_backtest.py` needs `GODS_EYE_MOCK=true` OR pass it inline:
```python
os.environ['GODS_EYE_MOCK'] = 'true'   # add before config import
```

**1.3 — Verify expected output**

In April 2024 bull market with CONVICTION_FLOOR=70:
- Expected trades: ~6 out of 20 days (April 1, 3, 4, 24, 25, 26 had conviction ≥70)
- Expected selectivity: ~30%
- If still 100%: mock agents all return same conviction → check mock_responses.py

**1.4 — If mock results look right, note: live backtest will need to run unattended**

Live backtest timing: 20 days × ~15s/day (LLM) = ~5 minutes. Use nohup or tmux.

### Verification Checklist
- [ ] `CONVICTION_FLOOR` in logs shows 70.0 (not 55.0)
- [ ] `trades_taken / total_days` < 0.40
- [ ] No Python traceback
- [ ] `hit_rate_pct` shown (not KeyError on result fields)

### Anti-patterns
- Do NOT use `asyncio.run()` inside Jupyter — use `await` directly or `loop.run_until_complete()`
- Do NOT set `GODS_EYE_DB_PATH` to a non-existent path — use `/tmp/gods_eye_local.db`

---

## Phase 2 — Capital-Aware Options P&L Engine

**Goal:** Replace "points P&L" with real ₹ P&L that respects lot sizes, premium costs, and ₹10k capital.
**Files to create/modify:** `backend/app/engine/options_pnl.py` (new), `backend/app/engine/backtest_engine.py` (modify)

### Tasks

**2.1 — Create `options_pnl.py`**

```python
# backend/app/engine/options_pnl.py
from dataclasses import dataclass
from typing import Optional

# NIFTY50 instrument lot sizes (NSE-defined, April 2024)
NIFTY_LOT_SIZE = 25
BANKNIFTY_LOT_SIZE = 15
FINNIFTY_LOT_SIZE = 40

# Stock lot sizes for commonly traded NIFTY50 options
STOCK_LOT_SIZES = {
    "RELIANCE": 250, "TCS": 150, "HDFCBANK": 550, "INFY": 300,
    "ICICIBANK": 700, "HINDUNILVR": 300, "SBIN": 1500, "AXISBANK": 625,
    "BAJFINANCE": 125, "WIPRO": 1500, "MARUTI": 100, "NTPC": 3000,
    "TATAMOTORS": 1425, "POWERGRID": 2700, "BHARTIARTL": 950,
}

@dataclass
class OptionsTrade:
    date: str
    instrument: str           # "NIFTY", "RELIANCE", etc.
    direction: str            # "CE" or "PE"
    strike: int
    expiry: str               # "YYYY-MM-DD"
    lot_size: int
    lots: int                 # how many lots (usually 1 for ₹10k)
    entry_premium: float      # ₹ per unit at entry
    exit_premium: float       # ₹ per unit at exit
    entry_cost: float         # lots × lot_size × entry_premium
    exit_value: float         # lots × lot_size × exit_premium
    gross_pnl: float          # exit_value - entry_cost
    brokerage: float          # ~₹40 flat per leg (Zerodha/Dhan)
    net_pnl: float            # gross_pnl - brokerage
    return_pct: float         # net_pnl / capital_deployed × 100

def compute_options_pnl(
    nifty_point_move: float,    # e.g. +50 points
    instrument: str,
    direction: str,             # "CE" or "PE"
    entry_premium: float,       # e.g. ₹150
    capital: float = 10000.0,
    brokerage_per_leg: float = 40.0,
) -> OptionsTrade:
    """
    Convert NIFTY point move to options P&L for ₹10k capital.

    Assumptions:
    - ATM ± 1 strike
    - Delta ~0.45 for near-ATM options
    - Theta/gamma effects approximated via delta
    """
    lot_size = NIFTY_LOT_SIZE if instrument == "NIFTY" else STOCK_LOT_SIZES.get(instrument, 500)
    lots = max(1, int(capital * 0.3 / (entry_premium * lot_size)))  # risk 30% of capital
    entry_cost = lots * lot_size * entry_premium

    delta = 0.45  # near-ATM assumption
    option_move = nifty_point_move * delta if direction == "CE" else -nifty_point_move * delta
    exit_premium = max(0.05, entry_premium + option_move)
    exit_value = lots * lot_size * exit_premium

    gross_pnl = exit_value - entry_cost
    brokerage = brokerage_per_leg * 2  # entry + exit legs
    net_pnl = gross_pnl - brokerage
    return_pct = (net_pnl / capital) * 100

    return OptionsTrade(...)  # fill all fields
```

**2.2 — Add ₹ P&L columns to BacktestDayResult**

In `backtest_engine.py`, add to `BacktestDayResult` dataclass:
```python
options_pnl_inr: float = 0.0       # net P&L in ₹
options_return_pct: float = 0.0    # % return on capital
lots_traded: int = 0
entry_premium: float = 0.0
```

**2.3 — Wire options_pnl into backtest loop**

After computing `pnl_points` for a day, call:
```python
from app.engine.options_pnl import compute_options_pnl
trade = compute_options_pnl(
    nifty_point_move=day.pnl_points,
    instrument="NIFTY",
    direction="CE" if direction in ("BUY", "STRONG_BUY") else "PE",
    entry_premium=estimate_atm_premium(nifty_close, india_vix),
    capital=10000.0
)
day.options_pnl_inr = trade.net_pnl
day.options_return_pct = trade.return_pct
```

**2.4 — Add ATM premium estimator**

```python
def estimate_atm_premium(spot: float, vix: float, dte: int = 5) -> float:
    """Black-Scholes approximation for ATM premium."""
    import math
    sigma = vix / 100  # annualized vol
    t = dte / 252
    return spot * sigma * math.sqrt(t) * 0.4  # 0.4 ≈ N(d1)-N(d2) for ATM
```

### Verification Checklist
- [ ] `options_pnl_inr` appears in BacktestDayResult output
- [ ] For a 50-point NIFTY move: expected ₹P&L ≈ 50 × 0.45 × 25 × lots ≈ ₹560/lot
- [ ] Return % is in realistic range (5–40% per trade for options)
- [ ] Brokerage deducted (₹80 round-trip)

### Anti-patterns
- Do NOT use actual Black-Scholes with live vol for backtest (use VIX approximation)
- Do NOT assume delta=0.5 for all options (0.45 is more realistic ATM)
- Do NOT forget lot size makes P&L nonlinear vs point moves

---

## Phase 3 — Stock Options Intelligence Agent

**Goal:** Add a 7th agent focused on NIFTY50 stock options for 1–5 day trades. Qualitative analysis only (LLM). Weight: 0.10 (pulled from DII).
**New file:** `backend/app/agents/stock_options_agent.py`

### Agent Design

```
Name: "Stock Options Desk"
agent_type: "LLM"
time_horizon: "Intraday"  # 1–5 day positional
risk_appetite: "Aggressive"
weight: 0.10  (reduce DII from 0.25 → 0.15, increase ALGO from 0.20 → 0.20)
```

**Responsibilities:**
- Identify 1–2 NIFTY50 stocks with strong options setups (high IV, trending, event-driven)
- Assess whether NIFTY index options or specific stock options offer better risk/reward
- Factor in: upcoming results, sector momentum, bulk deals, FII stock-level flows
- Recommend: CE or PE, ATM vs OTM (1–2 strikes), suggested DTE

**System prompt structure (follow base_agent.py pattern):**
```python
SYSTEM_PROMPT = """
You are the Stock Options Desk — a prop desk trader specializing in NIFTY50
stock options for 1–5 day positional trades on ₹10,000 capital.

Your edge: identifying stocks where options premium is CHEAP relative to expected move.
IV rank < 30 = options are cheap (BUY premium).
IV rank > 70 = options are expensive (avoid buying, wait for IV crush).

For ₹10,000 capital:
- Max 1 lot per trade
- Only trade stocks where 1 ATM lot < ₹5,000
- Prefer weekly expiry with 3–7 DTE for 1–5 day holds

You MUST respond with ONLY valid JSON matching the AgentResponse schema.
Pick BUY (stock CE setup) or SELL (stock PE setup) or HOLD (no clear stock setup).
"""
```

**Key inputs to analyze from market_data:**
- `pcr_stock` — aggregate stock options PCR
- `context` — enriched_context includes sector performance, FII stock flows
- `other_agents_output` — Round 2: align with FII/DII direction on specific stocks

### Tasks

**3.1 — Create `stock_options_agent.py`**

Copy structure from `retail_fno_agent.py` (most similar: intraday, aggressive).
Modify:
- `name = "Stock Options Desk"`
- `risk_appetite = "Aggressive"`
- `time_horizon = "Intraday"`
- Update system prompt with stock options focus
- Add `iv_rank`, `stock_setup` to `views` dict in response

**3.2 — Register in orchestrator**

In `orchestrator.py`, add `StockOptionsAgent` to agent list:
```python
from app.agents.stock_options_agent import StockOptionsAgent
agents = [FIIAgent(), DIIAgent(), RetailFNOAgent(), AlgoQuantAgent(),
          PromoterAgent(), RBIPolicyAgent(), StockOptionsAgent()]
```

**3.3 — Update AGENT_WEIGHTS in config.py**

```python
# New weights (sum = 1.0)
"FII": 0.28,
"DII": 0.20,
"RETAIL_FNO": 0.15,
"ALGO": 0.20,
"PROMOTER": 0.05,
"RBI": 0.05,
"STOCK_OPTIONS": 0.07,
```

Wait — sum check: 0.28+0.20+0.15+0.20+0.05+0.05+0.07 = 1.00 ✓

**3.4 — Add STOCK_OPTIONS to backtest agent list**

In `backtest_engine.py`, find agent instantiation and add `StockOptionsAgent`.

### Verification Checklist
- [ ] `StockOptionsAgent` appears in per_agent_accuracy dict in backtest results
- [ ] `views` dict contains `iv_rank` and `stock_setup` keys
- [ ] Weight sum still = 1.0 after adding new agent
- [ ] Agent returns valid direction (not empty string or None)

### Anti-patterns
- Do NOT add StockOptionsAgent to backtest BEFORE Phase 1 validation passes
- Do NOT set weight > 0.15 (would over-index vs macro agents)
- Do NOT hardcode stock names in system prompt — pass via enriched_context

---

## Phase 4 — MarketInput Extensions for Options

**Goal:** Extend `MarketInput` schema with IV-rank and options-specific fields needed by the new agent and options P&L engine.
**File:** `backend/app/api/schemas.py`

### New Fields to Add

```python
# In MarketInput (after existing pcr_index, pcr_stock fields)
iv_rank: Optional[float] = None          # 0–100: current IV vs 52-week range
iv_percentile: Optional[float] = None    # % of days IV was lower
atm_call_premium: Optional[float] = None # current ATM CE premium in ₹/unit
atm_put_premium: Optional[float] = None  # current ATM PE premium in ₹/unit
weekly_expiry_date: Optional[str] = None # next Thursday expiry YYYY-MM-DD
top_stock_setups: Optional[str] = None   # comma-sep: "RELIANCE:CE,INFY:PE"
```

### IV Rank Computation

Add to `technical_signals.py`:
```python
def compute_iv_rank(vix_series: List[float], current_vix: float) -> float:
    """IV rank = (current - 52w_low) / (52w_high - 52w_low) × 100"""
    low_52w = min(vix_series[-252:]) if len(vix_series) >= 252 else min(vix_series)
    high_52w = max(vix_series[-252:]) if len(vix_series) >= 252 else max(vix_series)
    if high_52w == low_52w:
        return 50.0
    return (current_vix - low_52w) / (high_52w - low_52w) * 100
```

### Tasks

**4.1 — Add optional fields to MarketInput in schemas.py**

Find MarketInput class (lines 8–41). Add the 6 new Optional[float]/Optional[str] fields with defaults = None.

**4.2 — Add `compute_iv_rank()` to technical_signals.py**

Paste function above. Import and call in the market data assembly step.

**4.3 — Pass iv_rank into enriched_context for all LLM agents**

In `profile_generator.py` or orchestrator's `_build_enriched_context()`, add:
```python
if market_data.iv_rank is not None:
    context_parts.append(f"IV Rank: {market_data.iv_rank:.0f}/100 "
                         f"({'cheap' if market_data.iv_rank < 30 else 'expensive' if market_data.iv_rank > 70 else 'normal'})")
```

### Verification Checklist
- [ ] `MarketInput(iv_rank=45.0)` instantiates without error
- [ ] `iv_rank` appears in enriched_context string passed to agents
- [ ] `compute_iv_rank([15,18,22,25], 20)` returns ~50.0

### Anti-patterns
- Do NOT make iv_rank a required field (breaks existing MarketInput instantiation in backtest)
- Do NOT compute IV rank from options chain — use VIX proxy (sufficient for Nifty)

---

## Phase 5 — Full FY2024–25 Backtest (Unattended)

**Goal:** Run the full year backtest with all fixes in place. Validate monthly returns hit 10%+ target.
**Duration:** ~60 minutes (252 days × ~15s/day). Run with `nohup` or `tmux`.

### Pre-conditions
- Phase 1 complete (mock backtest shows ≤35% selectivity)
- CONVICTION_FLOOR=70 confirmed in .env
- Historical data covers April 2024 – March 2025

### Run Command

```bash
cd /path/to/gods-eye/backend
export $(grep -v '^#' .env | xargs)
nohup python3 -c "
import asyncio, sys, os
sys.path.insert(0, '.')
os.environ['GODS_EYE_DB_PATH'] = '/tmp/gods_eye_local.db'
from app.engine.backtest_engine import BacktestEngine
async def main():
    e = BacktestEngine()
    r = await e.run_backtest('NIFTY', '2024-04-01', '2025-03-31')
    print(f'Trades: {r.total_trades}/{len(r.days)} ({r.total_trades/len(r.days)*100:.1f}%)')
    print(f'Win rate: {r.hit_rate_pct:.1f}%')
    print(f'Total P&L pts: {r.total_pnl_points:.0f}')
    print(f'Sharpe: {r.sharpe_ratio:.2f}')
asyncio.run(main())
" > /tmp/fy2425_backtest.log 2>&1 &
echo "PID=$!"
```

### Target Metrics

| Metric | Minimum | Good | Great |
|---|---|---|---|
| Selectivity | 20% | 25–30% | <35% |
| Win rate | 55% | 60% | >65% |
| Monthly P&L pts | +150 | +300 | +500 |
| Monthly ₹ return | 10% | 20–30% | >50% |
| Max drawdown | <20% | <15% | <10% |
| Sharpe ratio | >0.5 | >1.0 | >1.5 |

### Monthly ₹ Return Estimate (back of envelope)
- 252 trading days / 12 = 21 days/month
- 25% selectivity = 5–6 trades/month
- 60% win rate = 3–4 wins, 2 losses
- Avg win: +80 pts → options ≈ +₹900 (80 × 0.45 delta × 25 lots)
- Avg loss: –50 pts → options ≈ –₹560 (stop-loss cuts loss)
- Net/month: 3.5×₹900 – 2×₹560 = ₹3,150 – ₹1,120 = **+₹2,030 on ₹10k = ~20% monthly**

### Verification Checklist
- [ ] Log shows "Trades: X/252" (X should be 50–90)
- [ ] No LLM timeout errors (server timeout set to 180s)
- [ ] Monthly breakdown shows no single month > –30% drawdown
- [ ] Win rate never < 45% in any 3-month rolling window

### Anti-patterns
- Do NOT run with `--workers 4` — singleton config bug causes non-determinism
- Do NOT kill mid-run — partial results won't save cleanly
- Do NOT compare "points P&L" to "₹ P&L" — they need Phase 2 conversion

---

## Execution Order

```
Phase 1 (30 min)  → validate filter fix with mock backtest
Phase 2 (2 hrs)   → build options P&L engine
Phase 3 (3 hrs)   → build StockOptionsAgent
Phase 4 (1 hr)    → extend MarketInput, add IV rank
Phase 5 (overnight) → full FY2024-25 backtest
```

## Decisions (locked)

| Question | Decision | Rationale |
|---|---|---|
| Weight source | DII: 0.25 → 0.18 | DII is quarterly/defensive — least edge for 1–5 day options |
| Final weights | FII=0.30, DII=0.18, RETAIL=0.15, ALGO=0.20, PROMOTER=0.05, RBI=0.05, STOCK_OPT=0.07 | Sum=1.00 ✓ |
| Expiry cycle | System decides: conviction ≥75 → weekly (3–7 DTE); conviction 70–74 → monthly (15–30 DTE) | Maximize leverage on high-conviction, buffer on moderate |
| Stock scope | NIFTY50 filtered to top 25 by OI | Excludes illiquid names (Adani, some PSUs) where spreads eat ₹10k |
| Top 25 stocks | RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, SBIN, AXISBANK, BAJFINANCE, HINDUNILVR, WIPRO, LT, MARUTI, TATAMOTORS, NTPC, POWERGRID, BHARTIARTL, ASIANPAINT, ULTRACEMCO, SUNPHARMA, KOTAKBANK, TITAN, TECHM, ONGC, COALINDIA, NESTLEIND | High liquidity, tight spreads |
| Stop loss | 40% premium-based SL | Buy ₹120 → exit ₹72. Options-native, capital-conscious for ₹10k |
