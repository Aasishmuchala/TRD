# Roadmap: God's Eye — Multi-Agent Indian Market Intelligence

## Milestones

- ✅ **v1.0 Production** - Phases 1-4 (shipped 2026-03-30)
- 🚧 **v2.0 Backtesting & Signal Engine** - Phases 5-9 (in progress)

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

### v2.0 Backtesting & Signal Engine (In Progress)

**Milestone Goal:** Prove God's Eye has a tradeable edge by backtesting against historical Nifty/Bank Nifty data and building a technical signal engine that combines agent sentiment with indicators.

- [x] **Phase 5: Historical Data Backfill** - Fetch and cache 1+ year of OHLCV data for Nifty, Bank Nifty, and India VIX from Dhan API into SQLite (completed 2026-03-30)
- [x] **Phase 6: Technical Signal Engine** - Compute RSI, VWAP deviation, Supertrend, OI change, and VIX regime classification from stored historical data (completed 2026-03-30)
- [x] **Phase 7: Backtest Engine** - Replay a date range through agents using historical conditions as input and compare predictions against actual next-day moves (completed 2026-03-30)
- [ ] **Phase 8: Signal Scoring** - Produce a combined 0-100 score merging agent sentiment conviction with technical signal alignment into actionable trade signals
- [ ] **Phase 9: Backtest Dashboard** - Interactive UI for running backtests, viewing accuracy/P&L/drawdown metrics, and drilling into individual backtest days

## Phase Details

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
**Plans**: TBD

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
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7 → 8 → 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. UI Alignment and Auth Routing | v1.0 | 4/4 | Complete | 2026-03-30 |
| 2. Backend Wiring and Data Integrity | v1.0 | 3/3 | Complete | 2026-03-30 |
| 3. Frontend Polish and UX Completeness | v1.0 | 4/4 | Complete | 2026-03-30 |
| 4. Production Deployment and Verification | v1.0 | 3/3 | Complete | 2026-03-30 |
| 5. Historical Data Backfill | v2.0 | 2/2 | Complete   | 2026-03-30 |
| 6. Technical Signal Engine | v2.0 | 2/2 | Complete   | 2026-03-30 |
| 7. Backtest Engine | v2.0 | 2/2 | Complete   | 2026-03-30 |
| 8. Signal Scoring | v2.0 | 0/TBD | Not started | - |
| 9. Backtest Dashboard | v2.0 | 0/TBD | Not started | - |
