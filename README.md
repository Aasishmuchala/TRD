# God's Eye — Multi-Agent Indian Market Intelligence

A multi-agent AI system that simulates the behavioral forces driving Indian equity markets (NSE/BSE). Six AI agents — modeled on the actual participants that move Indian markets — independently analyze scenarios through a 3-round debate and produce a weighted consensus on market direction.

## What It Does

```
Market conditions (live or manual)
  -> 6 AI agents analyze independently (Round 1)
  -> Agents react to each other's positions (Round 2)
  -> Final positions with conviction scores (Round 3)
  -> Weighted consensus: BULLISH/BEARISH + confidence %
```

### The 6 Agents

| Agent | Models After | Weight |
|-------|-------------|--------|
| **FII** | Goldman, Morgan Stanley India desks | 0.30 |
| **DII** | SBI MF, HDFC AMC, LIC | 0.25 |
| **Retail F&O** | Zerodha/Groww retail crowd | 0.15 |
| **Algo/Quant** | Tower Research, quant desks | 0.10 |
| **Promoter** | Company management, insider flows | 0.10 |
| **RBI/Policy** | Reserve Bank of India | 0.10 |

### Features

- **Real-time streaming** — watch agents debate live via WebSocket
- **Accuracy feedback** — agent weights auto-tune from prediction accuracy
- **Auto-learning** — extracts patterns from past simulations
- **Paper trading** — 6-criteria graduation system
- **Live market data** — Nifty, Bank Nifty, VIX, FII/DII flows
- **Preset scenarios** — Budget Day, RBI MPC, FII Exodus, Expiry Week
- **Skills page** — view learned patterns per agent
- **CSV export** — download simulation history

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- LLM API key (OpenAI or Anthropic)

### Backend

```bash
cd gods-eye/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add your LLM_API_KEY
python run.py          # -> http://localhost:8000
```

### Frontend

```bash
cd gods-eye/frontend
npm install
npm run dev            # -> http://localhost:5173
```

Open `http://localhost:5173` -> enter API key -> run simulations.

### Mock Mode

Click **Try Mock Mode** on the Welcome page to explore with simulated data. No API key needed.

### Docker

```bash
cd gods-eye
cp .env.example .env
docker compose up --build
```

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python, FastAPI, SQLite, Alembic |
| Frontend | React 18, Tailwind CSS, Recharts, Vite |
| AI | Multi-provider LLM (OpenAI, Anthropic, custom) |
| Streaming | WebSocket (real-time agent events) |
| Data | NSE India live data + fallback mocks |

## UI Screens

| Screen | What It Shows |
|--------|---------------|
| **Welcome** | API key entry, mock mode, agent network viz |
| **Dashboard** | Scenario input, agent pressure bars, insights, live ticker |
| **Agent Detail** | Per-agent accuracy, reasoning by round, failure patterns |
| **History** | Filterable table, outcome recording, CSV export |
| **Paper Trading** | Progress ring, 6-criteria graduation checklist |
| **Settings** | Agent weights, Quant/LLM balance (45/55), sim params |
| **Skills** | Learned patterns per agent, learning toggle |

## Environment Variables

### Backend (`gods-eye/backend/.env.example`)

| Variable | Required | Default |
|----------|----------|---------|
| `LLM_API_KEY` | Yes | — |
| `GODS_EYE_LLM_PROVIDER` | No | `openai` |
| `GODS_EYE_MODEL` | No | `o4-mini` |
| `GODS_EYE_MOCK` | No | `false` |
| `GODS_EYE_DB_PATH` | No | `~/gods_eye.db` |

### Frontend (`gods-eye/frontend/.env.example`)

| Variable | Required | Default |
|----------|----------|---------|
| `VITE_API_BASE` | No | `/api` (local proxy) |
| `VITE_WS_BASE` | No | Same host (local) |

## API

| Endpoint | Description |
|----------|-------------|
| `POST /api/simulate` | Run simulation (REST) |
| `WS /api/simulate/stream` | Run simulation (streaming) |
| `GET /api/history` | Simulation history |
| `GET /api/agent/{id}/accuracy` | Per-agent stats |
| `GET /api/market/live` | Live Nifty/VIX/FII/DII |
| `GET/POST /api/settings` | Simulation config |
| `GET /api/learning/skills` | Learned patterns |
| `GET /api/health` | Health check |

## Project Structure

```
gods-eye/
  backend/
    app/
      agents/        # 6 LLM agents + 1 quant agent
      engine/        # Orchestrator, aggregator, streaming
      learning/      # Auto-learning, skill extraction
      memory/        # Agent memory, prediction tracking
      data/          # Market data, signals
      api/           # Routes + schemas
    run.py
  frontend/
    src/
      pages/         # 7 screens
      components/    # 18 reusable components
      constants/     # Canonical agent definitions
      hooks/         # Streaming simulation hook
      api/           # API client
  .env.example       # Deployment checklist
```

## Design

Apple dark mode + Claude warm palette. Background `#0A0A0F`, primary coral `#D97757`, frosted glass cards, Inter + JetBrains Mono typography.

## License

Private — All rights reserved.
