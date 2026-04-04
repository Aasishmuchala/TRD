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

### Active (v3.0 — Hybrid Trading Engine)

- [ ] Rules-based quantitative signal engine (FII/DII flows, PCR, RSI, VIX, Supertrend)
- [ ] Rewrite 6 agent prompts for signal-oriented analysis (not just qualitative commentary)
- [ ] Parallel fast agent calls (all 6 simultaneously, 1 round)
- [ ] Hybrid scoring: quantitative score (60%) + agent consensus (40%) → final signal
- [ ] LLM validator layer: 1 call to confirm/adjust/skip with explanation
- [ ] Fast backtesting on rules engine only (2 years in <10 seconds)
- [ ] Hybrid backtesting (rules + agents, 1 month in <5 minutes)
- [ ] Risk rules: position sizing, max loss per day, stop loss levels
- [ ] Updated dashboard showing both quant score + agent reasoning per signal

### Out of Scope

- Live order execution — simulation tool, not a trading platform
- Portfolio management — not core to market intelligence value
- Brokerage API integration — educational/research tool
- Mobile app — web-first; defer to v2+
- Multi-user / SaaS features — single-user tool
- Real-time charting (TradingView) — would dilute simulation focus
- Social features / chat — not relevant to intelligence product
- Freeform chatbot layer — would dilute structured simulation paradigm

## Current Milestone: v2.0 Backtesting & Signal Engine

**Goal:** Prove God's Eye has a tradeable edge by backtesting against historical Nifty/Bank Nifty data and building a technical signal engine that combines agent sentiment with indicators.

**Target features:**
- Historical OHLCV backfill via Dhan Data API
- Backtest engine replaying scenarios through agents
- Technical indicators (RSI, VWAP, Supertrend, OI change)
- Combined scoring: sentiment + technicals → signal
- Results dashboard: accuracy, P&L, max drawdown
- Nifty & Bank Nifty options focus

## Context

- **v1.0 shipped:** 4 phases, 14 plans — UI alignment, backend wiring, frontend polish, deployment config
- **v1.0 post-fixes:** WebSocket data_source, quant_llm_balance persistence, Dhan integration, agent reasoning UI
- **Current state:** Dhan API wired as sole data source, Kimi K2.5 via OpenRouter for LLM, simulations working locally
- **Trading focus:** Nifty & Bank Nifty options only
- **Codebase:** Python/FastAPI backend + React/Tailwind frontend

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
| Dhan as sole data source | NSE scraping unreliable, Dhan is authenticated + stable | ✓ Good — clean errors instead of silent fallback |
| OpenRouter + Kimi K2.5 | Cost-effective, capable model for agent reasoning | — Pending (testing) |
| Nifty/BankNifty options focus | Start narrow, prove edge, then expand | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

---
*Last updated: 2026-03-31 after v2.0 milestone start*
