# God's Eye — Multi-Agent Indian Market Intelligence

## What This Is

God's Eye is an India-specific multi-agent market intelligence system that simulates the behavioral forces driving Indian equity markets (NSE/BSE). Six AI agents — modeled on FII, DII, Retail F&O, Algo/Quant, Promoter/Insider, and RBI/Policy — independently analyze market scenarios through a 3-round debate and produce a weighted consensus on market direction and confidence. Features include real-time streaming simulation, accuracy-driven agent weight tuning, auto-learning skill extraction, and a complete React dashboard with agent detail, simulation history, paper trading, and skills management.

## Core Value

Deliver accurate, explainable multi-agent market direction calls that a derivatives trader on Dalal Street would actually use to think through scenarios before market open.

## Requirements

### Validated

- ✓ Canonical agent constants with plan-spec names, weights, colors — v1.0
- ✓ Auth routing: /welcome as public entry, AuthGate redirect — v1.0
- ✓ Sidebar with 5 in-scope nav items only — v1.0
- ✓ Quant/LLM balance slider at 45/55 default — v1.0
- ✓ 6 plan-spec graduation criteria with exact thresholds — v1.0
- ✓ Scenario Modal with all 6 flow data fields — v1.0
- ✓ Date-based paper trading session format — v1.0
- ✓ Skill injection into agent prompts via seeded SkillStore — v1.0
- ✓ Configurable SkillStore path via GODS_EYE_LEARNING_SKILL_DIR — v1.0
- ✓ AlgoQuantAgent interaction_effects populated — v1.0
- ✓ Per-round streaming progress labels — v1.0
- ✓ Error/empty states across Settings, PaperTrading, AgentDetail, Skills — v1.0
- ✓ Live market ticker (Nifty, Bank Nifty, VIX) — v1.0
- ✓ CSV export for simulation history — v1.0
- ✓ Learning/Skills management page — v1.0
- ✓ Dark mode palette consistency audit — v1.0
- ✓ Railway deployment config (Dockerfile, railway.toml, volumes) — v1.0
- ✓ Vercel deployment config (vercel.json, SPA rewrite) — v1.0
- ✓ WebSocket VITE_WS_BASE env var for production — v1.0
- ✓ .env.example files documenting all vars — v1.0

### Active

- [ ] Fix WebSocket data_source propagation (fallback banner invisible via streaming path)
- [ ] Persist quant_llm_balance in backend settings handler
- [ ] Populate graduation criteria fields in history API response
- [ ] Migrate PaperTrading.jsx from utils/colors to constants/agents import
- [ ] Actually deploy to Railway + Vercel (config ready, needs credentials)
- [ ] Historical price data backfill from NSE (backtesting enabler)

### Out of Scope

- Live order execution — simulation tool, not a trading platform
- Portfolio management — not core to market intelligence value
- Brokerage API integration — educational/research tool
- Mobile app — web-first; defer to v2+
- Multi-user / SaaS features — single-user tool
- Real-time charting (TradingView) — would dilute simulation focus
- Social features / chat — not relevant to intelligence product
- Freeform chatbot layer — would dilute structured simulation paradigm

## Context

- **v1.0 shipped:** 4 phases, 14 plans, 32 commits in one session
- **Codebase:** Python/FastAPI backend + React/Tailwind frontend, both production-ready
- **Deployment:** Config files ready (Railway + Vercel), pending user credentials
- **Known gaps:** 2 partial requirements (WebSocket data_source, quant_llm_balance persistence), graduation criteria fields not yet in history API
- **Sub-repo structure:** gods-eye/ has its own .git

## Constraints

- **Tech stack**: Python + FastAPI backend, React + Tailwind + Recharts frontend
- **AI Engine**: Multi-provider LLM client via httpx (OpenAI, Nous, custom)
- **Database**: SQLite (persistent volume at /app/data on Railway)
- **Deployment**: Vercel (frontend) + Railway (backend)
- **Agent Architecture**: 6 agents with weights (FII 0.30, DII 0.25, Retail 0.15, Algo 0.10, Promoter 0.10, RBI 0.10)
- **Quant/LLM Balance**: 45% quant / 55% LLM

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use plan agent names everywhere | Stitch mockups used inconsistent names | ✓ Good — all screens now consistent |
| Use plan's 6 graduation criteria | Stitch showed wrong criteria/thresholds | ✓ Good — exact plan thresholds implemented |
| Remove sidebar scope creep | Plan explicitly excludes Portfolio/Trade/Markets | ✓ Good — 5 clean nav items |
| Plan spec is source of truth over Stitch HTML | 32 divergences documented | ✓ Good — React aligned to plan |
| Quant/LLM default 45/55 | Plan spec; Stitch over-weighted LLM | ✓ Good — slider defaults correctly |
| Single worker gunicorn (-w 1) | Mutable config singleton breaks with multiple workers | ✓ Good — prevents state desync |
| VITE_WS_BASE env var for WebSocket | Vercel + Railway split means different hosts | ✓ Good — production-ready pattern |
| Seed 5 skills at startup | Empty SkillStore means no LEARNED PATTERNS block | ✓ Good — immediate value |

## Evolution

This document evolves at phase transitions and milestone boundaries.

---
*Last updated: 2026-03-30 after v1.0 milestone*
