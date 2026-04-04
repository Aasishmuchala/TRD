# God's Eye Backend - Setup & Architecture Guide

## Overview

God's Eye is a production-ready multi-agent AI market simulation system for Indian markets. It simulates the behavior of 6 different market participant types using a combination of quantitative algorithms and Claude LLM-powered agents.

## Architecture

### Agent Types

1. **FII Agent** (LLM-powered): Foreign Institutional Investor behavior
   - Tracks USD/INR, DXY, yield spreads, EM sentiment
   - Time horizon: Quarterly
   - Conviction based on capital allocation signals

2. **DII Agent** (LLM-powered): Domestic Institutional Investor behavior
   - Monitors SIP inflows, sector mandates, SEBI compliance
   - Time horizon: Quarterly
   - Conservative risk appetite, long-term horizon

3. **Retail F&O Agent** (LLM-powered): Retail derivatives trader behavior
   - Focused on technical levels, expiry dynamics, gamma squeezes
   - Time horizon: Intraday
   - Aggressive risk appetite, social sentiment tracking

4. **Promoter Agent** (LLM-powered): Company insider behavior
   - Tracks pledge ratios, bulk deals, control dynamics
   - Time horizon: Yearly
   - Conservative, focused on maintaining control

5. **RBI Policy Agent** (LLM-powered): Central bank policy response
   - Analyzes inflation, forex, growth vs stability tradeoff
   - Time horizon: Quarterly
   - Dovish = rate cuts (STRONG_BUY), Hawkish = rate hikes (STRONG_SELL)

6. **Algo Agent** (Pure Quant): Technical algorithm analysis
   - Uses RSI, MACD, Bollinger Bands, PCR, VIX regimes
   - Time horizon: Intraday
   - Fully deterministic (reproducible=True)

### Simulation Flow

```
Market Input (NIFTY, VIX, flows, FX, etc.)
    ↓
[ROUND 1] - All agents analyze independently
    ↓
[ROUND 2] - Agents receive R1 outputs, adjust positions
    ↓
[DECISION] - If any agent changed direction, proceed to Round 3
    ↓
[ROUND 3] - Confirmation round (optional)
    ↓
[AGGREGATION] - Weighted consensus with conflict detection
    ↓
Final Direction + Conviction + Reasoning
```

### Agent Weights (Config)

```python
{
    "FII": 0.30,
    "DII": 0.25,
    "RETAIL_FNO": 0.15,
    "ALGO": 0.10,
    "PROMOTER": 0.10,
    "RBI": 0.10,
}
```

### Configuration

All settings in `app/config.py`:

- **CLAUDE_API_KEY**: Set via environment variable
- **MODEL**: claude-sonnet-4-20250514
- **SAMPLES_PER_AGENT**: 3 (parallel LLM calls for consensus)
- **INTERACTION_ROUNDS**: 3
- **TEMPERATURE**: 0.3 (deterministic)

## Installation

### Prerequisites
- Python 3.10+
- CLAUDE_API_KEY environment variable set

### Setup Steps

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variable
export CLAUDE_API_KEY="sk-..."

# 4. Run server
python run.py
```

Server starts on `http://0.0.0.0:8000`

## API Endpoints

### POST /api/simulate
Run a market simulation.

**Request:**
```json
{
  "nifty_spot": 20500,
  "india_vix": 15.2,
  "fii_flow_5d": 150.0,
  "dii_flow_5d": 200.0,
  "usd_inr": 82.5,
  "dxy": 104.2,
  "pcr_index": 1.3,
  "max_pain": 20400,
  "dte": 8,
  "context": "normal",
  "historical_prices": [20200, 20250, 20300, 20350, 20400, 20500]
}
```

**Response:**
```json
{
  "simulation_id": "sim_abc123",
  "timestamp": "2026-03-30T10:30:00Z",
  "market_input": {...},
  "agents_output": {
    "FII": {
      "agent_name": "FII Flows Analyst",
      "direction": "BUY",
      "conviction": 65,
      "reasoning": "...",
      "key_triggers": [...]
    },
    ...
  },
  "aggregator_result": {
    "final_direction": "BUY",
    "final_conviction": 62,
    "consensus_score": 35.2,
    "conflict_level": "HIGH_AGREEMENT",
    "quant_consensus": "BUY",
    "llm_consensus": "BUY",
    "agreement_boost": 1.15
  },
  "execution_time_ms": 8500.0,
  "model_used": "claude-sonnet-4-20250514"
}
```

### GET /api/presets
List all 8 preset scenarios.

### GET /api/presets/{scenario_id}
Get specific preset scenario with pre-filled market data.

Available scenarios:
- `rbi_rate_cut` - RBI announces rate cut
- `fii_exodus` - FII mass selling
- `budget_bull` - Pro-growth budget
- `budget_bear` - Fiscal shock
- `expiry_carnage` - Options expiry squeeze
- `global_contagion` - Global crisis spreads
- `adani_shock` - Corporate governance shock
- `election_day` - Election result surprise

### GET /api/history
Get paginated simulation history.

Parameters:
- `limit`: Results per page (default: 20)
- `offset`: Pagination offset (default: 0)

### POST /api/history/{simulation_id}/outcome
Record actual market outcome to track prediction accuracy.

**Request:**
```json
{
  "actual_direction": "BUY",
  "notes": "Market rallied as expected"
}
```

### GET /api/metrics
Get accuracy metrics for recent predictions.

Parameters:
- `lookback_days`: How many days back (default: 30)

### GET /api/health
Health check endpoint.

## Key Components

### BaseAgent (`app/agents/base_agent.py`)
Abstract base class for all agents. Subclasses implement `analyze()` method.

**AgentResponse Structure:**
- `agent_name`: Agent identifier
- `agent_type`: "QUANT" or "LLM"
- `direction`: STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
- `conviction`: 0-100 confidence score
- `reasoning`: Agent's explanation
- `key_triggers`: List of decision factors
- `views`: Multi-timeframe analysis (intraday/weekly/monthly)
- `internal_consistency`: 0-1 (only for LLM agents)
- `reproducible`: Boolean (True for QUANT, False for LLM)

### Orchestrator (`app/engine/orchestrator.py`)
Manages 3-round simulation flow:
1. Runs QUANT agents first (instant)
2. Runs LLM agents in parallel
3. Checks for direction changes
4. Optionally runs Round 3 for confirmation

### Aggregator (`app/engine/aggregator.py`)
Computes weighted consensus from all agents:

**Standard Aggregation:**
- Converts directions to numeric scores: STRONG_BUY=1.0, BUY=0.6, HOLD=0, SELL=-0.6, STRONG_SELL=-1.0
- Weights by agent importance (config.AGENT_WEIGHTS)
- Scales by conviction (0-100)
- Returns consensus_score (-100 to +100)

**Hybrid Aggregation (Enabled by Default):**
- Quant agents: 45% weight
- LLM agents: 55% weight
- If agreement: 1.15x boost to conviction
- If disagreement: 0.70x penalty to conviction

### SignalEngine (`app/data/signal_engine.py`)
Pre-processes market indicators:
- RSI(14) computation
- MACD signal line
- Bollinger Bands position
- VIX regime classification (low_fear / normal / elevated / high_fear)
- PCR regime (extremely_bullish to extremely_bearish)
- Z-scores for flow anomalies

### PredictionTracker (`app/memory/prediction_tracker.py`)
SQLite-based prediction logging:
- Stores all simulations and predictions
- Records actual outcomes when reported
- Computes accuracy metrics by direction
- Supports pagination for history

## LLM Agent Prompts

Each LLM agent receives:
1. **Persona**: Role description (FII manager, retail trader, etc.)
2. **Framework**: Decision-making factors specific to that agent
3. **Market Data**: Current NIFTY, VIX, flows, FX, PCR, context
4. **Interaction Info**: Other agents' Round 1 decisions (in R2/R3)
5. **Response Format**: Structured JSON with direction, conviction, triggers

All prompts enforce:
- 3 parallel calls per agent (n_samples=3)
- Temperature=0.3 (low variance)
- Majority-vote consensus for final direction
- Conviction penalty by consistency

## Sample Usage

```python
from app.api.schemas import MarketInput
from app.engine.orchestrator import Orchestrator
from app.engine.aggregator import Aggregator
import asyncio

async def test_simulation():
    market_data = MarketInput(
        nifty_spot=20500,
        india_vix=15.2,
        fii_flow_5d=150.0,
        dii_flow_5d=200.0,
        usd_inr=82.5,
        dxy=104.2,
        pcr_index=1.3,
        max_pain=20400,
        dte=8,
        context="normal",
    )

    orchestrator = Orchestrator()
    result = await orchestrator.run_simulation(market_data)

    aggregator_result = Aggregator.aggregate(result["final_outputs"], hybrid=True)

    print(f"Direction: {aggregator_result.final_direction}")
    print(f"Conviction: {aggregator_result.final_conviction:.1f}")
    print(f"Consensus Score: {aggregator_result.consensus_score:.2f}")

asyncio.run(test_simulation())
```

## Production Checklist

- [x] All agent implementations complete (6 agents)
- [x] 3-round orchestration with interaction effects
- [x] Weighted consensus aggregation (standard + hybrid)
- [x] SQLite prediction tracking
- [x] 8 preset market scenarios
- [x] Full FastAPI server with CORS
- [x] Comprehensive error handling
- [x] Production-ready prompts for all LLM agents
- [x] Type hints throughout (Pydantic models)
- [x] No TODOs or placeholders

## Deployment Notes

1. **API Key**: Set CLAUDE_API_KEY before running
2. **CORS**: Configured for localhost:5173 (Vite frontend) and localhost:3000
3. **Database**: SQLite file created automatically on first run
4. **Async**: All agents run asynchronously (LLM agents in parallel)
5. **Rate Limiting**: Implement if deploying to production with high traffic

## Troubleshooting

**"CLAUDE_API_KEY not set"**
- Export: `export CLAUDE_API_KEY="sk-..."`

**"LLM agent returning null"**
- Check Claude API response format in agent code
- Increase temperature temporarily to debug
- Review prompt for JSON parsing issues

**"Slow simulation execution"**
- Normal: 8-15 seconds (3 LLM agents × 3 samples = 9 Claude API calls)
- Quant agent: <100ms
- LLM agent: 1-2 seconds per agent (sequential samples)

## File Structure

```
god's-eye/backend/
├── app/
│   ├── agents/                    # 6 agent implementations
│   │   ├── base_agent.py         # Abstract base
│   │   ├── algo_agent.py         # QUANT agent
│   │   ├── fii_agent.py          # FII LLM agent
│   │   ├── dii_agent.py          # DII LLM agent
│   │   ├── retail_fno_agent.py   # Retail LLM agent
│   │   ├── promoter_agent.py     # Promoter LLM agent
│   │   └── rbi_policy_agent.py   # RBI LLM agent
│   ├── api/                      # FastAPI layer
│   │   ├── routes.py             # All HTTP endpoints
│   │   └── schemas.py            # Pydantic models
│   ├── engine/                   # Simulation engine
│   │   ├── orchestrator.py       # 3-round simulation
│   │   ├── streaming_orchestrator.py  # WebSocket streaming
│   │   ├── aggregator.py         # Weighted consensus
│   │   ├── feedback_engine.py    # Accuracy-tuned weights
│   │   └── scenarios.py          # 8 preset scenarios
│   ├── data/
│   │   ├── signal_engine.py      # Technical indicators
│   │   ├── market_data.py        # NSE live data pipeline
│   │   └── cache.py              # In-memory TTL cache
│   ├── memory/
│   │   ├── prediction_tracker.py # SQLite prediction log
│   │   └── agent_memory.py       # Per-agent accuracy tracking
│   └── config.py                 # All configuration
├── run.py                        # FastAPI + WebSocket entry
└── requirements.txt              # Dependencies
```

## Phase 2 Features

### Live Market Data (NSE Integration)

Real-time data pipeline from NSE India with anti-bot session management.

**Architecture:**
- `NSESession`: httpx async client with cookie refresh every 4 minutes
- `MarketDataService`: parallel fetchers for Nifty, VIX, FII/DII, options, sectors
- `InMemoryCache`: TTL-based caching (spot=5min, flows=30min, options=2hr)
- Fallback data for all fetchers when NSE is unreachable

**Endpoints:**
- `GET /api/market/live` — Current Nifty, VIX, FII/DII, breadth
- `GET /api/market/options?symbol=NIFTY` — PCR, max pain, top OI strikes
- `GET /api/market/sectors` — Sector index values with % change
- `GET /api/market/cache-stats` — Cache hit/miss stats for debugging

**Live Simulation:**
Send `{"source": "live"}` to POST `/api/simulate` to auto-populate MarketInput from NSE.

### WebSocket Streaming

Real-time simulation streaming via WebSocket at `ws://host/api/simulate/stream`.

**Event Flow:**
```
Client sends: {"scenario_id": "rbi_rate_cut"} or {"source": "live"}
Server yields:
  → simulation_start (market data, config)
  → round_start (round number)
  → agent_result (per agent, in completion order)
  → round_complete (all agents for that round)
  → round_skipped (if Round 3 not needed)
  → aggregation (final consensus result)
  → simulation_end (execution time, simulation ID)
```

**Key Implementation Details:**
- `StreamingOrchestrator` uses AsyncGenerator pattern
- LLM agents stream via `asyncio.wait(FIRST_COMPLETED)` — results appear as each agent finishes
- QUANT agents yield instantly before LLM agents start
- Round 3 automatically skipped when consensus reached in Round 2

### Enhanced Signal Engine

Additional computed indicators in `signal_engine.py`:
- `max_pain_distance_pct` — Distance from spot to max pain as percentage
- `fii_flow_regime` — heavy_buying / buying / neutral / selling / heavy_selling
- `dii_flow_regime` — Same classification for DII
- `dxy_regime` — strong_dollar_headwind / neutral / weak_dollar_tailwind
- `expiry_proximity` — expiry_day / near_expiry / mid_expiry / far_from_expiry

### Feedback Engine

Per-agent accuracy tracking with weight tuning:
- `AgentMemory` (SQLite) stores per-agent predictions and outcomes
- `FeedbackEngine` computes accuracy-tuned weights when sufficient data exists
- `GET /api/feedback/weights` — Accuracy-tuned vs base weights
- `GET /api/feedback/patterns/{agent_id}` — Failure pattern detection with prompt hints
- Agents receive prompt hints based on failure patterns (e.g., "overconfident in high-VIX")

### Frontend Enhancements

- **MarketTicker**: Persistent top bar with live Nifty, VIX, FII/DII, PCR (auto-refreshes 60s)
- **SimulationStream**: Real-time agent result cards during streaming simulation
- **CustomScenarioForm**: Manual market data input (Nifty, VIX, flows, FX, PCR, context)
- **Loading Skeletons**: Shimmer states for PressurePanel and InsightsPanel during simulation
- **Toast Notifications**: Success/error feedback after simulation completes

## Production Checklist

- [x] All agent implementations complete (6 agents)
- [x] 3-round orchestration with interaction effects
- [x] Weighted consensus aggregation (standard + hybrid)
- [x] SQLite prediction tracking
- [x] 8 preset market scenarios
- [x] Full FastAPI server with CORS
- [x] Comprehensive error handling
- [x] Production-ready prompts for all LLM agents
- [x] Type hints throughout (Pydantic models)
- [x] No TODOs or placeholders
- [x] Live market data pipeline (NSE)
- [x] WebSocket streaming simulation
- [x] Feedback engine with weight tuning
- [x] Custom scenario input form
- [x] Loading skeleton states
- [x] Market ticker component
