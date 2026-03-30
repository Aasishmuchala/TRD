# Project Research Summary

**Project:** God's Eye — Multi-Agent Indian Market Intelligence System
**Domain:** AI-powered market simulation tool for Indian derivatives traders
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Summary

God's Eye is a brownfield deployment project: the backend simulation engine (Python/FastAPI + SQLite + 6 LLM agents), frontend dashboard (React 18 + Tailwind + Recharts), and core product logic are approximately 90% functionally complete. The work ahead is not greenfield engineering — it is precision polish, critical wiring, and production deployment. The recommended approach is to treat this as a sequence of gate-checks: UI alignment first, then auth routing, then deployment infrastructure, then feature completion. Each gate must fully pass before proceeding, because downstream work is dependent on the correctness of upstream layers.

The deployment target is Railway (backend, Hobby $5/mo) + Vercel (frontend, free tier). This combination supports WebSocket streaming natively and keeps SQLite persistence viable via Railway Volumes. The architecture is sound and well-separated, but has five specific production-blocking gaps: an unrouted auth page, a mutable config singleton incompatible with multi-worker deployments, a SkillStore path that breaks under non-root container users, missing CORS production configuration, and VITE_API_BASE not set for the Vercel frontend. None of these require architectural change — they are operational and wiring issues.

The biggest risk is shipping Stitch UI divergences to production. The 32 documented discrepancies between the Stitch mockups and the plan spec include functional mismatches (wrong agent names, incorrect slider defaults, graduation criteria thresholds) that will directly contradict backend output. Users comparing what the settings slider shows versus what the system actually computes will lose trust immediately. This must be the first phase — a systematic reconcile pass that resolves all 10 plan decisions from stitch-vs-plan-comparison.md before any other work proceeds.

---

## Key Findings

### Recommended Stack

The existing stack (FastAPI + React/Vite + SQLite + Recharts + Tailwind) is locked and correct — do not add new architectural dependencies. The deployment additions are minimal: `pydantic-settings` for typed env var loading, `gunicorn` + `uvicorn[standard]` for production ASGI serving, and `sonner` + `clsx` + `tailwind-merge` for frontend polish. The critical configuration decision is `--workers 1` for gunicorn — the mutable config singleton in the existing codebase means 4 workers will produce non-deterministic behavior when settings are changed. Single worker is the correct choice for a single-user tool with SQLite.

**Core technologies:**
- Railway (Hobby $5/mo): Backend hosting — keeps container alive 24/7 (Render free tier sleeps after 15 min, unacceptable for pre-market use)
- Vercel (free tier): Frontend hosting — zero-config Vite detection, requires `vercel.json` SPA rewrite stanza for React Router
- gunicorn + UvicornWorker: Production ASGI serving — `--workers 1 --timeout 180` (LLM chains take 30-60s, default 30s timeout kills mid-simulation)
- pydantic-settings 2.x: Typed config with automatic Railway env var injection, replaces existing config dataclass
- sonner 2.x: Toast notifications, 3KB gzipped, promise-based API fits async simulation flow
- Railway Volumes: Two mounts required — `/app/data` for SQLite, `/app/skills` for SkillStore YAML files

### Expected Features

The prototype is approximately 90% functionally complete. What separates "working prototype" from "shippable product" for a Dalal Street derivatives trader is trust signals: data freshness visibility, consistent naming, readable confidence labels, and dark-first UI matching the aesthetic standard set by Zerodha Kite and Sensibull.

**Must have (table stakes):**
- Agent naming consistency everywhere — FII/DII/Algo Quant/Promoter/RBI must match across all UI surfaces, API responses, history records, and export labels. Currently diverges between Stitch HTML and React components.
- Auth flow end-to-end — Welcome.jsx exists but is unrouted; AuthGate renders nothing when unauthenticated
- Error states for simulation and data fetch failures — blank screens on LLM or NSE failure are unacceptable
- Loading indicators showing per-round progress — WebSocket stream already sends events; UI must render Round 1 of 3, Round 2 of 3
- Data freshness label — always-visible "Live / Cached / Mock" indicator; NSE fallback data must never be silently treated as live
- Readable consensus labels — map numeric score to "Strongly Bullish / High Conviction" style labels
- Dark mode — all serious Indian trading tools are dark-first; light mode signals "not built for traders"
- Mobile-responsive dashboard — 70%+ of Indian retail market activity is mobile; dashboard and history must be readable at 375px
- Skill injection wired — auto-learned skills must reach agent prompts; Learning/Skills UI must show what was learned
- Live NSE ticker strip — Nifty, Bank Nifty, India VIX on dashboard header
- Simulation history CSV export — full per-simulation record with agent calls, consensus, outcome
- Sidebar scope cleanup — remove Portfolio, Execute Trade, Markets links from Stitch HTML
- Deployment — publicly accessible Railway + Vercel URLs

**Should have (differentiators, v1.x after validation):**
- Pre-market scenario templates (RBI MPC, FII sell-off, Budget day, Weekly expiry) — reduces friction from 2 minutes to 10 seconds
- Agent disagreement surfacing — FII vs DII divergence as signal, not just consensus number
- India VIX-aware simulation framing — "VIX elevated — confidence bands widen" when VIX > 18
- Outcome annotation field — free-text annotation on recorded outcomes for learning journal
- Simulation result share card — PNG image for WhatsApp/Telegram community sharing
- Session persistence — last scenario inputs survive page refresh via localStorage

**Defer (v2+):**
- Backtesting against historical NSE data — data licensing required, explicitly deferred in PROJECT.md
- Email digest reminders — disproportionate infra for single-user tool
- Multi-user / team access — explicit out-of-scope per PROJECT.md
- Mobile app (PWA or native) — responsive web covers v1 mobile use case
- WhatsApp/Telegram bot integration — scope explosion, share-as-image covers the use case manually

**Anti-features to avoid:**
- Live order execution / broker integration — SEBI regulatory liability, out of scope
- Portfolio P&L tracking — requires separate auth/billing/reconciliation product
- Real-time charting — TradingView and Kite already do this; link out instead
- AI chatbot on dashboard — undermines the structured simulation paradigm that makes the product trustworthy

### Architecture Approach

The architecture is layered correctly: React SPA communicates exclusively via `api/client.js` (REST + WebSocket), FastAPI routes dispatch to either the batch `Orchestrator` or `StreamingOrchestrator`, agents call the LLM in parallel using `asyncio.wait(FIRST_COMPLETED)`, background skill extraction runs fire-and-forget via `asyncio.create_task()`, and accuracy feedback closes the loop via `FeedbackEngine` which tunes agent weights from SQLite accuracy history. The dual orchestration pattern (batch + streaming) is correct and intentional — do not refactor it. Production deployment requires no architectural changes, only operational configuration.

**Major components:**
1. StreamingOrchestrator — 3-round parallel LLM simulation yielding per-agent events to WebSocket; agents appear in actual completion order (not faked animation)
2. FeedbackEngine + AgentMemory — accuracy-weighted agent tuning; activates after 50+ predictions per agent; the differentiator that makes God's Eye self-improving
3. SimulationReviewEngine — background skill extraction via LLM after each simulation; stores patterns to SkillStore YAML; feeds ProfileGenerator context enrichment
4. MarketDataService — NSE live data with session cookie management, 60s TTL cache, and fallback to mock data; data_source field in responses must be surfaced in UI
5. Railway Volume (two mounts) — `/app/data` for SQLite persistence, `/app/skills` for SkillStore; both are ephemeral without explicit volume configuration

### Critical Pitfalls

1. **Stitch UI divergence shipped to production** — 32 documented discrepancies include functional bugs (wrong agent names, Settings slider defaults to 70% LLM vs correct 45%, graduation criteria threshold mismatch). Execute all 10 decisions from stitch-vs-plan-comparison.md Section 9 as a single dedicated phase before any other work. Warning sign: Settings.jsx slider initial value is not 45.

2. **SQLite data lost on redeploy** — Railway container filesystem is ephemeral; every deploy wipes simulation history, agent accuracy records, and learned skills with no error message. Fix: attach Railway Volume at `/app/data` for SQLite and `/app/skills` for SkillStore; set `GODS_EYE_DB_PATH=/app/data/gods_eye.db` and `GODS_EYE_LEARNING_SKILL_DIR=/app/skills`. Verify by deliberately redeploying and checking history count persists.

3. **WebSocket connects to localhost in production** — `VITE_API_BASE` not set in Vercel environment variables causes `ws://` connections to silently target `your-vercel-app.vercel.app` (which does not serve WebSocket). Fix: set `VITE_API_BASE=https://your-railway-backend.railway.app` in Vercel project settings before first deploy. Also: HTTPS backends require `wss://`, not `ws://`.

4. **CORS blocks all production API calls** — Backend CORS defaults to `localhost`. The Vercel frontend URL is not in the allowlist. Fix: set `GODS_EYE_CORS_ORIGINS=https://gods-eye.vercel.app` in Railway environment variables before deploying. Warning sign: curl to backend returns 200 but browser shows CORS error.

5. **NSE fallback data used silently** — After 10-50 requests, NSE anti-bot detection triggers and all subsequent market data calls silently return hardcoded fallback values (Nifty: 22,400, VIX: 14.2) that haven't changed since the fallback was written. Fix: surface `data_source` field from API responses as a persistent banner in the dashboard UI; never let "offline data" be invisible to the user.

6. **Skill injection produces zero effect on fresh deployment** — SkillStore starts empty; skills only accumulate after many simulations under specific conditions; if the skills volume is not persisted across redeploys, weeks of learning are lost. Fix: seed 3-5 hand-authored skills per agent covering obvious India market patterns (VIX > 22, expiry week, budget day) before launch. Also: fix SkillStore container path from `~/.gods-eye/skills/` to `/app/skills` to avoid non-root user write permission failure.

7. **Auth flow shows blank screen** — `Welcome.jsx` exists but is not routed in `App.jsx`; `AuthGate` renders `null` when unauthenticated. Fix: add `<Route path="/welcome" element={<Welcome />} />` and redirect `AuthGate` to `/welcome` instead of rendering nothing.

---

## Implications for Roadmap

Based on research, the natural phase structure follows the dependency chain identified in ARCHITECTURE.md's build order, FEATURES.md's dependency graph, and PITFALLS.md's phase-to-pitfall mapping. Each phase gates the next.

### Phase 1: UI Alignment and Stitch Reconciliation

**Rationale:** The 32 Stitch divergences include functional bugs that will contradict backend output in production. Fixing these first ensures every subsequent phase builds on a correct UI foundation. Agent naming consistency is a prerequisite for history, export, and agent detail features. This phase has no external dependencies and can be fully verified against the plan spec without deployment.

**Delivers:** Correct agent names on all surfaces, Settings slider at 45% (matching backend config), 6-item graduation criteria matching plan thresholds, sidebar with out-of-scope items removed, Welcome.jsx routed and AuthGate redirecting to `/welcome`.

**Addresses:** Agent naming consistency, auth flow end-to-end, sidebar scope cleanup (all P1 from FEATURES.md)

**Avoids:** Stitch divergence pitfall (Pitfall 2), auth blank screen pitfall (Pitfall 4)

**Research flag:** No additional research needed — stitch-vs-plan-comparison.md Section 9 provides exact checklist of 10 items.

### Phase 2: Backend Wiring and Data Integrity

**Rationale:** Skill injection is architecturally complete but functionally silent (SkillStore path bug, empty skills on fresh deployment). NSE fallback data is invisible to users. These are data-integrity issues that affect the core product trustworthiness and must be resolved before deployment.

**Delivers:** Skill injection verified end-to-end (enriched_context contains LEARNED PATTERNS), hand-seeded skills per agent, SkillStore container path fixed to `/app/skills`, data freshness label surfaced in dashboard, `data_source: "fallback"` rendered as visible banner, gunicorn worker count set to 1.

**Addresses:** Skill injection wired, data freshness label (P1 from FEATURES.md)

**Avoids:** Skill injection zero-effect pitfall (Pitfall 6), NSE fallback invisible pitfall (Pitfall 5), mutable config singleton anti-pattern (ARCHITECTURE.md Anti-Pattern 2)

**Research flag:** No additional research needed — codebase inspection has identified the exact fixes.

### Phase 3: Frontend Polish and UX Completeness

**Rationale:** With correct data wiring and UI alignment complete, this phase builds the full user-facing quality layer: per-round simulation progress, readable confidence labels, error states, empty states, dark mode, mobile responsiveness, CSV export, and live NSE ticker strip. These are all P1 launch requirements from FEATURES.md with LOW-MEDIUM implementation complexity.

**Delivers:** Per-round loading indicators (Round 1 of 3 via WebSocket events), consensus readable labels ("Strongly Bullish / High Conviction"), error states for simulation and data fetch failures, empty states for history and accuracy charts, dark-first UI across all pages, mobile-responsive dashboard at 375px, CSV export with per-simulation agent calls, live Nifty/Bank Nifty/India VIX ticker strip.

**Uses:** sonner for toast notifications, clsx + tailwind-merge for conditional className management

**Addresses:** All remaining P1 features from FEATURES.md

**Avoids:** UX pitfall of simulation running with no progress feedback, "OFFLINE DATA mode is invisible" UX pitfall

**Research flag:** No additional research needed — patterns are well-documented and libraries are confirmed compatible.

### Phase 4: Production Deployment and Verification

**Rationale:** Deploy only after UI alignment, data integrity, and UX polish are complete. The deployment phase is where all the pre-deployment configuration (CORS, VITE_API_BASE, Railway Volumes, gunicorn command) must be verified end-to-end. The "looks done but isn't" checklist from PITFALLS.md provides the exact verification protocol.

**Delivers:** Backend running on Railway with persistent volumes (`/app/data`, `/app/skills`), frontend deployed on Vercel with correct `VITE_API_BASE` and `vercel.json` SPA rewrite, CORS configured with exact Vercel URL, WebSocket connecting via `wss://`, SQLite persisting across redeploys, mock mode disabled in production.

**Uses:** railway.json with gunicorn `--workers 1 --timeout 180`, vercel.json with SPA rewrite, pydantic-settings for Railway env var injection, Railway CLI + Vercel CLI for deployment

**Avoids:** SQLite data loss pitfall (Pitfall 3), WebSocket localhost pitfall (Pitfall 1), CORS blocking pitfall (Pitfall 7), mock mode silent in production (Technical Debt)

**Verification checklist (from PITFALLS.md):**
- `/api/health` shows `"mock_mode": false`
- Browser devtools confirms `wss://` connection succeeds
- 5 simulations run, redeploy triggered, history still shows 5 records
- `Access-Control-Allow-Origin` header present in browser network tab
- `VITE_API_BASE` set in Vercel environment variables panel

**Research flag:** No additional research needed — all configuration is documented in STACK.md with exact file contents.

### Phase 5: Differentiators and v1.x Features

**Rationale:** With a stable deployed product, add the features that create stickiness and competitive differentiation. These are all v1.x items from FEATURES.md — high value, low implementation cost, but require the live deployment to validate user behavior before committing.

**Delivers:** Pre-market scenario templates (RBI MPC, FII sell-off, Budget day, Weekly expiry, SGX gap, Monthly expiry), agent disagreement surfacing (FII vs DII divergence indicator), India VIX-aware framing (VIX > 18 annotation), outcome annotation field, simulation result share card (PNG for WhatsApp/Telegram), session persistence (last scenario inputs via localStorage).

**Addresses:** P2 features from FEATURES.md feature prioritization matrix

**Research flag:** Pre-market scenario templates may need user research on which scenarios are most commonly used. Agent disagreement surfacing and VIX-aware framing are well-defined and need no research.

### Phase Ordering Rationale

- **UI first** because Stitch divergence is a functional bug, not cosmetic, and all downstream work (history display, agent detail, export labels) depends on correct naming
- **Backend wiring before deployment** because deploying with silent skill injection failure or invisible fallback data means the live product is technically wrong from day one
- **Frontend polish before deployment** because UX completeness (dark mode, mobile, error states) determines whether the deployed product passes first-impression user judgment
- **Deployment after polish** because deploying is not the goal — deploying a product ready for use is
- **Differentiators after deployment validation** because v1.x features should be informed by actual user behavior on the live product

### Research Flags

Phases with standard patterns (no additional research needed):
- **Phase 1 (UI Alignment):** Fully documented in stitch-vs-plan-comparison.md Section 9 — pure execution
- **Phase 2 (Backend Wiring):** Codebase inspection identified exact fixes; no external dependencies
- **Phase 3 (Frontend Polish):** Tailwind dark mode, mobile-responsive patterns, and error state UX are well-documented
- **Phase 4 (Deployment):** STACK.md provides exact configuration file contents; Railway and Vercel docs confirmed

Phases that may benefit from lightweight research during planning:
- **Phase 5 (Differentiators):** Pre-market scenario templates need user research to confirm which 6-8 scenarios to build first. India VIX threshold annotation (VIX > 18) should be validated against current NSE options trader conventions.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Deployment platforms verified against current Railway/Vercel docs; library versions confirmed via npm/PyPI; gunicorn/uvicorn pattern from FastAPI official docs |
| Features | MEDIUM | Indian trading ecosystem (Sensibull, StockEdge, Trendlyne) well-studied; multi-agent simulation product analogues are sparse — feature prioritization is reasoned inference from competitive analysis, not direct evidence |
| Architecture | HIGH | Based on direct codebase inspection of gods-eye/ source files; component boundaries and data flows are confirmed, not inferred |
| Pitfalls | HIGH | 7 critical pitfalls grounded in codebase inspection + verified with current platform docs; stitch-vs-plan-comparison.md and LAUNCH_PLAN.md provide first-party documentation of known issues |

**Overall confidence:** HIGH

### Gaps to Address

- **NSE data reliability long-term:** NSE's public API is not a licensed product. The current session cookie approach will continue to face anti-bot mitigation. For Phase 5+, consider whether a licensed NSE data feed (e.g., via a broker API like Zerodha's Kite Connect) is worth the integration cost. Not urgent for single-user v1 given the fallback visibility fix in Phase 2.
- **FeedbackEngine activation threshold:** The accuracy feedback loop requires 50+ predictions per agent before activating. A fresh deployment will run on fixed base weights until enough simulations accumulate. Users should be informed of this via a "Learning status" indicator (skills count + predictions toward activation). This gap is partially addressed by the skill injection UI in Phase 2 but the prediction count threshold is not yet surfaced.
- **Pre-market scenario selection:** The 6-8 scenario templates proposed are based on general Indian market event categories. Actual derivatives traders may have different priority scenarios (e.g., F&O expiry day may matter more than Budget day for options traders). Phase 5 should validate with at least one target user before building all 8 templates.
- **OAuth device flow production validation:** The device auth flow works locally (token file already present) but has never been tested from a fresh production environment with no existing token. This must be tested explicitly during Phase 4 deployment verification by clearing the auth state and completing the full unauthenticated flow.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `/TRD/TRD/gods-eye/backend/` and `/TRD/TRD/gods-eye/frontend/src/` — architecture, component boundaries, data flows
- `stitch-vs-plan-comparison.md` — 32 UI divergences, 10 reconciliation decisions
- `LAUNCH_PLAN.md` — documented bugs, data issues, deployment steps
- `QA_REPORT.md` — known limitations including NSE rate limiting and mock-mode-only testing
- Railway FastAPI deployment guide: https://docs.railway.com/guides/fastapi
- Railway volumes documentation: https://docs.railway.com/volumes
- Vercel Vite deployment documentation: https://vercel.com/docs/frameworks/frontend/vite
- FastAPI deployment guide (gunicorn + UvicornWorker): https://fastapi.tiangolo.com/deployment/server-workers/
- Vercel WebSocket limitation (official): https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections

### Secondary (MEDIUM confidence)
- Railway vs Render 2026 comparison: https://thesoftwarescout.com/railway-vs-render-2026-best-platform-for-deploying-apps/
- Sensibull feature documentation and review: https://sensibull.com / https://www.strike.money/reviews/sensibull
- StockEdge, Tickertape, Trendlyne comparison: https://help.trendlyne.com/support/solutions/articles/84000396310
- AI tools for Indian stock market 2025: https://thefingain.com/free-ai-tools-for-stock-analysis-india/
- sonner npm registry (v2.0.7 confirmed): https://www.npmjs.com/package/sonner
- Dark mode UX for trading tools: https://www.tradesviz.com/blog/darkmode/
- 7 Ways Multi-Agent AI Fails in Production: https://www.techaheadcorp.com/blog/ways-multi-agent-ai-fails-in-production/
- Why AI Agent Pilots Fail in Production: https://composio.dev/blog/why-ai-agent-pilots-fail-2026-integration-roadmap

### Tertiary (LOW confidence)
- NSE India scraping legality and anti-bot: https://www.quora.com/Is-data-scraping-from-NSE-and-BSE-website-illegal — community source, approach cautiously

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
