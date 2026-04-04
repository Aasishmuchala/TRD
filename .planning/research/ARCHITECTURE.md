# Architecture Research

**Domain:** Multi-agent AI market intelligence — Python/FastAPI backend + React SPA frontend
**Researched:** 2026-03-30
**Confidence:** HIGH (based on direct codebase inspection)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         BROWSER / CLIENT                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Dashboard │  │AgentDetail│  │SimHistory│  │PaperTrade│  Settings  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│       │              │             │              │                  │
│  ┌────┴──────────────┴─────────────┴──────────────┴────────────┐    │
│  │         api/client.js  (REST + WebSocket)                    │    │
│  └───────────────────────────────────────┬──────────────────────┘   │
└──────────────────────────────────────────│──────────────────────────┘
                                           │ HTTP REST  /  ws://
┌──────────────────────────────────────────│──────────────────────────┐
│                     FASTAPI BACKEND       │                          │
│  ┌───────────────────────────────────────┴──────────────────────┐   │
│  │  REST Router (/api/*)          WebSocket (/api/simulate/stream)│  │
│  └──────────┬──────────────────────────────────────┬────────────┘   │
│             │                                       │               │
│  ┌──────────▼───────┐                  ┌────────────▼────────────┐  │
│  │   Orchestrator   │                  │  StreamingOrchestrator  │  │
│  │  (batch mode)    │                  │  (event-yielding mode)  │  │
│  └──────────┬───────┘                  └────────────┬────────────┘  │
│             └────────────────┬──────────────────────┘               │
│                              │ run_simulation / stream_simulation    │
│  ┌───────────────────────────▼──────────────────────────────────┐   │
│  │                     AGENT LAYER                               │   │
│  │  ALGO(Q) │ FII(L) │ DII(L) │ RetailFNO(L) │ Promoter(L) │ RBI(L)│
│  └──────────┬────────────────────────────────────────┬──────────┘   │
│             │  ProfileGenerator (context enrichment)  │             │
│  ┌──────────▼──────────────────────────────────────── ▼──────────┐  │
│  │                   INTELLIGENCE LAYER                           │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────┐  │  │
│  │  │ AgentMemory │  │FeedbackEngine│  │SimulationReviewEngine │  │  │
│  │  │(SQLite/pred)│  │(weight tuning│  │(skill extraction)     │  │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────┬────────────┘  │  │
│  └─────────│───────────────-│───────────────────--│───────────────┘  │
│            │                │                     │                  │
│  ┌─────────▼────────────────▼─────────────────────▼──────────────┐  │
│  │                    DATA LAYER                                  │  │
│  │  ┌──────────────┐  ┌────────────────┐  ┌───────────────────┐  │  │
│  │  │  SQLite DB   │  │MarketDataService│  │ SkillStore (YAML) │  │  │
│  │  │(gods_eye.db) │  │ (NSE live data)│  │ (~/.gods-eye/)    │  │  │
│  │  └──────────────┘  └────────────────┘  └───────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  EXTERNAL CALLS: Anthropic / OpenAI API  +  NSE India API      │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| React SPA (5 pages) | User interface, state display | api/client.js only |
| api/client.js | Typed HTTP + WebSocket client | FastAPI REST + WS |
| FastAPI REST Router | Request validation, route dispatch | Orchestrator, trackers |
| WebSocket endpoint | Streaming simulation events | StreamingOrchestrator |
| Orchestrator (batch) | Runs 2-3 rounds, returns final result | Agents, Memory, FeedbackEngine |
| StreamingOrchestrator | Same logic but yields events incrementally | Agents, Memory, FeedbackEngine |
| Agent Layer (6 agents) | LLM/quant analysis per persona | LLM API, ProfileGenerator |
| ProfileGenerator | Enriches each agent prompt with memory + market signals | AgentMemory, SkillStore |
| Aggregator | Weighted consensus from all agents | Config (weights) |
| AgentMemory | Per-agent SQLite prediction logging + accuracy stats | SQLite |
| PredictionTracker | Aggregate simulation logging + outcome recording | SQLite |
| FeedbackEngine | Auto-tunes agent weights from accuracy history | AgentMemory |
| SimulationReviewEngine | Background skill extraction after simulations | LLM API, SkillStore |
| MarketDataService | Fetches live NSE data with session management + cache | NSE India API, MarketCache |
| SkillStore | YAML-frontmatter skill file persistence | Filesystem (~/.gods-eye/) |
| SQLite + Alembic | Persistent storage: simulations, predictions, agent memory | Filesystem |

---

## Recommended Project Structure

The existing structure is well-organized. The production deployment adds two additional concerns: environment config management and static skill file persistence.

```
gods-eye/
├── docker-compose.yml           # Local full-stack orchestration
├── .env.example                 # Template — copy to .env
├── backend/
│   ├── Dockerfile               # python:3.11-slim + gunicorn 4 workers
│   ├── requirements.txt         # Pinned deps (no -r ranges)
│   ├── run.py                   # FastAPI app + WebSocket mount + lifecycle
│   └── app/
│       ├── config.py            # Env-var-driven Config dataclass
│       ├── logging_config.py    # JSON structured logging (prod)
│       ├── limiter.py           # slowapi rate limits (10/min simulate)
│       ├── models.py            # SQLAlchemy ORM models
│       ├── agents/              # 6 agent classes + base + profile generator
│       ├── engine/              # orchestrator, streaming_orchestrator, aggregator, feedback, scenarios
│       ├── memory/              # agent_memory.py, prediction_tracker.py
│       ├── learning/            # review_engine.py, skill_store.py
│       ├── knowledge/           # market_graph.py (India market relationship graph)
│       ├── data/                # market_data.py (NSE), cache.py, signal_engine.py
│       ├── auth/                # device_auth.py, llm_client.py, middleware.py
│       └── api/                 # routes.py, schemas.py, errors.py
└── frontend/
    ├── Dockerfile               # node:20-alpine build + nginx:alpine serve
    ├── nginx.conf               # Proxy /api/* to backend, SPA fallback, WS upgrade
    ├── vite.config.js           # Dev proxy to :8000, manual chunk splits
    └── src/
        ├── App.jsx              # Router: 5 routes wrapped in AuthGate + ErrorBoundary
        ├── api/client.js        # All API calls (REST + WS address)
        ├── pages/               # Dashboard, AgentDetail, SimulationHistory, PaperTrading, Settings, Welcome
        ├── components/          # 18 components (panels, charts, forms, layout)
        ├── hooks/               # useSimulation.js, useStreamingSimulation.js
        └── utils/               # Utility helpers
```

### Structure Rationale

- **engine/ vs agents/:** Correct separation — orchestration logic is independent of agent personas.
- **memory/ vs learning/:** Memory is tracking/querying past data; learning is acting on it to extract skills. Good boundary.
- **data/:** NSE data service keeps external I/O isolated from domain logic.
- **auth/:** Device OAuth + LLM client as one concern — correct, since auth gates LLM access.
- **SkillStore on filesystem:** Skills stored at `~/.gods-eye/skills/` as YAML+markdown. In containers this must be a named volume (already done in docker-compose).

---

## Architectural Patterns

### Pattern 1: Dual Orchestration (Batch + Streaming)

**What:** The same 3-round simulation logic is implemented twice — `Orchestrator` gathers all results and returns a full response; `StreamingOrchestrator` runs the same logic but yields typed event dicts via an async generator as each agent completes.

**When to use:** Batch mode for REST `/api/simulate`; streaming mode for WebSocket `/api/simulate/stream`. The Dashboard uses WebSocket streaming for live UI updates.

**Trade-offs:** Code duplication (the two classes share ~80% logic). This is the correct trade-off: the streaming interface requires yielding mid-computation, which fundamentally can't be wrapped over a batch result without faking the stream. Any refactor to share logic must keep the async generator boundary intact.

**Key implementation detail:**
```python
# LLM agents run in parallel; yield as each completes (not in submission order)
done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
```
This is why the UI shows agents appearing one by one — it is not artificial animation, it is actual completion order.

### Pattern 2: Tiered Confidence / Progressive Rounds

**What:** Round 3 only runs when at least one agent changes direction between rounds 1 and 2. Round 2 is always run. This gates LLM cost — most consensual simulations terminate after 2 rounds.

**When to use:** Any multi-agent system where LLM calls are the bottleneck.

**Trade-offs:** Round 3 adds latency (~5-15 seconds) when triggered. The UI should communicate this with a "seeking equilibrium" indicator rather than a spinner.

### Pattern 3: Fire-and-Forget Background Learning

**What:** After each simulation completes (both batch and streaming), a `asyncio.create_task()` triggers `SimulationReviewEngine.review_simulation()` asynchronously. This calls the LLM again to extract skills — without blocking the response to the user.

**When to use:** Any post-processing that does not affect the current response.

**Trade-offs:** If the FastAPI process restarts during the background task, the skill extraction is lost. Acceptable for Phase 1. For Phase 2, queue this work in a persistent task queue (Celery, or Railway's built-in cron).

**Current risk:** The background task uses `asyncio.create_task()` which ties the task lifetime to the current event loop iteration. Under gunicorn with 4 workers, each worker has its own event loop — tasks do not cross workers. This is fine for a single-user tool but worth noting.

### Pattern 4: Config as Runtime-Mutable Dataclass

**What:** `config` is a module-level singleton `Config()` instance. Routes mutate it directly (`config.AGENT_WEIGHTS = weights`). This means settings changes are in-memory only and reset on process restart.

**When to use:** Acceptable for a single-user tool where SQLite holds the canonical state.

**Trade-offs:** With gunicorn's 4 workers, a settings change in worker A is not visible to worker B. For the `/api/settings` POST endpoint, this means the update is non-deterministic across requests. Fix: persist settings to SQLite and reload from DB on each request, or use `--workers 1` in gunicorn for this tool's use case.

---

## Data Flow

### Simulation Request Flow (WebSocket)

```
User triggers "Run Simulation" in Dashboard
    ↓
useStreamingSimulation.js opens ws://backend/api/simulate/stream
    ↓
Sends: {"scenario_id": "rbi_rate_cut"} or {"source": "live"}
    ↓
FastAPI WebSocket handler (run.py)
    ↓
StreamingOrchestrator.stream_simulation(market_input)
    ↓
[event: simulation_start] → UI updates header
    ↓
[event: round_start round=1] → UI shows round indicator
    ↓
ProfileGenerator.build_context() per agent
    ↓ (parallel)
LLM agents: LLM_API → AgentResponse
ALGO agent: signal_engine → AgentResponse
    ↓ (as each completes)
[event: agent_result] × 6 → UI renders each agent card
    ↓
Round 2 repeats with round1 outputs as context
    ↓
Direction change check → conditional Round 3
    ↓
Aggregator.aggregate() → weighted consensus
    ↓
[event: aggregation] → UI renders direction gauge + conviction
    ↓
AgentMemory.log_agent_prediction() × 6 (synchronous, blocking)
    ↓
asyncio.create_task(review_engine.review_simulation())  ← background
    ↓
[event: simulation_end] → UI marks complete
    ↓
PredictionTracker.log_simulation() + log_prediction()
    ↓
WebSocket closes
```

### Live Market Data Flow

```
Dashboard mounts → MarketTicker component
    ↓
apiClient.getMarketLive() → GET /api/market/live
    ↓
MarketDataService.get_live_snapshot()
    ↓
NSE Session Manager (first call sets cookies via nseindia.com homepage)
    ↓
NSE API: /api/allIndices (Nifty, VIX), /api/equity-stockIndices (sectors)
    ↓
MarketCache (TTL-based, 60s for live data)
    ↓ (if NSE unreachable)
Mock data fallback with realistic ranges
    ↓
Returns: {nifty_spot, india_vix, fii_flow_5d, dii_flow_5d, ...}
```

### Accuracy Feedback Loop

```
Simulation completed → PredictionTracker.log_prediction()
    ↓ (user records outcome days later)
POST /api/history/{id}/outcome
    ↓
PredictionTracker.record_outcome()
    ↓
FeedbackEngine.get_tuned_weights() (next simulation)
    ├── Requires >= 50 predictions per agent before activating
    ├── Computes accuracy-weighted delta from base weights
    └── Returns tuned_weights dict → Aggregator.aggregate()
```

### Key Data Flows Summary

1. **Simulation input:** User/preset/NSE → MarketInput schema → Orchestrator
2. **Agent enrichment:** AgentMemory + SkillStore → ProfileGenerator → per-agent context string prepended to prompt
3. **LLM call:** base prompt + enriched context + round N peer outputs → LLM API → AgentResponse
4. **Persistence:** SimulationResult → SQLite (predictions, agent_predictions tables)
5. **Skills persistence:** SimulationReviewEngine → LLM call → YAML file → SkillStore filesystem
6. **Weight adaptation:** SQLite accuracy data → FeedbackEngine → tuned_weights → next Aggregator call

---

## Production Deployment Architecture

### Target: Railway (backend) + Vercel (frontend)

```
                    ┌──────────────────────────────┐
Internet → HTTPS → │     Vercel Edge Network       │
                    │  React SPA (static build)     │
                    │  VITE_API_BASE=https://api.x  │
                    └──────────────┬───────────────┘
                                   │ XHR / WebSocket
                    ┌──────────────▼───────────────┐
                    │      Railway Service          │
                    │  Docker container             │
                    │  gunicorn 4 workers           │
                    │  uvicorn ASGI                 │
                    │  Port: 8000                   │
                    │                               │
                    │  /app/data/gods_eye.db  ──── Railway Volume
                    │  ~/.gods-eye/skills/    ──── Railway Volume
                    └──────────────────────────────┘
```

**CORS configuration required:** In production, `GODS_EYE_CORS_ORIGINS` must be set to the Vercel deployment URL (e.g., `https://gods-eye.vercel.app`). The current default `http://localhost,...` will block all production requests.

**WebSocket on Railway:** Railway supports WebSocket upgrades natively. No additional config needed. Vercel does NOT run servers — the frontend makes WebSocket connections directly to the Railway backend URL (`wss://your-app.railway.app/api/simulate/stream`).

**Frontend env var:** `VITE_API_BASE` must be set at Vercel build time to point to the Railway backend URL. The current `nginx.conf` proxy pattern only works in Docker; Vercel serves pure static files.

### Critical Production Gap: WebSocket Origin

The current WebSocket handler in `run.py` does not validate the `Origin` header. Any page can connect. For a single-user tool this is acceptable, but for Railway deployment add an `Origin` check or ensure rate limiting covers this.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single user (current target) | Gunicorn 1-2 workers avoids config sync issues. SQLite is fine. |
| 5-10 concurrent simulations | Background review tasks can pile up on a single process. Consider `--timeout 180` in gunicorn since LLM chains can take 30-60s. |
| 100+ users | SQLite write contention becomes a blocker at ~50 concurrent writes. Migrate to PostgreSQL. Settings-as-config becomes broken — need DB-backed settings. |
| High throughput | Separate the background review task into a worker queue (Celery + Redis). NSE scraping is rate-limited externally. |

### Scaling Priorities

1. **First bottleneck:** LLM API latency (5-15 seconds per simulation round). Already mitigated via parallel agent execution. Cannot be reduced further without caching LLM responses, which reduces accuracy.
2. **Second bottleneck:** SQLite write lock during background learning tasks. `aiosqlite` handles async reads, but Alembic migrations are synchronous. Prevent migrations from running under load.
3. **Third bottleneck:** NSE session cookie management. The session must be re-established if the cookie expires (~15 min). MarketCache mitigates this for live data reads, but a cold start always hits NSE first.

---

## Anti-Patterns

### Anti-Pattern 1: Orchestrator Instantiated Per Request

**What people do:** Current code creates `Orchestrator()` and `StreamingOrchestrator()` on every request, including all 6 agent instances and database connections.

**Why it's wrong:** Each instantiation opens a new `AgentMemory(db_path=...)` which creates a new SQLite connection. Under load, this creates many short-lived connections. Also, `PredictionTracker()` in `StreamingOrchestrator.__init__` opens another connection.

**Do this instead:** Use FastAPI's dependency injection to create these as application-scoped singletons via `@app.on_event("startup")`. Store on `app.state`. This is already partially done for `market_data_service` but not for orchestrators.

### Anti-Pattern 2: Mutable Config Singleton with Multiple Workers

**What people do:** Current `POST /api/settings` mutates the module-level `config` object directly.

**Why it's wrong:** Gunicorn spawns 4 separate Python processes. A weight update in process 1 is invisible to processes 2, 3, 4. Users will see inconsistent simulation behavior after changing settings.

**Do this instead:** Either run with `--workers 1` (sufficient for a single-user tool), or persist settings changes to a `settings` table in SQLite and read from DB at simulation start.

### Anti-Pattern 3: SkillStore Writing to Home Directory in Containers

**What people do:** `LEARNING_SKILL_DIR` defaults to `~/.gods-eye/skills/`. In `docker-compose.yml` this maps to the root user's home inside the container (`/root/.gods-eye/`).

**Why it's wrong:** The Dockerfile creates `appuser` and runs as non-root, but the skills volume is mounted at `/root/.gods-eye/skills`. The non-root user cannot write there.

**Do this instead:** Set `LEARNING_SKILL_DIR=/app/skills` and mount that path as the Docker volume. Update Dockerfile to `mkdir -p /app/skills && chown appuser:appuser /app/skills`.

### Anti-Pattern 4: Welcome Page Not Routed

**What people do:** `Welcome.jsx` exists and contains the auth flow UI but is not included in `App.jsx`'s route tree. The `AuthGate` wraps the entire router, but there is no `/welcome` or `/login` route.

**Why it's wrong:** Users who are not authenticated see no feedback — the `AuthGate` likely renders nothing or redirects to dashboard, which then fails API calls silently.

**Do this instead:** Add `<Route path="/welcome" element={<Welcome />} />` and have `AuthGate` redirect unauthenticated users to `/welcome` before mounting the Router.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenAI / Anthropic API | httpx async POST in `llm_client.py`, bearer token from device auth or env var | Mock mode (`GODS_EYE_MOCK=true`) bypasses entirely |
| NSE India API | httpx with browser-mimicking headers + session cookie management | Fragile — NSE changes headers/endpoints. Cache aggressively (60s TTL). |
| OAuth Provider (device flow) | httpx polling against provider's token endpoint | Currently "openai" provider hardcoded. Device codes expire in 10min. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Frontend ↔ Backend | REST JSON + WebSocket JSON events | VITE_API_BASE env var must match backend URL in prod |
| Nginx ↔ FastAPI (Docker) | Internal Docker network `http://backend:8000` | Only used in docker-compose; Vercel+Railway uses direct URL |
| Agents ↔ LLM API | Async httpx in `llm_client.py` | All 5 LLM agents call this; ALGO agent does not |
| Orchestrator ↔ SQLite | Direct sqlite3 + aiosqlite via AgentMemory, PredictionTracker | Not connection-pooled; acceptable for single-user |
| ReviewEngine ↔ SkillStore | Filesystem read/write (YAML+markdown) | Path must be writable inside container — see anti-pattern 3 |
| FeedbackEngine ↔ AgentMemory | In-process Python method calls | No serialization overhead; tight coupling is acceptable here |

---

## Build Order for Deployment Milestone

The following ordering reflects actual dependencies — each step unblocks the next.

1. **Fix SkillStore container path** (anti-pattern 3) — unblocks all Docker and Railway deploys
2. **Route Welcome.jsx + fix AuthGate redirect** — unblocks auth testing in production
3. **Add CORS production config** — unblocks frontend-backend connection on Railway+Vercel
4. **Set VITE_API_BASE for Vercel** — unblocks frontend API calls in production
5. **Wire skill injection into agent prompts** — once SkillStore path is fixed, injection can be tested end-to-end
6. **Deploy backend to Railway** with correct volumes (`/app/data` and `/app/skills`)
7. **Deploy frontend to Vercel** with `VITE_API_BASE=https://your-railway-url`
8. **Fix gunicorn worker count** to 1 or persist settings to DB — unblocks reliable settings changes
9. **Align agent names + graduation criteria** (UI correctness)
10. **Build Learning/Skills management UI** — skills infrastructure must work first (steps 1, 5)

---

## Sources

- Direct inspection of `/gods-eye/backend/` and `/gods-eye/frontend/src/` source files
- `DEPLOYMENT.md` — existing deployment documentation
- `docker-compose.yml` and `backend/Dockerfile` and `frontend/Dockerfile`
- `backend/app/config.py` — environment variable mapping
- `backend/run.py` — FastAPI app entry point with WebSocket mount
- Railway documentation (confirmed WebSocket support, volume persistence): https://docs.railway.app
- Vercel static hosting constraints (no server-side process, no WebSocket origination): https://vercel.com/docs

---

*Architecture research for: God's Eye — Multi-Agent Indian Market Intelligence (FastAPI + React, production deployment)*
*Researched: 2026-03-30*
