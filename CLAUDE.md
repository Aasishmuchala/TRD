<!-- GSD:project-start source:PROJECT.md -->
## Project

**God's Eye — Multi-Agent Indian Market Intelligence**

God's Eye is an India-specific multi-agent market intelligence system that simulates the behavioral forces driving Indian equity markets (NSE/BSE). Six AI agents — modeled on FII, DII, Retail F&O, Algo/Quant, Promoter/Insider, and RBI/Policy — independently analyze market scenarios and produce a weighted consensus on market direction and confidence.

**Core Value:** Deliver accurate, explainable multi-agent market direction calls that a derivatives trader on Dalal Street would actually use to think through scenarios before market open.

### Constraints

- **Tech stack**: Python + FastAPI backend, React + Tailwind + Recharts frontend — established, do not change
- **AI Engine**: Claude API via Anthropic SDK (backend uses generic httpx for multi-provider support)
- **Database**: SQLite Phase 1, PostgreSQL Phase 2
- **Deployment**: Vercel (frontend) + Railway/Render (backend)
- **Agent Architecture**: 8 agents (FII 0.27, DII 0.22, RETAIL_FNO 0.13, ALGO 0.17, PROMOTER 0.05, RBI 0.05, STOCK_OPTIONS 0.04, NEWS_EVENT 0.07). Sum=1.00. See `backend/app/config.py` for redistribution rationale.
- **Quant/LLM Balance**: 45% quant / 55% LLM (plan spec)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Context
- Backend: Python 3 + FastAPI + SQLite + httpx + pydantic (existing, do not change)
- Frontend: React 18 + Tailwind CSS 3 + Recharts + Vite 5 + React Router 6 (existing, do not change)
- AI: Multi-provider LLM client via httpx (existing)
## Recommended Stack
### Deployment Platforms
| Technology | Version/Tier | Purpose | Why Recommended |
|------------|-------------|---------|-----------------|
| Railway | Hobby ($5/mo) | FastAPI backend hosting | Native WebSocket support (confirmed), persistent volumes for SQLite + SkillStore, Dockerfile-based deploy matches existing backend/Dockerfile, consumption pricing stays under $5/mo for single-user tool |
| Vercel | Free (Hobby) | React/Vite frontend hosting | Zero-config Vite detection, automatic SPA rewrites via vercel.json, CDN edge delivery, free tier is genuinely free (not trial), CI/CD from Git with zero setup |
### Production Server (Backend)
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| gunicorn | 21.x | Process manager for FastAPI | Manages worker restarts, handles SIGTERM gracefully, industry standard for Python production servers |
| uvicorn workers (`uvicorn.workers.UvicornWorker`) | 0.34.x | ASGI worker class inside gunicorn | FastAPI requires ASGI; gunicorn alone cannot serve async code — the UvicornWorker bridges them |
### Environment Configuration (Backend)
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pydantic-settings | 2.x | Typed env var loading with BaseSettings | Already using Pydantic v2 for request schemas; pydantic-settings is the official companion package for config. Validates types, reads from env or .env file, works with Railway env vars without code changes. Do NOT add python-dotenv separately — pydantic-settings includes .env file support via `model_config = SettingsConfigDict(env_file=".env")` |
### Frontend UI Polish
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| sonner | 2.x (`npm i sonner`) | Toast notifications | 3KB gzipped (vs react-toastify at 11KB), no setup required beyond `<Toaster />`, adopted by shadcn/ui ecosystem, promise-based API fits the async simulation flow (`toast.promise(runSimulation(), {...})`). Works with React 18 without additional config |
| clsx | 2.x | Conditional className merging | Standard utility for Tailwind + conditional classes. Already used in most React/Tailwind projects. Replaces string concatenation anti-pattern. Pairs with `tailwind-merge` for deduplication |
| tailwind-merge | 3.x | Deduplicate conflicting Tailwind classes | Prevents `text-red-500 text-green-500` conflicts when composing components. Required when building reusable components that accept className props |
### Deployment Tooling
| Tool | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| Railway CLI | latest | Deploy, logs, env management from terminal | `railway up`, `railway logs`, `railway variables set KEY=VALUE` — faster than UI for iteration |
| Vercel CLI | latest | Deploy frontend, set env vars | `vercel --prod` triggers production deploy; `vercel env add VITE_API_BASE production` sets the critical env var |
## Installation
# Backend additions (requirements.txt)
# Frontend additions
# Deployment CLIs (local dev machine only, not in requirements)
# OR: brew install railway
## Critical Configuration Files
### railway.json (backend root)
### vercel.json (frontend root)
### Railway Volume Configuration
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Railway (Hobby $5/mo) | Render (Starter $7/mo) | Render if you need managed PostgreSQL (Phase 2 database migration) — their managed Postgres has PITR, read replicas. For SQLite + $0 DB cost now, Railway wins |
| Railway | Fly.io | Fly.io if you need multi-region for <50ms latency to Indian users. Fly has Mumbai region. Railway does not. Not needed at single-user scale |
| Railway | AWS ECS / DigitalOcean App Platform | If team grows >3 people or traffic exceeds 1000 req/day. Over-engineered for current scale |
| Vercel (frontend) | Netlify | Netlify is equally valid. Switch only if Vercel pricing becomes a concern (unlikely at hobby scale) |
| Vercel (frontend) | Cloudflare Pages | Cloudflare Pages if you need <50ms edge delivery to India. CF has Mumbai PoPs; Vercel does not have a Mumbai edge node. Not needed for single-user |
| gunicorn + uvicorn workers | Hypercorn standalone | Railway's official FastAPI template uses Hypercorn. Both work. gunicorn is more battle-tested for process supervision. Hypercorn is fine if you prefer a single-binary approach |
| `--workers 1` | `--workers 4` | Use 4 workers ONLY after migrating settings persistence to SQLite (eliminating the mutable config singleton) |
| sonner | react-toastify | react-toastify if the team is already familiar with it. sonner is smaller and more modern but either works |
| pydantic-settings | python-dotenv alone | python-dotenv if you do not want typed config validation. pydantic-settings is strictly better when you already use Pydantic — it validates types and gives IDE autocomplete on config values |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Render free tier | Sleeps after 15 min of inactivity. A trading tool pinged at market open (9:15 AM IST) after overnight silence will have a 60-second cold start — unacceptable | Railway Hobby $5/mo which keeps the container running |
| `gunicorn --workers 4` | Config singleton mutation (existing architecture) means settings changes in one worker are invisible to others. Non-deterministic behavior | `--workers 1` until settings persistence is fixed |
| `gunicorn --timeout 30` (default) | LLM simulation chains take 30-60 seconds. Default timeout kills requests mid-simulation with a 502 | `--timeout 180` |
| Vercel for backend hosting | Vercel runs serverless functions only — no persistent process, no WebSocket support, 10-second function timeout. FastAPI with WebSocket streaming cannot run on Vercel | Railway or Render for the backend |
| `allow_origins=["*"]` in CORS middleware | Already in the codebase for local dev. Shipping this to production allows any domain to make authenticated requests to the backend | Explicitly set `GODS_EYE_CORS_ORIGINS=https://your-app.vercel.app` in Railway env vars |
| sqlite3 DB file in container filesystem | Container filesystem is ephemeral on Railway — every deploy wipes the DB | Mount a Railway Volume at `/app/data` and set `GODS_EYE_DB_PATH=/app/data/gods_eye.db` |
| SkillStore at `~/.gods-eye/` in production | Root home directory in container is ephemeral; also a non-root user (appuser in Dockerfile) cannot write to `/root/`. Simulations run but skills are silently lost | Set `GODS_EYE_LEARNING_SKILL_DIR=/app/skills` on the same Railway Volume |
| Component libraries (shadcn/ui, Radix, MUI) | Adding a component library to an existing Tailwind + custom-components codebase mid-project causes style conflicts. The existing components are ~85% done — finishing them is faster than rewriting in a new library | Finish the existing Tailwind components; use sonner for toasts only |
| react-query / TanStack Query | The current api/client.js + useState hooks pattern is already working for this single-user tool. Adding TanStack Query is 1-2 days of migration for marginal benefit at current scale | Keep the existing fetch pattern; add only where it solves a real problem (e.g., polling for market data) |
## Stack Patterns by Variant
- Verify the volume is mounted at `/app/data` (not `/data` — Railway mounts relative to the working dir `/app`)
- Add `RAILWAY_RUN_UID=0` env var if permission errors appear (volumes default to root ownership)
- Check that the DB connection string uses the absolute path `/app/data/gods_eye.db`, not a relative path
- Railway supports WebSocket natively, no extra config needed
- Ensure gunicorn timeout (`--timeout 180`) does not terminate long-running simulation WebSocket sessions
- The WebSocket handler in `run.py` must not set a `ping_interval` shorter than the longest simulation round (~60s)
- Verify `VITE_API_BASE` is set in Vercel project settings under Environment Variables → Production
- The build command is `npm run build`, output dir is `dist` — Vercel auto-detects this for Vite
- Run `vercel env pull .env.local` to sync env vars to local for debugging
- The symptom is `Access-Control-Allow-Origin` header missing in browser console
- Fix: set `GODS_EYE_CORS_ORIGINS=https://your-app.vercel.app` in Railway variables
- Important: include the exact URL with `https://` — missing the protocol is the most common cause
## Version Compatibility
| Package | Compatible With | Notes |
|---------|-----------------|-------|
| pydantic-settings 2.x | pydantic 2.x | pydantic-settings 1.x was part of pydantic 1.x. If the existing codebase uses pydantic 2.x (likely given FastAPI 0.100+), use pydantic-settings 2.x. They are separate packages — install both |
| gunicorn 21.x | uvicorn 0.34.x | Use `uvicorn[standard]` for the full feature set including WebSocket support in the UvicornWorker |
| sonner 2.x | React 18 | sonner 2.x requires React 18+. Compatible with existing stack |
| tailwind-merge 3.x | Tailwind CSS 3.x | tailwind-merge 3.x is compatible with Tailwind 3. If upgrading to Tailwind 4 later, check tailwind-merge release notes |
| clsx 2.x | Any React version | No React dependency — pure string utility |
| Vercel CLI | Vite 5 | Vercel auto-detects Vite 5 projects. No special configuration needed beyond `vercel.json` for SPA routing |
## Sources
- Railway FastAPI deployment guide (verified current): https://docs.railway.com/guides/fastapi
- Railway volumes documentation: https://docs.railway.com/volumes
- Railway pricing plans (Hobby $5/mo, confirmed): https://docs.railway.com/pricing/plans
- Vercel Vite deployment documentation (SPA rewrites confirmed): https://vercel.com/docs/frameworks/frontend/vite
- FastAPI official deployment guide (gunicorn + UvicornWorker): https://fastapi.tiangolo.com/deployment/server-workers/
- FastAPI settings documentation (pydantic-settings): https://fastapi.tiangolo.com/advanced/settings/
- Render free tier sleep behavior (community forum, confirmed 15 min sleep): https://community.render.com/t/do-web-services-on-a-free-tier-go-to-sleep-after-some-time-inactive/3303
- Railway vs Render 2026 comparison: https://thesoftwarescout.com/railway-vs-render-2026-best-platform-for-deploying-apps/
- sonner npm registry (v2.0.7 confirmed): https://www.npmjs.com/package/sonner
- ARCHITECTURE.md (this project) — existing constraints and anti-patterns that drive stack decisions
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
