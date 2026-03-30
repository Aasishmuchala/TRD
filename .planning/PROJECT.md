# God's Eye — Multi-Agent Indian Market Intelligence

## What This Is

God's Eye is an India-specific multi-agent market intelligence system that simulates the behavioral forces driving Indian equity markets (NSE/BSE). Six AI agents — modeled on FII, DII, Retail F&O, Algo/Quant, Promoter/Insider, and RBI/Policy — independently analyze market scenarios and produce a weighted consensus on market direction and confidence.

## Core Value

Deliver accurate, explainable multi-agent market direction calls that a derivatives trader on Dalal Street would actually use to think through scenarios before market open.

## Requirements

### Validated

- ✓ Backend simulation engine with 3-round agent interaction — existing
- ✓ 6 LLM agents + 1 quant agent with India-specific personas — existing
- ✓ Weighted consensus aggregator (quant/LLM hybrid scoring) — existing
- ✓ REST API + WebSocket streaming for real-time simulation — existing
- ✓ Live NSE market data fetching with fallback mocks — existing
- ✓ Accuracy feedback engine (auto-tunes agent weights) — existing
- ✓ Auto-learning system (skill extraction from simulations) — existing
- ✓ SQLite persistence with Alembic migrations — existing
- ✓ OAuth device code auth flow — existing
- ✓ Rate limiting + CORS — existing
- ✓ Frontend Dashboard with 6 panels (Scenario, Pressure, Insights, Accuracy, Feedback, Stream) — existing
- ✓ Frontend Agent Detail page with accuracy/pattern analysis — existing
- ✓ Frontend Simulation History with outcome recording — existing
- ✓ Frontend Paper Trading with graduation tracker — existing
- ✓ Frontend Settings with weight sliders + sim params — existing
- ✓ Frontend Welcome/Auth page — existing (not routed)
- ✓ Stitch UI mockups (7 HTML screens) in gods-eye-ui/ — existing

### Active

- [ ] Fix UI/design alignment (agent names, graduation criteria, scope creep in sidebar)
- [ ] Route Welcome.jsx and fix auth flow
- [ ] Wire skill injection into agent prompts
- [ ] Build Learning/Skills management UI
- [ ] Integrate live market ticker in dashboard
- [ ] Add simulation history export (CSV/JSON)
- [ ] Deploy backend (Railway/Render) and frontend (Vercel)
- [ ] Align Stitch HTML designs with React components

### Out of Scope

- Live order execution — simulation tool, not a trading platform
- Portfolio management — not in scope per plan
- Backtesting against historical data — Phase 2
- Mobile app — web-first
- Multi-user / SaaS features — single-user tool
- Real money or brokerage API integration — educational/research tool
- Blockchain/crypto features — "Secure Node" hash from Stitch is irrelevant

## Context

- **Existing codebase:** Brownfield project with functional backend (~95% complete) and frontend (~85% complete)
- **Two UI sources:** Stitch-generated HTML mockups (gods-eye-ui/) and React components (gods-eye/frontend/src/) — these diverge on agent names, weights, graduation criteria, and sidebar scope
- **Plan document:** `gods-eye-plan.md` is the source of truth for agent definitions, weights, thresholds, and architecture
- **Comparison doc:** `stitch-vs-plan-comparison.md` documents 32 differences across 7 categories with clear decisions needed
- **Tech stack:** Python/FastAPI backend, React/Tailwind/Recharts frontend, SQLite, Claude API
- **Sub-repo structure:** gods-eye/ has its own .git (separate repo within workspace)

## Constraints

- **Tech stack**: Python + FastAPI backend, React + Tailwind + Recharts frontend — established, do not change
- **AI Engine**: Claude API via Anthropic SDK (backend uses generic httpx for multi-provider support)
- **Database**: SQLite Phase 1, PostgreSQL Phase 2
- **Deployment**: Vercel (frontend) + Railway/Render (backend)
- **Agent Architecture**: 6 agents with specific weights (FII 0.30, DII 0.25, Retail 0.15, Algo 0.10, Promoter 0.10, RBI 0.10)
- **Quant/LLM Balance**: 45% quant / 55% LLM (plan spec)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use plan agent names everywhere (FII, DII, Retail F&O, Algo/Quant, Promoter, RBI) | Stitch mockups use inconsistent names across screens | — Pending |
| Use plan's 6 graduation criteria with exact thresholds | Stitch shows different criteria and thresholds | — Pending |
| Remove sidebar scope creep (Portfolio, Execute Trade, Markets) | Plan explicitly excludes these features | — Pending |
| Plan spec is source of truth over Stitch HTML | 32 divergences documented; plan has clearer reasoning | — Pending |
| Quant/LLM default 45/55 | Plan spec; Stitch shows 30/70 which over-weights LLM | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? Move to Out of Scope with reason
2. Requirements validated? Move to Validated with phase reference
3. New requirements emerged? Add to Active
4. Decisions to log? Add to Key Decisions
5. "What This Is" still accurate? Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-30 after initialization*
