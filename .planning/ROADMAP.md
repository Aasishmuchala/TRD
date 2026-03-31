# Roadmap: God's Eye — Multi-Agent Indian Market Intelligence

## Milestones

- ✅ **v1.0 Production** - Phases 1-4 (shipped 2026-03-30)
- ✅ **v2.0 Backtesting & Signal Engine** - Phases 5-9 (shipped 2026-03-31)
- 🚧 **v3.0 Hybrid Trading Engine** - Phases 10-15 (in progress)

## Phases

<details>
<summary>✅ v1.0 Production (Phases 1-4) — SHIPPED 2026-03-30</summary>

God's Eye is approximately 90% functionally complete. The path to production is not greenfield engineering — it is four sequential gate-checks, each of which must fully pass before the next begins. Phase 1 eliminates all functional divergences between the Stitch UI mockups and the plan spec (agent names, weights, graduation criteria, auth routing) so every downstream phase builds on a correct foundation. Phase 2 wires the backend behaviors that affect product trustworthiness: skill injection into agent prompts and visible data freshness indicators. Phase 3 builds the full user-facing quality layer before anything ships publicly. Phase 4 deploys to Railway and Vercel with every production-blocking pitfall from research actively verified.

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: UI Alignment and Auth Routing** - Eliminate all functional divergences between Stitch mockups and the plan spec; route Welcome.jsx and fix AuthGate (completed 2026-03-30)
- [x] **Phase 2: Backend Wiring and Data Integrity** - Wire skill injection into agent prompts, fix SkillStore container path, surface NSE data freshness in UI (completed 2026-03-30)
- [x] **Phase 3: Frontend Polish and UX Completeness** - Add loading states, empty states, error states, live market ticker, CSV export, Learning/Skills page, and dark mode consistency (completed 2026-03-30)
- [x] **Phase 4: Production Deployment and Verification** - Deploy to Railway and Vercel with persistent volumes, correct CORS, wss:// WebSocket, and documented env vars (completed 2026-03-30)

### Phase 1: UI Alignment and Auth Routing
**Goal**: Every UI surface reflects the plan spec exactly — correct agent names, weights, graduation criteria, sidebar scope — and unauthenticated users see a functional Welcome page instead of a blank screen
**Depends on**: Nothing (first phase)
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):
  1. Every screen that displays agent names shows exactly: FII, DII, Retail F&O, Algo/Quant, Promoter, RBI — no Stitch-era variants
  2. Settings page shows agent weights matching plan spec (FII 0.30, DII 0.25, Retail 0.15, Algo 0.10, Promoter 0.10, RBI 0.10) and Quant/LLM slider defaults to 45/55
  3. Paper Trading graduation criteria panel shows all 6 thresholds at plan-specified values (1-day >=57%, 1-week >=60%, calibration <15%, quant-LLM agreement >=70%, no catastrophic miss, internal consistency >=75%)
  4. Sidebar navigation contains exactly 5 items: Dashboard, Agents, History, Paper Trading, Settings — no Portfolio, Execute Trade, Markets, or Secure Node links
  5. Navigating to the app while unauthenticated lands on /welcome with a functional API key entry form; entering a valid key proceeds to the dashboard
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Create src/constants/agents.js (canonical agent definitions: names, labels, colors, weights)
- [x] 01-02-PLAN.md — Fix auth routing: restructure App.jsx + simplify AuthGate to redirect to /welcome
- [x] 01-03-PLAN.md — Fix sidebar labels, add Quant/LLM slider to Settings, align Welcome agent nodes
- [x] 01-04-PLAN.md — Replace PaperTrading graduation criteria (6 plan-spec thresholds), add ScenarioModal flow fields

### Phase 2: Backend Wiring and Data Integrity
**Goal**: Learned skills actively reach agent prompts during simulation, SkillStore writes succeed under container non-root users, and users always know whether market data is live or fallback
**Depends on**: Phase 1
**Requirements**: BACK-01, BACK-02, BACK-03, BACK-04
**Success Criteria** (what must be TRUE):
  1. After running a simulation, the backend enriched_context payload for each agent contains a "LEARNED PATTERNS" section (not empty or absent)
  2. The SkillStore writes to the path set by the GODS_EYE_LEARNING_SKILL_DIR environment variable, not a hardcoded user home directory path
  3. When NSE data falls back to mock values, a visible banner or indicator appears in the dashboard UI — the data source is never invisible to the user
  4. Agent response objects include non-empty interaction_effects with amplifies and dampened_by fields populated
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Fix LEARNING_SKILL_DIR env var (BACK-02) and seed SkillStore with 5 skills (BACK-01)
- [x] 02-02-PLAN.md — Populate AlgoQuantAgent interaction_effects from computed signals (BACK-04)
- [x] 02-03-PLAN.md — Expose data_source in simulate response and render amber fallback banner in Dashboard (BACK-03)

### Phase 3: Frontend Polish and UX Completeness
**Goal**: Every user-facing flow communicates its state (loading, empty, error) clearly, the live market ticker works, simulation history is exportable, the Learning/Skills page is accessible, and the dark mode theme is consistent across all screens
**Depends on**: Phase 2
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, FE-07
**Success Criteria** (what must be TRUE):
  1. Running a simulation shows per-round progress ("Round 1 of 3", "Round 2 of 3") driven by WebSocket events — the screen never sits blank during a multi-round simulation
  2. Pages with no data (empty history, agents with no accuracy records) show a meaningful empty state message, not a blank area or spinner that never resolves
  3. When an API call fails (simulation error, NSE fetch failure), the user sees an actionable error message describing what went wrong — not a blank screen or silent failure
  4. The dashboard header shows a live Nifty, Bank Nifty, and India VIX ticker that updates with real or fallback-labeled values
  5. Simulation history page offers a working Export button that downloads a CSV or JSON file containing agent calls, consensus, and outcome data
  6. A Learning/Skills page is accessible from navigation and shows extracted skills per agent with the count of patterns learned
**Plans**: 4 plans

Plans:
- [x] 03-01-PLAN.md — Per-round progress "Round X of 3" in SimulationStream; error/empty states for Settings, PaperTrading, AgentDetail (FE-01, FE-02, FE-03)
- [x] 03-02-PLAN.md — Add Bank Nifty to backend market snapshot and MarketTicker component (FE-04)
- [x] 03-03-PLAN.md — CSV export on History page; new Skills page at /skills with sidebar nav item (FE-05, FE-06)
- [x] 03-04-PLAN.md — Dark mode palette consistency audit across Welcome, PaperTrading, AccuracyPanel, FeedbackPanel, ScenarioPanel (FE-07)

### Phase 4: Production Deployment and Verification
**Goal**: God's Eye is live and accessible at public Railway and Vercel URLs, with SQLite and SkillStore data persisting across redeploys, WebSocket streaming working over wss://, CORS configured for the production frontend domain, and all environment variables documented
**Depends on**: Phase 3
**Requirements**: DEP-01, DEP-02, DEP-03, DEP-04, DEP-05, DEP-06
**Success Criteria** (what must be TRUE):
  1. The backend is reachable at a public Railway URL; GET /api/health returns 200 with "mock_mode": false
  2. The frontend is reachable at a public Vercel URL; direct navigation to /welcome and /dashboard (deep links) loads correctly without a 404
  3. Running a simulation from the Vercel frontend shows real-time per-agent streaming in the browser — browser devtools confirms a wss:// WebSocket connection to the Railway backend
  4. Running 5 simulations, triggering a Railway redeploy, and then reloading history still shows all 5 records — SQLite and SkillStore data survive the redeploy
  5. A .env.example file exists in the repository root documenting every required environment variable with a comment explaining its purpose
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md — Fix Dockerfile (1 worker, /app/skills dir), create railway.toml, fix docker-compose skills volume and LEARNING_SKILL_DIR default
- [x] 04-02-PLAN.md — Fix WebSocket URL to use VITE_WS_BASE env var; create frontend/vercel.json SPA rewrite
- [x] 04-03-PLAN.md — Create .env.example files (gods-eye root, backend, frontend) documenting all env vars and CORS configuration

</details>

---

<details>
<summary>✅ v2.0 Backtesting & Signal Engine (Phases 5-9) — SHIPPED 2026-03-31</summary>

- [x] **Phase 5: Historical Data Backfill** - Fetch and cache 1+ year of OHLCV data for Nifty, Bank Nifty, and India VIX from Dhan API into SQLite (completed 2026-03-30)
- [x] **Phase 6: Technical Signal Engine** - Compute RSI, VWAP deviation, Supertrend, OI change, and VIX regime classification from stored historical data (completed 2026-03-30)
- [x] **Phase 7: Backtest Engine** - Replay a date range through agents using historical conditions as input and compare predictions against actual next-day moves (completed 2026-03-30)
- [x] **Phase 8: Signal Scoring** - Produce a combined 0-100 score merging agent sentiment conviction with technical signal alignment into actionable trade signals (completed 2026-03-31)
- [x] **Phase 9: Backtest Dashboard** - Interactive UI for running backtests, viewing accuracy/P&L/drawdown metrics, and drilling into individual backtest days (completed 2026-03-31)

### Phase 5: Historical Data Backfill
**Goal**: The system has at least one year of daily OHLCV data for Nifty 50, Bank Nifty, and India VIX stored in SQLite and refreshed automatically — every downstream phase (indicators, backtesting) has clean data to work from
**Depends on**: Phase 4 (Dhan API already wired as sole data source)
**Requirements**: HIST-01, HIST-02, HIST-03, HIST-04
**Success Criteria** (what must be TRUE):
  1. Calling the historical data endpoint for Nifty 50 returns at least 252 daily OHLCV records (approximately one trading year) fetched from Dhan API
  2. Calling the historical data endpoint for Bank Nifty returns at least 252 daily OHLCV records with no silent fallback to mock data — Dhan failure raises an explicit error
  3. India VIX daily close values for the same date range are stored alongside price data and queryable
  4. After a successful backfill, a subsequent fetch within the same trading day returns data from SQLite cache without hitting the Dhan API again
  5. On a fresh database, the system can trigger a full backfill for all three instruments and complete without manual intervention
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md — Add DhanFetchError + fetch_historical_candles; create HistoricalStore with SQLite schema and cache-first fetch logic
- [x] 05-02-PLAN.md — Wire historical endpoints (GET /api/market/historical/{instrument}, POST backfill) and startup auto-backfill hook

### Phase 6: Technical Signal Engine
**Goal**: The system can compute RSI, VWAP deviation, Supertrend, OI change, and VIX regime for any date in the historical dataset — every technical input the backtest engine and signal scorer need is available as a structured data object
**Depends on**: Phase 5
**Requirements**: TECH-01, TECH-02, TECH-03, TECH-04, TECH-05
**Success Criteria** (what must be TRUE):
  1. For any date with stored historical data, the system returns a 14-period RSI value for both Nifty and Bank Nifty
  2. VWAP deviation for a given date is computable and expressed as a percentage deviation from the rolling VWAP reference
  3. Supertrend direction (bullish/bearish) is derivable for any date using ATR-based calculation from stored OHLCV data
  4. OI change data (call/put) from Dhan options chain is fetched and stored as a net sentiment indicator (put/call ratio or directional delta)
  5. Any date in the dataset returns a VIX regime classification: one of low (<14), normal (14-20), elevated (20-30), or high (>30)
**Plans**: 2 plans

Plans:
- [x] 06-01-PLAN.md -- Create technical_signals.py with RSI-14, VWAP deviation, Supertrend, and VIX regime (pure numpy computation)
- [x] 06-02-PLAN.md -- Add oi_snapshots SQLite table, OI store/fetch methods, and GET /api/market/signals/{instrument}/{date} endpoint

### Phase 7: Backtest Engine
**Goal**: The system can replay any date range through the 6 agents using historical market conditions as input, run a full 3-round simulation per day, compare direction predictions against actual next-day moves, and accumulate per-agent and overall accuracy metrics
**Depends on**: Phase 5, Phase 6
**Requirements**: BT-01, BT-02, BT-03, BT-04, BT-05
**Success Criteria** (what must be TRUE):
  1. Submitting a backtest request for a 30-day date range completes without error and returns results for each trading day in that range
  2. Each backtest day record shows the 3-round agent debate with historical data as context, matching the same simulation structure used in live mode
  3. Each day record shows the predicted direction and conviction alongside the actual Nifty/Bank Nifty next-day move and whether the prediction was correct
  4. After a backtest run, the system reports per-agent direction accuracy and overall win rate across the entire date range
  5. The system reports a simulated P&L figure assuming a fixed strategy: buy ATM CE on BUY, buy ATM PE on SELL, do nothing on HOLD — using notional option pricing
**Plans**: 2 plans

Plans:
- [x] 07-01-PLAN.md — BacktestEngine class with SQLite schema, day-loop logic, direction accuracy, and P&L formula
- [x] 07-02-PLAN.md — POST /api/backtest/run and GET /api/backtest/results/{run_id} endpoints with Pydantic schemas

### Phase 8: Signal Scoring
**Goal**: Every simulation (live or backtest) produces a combined 0-100 signal score that merges agent sentiment conviction with technical alignment, so a trader can see at a glance whether the setup is strong, moderate, or worth skipping
**Depends on**: Phase 6, Phase 7
**Requirements**: SIG-01, SIG-02, SIG-03
**Success Criteria** (what must be TRUE):
  1. Every simulation result includes a combined signal score between 0 and 100, derived from agent consensus strength and the number of technical indicators aligned with that direction
  2. The score clearly maps to one of three tiers: strong signal (>70), moderate signal (50-70), or skip (<50) — displayed with the threshold label, not just the raw number
  3. The signal output specifies direction (BUY/SELL/HOLD), score, the contributing factors (which agents and which technicals drove the score), and the suggested instrument (Nifty CE/PE or Bank Nifty CE/PE)
**Plans**: 2 plans

Plans:
- [x] 08-01-PLAN.md — SignalScorer module with ScoreResult dataclass and 60/40 sentiment+technical formula (TDD)
- [x] 08-02-PLAN.md — Wire signal_score into BacktestDayResult and POST /api/simulate response

### Phase 9: Backtest Dashboard
**Goal**: A user can select a date range, run a backtest from the browser, and immediately see accuracy, P&L, drawdown, and per-agent performance — plus drill into any individual day to read the full agent reasoning vs what actually happened
**Depends on**: Phase 7, Phase 8
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06
**Success Criteria** (what must be TRUE):
  1. The backtest page has a date range picker and a Run Backtest button; submitting a valid range triggers the backtest and shows a progress indicator while it runs
  2. After a backtest completes, the dashboard shows overall direction accuracy (%), win rate (%), and total simulated P&L in a summary panel
  3. A per-agent accuracy table shows each agent's direction accuracy for the period, sortable by performance
  4. An equity curve chart plots cumulative simulated P&L over time for the backtest period using Recharts
  5. A stats panel shows max drawdown, Sharpe ratio, and average win/loss size computed from the backtest results
  6. Clicking any individual backtest day opens a detail view showing the full agent reasoning, the predicted direction and conviction, and the actual market outcome
**Plans**: 3 plans

Plans:
- [x] 09-01-PLAN.md — Extend API client + add /backtest route + Sidebar nav + Backtest.jsx page with form, run action, and progress state
- [x] 09-02-PLAN.md — BacktestSummary, StatsPanel, and AgentAccuracyTable components wired into Backtest.jsx
- [x] 09-03-PLAN.md — EquityCurve Recharts chart and DayDetailModal drill-down wired into Backtest.jsx

</details>

---

### v3.0 Hybrid Trading Engine (In Progress)

**Milestone Goal:** Replace the 3-round qualitative debate with a quantitative rules engine (60%) combined with single-round parallel agent calls (40%), validated by one LLM pass — delivering faster, more consistent signals with full risk rules and dual-mode backtesting.

- [x] **Phase 10: Quantitative Signal Engine** - Pure rules-based score (0-100) from FII/DII flows, PCR, RSI-14, VIX, and Supertrend — zero LLM calls, complete in under 10 seconds for 1-year backtest (completed 2026-03-31)
- [ ] **Phase 11: Agent Signal Rewrite** - Rewrite all 6 agent prompts for directional signal output and run them in parallel in a single round (~5 seconds total)
- [ ] **Phase 12: Hybrid Scoring and LLM Validator** - Combine quant score (60%) and agent consensus (40%) into a final signal, with a single LLM validator call that can reduce conviction or skip but cannot flip direction
- [ ] **Phase 13: Risk Management Rules** - Apply configurable position sizing, daily max-loss guard, VIX-scaled stop loss, and 1.5x risk target exit to every signal
- [ ] **Phase 14: Fast Backtesting Both Modes** - Rules-only backtest (1 year in <10 seconds) and hybrid backtest (1 month in <5 minutes) with risk-adjusted metrics side by side
- [ ] **Phase 15: Dashboard Updates** - Signal page showing quant score + agent reasoning + validator output; trade history distinguishing quant-driven vs agent-confirmed signals; performance comparison of both modes

## Phase Details

### Phase 10: Quantitative Signal Engine
**Goal**: The system can compute a deterministic 0-100 score from live Dhan data inputs (FII/DII flows, PCR, RSI-14, VIX, Supertrend) with no LLM calls — the quant engine works standalone and is fast enough to backtest 1 year in under 10 seconds
**Depends on**: Phase 9 (historical data and technical signals already in SQLite)
**Requirements**: QUANT-01, QUANT-02, QUANT-03, QUANT-04, QUANT-05
**Success Criteria** (what must be TRUE):
  1. Calling the quant signal endpoint for today's date returns a score between 0 and 100 with a per-factor breakdown showing FII/DII flows, PCR, RSI-14, VIX regime, and Supertrend contributions
  2. Each factor has a documented threshold (e.g. RSI < 30 = bullish +15 pts) and the API response shows which threshold each factor hit
  3. A score above 50 returns direction BUY or SELL; a score at or below 50 returns HOLD — the direction is always deterministic from the score alone
  4. Running the quant engine against one year of stored historical data (approximately 250 trading days) completes in under 10 seconds with zero LLM calls
  5. The quant engine can be invoked standalone (no agent system, no LLM client) and returns a valid ScoreResult for any date with sufficient historical data
**Plans**: 2 plans

Plans:
- [x] 10-01-PLAN.md — TDD: QuantSignalEngine pure rules module (11 scoring rules, 20 tests)
- [x] 10-02-PLAN.md — QuantBacktestEngine + GET /api/signal/quant + POST /api/backtest/quant-run

### Phase 11: Agent Signal Rewrite
**Goal**: All 6 agents produce directional trading signals (BUY/SELL/HOLD with conviction) in a single parallel round — the FII, DII, Retail F&O, and RBI agents use rewritten signal-oriented prompts; the Algo agent runs as pure quant with no LLM call; all finish together in approximately 5 seconds
**Depends on**: Phase 10
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06
**Success Criteria** (what must be TRUE):
  1. Each of the 6 agents returns a structured response containing direction (BUY/SELL/HOLD), conviction (0-100), and a one-paragraph signal rationale — no open-ended commentary without a directional conclusion
  2. The FII agent prompt explicitly processes USD/INR and DXY data alongside flow figures and outputs a prediction of FII buying or selling pressure
  3. The DII agent prompt explicitly weighs SIP inflow absorption against FII outflow and outputs whether DII support is likely to hold or be overwhelmed
  4. The Retail F&O agent prompt identifies PCR extremes, max pain proximity, and OI positioning as contrarian signals against the retail consensus direction
  5. The Algo agent produces its signal from RSI, VWAP, and Supertrend computation only — no LLM call is made for this agent
  6. All 6 agents are dispatched concurrently and the last response arrives within 8 seconds of the first dispatch (wall-clock time, not cumulative)
**Plans**: 3 plans

Plans:
- [ ] 11-01-PLAN.md — Rewrite FII, DII, Retail F&O, Promoter, RBI _build_prompt methods (AGENT-01 through AGENT-04)
- [x] 11-02-PLAN.md — Replace AlgoQuantAgent with QuantSignalEngine delegation — no LLM (AGENT-05)
- [ ] 11-03-PLAN.md — Collapse Orchestrator + StreamingOrchestrator to single-round asyncio.gather dispatch (AGENT-06)

### Phase 12: Hybrid Scoring and LLM Validator
**Goal**: Every signal request produces a final output that combines the quant score (60%) with agent consensus (40%) into a single hybrid score, then passes through one LLM validator call that may reduce conviction or skip the signal but cannot reverse the direction
**Depends on**: Phase 10, Phase 11
**Requirements**: HYB-01, HYB-02, HYB-03, HYB-04
**Success Criteria** (what must be TRUE):
  1. The final signal score is computed as quant_score * 0.60 + agent_consensus_score * 0.40 and the response shows both components with their weights
  2. A single LLM validator call runs after scoring and returns one of three verdicts: confirm (no change), adjust (reduces conviction by a specified amount), or skip (marks signal as not tradeable)
  3. The validator response includes a plain-language explanation of why it confirmed, adjusted, or skipped — visible to the user alongside the signal
  4. The validator cannot flip direction: a BUY signal remains BUY after validation even if conviction is reduced; only conviction and tradeable status change
  5. The complete signal output includes direction, hybrid score, quant breakdown, agent breakdown, validator verdict, validator reasoning, and recommended instrument (Nifty/Bank Nifty CE/PE)
**Plans**: TBD

### Phase 13: Risk Management Rules
**Goal**: Every tradeable signal (score > 50, not skipped by validator) is accompanied by position size, stop loss level, and target exit — computed deterministically from signal conviction and current VIX — and the daily max-loss guard prevents any new signals once the day limit is hit
**Depends on**: Phase 12
**Requirements**: RISK-01, RISK-02, RISK-03, RISK-04
**Success Criteria** (what must be TRUE):
  1. A configurable max-loss-per-day setting (default 5000 pts) is applied per session; once cumulative paper losses reach the limit, the system marks subsequent signals as blocked and explains why
  2. Each tradeable signal specifies position size: strong conviction (score >70) = 2 lots, moderate conviction (50-70) = 1 lot, weak or skipped (<50) = do not trade
  3. Stop loss level is derived from VIX: a higher VIX produces a wider stop — the response shows the VIX value used and the resulting stop distance in points
  4. Each tradeable signal includes a target exit at exactly 1.5x the risk (stop distance), shown as an absolute Nifty/Bank Nifty level
**Plans**: TBD

### Phase 14: Fast Backtesting Both Modes
**Goal**: A user can run a rules-only backtest covering 1 year of history in under 10 seconds and a hybrid backtest covering 1 month in under 5 minutes, with both modes reporting risk-adjusted metrics side by side so the hybrid premium over rules-only is visible
**Depends on**: Phase 10, Phase 11, Phase 12, Phase 13
**Requirements**: FBT-01, FBT-02, FBT-03, FBT-04
**Success Criteria** (what must be TRUE):
  1. Submitting a rules-only backtest for a 1-year date range completes and returns results in under 10 seconds (wall-clock time from API call to response)
  2. Submitting a hybrid backtest for a 1-month date range completes and returns results in under 5 minutes including all agent calls and validator passes
  3. The backtest results page shows both modes in adjacent panels — rules-only accuracy, P&L, and drawdown next to hybrid accuracy, P&L, and drawdown — with a delta row showing the difference
  4. Both modes report Sharpe ratio, max drawdown, win/loss ratio, and total P&L with position sizing applied — weak signals are counted as skipped, not as HOLD P&L
**Plans**: TBD

### Phase 15: Dashboard Updates
**Goal**: The signal page, trade history, and performance comparison views are updated to reflect the hybrid engine — a trader can see the quant score, each agent's directional call, the validator verdict, and how rules-only vs hybrid have performed historically, all from one screen
**Depends on**: Phase 12, Phase 13, Phase 14
**Requirements**: DASH-07, DASH-08, DASH-09
**Success Criteria** (what must be TRUE):
  1. The signal page shows a live signal card with four distinct sections: quant score breakdown (factors and points), agent consensus (each agent's direction and conviction), validator verdict (confirm/adjust/skip with explanation), and the final recommended trade with risk parameters
  2. The trade history page has a column or tag distinguishing quant-driven signals (validator confirmed with no agent override) from agent-confirmed signals (agent consensus moved the hybrid score above threshold)
  3. The performance comparison page shows rules-only vs hybrid backtests side by side with accuracy, P&L, Sharpe ratio, and drawdown — selectable date range applies to both modes simultaneously
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 10 → 11 → 12 → 13 → 14 → 15

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. UI Alignment and Auth Routing | v1.0 | 4/4 | Complete | 2026-03-30 |
| 2. Backend Wiring and Data Integrity | v1.0 | 3/3 | Complete | 2026-03-30 |
| 3. Frontend Polish and UX Completeness | v1.0 | 4/4 | Complete | 2026-03-30 |
| 4. Production Deployment and Verification | v1.0 | 3/3 | Complete | 2026-03-30 |
| 5. Historical Data Backfill | v2.0 | 2/2 | Complete | 2026-03-30 |
| 6. Technical Signal Engine | v2.0 | 2/2 | Complete | 2026-03-30 |
| 7. Backtest Engine | v2.0 | 2/2 | Complete | 2026-03-30 |
| 8. Signal Scoring | v2.0 | 2/2 | Complete | 2026-03-31 |
| 9. Backtest Dashboard | v2.0 | 3/3 | Complete | 2026-03-31 |
| 10. Quantitative Signal Engine | v3.0 | 2/2 | Complete    | 2026-03-31 |
| 11. Agent Signal Rewrite | v3.0 | 1/3 | In Progress|  |
| 12. Hybrid Scoring and LLM Validator | v3.0 | 0/TBD | Not started | - |
| 13. Risk Management Rules | v3.0 | 0/TBD | Not started | - |
| 14. Fast Backtesting Both Modes | v3.0 | 0/TBD | Not started | - |
| 15. Dashboard Updates | v3.0 | 0/TBD | Not started | - |
