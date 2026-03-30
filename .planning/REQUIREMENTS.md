# Requirements: God's Eye

**Defined:** 2026-03-30
**Core Value:** Deliver accurate, explainable multi-agent market direction calls that a derivatives trader on Dalal Street would actually use before market open.

## v1 Requirements

Requirements for production release. Each maps to roadmap phases.

### UI Alignment

- [ ] **UI-01**: All screens use consistent agent names: FII, DII, Retail F&O, Algo/Quant, Promoter, RBI
- [ ] **UI-02**: Agent weights match plan spec across all screens (0.30, 0.25, 0.15, 0.10, 0.10, 0.10)
- [ ] **UI-03**: Graduation criteria match plan's 6 thresholds (1-day >=57%, 1-week >=60%, calibration <15%, quant-LLM agreement >=70%, no catastrophic miss, internal consistency >=75%)
- [ ] **UI-04**: Sidebar navigation contains only in-scope items (Dashboard, Agents, History, Paper Trading, Settings)
- [ ] **UI-05**: Remove out-of-scope elements (Portfolio, Execute Trade, Markets, Secure Node hash, Terminal branding, user profile/tier)
- [ ] **UI-06**: Quant/LLM balance slider defaults to 45/55 (not 30/70)
- [ ] **UI-07**: Paper Trading sessions use date-based format ("Mar 29 - BEAR 65%") not session IDs
- [ ] **UI-08**: Scenario Modal includes all flow data fields (FII daily, FII 5-Day, FII Futures OI change, DII daily, DII 5-Day, SIP Inflow)

### Auth & Routing

- [ ] **AUTH-01**: Welcome.jsx is routed at /welcome and accessible to unauthenticated users
- [ ] **AUTH-02**: AuthGate redirects unauthenticated users to /welcome (not blank screen)
- [ ] **AUTH-03**: User can enter API key on Welcome page and proceed to dashboard
- [ ] **AUTH-04**: Mock mode accessible from Welcome page without API key

### Backend Wiring

- [ ] **BACK-01**: Learned skills are injected into agent prompts during simulation
- [ ] **BACK-02**: SkillStore path is configurable via environment variable (not hardcoded to ~/.gods-eye/)
- [ ] **BACK-03**: NSE data fallback displays visible staleness indicator to user
- [ ] **BACK-04**: Agent interaction_effects populated (amplifies/dampened_by) instead of empty {}

### Frontend Polish

- [ ] **FE-01**: All pages show proper loading states during API calls
- [ ] **FE-02**: All pages show meaningful empty states when no data exists
- [ ] **FE-03**: Error states display actionable messages (not blank screens)
- [ ] **FE-04**: Live market ticker in dashboard header shows real-time Nifty/Sensex/VIX
- [ ] **FE-05**: Simulation history supports CSV/JSON export
- [ ] **FE-06**: Learning/Skills management page shows extracted skills per agent
- [ ] **FE-07**: Dark mode theme consistent across all screens (Apple dark + Claude warm palette)

### Deployment

- [ ] **DEP-01**: Backend deployed to Railway with persistent SQLite volume
- [ ] **DEP-02**: Frontend deployed to Vercel with SPA rewrite and VITE_API_BASE configured
- [ ] **DEP-03**: WebSocket streaming works in production (wss:// to Railway backend)
- [ ] **DEP-04**: CORS configured for production Vercel domain
- [ ] **DEP-05**: Skills directory uses persistent volume (not ephemeral container storage)
- [ ] **DEP-06**: Environment variables documented in .env.example

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
| UI-01 | Phase 1 | Pending |
| UI-02 | Phase 1 | Pending |
| UI-03 | Phase 1 | Pending |
| UI-04 | Phase 1 | Pending |
| UI-05 | Phase 1 | Pending |
| UI-06 | Phase 1 | Pending |
| UI-07 | Phase 1 | Pending |
| UI-08 | Phase 1 | Pending |
| AUTH-01 | Phase 1 | Pending |
| AUTH-02 | Phase 1 | Pending |
| AUTH-03 | Phase 1 | Pending |
| AUTH-04 | Phase 1 | Pending |
| BACK-01 | Phase 2 | Pending |
| BACK-02 | Phase 2 | Pending |
| BACK-03 | Phase 2 | Pending |
| BACK-04 | Phase 2 | Pending |
| FE-01 | Phase 3 | Pending |
| FE-02 | Phase 3 | Pending |
| FE-03 | Phase 3 | Pending |
| FE-04 | Phase 3 | Pending |
| FE-05 | Phase 3 | Pending |
| FE-06 | Phase 3 | Pending |
| FE-07 | Phase 3 | Pending |
| DEP-01 | Phase 4 | Pending |
| DEP-02 | Phase 4 | Pending |
| DEP-03 | Phase 4 | Pending |
| DEP-04 | Phase 4 | Pending |
| DEP-05 | Phase 4 | Pending |
| DEP-06 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after initial definition*
