# God's Eye — Multi-Agent Indian Market Simulation

Real-time market analysis powered by 6 AI agents that debate, challenge each other, and reach consensus on Indian stock market direction.

## How It Works

```
Market Data (NSE/BSE, FII/DII flows, USD/INR, DXY)
        ↓
┌──────────────────────────────────────────────┐
│  Round 1: Independent Analysis               │
│  6 agents analyze from their specialty       │
├──────────────────────────────────────────────┤
│  Round 2: Debate & Challenge                 │
│  Agents see each other's calls, push back    │
├──────────────────────────────────────────────┤
│  Round 3: Final Revision (if disagreement)   │
│  Agents update positions after debate        │
├──────────────────────────────────────────────┤
│  Aggregation: Weighted Consensus             │
│  Conviction-weighted final direction + score │
└──────────────────────────────────────────────┘
        ↓
  Direction (Bullish/Bearish/Neutral)
  Conviction (0-100%), Consensus Score
```

## The 6 Agents

| Agent | Analyzes |
|-------|----------|
| **Technical** | Price action, chart patterns, support/resistance |
| **Fundamental** | FII/DII flows, sector rotation, valuations |
| **Sentiment** | News, social media, fear/greed indicators |
| **Algorithmic** | Quantitative signals, statistical patterns |
| **Macro** | RBI policy, USD/INR, global cues, DXY |
| **Options Flow** | Put/call ratios, max pain, unusual activity |

## Architecture

```
gods-eye/
├── backend/                  # FastAPI + Python
│   ├── app/
│   │   ├── agents/          # 6 AI agent implementations
│   │   ├── api/             # REST endpoints + WebSocket
│   │   ├── auth/            # JWT auth + device OAuth
│   │   ├── data/            # Market data feeds + cache
│   │   ├── engine/          # Orchestrator + aggregator
│   │   ├── learning/        # Skill store + review engine
│   │   └── memory/          # Agent memory + prediction tracking
│   ├── tests/               # 26 tests (pytest)
│   └── alembic/             # Database migrations
├── frontend/                 # React + Vite + Tailwind
│   ├── src/
│   │   ├── components/      # UI components
│   │   ├── pages/           # Dashboard, History, Settings, etc.
│   │   ├── hooks/           # useSimulation, useStreamingSimulation
│   │   ├── api/             # API client with retry logic
│   │   └── __tests__/       # 12 tests (vitest)
│   └── nginx.conf           # Production reverse proxy
└── docker-compose.yml        # One-command deployment
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- An LLM API key (Claude, OpenAI, or Gemini)

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # Edit: add your API key
python -m uvicorn run:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
cp .env.example .env
npm run dev                   # Opens on http://localhost:5173
```

### Docker (Production)

```bash
cp .env.example .env          # Edit: add your API key, set GODS_EYE_ENV=production
docker compose up --build -d

# App available at http://localhost:80
# Backend API at http://localhost:80/api/
```

## Key Features

- **Real-time streaming** — Watch agents think and debate via WebSocket
- **Scenario presets** — Budget Day, RBI Policy, Earnings Season, Global Crisis, etc.
- **Custom scenarios** — Define your own market conditions
- **Agent memory** — Agents learn from past predictions
- **Skill system** — Agents develop specialized skills over time
- **Paper trading** — Track predictions against actual outcomes
- **JWT auth** — Protected API with rate limiting
- **Encrypted tokens** — OAuth tokens encrypted at rest (Fernet)

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | No | Health check |
| POST | `/auth/login` | No | Start device auth flow |
| GET | `/auth/poll/{code}` | No | Poll for auth completion |
| POST | `/simulate` | Yes | Run full simulation |
| WS | `/ws/simulate` | No | Streaming simulation |
| GET | `/presets` | Yes | List scenario presets |
| GET | `/history` | Yes | Simulation history |
| GET | `/learning/skills` | Yes | Agent skills |

## Testing

```bash
# Backend (26 tests)
cd backend
pytest -v

# Frontend (12 tests)
cd frontend
npm test

# Load testing
cd backend
locust -f locustfile.py --host=http://localhost:8000
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GODS_EYE_LLM_PROVIDER` | `claude` | LLM provider (claude/openai/gemini) |
| `GODS_EYE_MODEL` | `claude-sonnet-4-20250514` | Model name |
| `LLM_API_KEY` | — | Your API key |
| `GODS_EYE_ENV` | `development` | Environment (development/production) |
| `GODS_EYE_MOCK_MODE` | `false` | Use mock responses (no API key needed) |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins |

## Documentation

- [SETUP.md](./SETUP.md) — Detailed setup walkthrough
- [DEPLOYMENT.md](./DEPLOYMENT.md) — Docker deployment guide
- [CHANGELOG.md](./CHANGELOG.md) — Version history
- [QA_REPORT.md](./QA_REPORT.md) — Test results & security checklist
- [LAUNCH_PLAN.md](./LAUNCH_PLAN.md) — Production launch plan
