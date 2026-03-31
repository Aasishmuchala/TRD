# Requirements: God's Eye v2.0 — Backtesting & Signal Engine

**Defined:** 2026-03-31
**Core Value:** Prove God's Eye has a tradeable edge on Nifty/Bank Nifty options before risking real money.

## v2.0 Requirements

### Historical Data

- [x] **HIST-01**: System can fetch and store daily OHLCV data for Nifty 50 from Dhan API (minimum 1 year history)
- [x] **HIST-02**: System can fetch and store daily OHLCV data for Bank Nifty from Dhan API (minimum 1 year history)
- [x] **HIST-03**: System can fetch and store historical India VIX daily close values
- [x] **HIST-04**: Historical data is cached locally in SQLite and refreshed daily during market hours

### Technical Signals

- [x] **TECH-01**: System computes RSI (14-period) for Nifty and Bank Nifty from historical data
- [x] **TECH-02**: System computes VWAP deviation for intraday context
- [x] **TECH-03**: System computes Supertrend indicator (ATR-based) for trend direction
- [x] **TECH-04**: System tracks OI change (call/put) from Dhan options chain for sentiment shift detection
- [x] **TECH-05**: System classifies VIX regime (low <14, normal 14-20, elevated 20-30, high >30)

### Backtest Engine

- [x] **BT-01**: System can replay a date range through agents using historical data as input
- [x] **BT-02**: Each backtest day runs a full 3-round simulation with historical market conditions
- [x] **BT-03**: System compares agent prediction (direction + conviction) against actual next-day Nifty/Bank Nifty move
- [x] **BT-04**: System tracks per-agent accuracy, overall accuracy, and conviction calibration across backtest period
- [x] **BT-05**: System computes P&L assuming simple option strategy (buy ATM CE on BUY, ATM PE on SELL, skip HOLD)

### Signal Scoring

- [x] **SIG-01**: System produces a combined score (0-100) merging agent sentiment with technical signal alignment
- [x] **SIG-02**: Score > 70 with technicals aligned = strong signal, 50-70 = moderate, < 50 = skip
- [x] **SIG-03**: Signal includes direction, strength, contributing factors, and suggested instrument (Nifty/BankNifty CE/PE)

### Backtest Dashboard

- [x] **DASH-01**: User can select date range and run backtest from the UI
- [x] **DASH-02**: Dashboard shows overall accuracy (1-day direction), win rate, and total P&L
- [x] **DASH-03**: Dashboard shows per-agent accuracy breakdown over the backtest period
- [x] **DASH-04**: Dashboard shows equity curve (cumulative P&L over time)
- [x] **DASH-05**: Dashboard shows max drawdown, Sharpe ratio, and average win/loss size
- [x] **DASH-06**: User can drill into individual backtest days to see agent reasoning vs actual outcome

## Future Requirements

### Execution (v3.0)
- **EXEC-01**: Place option orders via Dhan Trading API
- **EXEC-02**: Position sizing based on conviction + account size
- **EXEC-03**: Auto stop-loss and target exit
- **EXEC-04**: Multi-leg strategies (straddles based on VIX)

## Out of Scope (v2.0)

| Feature | Reason |
|---------|--------|
| Live order execution | v3.0 — must prove edge first |
| Real money trading | Backtesting must pass graduation criteria |
| Intraday backtesting | Start with daily timeframe |
| Non-index instruments | Nifty/Bank Nifty options only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| HIST-01 | Phase 5 — Historical Data Backfill | Complete |
| HIST-02 | Phase 5 — Historical Data Backfill | Complete |
| HIST-03 | Phase 5 — Historical Data Backfill | Complete |
| HIST-04 | Phase 5 — Historical Data Backfill | Complete |
| TECH-01 | Phase 6 — Technical Signal Engine | Complete |
| TECH-02 | Phase 6 — Technical Signal Engine | Complete |
| TECH-03 | Phase 6 — Technical Signal Engine | Complete |
| TECH-04 | Phase 6 — Technical Signal Engine | Complete |
| TECH-05 | Phase 6 — Technical Signal Engine | Complete |
| BT-01 | Phase 7 — Backtest Engine | Complete |
| BT-02 | Phase 7 — Backtest Engine | Complete |
| BT-03 | Phase 7 — Backtest Engine | Complete |
| BT-04 | Phase 7 — Backtest Engine | Complete |
| BT-05 | Phase 7 — Backtest Engine | Complete |
| SIG-01 | Phase 8 — Signal Scoring | Complete |
| SIG-02 | Phase 8 — Signal Scoring | Complete |
| SIG-03 | Phase 8 — Signal Scoring | Complete |
| DASH-01 | Phase 9 — Backtest Dashboard | Complete |
| DASH-02 | Phase 9 — Backtest Dashboard | Complete |
| DASH-03 | Phase 9 — Backtest Dashboard | Complete |
| DASH-04 | Phase 9 — Backtest Dashboard | Complete |
| DASH-05 | Phase 9 — Backtest Dashboard | Complete |
| DASH-06 | Phase 9 — Backtest Dashboard | Complete |

**Coverage:**
- v2.0 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---
*Requirements defined: 2026-03-31*
*Last updated: 2026-03-31 after v2.0 roadmap creation*

## v1 Requirements

Requirements for production release. Each maps to roadmap phases.

### UI Alignment

- [x] **UI-01**: All screens use consistent agent names: FII, DII, Retail F&O, Algo/Quant, Promoter, RBI
- [x] **UI-02**: Agent weights match plan spec across all screens (0.30, 0.25, 0.15, 0.10, 0.10, 0.10)
- [x] **UI-03**: Graduation criteria match plan's 6 thresholds (1-day >=57%, 1-week >=60%, calibration <15%, quant-LLM agreement >=70%, no catastrophic miss, internal consistency >=75%)
- [x] **UI-04**: Sidebar navigation contains only in-scope items (Dashboard, Agents, History, Paper Trading, Settings)
- [x] **UI-05**: Remove out-of-scope elements (Portfolio, Execute Trade, Markets, Secure Node hash, Terminal branding, user profile/tier)
- [x] **UI-06**: Quant/LLM balance slider defaults to 45/55 (not 30/70)
- [x] **UI-07**: Paper Trading sessions use date-based format ("Mar 29 - BEAR 65%") not session IDs
- [x] **UI-08**: Scenario Modal includes all flow data fields (FII daily, FII 5-Day, FII Futures OI change, DII daily, DII 5-Day, SIP Inflow)

### Auth & Routing

- [x] **AUTH-01**: Welcome.jsx is routed at /welcome and accessible to unauthenticated users
- [x] **AUTH-02**: AuthGate redirects unauthenticated users to /welcome (not blank screen)
- [x] **AUTH-03**: User can enter API key on Welcome page and proceed to dashboard
- [x] **AUTH-04**: Mock mode accessible from Welcome page without API key

### Backend Wiring

- [x] **BACK-01**: Learned skills are injected into agent prompts during simulation
- [x] **BACK-02**: SkillStore path is configurable via environment variable (not hardcoded to ~/.gods-eye/)
- [x] **BACK-03**: NSE data fallback displays visible staleness indicator to user
- [x] **BACK-04**: Agent interaction_effects populated (amplifies/dampened_by) instead of empty {}

### Frontend Polish

- [x] **FE-01**: All pages show proper loading states during API calls
- [x] **FE-02**: All pages show meaningful empty states when no data exists
- [x] **FE-03**: Error states display actionable messages (not blank screens)
- [x] **FE-04**: Live market ticker in dashboard header shows real-time Nifty/Sensex/VIX
- [x] **FE-05**: Simulation history supports CSV/JSON export
- [x] **FE-06**: Learning/Skills management page shows extracted skills per agent
- [x] **FE-07**: Dark mode theme consistent across all screens (Apple dark + Claude warm palette)

### Deployment

- [x] **DEP-01**: Backend deployed to Railway with persistent SQLite volume
- [x] **DEP-02**: Frontend deployed to Vercel with SPA rewrite and VITE_API_BASE configured
- [x] **DEP-03**: WebSocket streaming works in production (wss:// to Railway backend)
- [x] **DEP-04**: CORS configured for production Vercel domain
- [x] **DEP-05**: Skills directory uses persistent volume (not ephemeral container storage)
- [x] **DEP-06**: Environment variables documented in .env.example

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Differentiators

- **DIFF-01**: Pre-market scenario templates (Budget Day, RBI MPC, Expiry Week, Global Contagion)
- **DIFF-02**: Agent disagreement surfacing with visual conflict indicators
- **DIFF-03**: India VIX-aware framing in insights panel
- **DIFF-04**: Shareable simulation result cards (image export)
- **DIFF-05**: Outcome annotation with actual market data overlay

### Historical Data

- **HIST-01**: Historical price data backfill from NSE
- **HIST-02**: Backtesting simulations against historical data
- **HIST-03**: Agent accuracy tracking across market regimes

### Advanced Signals

- **SIG-01**: Order flow analysis integration
- **SIG-02**: Gamma exposure calculation
- **SIG-03**: Volatility surface visualization

## Out of Scope

| Feature | Reason |
|---------|--------|
| Live order execution | Simulation tool, not trading platform |
| Portfolio management | Not core to market intelligence value |
| Brokerage API integration | Educational/research tool |
| Mobile app | Web-first; defer to v2+ |
| Multi-user / SaaS | Single-user tool for now |
| Real-time charting (TradingView) | Would dilute simulation focus |
| Social features / chat | Not relevant to intelligence product |
| Freeform chatbot layer | Would dilute structured simulation paradigm |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-01 | Phase 1 — UI Alignment and Auth Routing | Complete |
| UI-02 | Phase 1 — UI Alignment and Auth Routing | Complete |
| UI-03 | Phase 1 — UI Alignment and Auth Routing | Complete |
| UI-04 | Phase 1 — UI Alignment and Auth Routing | Complete |
| UI-05 | Phase 1 — UI Alignment and Auth Routing | Complete |
| UI-06 | Phase 1 — UI Alignment and Auth Routing | Complete |
| UI-07 | Phase 1 — UI Alignment and Auth Routing | Complete |
| UI-08 | Phase 1 — UI Alignment and Auth Routing | Complete |
| AUTH-01 | Phase 1 — UI Alignment and Auth Routing | Complete |
| AUTH-02 | Phase 1 — UI Alignment and Auth Routing | Complete |
| AUTH-03 | Phase 1 — UI Alignment and Auth Routing | Complete |
| AUTH-04 | Phase 1 — UI Alignment and Auth Routing | Complete |
| BACK-01 | Phase 2 — Backend Wiring and Data Integrity | Complete |
| BACK-02 | Phase 2 — Backend Wiring and Data Integrity | Complete |
| BACK-03 | Phase 2 — Backend Wiring and Data Integrity | Complete |
| BACK-04 | Phase 2 — Backend Wiring and Data Integrity | Complete |
| FE-01 | Phase 3 — Frontend Polish and UX Completeness | Complete |
| FE-02 | Phase 3 — Frontend Polish and UX Completeness | Complete |
| FE-03 | Phase 3 — Frontend Polish and UX Completeness | Complete |
| FE-04 | Phase 3 — Frontend Polish and UX Completeness | Complete |
| FE-05 | Phase 3 — Frontend Polish and UX Completeness | Complete |
| FE-06 | Phase 3 — Frontend Polish and UX Completeness | Complete |
| FE-07 | Phase 3 — Frontend Polish and UX Completeness | Complete |
| DEP-01 | Phase 4 — Production Deployment and Verification | Complete |
| DEP-02 | Phase 4 — Production Deployment and Verification | Complete |
| DEP-03 | Phase 4 — Production Deployment and Verification | Complete |
| DEP-04 | Phase 4 — Production Deployment and Verification | Complete |
| DEP-05 | Phase 4 — Production Deployment and Verification | Complete |
| DEP-06 | Phase 4 — Production Deployment and Verification | Complete |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-31 after v2.0 roadmap creation*
