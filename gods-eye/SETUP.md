# God's Eye - Setup Guide

**God's Eye** is a multi-agent AI market simulation system for Indian equities. It runs 6 autonomous agents (LLM-powered and quantitative) that analyze market conditions and output a consensus trading signal.

---

## Prerequisites

Choose one of:
- **Local**: Python 3.10+, Node 18+
- **Docker**: Docker 20.10+, Docker Compose 2.0+

---

## Quick Start: Local Development

### Terminal 1 — Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

export GODS_EYE_ENV=development
export LLM_API_KEY="your-openai-api-key"
python run.py
```

Backend listens on `http://localhost:8000`

### Terminal 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend opens at `http://localhost:5173`

---

## Quick Start: Docker

```bash
cp .env.example .env
# Edit .env: set LLM_API_KEY and GODS_EYE_CORS_ORIGINS

docker-compose up
```

- Frontend: `http://localhost`
- Backend: `http://localhost:8000`

---

## Environment Variables

### Required
- `LLM_API_KEY` — OpenAI or compatible API key

### Optional (with sensible defaults)
- `GODS_EYE_ENV` — "development" or "production" (default: development)
- `GODS_EYE_LLM_PROVIDER` — "openai" (default)
- `GODS_EYE_MODEL` — Model name like "gpt-4o" (default: o4-mini)
- `GODS_EYE_DB_PATH` — SQLite database path (default: ./data/gods_eye.db)
- `GODS_EYE_LEARNING` — "true" or "false" (enable auto-learning, default: true)
- `GODS_EYE_LOG_LEVEL` — "debug", "info", "warning", "error" (default: info)
- `GODS_EYE_CORS_ORIGINS` — Comma-separated allowed origins (default: http://localhost:5173)

See `.env.example` for complete reference.

---

## Project Structure

```
gods-eye/
├── backend/
│   ├── app/
│   │   ├── agents/          # 6 agent implementations
│   │   ├── api/             # FastAPI routes & schemas
│   │   ├── engine/          # Simulation orchestrator, aggregator
│   │   ├── data/            # Market data & signal engine
│   │   ├── memory/          # Prediction tracking
│   │   └── config.py        # Configuration
│   ├── tests/               # Pytest test suite
│   ├── run.py               # FastAPI entry point
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/           # 6 page components
│   │   ├── components/      # Reusable UI components
│   │   ├── api/             # API client
│   │   └── App.jsx          # Router
│   ├── vite.config.js       # Build config
│   └── package.json         # Node dependencies
├── docker-compose.yml        # Orchestration
└── SETUP.md                 # This file
```

---

## Running Tests

### Backend

```bash
cd backend
python -m pytest tests/ -v
```

Covers: API routes, skill store, aggregation, webhook handling.

### Frontend

```bash
cd frontend
npm run test
```

Covers: Component rendering, API mocking, error boundaries.

---

## API Documentation

### Health Check
```
GET /api/health
```

Returns status, version, database connectivity, LLM provider, learning enabled flag.

### Simulate
```
POST /api/simulate
Content-Type: application/json

{
  "scenario_id": "rbi_rate_cut"
}
```

Returns: `simulation_id`, `agents_output` (6 agents), `aggregator_result` (consensus), `execution_time_ms`.

Modes:
- `scenario_id` — Use preset scenario (8 available)
- `source: "live"` — Auto-populate from NSE market data
- Flat fields — Send `{nifty_spot, india_vix, fii_flow_5d, ...}`

### Presets
```
GET /api/presets
```

Returns 8 scenarios: rbi_rate_cut, fii_exodus, budget_bull, budget_bear, expiry_carnage, global_contagion, adani_shock, election_day.

### WebSocket Streaming
```
ws://localhost:8000/api/simulate/stream

{
  "scenario_id": "rbi_rate_cut"
}
```

Yields real-time events: `simulation_start`, `round_start`, `agent_result`, `aggregation`, `simulation_end`.

---

## Troubleshooting

### NSE rate limiting (live market data)
**Problem**: Market data returns zeros or stale values during market hours.

**Solution**:
- Use mock mode: `GODS_EYE_MOCK=true`
- Or use preset scenarios with hardcoded data
- Live data fetcher retries with anti-bot session refresh, but NSE may still block heavy requests

### CORS errors
**Problem**: Frontend can't reach backend API.

**Solution**:
- Check `GODS_EYE_CORS_ORIGINS` includes your frontend URL
- In development: `http://localhost:5173`
- In Docker: `http://localhost` (frontend) and `http://backend:8000` (internal)

### Slow simulations
**Expected**: 8-15 seconds per simulation (6 agents × parallel requests)

**Quant agent**: <100ms
**LLM agents**: 1-2 seconds each (run in parallel)

### "No module named 'app'"
**Solution**: Ensure you're in the `backend/` directory and Python path is correct.

```bash
cd backend
export PYTHONPATH="."
python run.py
```

---

## What's Next

- **Live Trading**: Connect to a broker API to execute signals
- **Backtesting**: Replay historical data through the agents
- **Database Upgrade**: Migrate from SQLite to PostgreSQL for production
- **Monitoring**: Add Prometheus metrics and Grafana dashboards

See `DEPLOYMENT.md` for containerized production setup and `CHANGELOG.md` for recent updates.
