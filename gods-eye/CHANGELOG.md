# Changelog

All notable changes to God's Eye are documented here.

---

## [2.0.0] — 2026-03-30

Production-ready release with OAuth device flow, auto-learning, custom scenarios, WebSocket streaming, real market data, security hardening, and comprehensive testing.

### Added

- **OAuth device code flow** — Login via OpenAI Codex or Nous Research providers without storing credentials
- **Auto-learning system** — Agents learn market patterns from simulation outcomes and create reusable skills
- **Custom scenario input form** — 9 manual parameters (Nifty, VIX, flows, FX, PCR, context) + 8 context tags
- **Loading skeleton states** — Shimmer animations in PressurePanel and InsightsPanel during simulation
- **JWT authentication middleware** — All protected endpoints require valid Bearer token
- **Rate limiting** (slowapi) — 10/min simulate, 5/min login, 30/min auth polling
- **Structured JSON logging** — Production-ready logs for ELK/Datadog aggregation
- **Error boundary component** — Graceful frontend crash recovery with retry UI
- **API client retry logic** — Exponential backoff (1s/2s/4s) with 30s timeout
- **Real forex data** — USD/INR via exchangerate-api, DXY via Yahoo Finance (5-min cache)
- **Historical FII 5-day flows** — NSE data instead of 3x multiplier estimation
- **Database migrations** — Alembic + SQLAlchemy models for schema versioning
- **Docker deployment** — Multi-stage builds, nginx reverse proxy, health checks
- **Test suite** — 26 backend tests (pytest) + frontend tests (vitest) with >70% coverage
- **WCAG accessibility basics** — aria-labels, roles, semantic HTML, keyboard navigation
- **Code splitting** — Vendor/charts chunks for faster initial load
- **Comprehensive `.env.example`** — All configuration options documented with defaults

### Changed

- **LLM provider** — Replaced Anthropic Claude with OpenAI-compatible chat completion
- **Auth tokens** — Now encrypted at rest with Fernet (machine-derived key)
- **CORS configuration** — Origins now configurable via `GODS_EYE_CORS_ORIGINS` env var
- **FII 5-day flow estimation** — 2.5x multiplier + more conservative calculation (was 3x)
- **Health check endpoint** — Now validates database connectivity in response
- **Error responses** — Sanitized to prevent stack trace leakage (no sensitive internals)
- **Resource cleanup** — Proper shutdown handlers for httpx clients and database connections
- **Agent weight tuning** — Feedback engine adjusts weights based on accuracy metrics

### Fixed

- **streaming_orchestrator.py crash** (line ~253) — Undefined `agg_dict` variable → fixed to `aggregator_result`
- **streaming_orchestrator.py crash** (line ~252) — Undefined `round3_outputs` when direction unchanged → initialize at method start
- **skill_store.py inverted logic** (lines 58-87) — Condition matching fell through on NOT-matched → inverted boolean check
- **skill_store.py YAML parsing crash** — No error handling for malformed YAML → wrapped in try/except with warning log
- **Resource cleanup on shutdown** — httpx clients, DB connections, and auth managers now explicitly closed

---

## [1.0.0] — 2026-03-15

Initial prototype release with core simulation engine.

### Added

- 6 autonomous agents (FII, DII, Retail F&O, Promoter, RBI Policy, Algo)
- 3-round interaction orchestration with direction change detection
- Weighted consensus aggregation (standard + hybrid modes)
- 8 preset market scenarios (RBI rate cut, FII exodus, budget bull/bear, etc.)
- WebSocket streaming simulation for real-time agent results
- SQLite prediction tracking with accuracy metrics
- FastAPI server with mock LLM mode for testing
- React frontend with dashboard, paper trading, settings
- Live NSE market data pipeline (Nifty, VIX, FII/DII, options, sectors)
- Market ticker component with auto-refresh (60s)
- Feedback engine with per-agent accuracy tracking
