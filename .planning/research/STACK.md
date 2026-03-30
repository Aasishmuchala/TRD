# Stack Research

**Domain:** Deployment and polish for existing Python/FastAPI + React/Vite app — God's Eye market intelligence system
**Researched:** 2026-03-30
**Confidence:** HIGH (deployment platforms verified against current docs; library versions confirmed via npm/PyPI)

---

## Context

This is a brownfield deployment milestone. The core stack is locked:
- Backend: Python 3 + FastAPI + SQLite + httpx + pydantic (existing, do not change)
- Frontend: React 18 + Tailwind CSS 3 + Recharts + Vite 5 + React Router 6 (existing, do not change)
- AI: Multi-provider LLM client via httpx (existing)

Research below covers: deployment platforms, production server config, environment management, UI polish libraries, and deployment tooling. All choices preserve the existing stack without introducing new architectural dependencies.

---

## Recommended Stack

### Deployment Platforms

| Technology | Version/Tier | Purpose | Why Recommended |
|------------|-------------|---------|-----------------|
| Railway | Hobby ($5/mo) | FastAPI backend hosting | Native WebSocket support (confirmed), persistent volumes for SQLite + SkillStore, Dockerfile-based deploy matches existing backend/Dockerfile, consumption pricing stays under $5/mo for single-user tool |
| Vercel | Free (Hobby) | React/Vite frontend hosting | Zero-config Vite detection, automatic SPA rewrites via vercel.json, CDN edge delivery, free tier is genuinely free (not trial), CI/CD from Git with zero setup |

**Railway vs Render decision:** Railway wins for this project. Render's free tier sleeps after 15 min of inactivity — unacceptable for a trading tool (cold start during market open). Railway Hobby at $5/mo keeps the container alive. The single-user nature means consumption stays well under $5/mo in resource usage.

**Vercel vs Netlify/Cloudflare Pages:** Vercel wins because Vite SPA routing is supported with a single `vercel.json` stanza. All three are viable — Vercel is the most documented for Vite specifically.

### Production Server (Backend)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| gunicorn | 21.x | Process manager for FastAPI | Manages worker restarts, handles SIGTERM gracefully, industry standard for Python production servers |
| uvicorn workers (`uvicorn.workers.UvicornWorker`) | 0.34.x | ASGI worker class inside gunicorn | FastAPI requires ASGI; gunicorn alone cannot serve async code — the UvicornWorker bridges them |

**Workers count:** Use `--workers 1` for this project, not 4. The existing `config` singleton (Pattern 4 in ARCHITECTURE.md) is mutated per-request for settings. 4 workers means settings changes are non-deterministic. 1 worker is correct for a single-user tool. SQLite also serializes writes — more workers add contention, not throughput.

**Start command:**
```bash
gunicorn run:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 180
```
The `--timeout 180` is critical: LLM simulation chains take 30-60 seconds. Default gunicorn timeout (30s) will kill requests mid-simulation.

### Environment Configuration (Backend)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pydantic-settings | 2.x | Typed env var loading with BaseSettings | Already using Pydantic v2 for request schemas; pydantic-settings is the official companion package for config. Validates types, reads from env or .env file, works with Railway env vars without code changes. Do NOT add python-dotenv separately — pydantic-settings includes .env file support via `model_config = SettingsConfigDict(env_file=".env")` |

**Pattern to use:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GODS_EYE_", env_file=".env", env_file_encoding="utf-8")
    cors_origins: list[str] = ["http://localhost:5173"]
    mock_mode: bool = False
    ...
```
The existing `config.py` already uses a dataclass; migrating to `BaseSettings` adds automatic Railway env var injection with zero runtime overhead.

### Frontend UI Polish

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| sonner | 2.x (`npm i sonner`) | Toast notifications | 3KB gzipped (vs react-toastify at 11KB), no setup required beyond `<Toaster />`, adopted by shadcn/ui ecosystem, promise-based API fits the async simulation flow (`toast.promise(runSimulation(), {...})`). Works with React 18 without additional config |
| clsx | 2.x | Conditional className merging | Standard utility for Tailwind + conditional classes. Already used in most React/Tailwind projects. Replaces string concatenation anti-pattern. Pairs with `tailwind-merge` for deduplication |
| tailwind-merge | 3.x | Deduplicate conflicting Tailwind classes | Prevents `text-red-500 text-green-500` conflicts when composing components. Required when building reusable components that accept className props |

**Do NOT add:** shadcn/ui, Radix UI, Headless UI, or any component library. The existing Tailwind + Recharts components are already built. Adding a component library mid-project causes style conflicts and doubles the migration work.

### Deployment Tooling

| Tool | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| Railway CLI | latest | Deploy, logs, env management from terminal | `railway up`, `railway logs`, `railway variables set KEY=VALUE` — faster than UI for iteration |
| Vercel CLI | latest | Deploy frontend, set env vars | `vercel --prod` triggers production deploy; `vercel env add VITE_API_BASE production` sets the critical env var |

---

## Installation

```bash
# Backend additions (requirements.txt)
pydantic-settings>=2.0.0
gunicorn>=21.0.0
uvicorn[standard]>=0.34.0

# Frontend additions
npm install sonner clsx tailwind-merge

# Deployment CLIs (local dev machine only, not in requirements)
npm install -g vercel
pip install railway
# OR: brew install railway
```

---

## Critical Configuration Files

### railway.json (backend root)

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "backend/Dockerfile"
  },
  "deploy": {
    "startCommand": "gunicorn run:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 180",
    "healthcheckPath": "/api/health",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### vercel.json (frontend root)

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

This is mandatory. Without it, React Router 6 routes like `/agent/FII` return 404 on page refresh because Vercel looks for a physical file at that path.

### Railway Volume Configuration

Mount path: `/app/data` for SQLite database (`gods_eye.db`)
Mount path: `/app/skills` for SkillStore YAML files

The existing `docker-compose.yml` uses `~/.gods-eye/skills` which maps to `/root/.gods-eye/skills` inside the container. On Railway, override with:
```
GODS_EYE_LEARNING_SKILL_DIR=/app/skills
GODS_EYE_DB_PATH=/app/data/gods_eye.db
```
Both paths must be on the mounted Railway volume, not the container filesystem (which is ephemeral and resets on every deploy).

---

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

---

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

---

## Stack Patterns by Variant

**If Railway deploy fails to persist SQLite across redeploys:**
- Verify the volume is mounted at `/app/data` (not `/data` — Railway mounts relative to the working dir `/app`)
- Add `RAILWAY_RUN_UID=0` env var if permission errors appear (volumes default to root ownership)
- Check that the DB connection string uses the absolute path `/app/data/gods_eye.db`, not a relative path

**If WebSocket connections drop on Railway:**
- Railway supports WebSocket natively, no extra config needed
- Ensure gunicorn timeout (`--timeout 180`) does not terminate long-running simulation WebSocket sessions
- The WebSocket handler in `run.py` must not set a `ping_interval` shorter than the longest simulation round (~60s)

**If Vercel build fails:**
- Verify `VITE_API_BASE` is set in Vercel project settings under Environment Variables → Production
- The build command is `npm run build`, output dir is `dist` — Vercel auto-detects this for Vite
- Run `vercel env pull .env.local` to sync env vars to local for debugging

**If CORS errors appear in production:**
- The symptom is `Access-Control-Allow-Origin` header missing in browser console
- Fix: set `GODS_EYE_CORS_ORIGINS=https://your-app.vercel.app` in Railway variables
- Important: include the exact URL with `https://` — missing the protocol is the most common cause

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| pydantic-settings 2.x | pydantic 2.x | pydantic-settings 1.x was part of pydantic 1.x. If the existing codebase uses pydantic 2.x (likely given FastAPI 0.100+), use pydantic-settings 2.x. They are separate packages — install both |
| gunicorn 21.x | uvicorn 0.34.x | Use `uvicorn[standard]` for the full feature set including WebSocket support in the UvicornWorker |
| sonner 2.x | React 18 | sonner 2.x requires React 18+. Compatible with existing stack |
| tailwind-merge 3.x | Tailwind CSS 3.x | tailwind-merge 3.x is compatible with Tailwind 3. If upgrading to Tailwind 4 later, check tailwind-merge release notes |
| clsx 2.x | Any React version | No React dependency — pure string utility |
| Vercel CLI | Vite 5 | Vercel auto-detects Vite 5 projects. No special configuration needed beyond `vercel.json` for SPA routing |

---

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

---

*Stack research for: God's Eye deployment and polish — FastAPI + React/Vite targeting Indian market traders*
*Researched: 2026-03-30*
