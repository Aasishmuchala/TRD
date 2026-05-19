# God's Eye — Launch Plan

**Created**: 2026-03-30
**Goal**: Take God's Eye from working prototype to production-ready launch
**Estimated effort**: 6 phases, ~3-4 weeks

---

## Phase 0: Critical Bug Fixes (Day 1)

These are production blockers that must be fixed before anything else.

### 0.1 — Fix `streaming_orchestrator.py` crash bugs

**Problem**: Two undefined variable bugs crash every simulation's background review.

- **Line ~253**: `agg_dict` is undefined — should be `aggregator_result`
- **Line ~252**: `round3_outputs` is undefined when `direction_changed=False` — needs initialization at the top of the method

**File**: `backend/app/engine/streaming_orchestrator.py`

**Verify**: Run a simulation end-to-end, confirm background review completes without error in logs.

### 0.2 — Fix skill matching logic inversion

**Problem**: `skill_store.py` condition matching (lines 58-87) has inverted logic. When a condition is NOT met, it falls through instead of returning False.

**File**: `backend/app/learning/skill_store.py`, method `matches_context()`

**Verify**: Write a unit test: skill with trigger `india_vix > 22` should NOT match when `india_vix = 15`.

### 0.3 — Fix YAML parsing crash

**Problem**: `yaml.safe_load()` in `_parse_skill_file()` has no try/except — malformed YAML crashes the entire skill store.

**File**: `backend/app/learning/skill_store.py`, method `_parse_skill_file()`

**Verify**: Create a malformed .md skill file, confirm it's skipped gracefully with a warning log.

---

## Phase 1: Security & Error Handling (Days 2-4)

### 1.1 — API authentication middleware

Add JWT-based auth to all API endpoints (except `/api/health` and `/api/auth/*`).

**Approach**:
- Add `python-jose` and `passlib` to requirements.txt
- Create `backend/app/auth/middleware.py` with a FastAPI dependency that validates JWT tokens
- The device auth flow already gets tokens from OpenAI/Nous — use those as bearer tokens
- Add `Depends(require_auth)` to all route functions in `routes.py`
- Mock mode should bypass auth (check `config.MOCK_MODE`)

**Files to modify**: `routes.py`, `requirements.txt`
**Files to create**: `backend/app/auth/middleware.py`

### 1.2 — Rate limiting

**Approach**:
- Add `slowapi` to requirements.txt
- Add rate limiter to `run.py`: 60 req/min per IP for simulation, 10 req/min for auth polling
- Add WebSocket connection limit (max 10 concurrent)

**Files to modify**: `run.py`, `requirements.txt`

### 1.3 — Structured error responses

**Problem**: `str(e)` leaks stack traces to clients (routes.py line 155, run.py line 99).

**Approach**:
- Create error schema: `{"error": "code", "message": "user-safe message", "request_id": "uuid"}`
- Replace all `detail=str(e)` with safe error messages
- Add request ID middleware for tracing
- Log full exception server-side, return sanitized message to client

**Files to modify**: `routes.py`, `run.py`
**Files to create**: `backend/app/api/errors.py`

### 1.4 — Token encryption at rest

**Problem**: OAuth tokens stored as plain JSON in `~/.gods-eye/auth.json`.

**Approach**:
- Add `cryptography` to requirements.txt
- Use Fernet symmetric encryption with a machine-derived key
- Encrypt `access_token` and `refresh_token` fields before writing
- Set file permissions to 0o600 after writing

**Files to modify**: `device_auth.py`, `requirements.txt`

### 1.5 — Fix CORS for production

**Problem**: Hardcoded `localhost` origins, wildcard methods/headers.

**Approach**:
- Read allowed origins from `GODS_EYE_CORS_ORIGINS` env var
- Default to `["http://localhost:5173"]` in dev
- Restrict methods to `GET, POST, OPTIONS`
- Restrict headers to `Authorization, Content-Type`

**Files to modify**: `run.py`, `config.py`

---

## Phase 2: Data Layer & Market Data (Days 5-8)

### 2.1 — Real forex data

**Problem**: USD/INR hardcoded to 83.5, DXY hardcoded to 104.0 (market_data.py lines 228-229).

**Approach**:
- Add forex fetching to `market_data.py` using a free API (exchangerate-api.com or similar)
- Add DXY via Yahoo Finance scraping or a financial data API
- Cache forex data with 5-minute TTL
- Keep hardcoded values as fallback

**Files to modify**: `backend/app/data/market_data.py`

### 2.2 — Historical FII 5-day data

**Problem**: FII 5-day flow estimated as `today * 3` (line 298-301) — not real data.

**Approach**:
- NSE publishes historical FII/DII data — fetch last 5 trading days
- Sum the actual net values instead of estimating
- Add daily historical cache (refresh once per day)

**Files to modify**: `backend/app/data/market_data.py`

### 2.3 — Database migrations with Alembic

**Approach**:
- Add `sqlalchemy` and `alembic` to requirements.txt
- Create SQLAlchemy models for `predictions` and `simulations` tables
- Generate initial migration from current schema
- Replace raw SQL in `prediction_tracker.py` and `agent_memory.py` with SQLAlchemy

**Files to create**: `backend/alembic/`, `backend/app/models.py`, `backend/alembic.ini`
**Files to modify**: `prediction_tracker.py`, `agent_memory.py`, `requirements.txt`

### 2.4 — Resource cleanup

**Problem**: httpx clients and DB connections never closed — resource leak.

**Approach**:
- Add `on_event("shutdown")` handler in `run.py` to close LLM client, market data client
- Use async context managers for orchestrators
- Add `close()` call for `DeviceAuthManager` and `LLMClient` singletons

**Files to modify**: `run.py`, `llm_client.py`, `device_auth.py`, `market_data.py`

---

## Phase 3: Testing Foundation (Days 9-12)

### 3.1 — Backend test setup

**Approach**:
- Add `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` (test client) to requirements.txt
- Create `backend/tests/conftest.py` with app fixture, test database, mock LLM client
- Target: 70%+ coverage on critical paths

**Files to create**: `backend/tests/conftest.py`, `backend/pytest.ini`

### 3.2 — API route tests

Test every endpoint:
- `POST /api/simulate` — valid input, invalid input, auth required
- `GET /api/presets` — returns scenario list
- `GET /api/health` — returns healthy status
- `POST /api/auth/login` — initiates device flow
- `GET /api/history` — returns simulation history
- `POST /api/settings` — updates settings with auth
- `POST /api/learning/toggle` — toggles learning

**Files to create**: `backend/tests/test_routes.py`

### 3.3 — Simulation engine tests

- Test 3-round consensus produces valid output
- Test agent weight aggregation math
- Test direction change detection between rounds
- Test mock mode produces consistent results

**Files to create**: `backend/tests/test_orchestrator.py`

### 3.4 — Learning system tests

- Test skill save/load round-trip
- Test condition matching (positive and negative cases)
- Test duplicate detection
- Test review engine pattern detection
- Test skill injection into prompts

**Files to create**: `backend/tests/test_skill_store.py`, `backend/tests/test_review_engine.py`

### 3.5 — Frontend test setup

**Approach**:
- Add `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` to devDependencies
- Create `frontend/vitest.config.js`
- Test critical flows: AuthGate, simulation trigger, result display

**Files to create**: `frontend/vitest.config.js`, `frontend/src/__tests__/`

---

## Phase 4: Frontend Hardening (Days 13-15)

### 4.1 — Error boundaries

**Approach**:
- Create `ErrorBoundary` component that catches React errors
- Wrap routes in App.jsx with ErrorBoundary
- Show user-friendly fallback UI with "Retry" button

**Files to create**: `frontend/src/components/ErrorBoundary.jsx`
**Files to modify**: `frontend/src/App.jsx`

### 4.2 — API client robustness

**Approach**:
- Add retry logic with exponential backoff (3 retries, 1s/2s/4s)
- Add request timeout via AbortController (30s default)
- Add request deduplication for GET requests

**Files to modify**: `frontend/src/api/client.js`

### 4.3 — Environment-based configuration

**Approach**:
- Create `.env.example` with all VITE_* variables documented
- Make API base URL configurable: `VITE_API_BASE`
- Production build should not use Vite proxy — configure direct API URL
- Add production build optimizations to vite.config.js (code splitting, minification)

**Files to create**: `frontend/.env.example`
**Files to modify**: `frontend/vite.config.js`, `frontend/src/api/client.js`

### 4.4 — Accessibility basics

**Approach**:
- Add aria-labels to all buttons and interactive elements
- Add alt text to icons/images
- Add keyboard navigation support (tabIndex, onKeyDown)
- Ensure color contrast meets WCAG AA

**Files to modify**: All component files in `frontend/src/components/`

---

## Phase 5: Deployment & Infrastructure (Days 16-19)

### 5.1 — Dockerfile (multi-stage)

```
backend/Dockerfile:
  Stage 1: Install Python deps
  Stage 2: Copy app code, run uvicorn with --workers 4

frontend/Dockerfile:
  Stage 1: npm install & build
  Stage 2: Serve with nginx
```

**Files to create**: `backend/Dockerfile`, `frontend/Dockerfile`, `.dockerignore`

### 5.2 — Docker Compose

Single `docker-compose.yml` at project root:
- `backend` service (port 8000)
- `frontend` service (port 80, proxies /api to backend)
- `volumes` for database persistence and skill files
- Environment variables from `.env`

**Files to create**: `docker-compose.yml`, `.env.example`

### 5.3 — Production config

**Approach**:
- `config.py`: Read `GODS_EYE_ENV` (dev/staging/prod) — set RELOAD, LOG_LEVEL, CORS accordingly
- `run.py`: Use `gunicorn` with uvicorn workers in prod (4 workers)
- Add `gunicorn` to requirements.txt
- Nginx config for frontend with gzip, caching, SSL termination

**Files to modify**: `config.py`, `run.py`, `requirements.txt`
**Files to create**: `nginx.conf`

### 5.4 — Structured logging

**Approach**:
- Add `python-json-logger` to requirements.txt
- Configure root logger in `run.py` startup with JSON format
- Add request ID to all log entries
- Log level controlled by `GODS_EYE_LOG_LEVEL` env var

**Files to create**: `backend/app/logging_config.py`
**Files to modify**: `run.py`, `requirements.txt`

### 5.5 — Health checks & monitoring

**Approach**:
- Expand `/api/health` to check: DB connectivity, NSE reachability, auth token validity
- Add `/api/health/ready` (readiness probe for k8s)
- Add basic Prometheus metrics endpoint (optional)
- Add Sentry integration for error tracking

**Files to modify**: `routes.py`, `requirements.txt`

---

## Phase 6: Final Verification & Launch Prep (Days 20-21)

### 6.1 — Full integration test

- Start with `docker-compose up`
- Run full simulation flow: login → select scenario → run simulation → view results
- Run with live NSE data during market hours
- Verify learning system creates skills after simulation

### 6.2 — Load testing

- Use `locust` or `k6` to hit `/api/simulate` with 50 concurrent requests
- Verify WebSocket connections under load (20 concurrent streams)
- Check memory usage stays stable over 100 simulations

### 6.3 — Security checklist

- [ ] All endpoints require auth (except health, auth/login, auth/poll)
- [ ] Rate limiting active on all endpoints
- [ ] CORS restricted to production domain
- [ ] Tokens encrypted at rest
- [ ] Error messages don't leak internals
- [ ] No hardcoded secrets in code
- [ ] `.env.example` documents all variables (no actual secrets)

### 6.4 — Documentation update

- Update `SETUP.md` with Docker deployment instructions
- Update `QA_REPORT.md` with automated test results
- Create `DEPLOYMENT.md` with production runbook
- Create `CHANGELOG.md` with all changes since prototype

### 6.5 — Environment files

Create complete `.env.example`:
```
# Required
GODS_EYE_ENV=production
LLM_API_KEY=your-api-key-here

# Optional (with defaults)
GODS_EYE_LLM_PROVIDER=openai
GODS_EYE_MODEL=o4-mini
GODS_EYE_DB_PATH=./data/gods_eye.db
GODS_EYE_LEARNING=true
GODS_EYE_LOG_LEVEL=info
GODS_EYE_CORS_ORIGINS=https://your-domain.com
```

---

## Priority Summary

| Phase | What | Why | Days |
|-------|------|-----|------|
| 0 | Critical bug fixes | App crashes without these | 1 |
| 1 | Security & errors | Can't expose without auth | 3 |
| 2 | Data & database | Accuracy and reliability | 4 |
| 3 | Testing | Catch regressions, prove correctness | 4 |
| 4 | Frontend hardening | User experience and resilience | 3 |
| 5 | Deployment | Actually get it running in production | 4 |
| 6 | Verification | Prove it all works together | 2 |

**Total: ~21 working days (3-4 weeks)**

---

## What You Can Skip If You Want to Ship Faster

If you want a "minimum viable launch" in ~1.5 weeks instead of 3-4:

1. **Do**: Phase 0 (bugs), Phase 1 (security), Phase 5.1-5.2 (Docker)
2. **Defer**: Phase 2.3 (Alembic — SQLite works fine for now), Phase 3.5 (frontend tests), Phase 4.4 (accessibility), Phase 5.5 (monitoring)
3. **Simplify**: Phase 3 (just API route tests, skip engine/learning tests)

This gets you: bug-free, secured, deployable — but without full test coverage or monitoring.
