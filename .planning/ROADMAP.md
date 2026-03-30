# Roadmap: God's Eye — Multi-Agent Indian Market Intelligence

## Overview

God's Eye is approximately 90% functionally complete. The path to production is not greenfield engineering — it is four sequential gate-checks, each of which must fully pass before the next begins. Phase 1 eliminates all functional divergences between the Stitch UI mockups and the plan spec (agent names, weights, graduation criteria, auth routing) so every downstream phase builds on a correct foundation. Phase 2 wires the backend behaviors that affect product trustworthiness: skill injection into agent prompts and visible data freshness indicators. Phase 3 builds the full user-facing quality layer before anything ships publicly. Phase 4 deploys to Railway and Vercel with every production-blocking pitfall from research actively verified.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: UI Alignment and Auth Routing** - Eliminate all functional divergences between Stitch mockups and the plan spec; route Welcome.jsx and fix AuthGate (completed 2026-03-30)
- [ ] **Phase 2: Backend Wiring and Data Integrity** - Wire skill injection into agent prompts, fix SkillStore container path, surface NSE data freshness in UI
- [ ] **Phase 3: Frontend Polish and UX Completeness** - Add loading states, empty states, error states, live market ticker, CSV export, Learning/Skills page, and dark mode consistency
- [ ] **Phase 4: Production Deployment and Verification** - Deploy to Railway and Vercel with persistent volumes, correct CORS, wss:// WebSocket, and documented env vars

## Phase Details

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
- [ ] 02-02-PLAN.md — Populate AlgoQuantAgent interaction_effects from computed signals (BACK-04)
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
**Plans**: TBD

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
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. UI Alignment and Auth Routing | 4/4 | Complete   | 2026-03-30 |
| 2. Backend Wiring and Data Integrity | 2/3 | In Progress|  |
| 3. Frontend Polish and UX Completeness | 0/TBD | Not started | - |
| 4. Production Deployment and Verification | 0/TBD | Not started | - |
