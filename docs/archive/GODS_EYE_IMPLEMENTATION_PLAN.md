# God's Eye — Implementation Plan (Phases 1–5)

**Created:** 2026-04-01
**Author:** Claude (orchestrator) for Aashu
**Baseline:** Phase 0 complete — OpusCode Pro integrated, HOLD bias narrowed, SSE streaming live

---

## Phase 0: Allowed APIs & Anti-Patterns (Reference)

### Existing APIs You CAN Use

| API / Module | Location | Key Methods | Notes |
|---|---|---|---|
| `DhanClient` | `backend/app/data/dhan_client.py` | `get_ltp_batch()`, `get_option_chain(symbol)`, `get_historical_daily(security_id, exchange, from_date, to_date)` | Batch LTP fetches Nifty+BankNifty+VIX in 1 call. Options chain returns full chain with OI. Historical returns OHLCV candles. |
| `MarketDataService` | `backend/app/data/market_data.py` | `get_live_market()`, `get_options_data(symbol)`, `get_sector_performance()` | Dhan primary → NSE fallback → mock. Has TTL cache via `MarketCache`. |
| `PCRCollector` | `backend/app/tasks/pcr_collector.py` | `start()`, `stop()` | Runs every 5 min during market hours (9:15–15:30 IST). Stores to `pcr_store`. |
| `pcr_store` | `backend/app/data/pcr_store.py` | (to verify) | SQLite-backed PCR storage, already wired to collector. |
| `Orchestrator` | `backend/app/engine/orchestrator.py` | `run_simulation(market_data)` | 3-round simulation. Calls `ProfileGenerator.build_context()` for enriched context per agent. Uses `FeedbackEngine.get_tuned_weights()`. |
| `ProfileGenerator` | `backend/app/agents/profile_generator.py` | `build_context(agent_key, market_data, round_num)` | Builds enriched context string. **This is the pipeline to wire real data into.** |
| `AgentMemory` | `backend/app/memory/agent_memory.py` | `get_agent_accuracy(key, days)`, `record_prediction()`, `record_outcome()` | Returns `AgentAccuracyStats(accuracy_pct, total_predictions)`. SQLite-backed. |
| `FeedbackEngine` | `backend/app/engine/feedback_engine.py` | `get_tuned_weights(lookback_days)`, `get_prompt_hints(agent_key)`, `should_activate()` | Activates at 30+ predictions. Weight cap ±20%. Detects failure patterns. |
| `BacktestEngine` | `backend/app/engine/backtest_engine.py` | `run_backtest(instrument, from_date, to_date, mock_mode)` | Loads OHLCV + VIX from SQLite. Runs agents per day. Tracks per-agent accuracy. |
| `QuantSignalEngine` | `backend/app/engine/quant_signal_engine.py` | `compute(market_data)` | RSI, Supertrend, MACD(?), volume. Returns score 0–100 + direction + tier. |
| `Aggregator` | `backend/app/engine/aggregator.py` | `aggregate(agents_output, hybrid, tuned_weights)` | Hybrid: quant 0.45 × LLM 0.55 × agreement_boost. HOLD band: -8 to +8. |
| `RiskManager` | `backend/app/engine/risk_manager.py` | `compute(tier, direction, entry_close, vix)` | STOP_MULTIPLIER=5.0, RISK_REWARD=1.5. Lot sizing: strong=2, moderate=1, skip=0. |
| `Config` | `backend/app/config.py` | Dataclass with all params | AGENT_WEIGHTS, VIX thresholds (30/20), QUANT_LLM_BALANCE=0.45, SAMPLES_PER_AGENT=3 |

### SQLite Tables (Alembic migration `422bf1b3dbb6`)

| Table | Key Columns | Purpose |
|---|---|---|
| `simulations` | simulation_id, market_input (JSON), agents_output (JSON), final_direction, final_conviction | Full simulation records |
| `predictions` | prediction_id, predicted_direction, actual_direction, accuracy | Prediction tracking with outcome |
| `agent_predictions` | agent_key, direction, conviction, was_correct, round_num | Per-agent per-round tracking |
| `agent_weight_history` | agent_key, old_weight, new_weight, reason | Weight change audit trail |

### Python Dependencies (requirements.txt)

fastapi 0.115, uvicorn 0.30, pydantic 2.9, numpy 1.26, aiosqlite 0.20, httpx 0.27, sqlalchemy 2.0.36, alembic 1.14, gunicorn 23.0, cryptography 43.0, slowapi 0.1.9, pyyaml 6.0.1, pytest/locust

### Anti-Patterns — DO NOT

| Anti-Pattern | Why | Do Instead |
|---|---|---|
| Import `nsepy` or `nse-tools` | Not in requirements, unmaintained packages | Use Dhan API or direct NSE HTTP with existing `NSESession` |
| Add `pandas` for simple date operations | Not in requirements, heavy dependency | Use `datetime` + `numpy` (already available) |
| Create new SQLAlchemy models without Alembic migration | Schema drift | Always create Alembic migration for new tables |
| Modify `config.AGENT_WEIGHTS` at module level | Singleton mutation visible across workers | Pass tuned weights as parameter (already done in `Aggregator.aggregate(tuned_weights=)`) |
| Call Dhan API without rate limit awareness | 20 req/sec limit | Use existing `DhanClient` with its built-in cache + batching |
| Skip `_ensure_client()` on `DhanClient` | Token may have been renewed | Always go through the property/ensure pattern |
| Use `pandas.read_csv` for NSE bhavcopy parsing | No pandas | Use `csv` stdlib module + `numpy` |
| Store secrets in code | Security | Use `.env` + `os.getenv()` pattern (already established) |

---

## Phase 1: Data Quality (Target: 2 weeks)

**Goal:** Replace synthetic/mock data inputs with real stored data so agents reason on facts, not fiction.

### Task 1.1 — Store Daily PCR from Dhan Options Chain

**What:** The `PCRCollector` + `pcr_store` already exist and run during market hours. Verify it's working end-to-end and that stored PCR values flow into `MarketInput.pcr_index`.

**Files to modify:**
- `backend/app/data/market_data.py` → `get_live_market()` method: after fetching LTP, read today's PCR from `pcr_store` instead of computing from RSI proxy
- `backend/app/data/pcr_store.py` → verify `get_latest()` and `get_historical(days)` methods exist

**Verification:**
- `curl http://localhost:8000/api/market/live` → check `pcr_index` field is a real number (not default 1.0)
- Check `pcr_store` SQLite table has rows with timestamps during market hours
- Run simulation → agent prompts should show real PCR value

**Anti-pattern guard:** Do NOT add a new table for PCR if `pcr_store` already has one. Read the existing code first.

---

### Task 1.2 — Integrate Real FII/DII Daily Flow Data

**What:** Currently `fii_flow_5d` and `dii_flow_5d` in `MarketInput` are 0.0 or synthetic. Scrape real daily flows from NSDL or moneycontrol.

**Implementation approach:**
1. Create `backend/app/data/fii_dii_scraper.py` — scrape from `https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/` (public, no auth needed) OR `https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx`
2. Create Alembic migration for `fii_dii_flows` table: `date TEXT PK, fii_net REAL, dii_net REAL, source TEXT, fetched_at TEXT`
3. Add daily cron job (background task like `pcr_collector`) that fetches post-market (after 18:00 IST)
4. Update `MarketDataService.get_live_market()` to compute 5-day rolling sum from stored data

**Files to create:**
- `backend/app/data/fii_dii_scraper.py` — HTTP scraper with NSE-style session management (copy pattern from `NSESession` in `market_data.py`)
- `backend/alembic/versions/xxxx_add_fii_dii_flows.py` — new migration

**Files to modify:**
- `backend/app/data/market_data.py` → wire 5-day flow sums into `MarketInput`
- `backend/run.py` → add background task for post-market FII/DII fetch

**Verification:**
- `SELECT * FROM fii_dii_flows ORDER BY date DESC LIMIT 5` returns real data
- `curl http://localhost:8000/api/market/live` → `fii_flow_5d` and `dii_flow_5d` are non-zero
- Compare values against moneycontrol.com manually

---

### Task 1.3 — Store Historical VIX from NSE Bhavcopy

**What:** Backtest needs historical VIX. Currently loaded from SQLite OHLCV but VIX rows may be missing.

**Implementation approach:**
1. Use Dhan's `get_historical_daily()` with `INDIA_VIX_SECURITY_ID = "26"` and `NSE_IDX` exchange segment
2. Create a one-time backfill script and a daily updater
3. Store in existing OHLCV table (if schema allows instrument column) or create a `vix_daily` table

**Files to modify:**
- `backend/app/data/dhan_client.py` → add `backfill_vix(from_date, to_date)` method using existing `get_historical_daily()`
- `backend/app/api/routes.py` → wire to existing `/api/market/historical/backfill` endpoint

**Verification:**
- After backfill: `SELECT COUNT(*) FROM vix_daily WHERE date BETWEEN '2025-01-01' AND '2026-03-31'` > 300 rows
- BacktestEngine loads VIX without falling back to mock

**Anti-pattern guard:** Dhan `get_historical_daily()` works for equities but check if it supports `IDX_I` exchange segment for indices. If not, fall back to NSE bhavcopy CSV download.

---

### Task 1.4 — Add USD/INR and DXY Data

**What:** RBI Policy agent needs forex data. Currently `usd_inr` defaults to 83.5, `dxy` to 104.0.

**Implementation approach:**
1. Use a free forex API (e.g., `exchangerate-api.com` free tier, or scrape from RBI/FBIL)
2. Store daily closes in a `forex_daily` table
3. Wire into `MarketInput` construction

**Files to create:**
- `backend/app/data/forex_client.py` — fetch USD/INR from FBIL (RBI reference rate: `https://fbil.org.in/`)
- `backend/alembic/versions/xxxx_add_forex_daily.py`

**Files to modify:**
- `backend/app/data/market_data.py` → populate `usd_inr` and `dxy` from stored data

**Verification:**
- `curl http://localhost:8000/api/market/live` → `usd_inr` is a realistic value (80-90 range), `dxy` is realistic (95-110)
- RBI agent prompt includes real forex numbers

---

### Task 1.5 — Data Freshness Circuit Breaker

**What:** If Dhan API is down, system should warn rather than silently use stale data.

**Implementation approach:**
1. Add `last_fetched_at` timestamps to all data stores
2. Add a freshness check in `MarketDataService`: if any critical data > 1 hour old during market hours, set a `data_stale: true` flag on the response
3. Frontend shows a warning banner (extend existing "NSE Fallback" banner pattern)

**Files to modify:**
- `backend/app/data/market_data.py` → add staleness check
- `backend/app/api/schemas.py` → add `data_warnings: List[str]` to response
- `frontend/src/pages/Dashboard.jsx` → display data freshness warnings

**Verification:**
- Stop Dhan token → simulation response includes `data_warnings: ["PCR data >1hr old"]`
- Dashboard shows amber warning banner

---

## Phase 2: Signal Grounding (Target: Week 3–4)

**Goal:** Make LLM agents reason on quantitative evidence, not just vibes.

### Task 2.1 — Wire Enriched Context Pipeline

**What:** `ProfileGenerator.build_context()` already exists and is called in `Orchestrator.run_simulation()`. But the context it builds may be thin. Enrich it with quant signals, PCR, flows, forex.

**Files to modify:**
- `backend/app/agents/profile_generator.py` → `build_context()` method: include `QuantSignalEngine.compute()` results, PCR from store, FII/DII 5d flows, VIX regime, USD/INR
- Format as structured text block that each agent receives as `enriched_context` parameter

**Pattern to follow:** Each agent's `_build_prompt()` already accepts `enriched_context: str = None`. The context should be injected there. Example:

```
=== QUANTITATIVE CONTEXT ===
Quant Signal Score: 72/100 (BUY, strong tier)
- RSI(14): 58.3 (neutral-bullish)
- Supertrend: BUY since 3 days
- MACD: Bullish crossover 1 day ago
PCR (Nifty): 1.23 (bullish, above 1.0)
FII 5d Net Flow: +₹4,230 Cr (accumulating)
DII 5d Net Flow: -₹1,100 Cr (profit booking)
VIX: 14.5 (low, supportive)
USD/INR: 83.72 (stable)
```

**Verification:**
- Run simulation → check agent `reasoning` field references specific numbers from enriched context
- Compare a "with context" vs "without context" simulation — agent outputs should be more grounded

---

### Task 2.2 — Include Per-Agent Accuracy in Prompts

**What:** `FeedbackEngine.get_prompt_hints(agent_key)` already generates accuracy-based hints. Wire these into agent prompts.

**Files to modify:**
- `backend/app/agents/profile_generator.py` → append `feedback_engine.get_prompt_hints(agent_key)` to the enriched context
- Or: modify each agent's `_build_prompt()` to include a "YOUR TRACK RECORD" section

**Example prompt addition:**
```
=== YOUR TRACK RECORD (last 90 days) ===
Accuracy: 62% (31/50 correct)
Known weakness: Overconfident BUY in high-VIX environments
Adjustment: Reduce conviction by 10-15% when VIX > 25
```

**Verification:**
- After 30+ recorded predictions, agent prompts include accuracy data
- `FeedbackEngine.should_activate()` returns True

---

### Task 2.3 — Weight Conviction by Reproducibility

**What:** ALGO agent (quant, deterministic) should have its conviction weighted higher than LLM agents (stochastic).

**Files to modify:**
- `backend/app/engine/aggregator.py` → in `_standard_aggregate()`, multiply `conviction_factor` by 1.2 for agents where `response.reproducible == True`, by 0.9 for `reproducible == False`

**Current code (line 78):**
```python
conviction_factor = (response.conviction / 100.0) ** 0.8
```

**New code:**
```python
conviction_factor = (response.conviction / 100.0) ** 0.8
if response.reproducible:
    conviction_factor *= 1.2  # Quant is deterministic, trust it more
else:
    conviction_factor *= 0.9  # LLM is stochastic, slight penalty
```

**Verification:**
- Run same scenario twice → ALGO conviction unchanged, LLM agents may vary
- Aggregator score slightly more influenced by ALGO direction

---

### Task 2.4 — Increase ALGO Weight from 0.10 → 0.20

**What:** The quant engine is deterministic and backtestable. It deserves more weight. Reduce PROMOTER and RBI by 0.05 each.

**Files to modify:**
- `backend/app/config.py` → change `AGENT_WEIGHTS` default:
  ```python
  "ALGO": 0.20,      # was 0.10
  "PROMOTER": 0.05,   # was 0.10
  "RBI": 0.05,        # was 0.10
  ```

**Verification:**
- `config.validate()` passes (weights sum to 1.0: 0.30+0.25+0.15+0.20+0.05+0.05 = 1.00)
- Run simulation → agent_breakdown shows ALGO weight = 0.20

**Anti-pattern guard:** Do NOT change weights in the Alembic migration or database. Weights are in config, tuned by FeedbackEngine at runtime.

---

### Task 2.5 — Conviction Delta Trigger for Round 3

**What:** Currently Round 3 runs only if any direction changed between R1→R2. Add a trigger: if any agent's conviction shifted by >30 points between rounds, force Round 3.

**Files to modify:**
- `backend/app/engine/orchestrator.py` → `_check_direction_changes()` method: also check conviction delta

**Current logic (approx line 79):**
```python
direction_changed = self._check_direction_changes(round1_outputs, round2_outputs)
```

**New logic:**
```python
direction_changed = self._check_direction_changes(round1_outputs, round2_outputs)
conviction_swing = self._check_conviction_swings(round1_outputs, round2_outputs, threshold=30)
needs_round3 = direction_changed or conviction_swing
```

**Verification:**
- Scenario where R2 conviction shifts 40+ points → Round 3 triggers
- Round history shows 3 rounds in simulation output

---

## Phase 3: Validation (Target: Week 5–6)

**Goal:** Prove the system works with real data before trusting it.

### Task 3.1 — Run 90-Day Backtest with Real Historical Data

**What:** After Phase 1 data is stored, run a full backtest using real OHLCV + VIX + flows.

**Prerequisites:** Tasks 1.1–1.4 complete, at least 90 days of stored data.

**Execution:**
```bash
curl -X POST http://localhost:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"instrument": "NIFTY", "from_date": "2026-01-01", "to_date": "2026-03-31", "mock_mode": false}'
```

**Note:** `mock_mode: false` means real LLM calls — this will take 30-60 min and cost ~$5-15 in API credits. Run `mock_mode: true` first to verify data pipeline, then real.

**Verification:**
- `BacktestRunResult` returns with `overall_accuracy > 0` (not all HOLD)
- Per-agent accuracy shows differentiation (not all agents identical)
- Save results for Phase 4 comparison

---

### Task 3.2 — Compute Hit Rate, Avg Profit, Drawdown, Sharpe

**What:** The backtest returns `BacktestDayResult` with `pnl_points` and `direction_correct`. Compute aggregate metrics.

**Files to modify:**
- `backend/app/engine/backtest_engine.py` → add to `BacktestRunResult`:
  - `hit_rate_pct: float` (% of non-HOLD days where direction was correct)
  - `avg_pnl_per_trade: float` (mean P&L points on non-HOLD days)
  - `max_drawdown_pct: float` (max peak-to-trough on cumulative P&L)
  - `sharpe_ratio: float` (mean daily P&L / std daily P&L × √252)
  - `total_trades: int` (non-HOLD days)

**Verification:**
- Backtest response includes all 5 new fields
- Frontend Backtest page shows them in `BacktestSummary` component

**Files to modify (frontend):**
- `frontend/src/components/BacktestSummary.jsx` → display new metrics

---

### Task 3.3 — Per-Agent Accuracy by Market Regime

**What:** Compare agent accuracy in different VIX regimes: low (<15), normal (15-20), elevated (20-30), high (>30).

**Files to modify:**
- `backend/app/engine/backtest_engine.py` → add `regime_accuracy: Dict[str, Dict[str, float]]` to results
- Group `BacktestDayResult` by VIX regime, compute per-agent accuracy in each

**Output format:**
```json
{
  "regime_accuracy": {
    "low_vix": {"FII": 0.68, "DII": 0.55, "ALGO": 0.72, ...},
    "normal_vix": {"FII": 0.60, "DII": 0.62, ...},
    "elevated_vix": {...},
    "high_vix": {...}
  }
}
```

**Verification:**
- Some agents perform better in certain regimes (expected: ALGO better in low VIX, RBI better in high VIX)
- Data feeds into Phase 4 regime-stratified weight tuning

---

### Task 3.4 — Validation Dashboard in Frontend

**What:** New section on the Backtest page showing the results from 3.1–3.3 with charts.

**Files to modify:**
- `frontend/src/pages/Backtest.jsx` → add regime comparison section
- `frontend/src/components/RegimeAccuracyChart.jsx` (new) → grouped bar chart using Recharts

**Verification:**
- Navigate to `/backtest` → see regime accuracy chart after running a backtest

---

## Phase 4: Optimization (Target: Week 7–8)

**Goal:** Tune weights and behavior based on validated backtest data.

### Task 4.1 — Lower Feedback Engine Threshold from 30 → 15

**What:** Allow weight tuning to activate earlier.

**Files to modify:**
- `backend/app/engine/feedback_engine.py` → change `MIN_PREDICTIONS_FOR_TUNING = 15` (from 30)

**Risk:** May oscillate with too few data points. Mitigate by keeping `MAX_WEIGHT_ADJUSTMENT = 0.20`.

**Verification:**
- After 15 recorded predictions with outcomes, `feedback_engine.should_activate()` returns True
- `get_tuned_weights()` returns non-default weights

---

### Task 4.2 — Add Exponential Decay to Old Predictions

**What:** Recent predictions should matter more than 90-day-old ones. Add decay.

**Files to modify:**
- `backend/app/memory/agent_memory.py` → `get_agent_accuracy()`: weight each prediction by `exp(-λ × days_old)` where `λ = ln(2) / 90` (90-day half-life)

**Verification:**
- A prediction from 90 days ago has ~0.5× weight vs today's prediction
- Tuned weights shift gradually as new predictions accumulate

---

### Task 4.3 — Regime-Stratified Weight Tuning

**What:** Use different agent weights for different VIX regimes, informed by Phase 3 data.

**Files to modify:**
- `backend/app/engine/feedback_engine.py` → `get_tuned_weights()` accepts optional `vix_regime: str` parameter
- Store per-regime accuracy in `agent_memory`
- `Orchestrator.run_simulation()` → pass current VIX regime to weight tuning

**Verification:**
- In high VIX: weights shift toward agents with better high-VIX accuracy
- In low VIX: weights shift toward different agents

---

### Task 4.4 — Add MACD & Bollinger Bands to Quant Engine

**What:** Expand `QuantSignalEngine` with additional technical indicators.

**Files to modify:**
- `backend/app/engine/quant_signal_engine.py` → add:
  - MACD (12, 26, 9) scoring rules
  - Bollinger Bands (20, 2) — price position relative to bands
  - Adjust total score weighting to include new factors

**Verification:**
- `QuantSignalResponse.factors` includes `macd` and `bollinger` entries
- Quant backtest accuracy improves (compare before/after)

---

### Task 4.5 — Add BSE Bulk/Block Deal Data for Promoter Agent

**What:** Promoter agent currently has no real insider data. BSE publishes daily bulk/block deals.

**Files to create:**
- `backend/app/data/bse_deals_scraper.py` — scrape from `https://www.bseindia.com/markets/equity/EQReports/BulkDeals.aspx`
- `backend/alembic/versions/xxxx_add_bulk_deals.py` — table: `date, security, client_name, deal_type, quantity, price`

**Files to modify:**
- `backend/app/agents/profile_generator.py` → include recent bulk deals in Promoter agent context

**Verification:**
- Promoter agent prompt includes "Recent bulk deals: Adani Group bought 2M shares of XYZ"
- Promoter agent reasoning references specific deal data

---

## Phase 5: Production (Target: Week 9+)

**Goal:** Deploy and monitor in production.

### Task 5.1 — Deploy to Railway + Vercel

**What:** Follow the deployment config already documented in CLAUDE.md.

**Key steps:**
1. Create `railway.json` in backend root (per CLAUDE.md spec)
2. Create `vercel.json` in frontend root (per CLAUDE.md spec)
3. Set env vars on Railway: `GODS_EYE_LLM_PROVIDER`, `LLM_API_KEY`, `GODS_EYE_CORS_ORIGINS`, `GODS_EYE_DB_PATH=/app/data/gods_eye.db`
4. Mount Railway volume at `/app/data`
5. Set `VITE_API_BASE` on Vercel pointing to Railway URL

**Verification:**
- `curl https://<railway-url>/api/health` returns 200
- Frontend loads at `https://<vercel-url>/`
- Run a simulation from deployed frontend → get real LLM response

**Anti-pattern guard:** Do NOT use `allow_origins=["*"]` in production CORS. Set exact Vercel domain.

---

### Task 5.2 — Confidence Interval Modeling

**What:** Add uncertainty band to conviction scores based on agent agreement.

**Files to modify:**
- `backend/app/engine/aggregator.py` → compute `confidence_interval` from agent variance:
  - `ci_low = final_conviction - (agent_variance * 1.5)`
  - `ci_high = final_conviction + (agent_variance * 1.5)`
- `backend/app/api/schemas.py` → add `confidence_low`, `confidence_high` to `AggregatorResult`
- `frontend/src/components/DirectionGauge.jsx` → show confidence band visually

**Verification:**
- High-agreement simulations → narrow band (±5)
- Tug-of-war simulations → wide band (±25)

---

### Task 5.3 — Live Prediction Tracking Dashboard

**What:** Daily accuracy tracking with running hit rate.

**Files to create:**
- `frontend/src/pages/LiveTracker.jsx` — shows today's prediction, yesterday's outcome, rolling accuracy
- `frontend/src/components/AccuracyTimeline.jsx` — Recharts line chart of daily accuracy

**Files to modify:**
- `frontend/src/App.jsx` → add route `/tracker`
- `backend/app/api/routes.py` → add `GET /api/predictions/recent` endpoint

**Verification:**
- Navigate to `/tracker` → see prediction history with outcomes
- After recording 10 outcomes, rolling accuracy updates

---

### Task 5.4 — Alerting via Telegram

**What:** Send Telegram notification for STRONG_BUY or STRONG_SELL signals.

**Files to create:**
- `backend/app/notifications/telegram_bot.py` — uses `httpx` to call Telegram Bot API (`https://api.telegram.org/bot<token>/sendMessage`)

**Files to modify:**
- `backend/app/engine/orchestrator.py` → after simulation completes, if direction is STRONG_*, fire notification
- `backend/.env.example` → add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

**Verification:**
- Run simulation that produces STRONG_BUY → receive Telegram message with direction, conviction, key triggers

---

### Task 5.5 — Paper Trading P&L Tracker

**What:** Track virtual P&L from predictions as if trading Nifty options.

**Files to modify:**
- `backend/app/memory/prediction_tracker.py` → add `compute_paper_pnl()` using `RiskManager.compute()` for position sizing
- Wire to existing `/paper-trading` frontend page (`PaperTrading.jsx`)
- Compute: entry at prediction time, exit at next-day close, P&L = lots × point_move × 50 (Nifty lot size)

**Verification:**
- After 5+ predictions with outcomes, paper trading P&L shows cumulative equity curve
- Graduation criteria on PaperTrading page update based on real metrics

---

## Execution Notes

### Phase Dependencies
```
Phase 1 (Data Quality)    → no dependencies, start immediately
Phase 2 (Signal Grounding) → depends on Phase 1 tasks 1.1–1.4
Phase 3 (Validation)      → depends on Phase 1 + Phase 2
Phase 4 (Optimization)    → depends on Phase 3 results
Phase 5 (Production)      → Task 5.1 can start anytime; 5.2–5.5 after Phase 3
```

### Parallel Tracks
- **Phase 1 tasks 1.1–1.4** can all run in parallel (independent data sources)
- **Phase 2 tasks 2.1–2.4** mostly sequential (2.4 is independent)
- **Phase 5 task 5.1** (deployment) can start as soon as Phase 0 is stable

### LLM Cost Estimates
- Each simulation: ~$0.05–0.15 (6 agents × 3 samples × 3 rounds = 54 LLM calls)
- 90-day backtest (real LLM): ~$5–15
- Daily operations: ~$1–3/day (5–20 simulations)

### Risk Mitigation
- Always run `mock_mode: true` backtest first to verify data pipeline
- Keep `MAX_WEIGHT_ADJUSTMENT = 0.20` to prevent weight oscillation
- Monitor Dhan API rate limits (20 req/sec) — existing batching should be sufficient
- Test each phase's changes with a quick simulation before proceeding
