# God's Eye AI Market Simulation — Full Build Plan
## Indian Markets Multi-Agent Simulation System

---

# PART 1: CEO REVIEW (Founder Mode)

## The Big Question: Is This the Right Thing to Build?

**Verdict: Yes — with a sharper edge.**

The doc describes a generic multi-agent simulation. That's a starting point, not a product. The 10x version is a **India-specific market intelligence system** where the agents aren't abstract archetypes — they're modeled on the actual forces that move Indian markets: FII flows, DII accumulation, retail F&O frenzy, and algo-driven momentum.

---

## Scope Mode: SELECTIVE EXPANSION

Holding the core concept (multi-agent simulation) but cherry-picking three high-leverage expansions that make this genuinely useful rather than a toy demo.

### Expansion 1: India-Specific Agent Archetypes

The doc's generic agents (Retail, Institutional, Momentum, Panic) don't capture what actually moves NSE/BSE. Replace with:

| Agent | Modeled After | Behavioral Triggers |
|-------|--------------|---------------------|
| **FII (Foreign Institutional)** | Goldman, Morgan Stanley India desks | USD/INR moves, US Fed policy, DXY strength, India weight in MSCI EM, quarterly rebalancing windows |
| **DII (Domestic Institutional)** | SBI MF, HDFC AMC, LIC | SIP inflows (steady accumulation), SEBI regulations, quarterly deployment targets, sector rotation mandates |
| **Retail F&O Trader** | Zerodha/Groww retail crowd | Social media sentiment (Twitter/X, Telegram groups), Nifty round numbers, expiry-day gamma, FOMO on breakouts |
| **Algo/HFT** | Tower Research, Edelweiss quant desk | Order book imbalance, VWAP deviations, co-location speed, arbitrage between NSE/BSE/SGX Nifty |
| **Promoter/Insider** | Company management, pledged holdings | Bulk/block deal data, pledge ratios, SEBI disclosure filings |
| **RBI/Policy Agent** | Reserve Bank of India | Repo rate decisions, CRR/SLR changes, forex intervention signals, inflation data (CPI/WPI) |

**Why this matters:** A simulation with "Retail Investor" and "Institutional Investor" is a textbook exercise. A simulation with FII/DII dynamics, expiry-day effects, and RBI policy response is something traders actually want to look at.

### Expansion 2: Event-Driven Scenario Engine

Instead of just static "input market conditions," build a scenario engine that can model:

- **Budget Day simulation** — How do FIIs react to capital gains tax changes? How does retail respond to STT hikes?
- **RBI MPC day** — Rate hold vs cut vs hike cascading through agents
- **Global contagion** — US recession signal → FII outflow → DII absorption capacity → retail panic chain
- **Expiry week dynamics** — Max pain theory, OI buildup, gamma exposure shifts
- **SEBI regulation shocks** — New F&O margin rules, short-selling restrictions

### Expansion 3: Visual Pressure Map Dashboard

The doc mentions "dashboards" as a future extension. Make it core. The killer output isn't a text summary — it's a **real-time pressure heatmap** showing:

- Which agent class is dominant right now (buyer vs seller pressure by agent type)
- Confidence levels per agent with reasoning
- Conflicting signals highlighted (e.g., FII selling but DII absorbing = tug-of-war)
- Historical simulation accuracy tracking

---

## NOT In Scope (Phase 1)

- Live order execution or paper trading
- Portfolio management features
- Backtesting against historical data (Phase 2)
- Mobile app (web-first)
- Multi-user / SaaS features
- Real money or brokerage API integration

---

## Architecture Vision (ASCII)

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Scenario  │  │  Pressure    │  │  Agent Behavior   │  │
│  │ Input     │  │  Heatmap     │  │  Timeline         │  │
│  │ Panel     │  │  Dashboard   │  │  (per-agent view) │  │
│  └─────┬────┘  └──────┬───────┘  └────────┬──────────┘  │
│        └───────────────┼──────────────────-┘             │
│                        │ REST API / WebSocket             │
├────────────────────────┼────────────────────────────────-┤
│                    BACKEND (Python/FastAPI)               │
│  ┌─────────────────────┴──────────────────────────┐      │
│  │            Simulation Orchestrator              │      │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │      │
│  │  │  FII   │ │  DII   │ │ Retail │ │  Algo  │  │      │
│  │  │ Agent  │ │ Agent  │ │ F&O    │ │ Agent  │  │      │
│  │  │        │ │        │ │ Agent  │ │        │  │      │
│  │  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘  │      │
│  │      └──────────┼─────────-┼──────────┘        │      │
│  │                 ▼                               │      │
│  │        Market Pressure Aggregator               │      │
│  │        (weighted consensus engine)              │      │
│  └────────────────────┬───────────────────────────┘      │
│                       │                                   │
│  ┌────────────────────┴───────────────────────────┐      │
│  │              Data Layer                         │      │
│  │  Phase 1: Manual Input + Static Datasets        │      │
│  │  Phase 2: NSE/BSE APIs, MoneyControl scraping,  │      │
│  │           FII/DII daily flow data, RBI feeds    │      │
│  └────────────────────────────────────────────────┘      │
│                                                           │
│  ┌────────────────────────────────────────────────┐      │
│  │           Claude AI Engine                      │      │
│  │  Each agent = structured prompt with persona,   │      │
│  │  decision framework, and market data context    │      │
│  └────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────-┘
```

---

## Error & Rescue Map

| Failure Mode | Impact | Rescue Strategy |
|-------------|--------|-----------------|
| Claude API rate limits hit during multi-agent simulation | Simulation hangs mid-run | Queue agents, run sequentially with caching, show partial results |
| Agents produce contradictory nonsense | User loses trust | Confidence scoring + "low confidence" warnings when agents disagree beyond threshold |
| Indian market data source goes down (Phase 2) | Can't feed real data | Graceful fallback to last-known data with staleness indicator |
| Simulation takes too long (6 API calls per run) | Poor UX | Parallel agent execution + streaming results as each agent completes |
| User inputs unrealistic scenario | Garbage in, garbage out | Input validation with preset ranges for Indian market parameters |

---

## Key Insight from CEO Review

The original doc positions this as "educational and research purposes only." That's fine as a disclaimer, but the product should be built as if a derivatives trader on Dalal Street would actually use it to think through scenarios before market open. **Build it for the sharpest user, disclaim for the newest one.**

---

---

# PART 2: ENG REVIEW (Engineering Manager Mode)

## Step 0: Scope Check

- Files to create: ~12-15 (manageable)
- New abstractions: Agent base class + 6 agent implementations + orchestrator + API layer
- Complexity: **Medium** — the hard part is prompt engineering per agent, not the system architecture

**Verdict: Proceed. Not over-scoped.**

---

## Tech Stack Decision

| Layer | Choice | Why |
|-------|--------|-----|
| **Backend** | Python + FastAPI | Best Claude SDK support, fast async, Indian dev ecosystem familiarity |
| **AI Engine** | Claude API (Anthropic SDK) | The doc is designed around Claude; structured output support is excellent |
| **Frontend** | React + Tailwind + Recharts | Fast to build, good charting for pressure maps |
| **Database** | SQLite (Phase 1) → PostgreSQL (Phase 2) | No need for heavy DB initially; store simulation history |
| **Deployment** | Vercel (frontend) + Railway/Render (backend) | Free tiers available, simple deploys |

---

## Data Flow

```
User Input (scenario)
       │
       ▼
┌─────────────────┐
│ /api/simulate    │  ← FastAPI endpoint
│                  │
│  1. Validate     │
│     input        │
│                  │
│  2. Build agent  │
│     contexts     │
│     (6 agents)   │
│                  │
│  3. Fan out to   │──→ Claude API (parallel calls)
│     Claude API   │     - FII agent prompt + market data
│                  │     - DII agent prompt + market data
│  4. Collect      │     - Retail F&O prompt + market data
│     responses    │     - Algo agent prompt + market data
│                  │     - Promoter agent prompt + market data
│  5. Aggregate    │     - RBI/Policy agent prompt + data
│     via Market   │
│     Pressure     │
│     Engine       │
│                  │
│  6. Return       │
│     structured   │
│     result       │
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│ Frontend renders: │
│ - Agent cards     │
│ - Pressure map    │
│ - Direction +     │
│   confidence      │
│ - Key insight     │
└──────────────────┘
```

---

## File Structure

```
gods-eye/
├── backend/
│   ├── main.py                    # FastAPI app + routes
│   ├── config.py                  # API keys, model settings
│   ├── agents/
│   │   ├── base.py                # BaseAgent class
│   │   ├── fii_agent.py           # Foreign Institutional
│   │   ├── dii_agent.py           # Domestic Institutional
│   │   ├── retail_fno_agent.py    # Retail F&O Trader
│   │   ├── algo_agent.py          # Algo/HFT
│   │   ├── promoter_agent.py      # Promoter/Insider
│   │   └── rbi_policy_agent.py    # RBI/Policy
│   ├── engine/
│   │   ├── orchestrator.py        # Runs all agents, manages parallel execution
│   │   ├── aggregator.py          # Market Pressure Aggregator
│   │   └── scenarios.py           # Preset scenario templates
│   ├── models/
│   │   ├── schemas.py             # Pydantic models for input/output
│   │   └── database.py            # SQLite simulation history
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ScenarioInput.jsx      # Market condition form
│   │   │   ├── AgentCard.jsx          # Individual agent result
│   │   │   ├── PressureHeatmap.jsx    # Visual pressure map
│   │   │   ├── DirectionGauge.jsx     # Bull/Bear confidence dial
│   │   │   ├── AgentTimeline.jsx      # Sequential agent reasoning
│   │   │   └── PresetScenarios.jsx    # Quick scenario buttons
│   │   └── api/
│   │       └── simulate.js           # API client
│   ├── package.json
│   └── tailwind.config.js
└── README.md
```

---

## Agent Design Pattern

Each agent follows the same interface but with a unique persona and decision framework:

```python
class BaseAgent:
    name: str
    persona: str           # Who this agent represents
    decision_framework: str # How they analyze markets
    risk_appetite: str      # Conservative / Moderate / Aggressive
    time_horizon: str       # Intraday / Weekly / Quarterly / Yearly

    async def analyze(self, market_data: MarketInput) -> AgentResponse:
        """Send persona + market data to Claude, get structured response"""
        prompt = self._build_prompt(market_data)
        response = await claude_client.messages.create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": prompt}],
            # ... structured output schema
        )
        return self._parse_response(response)
```

**Structured Output per Agent:**
```json
{
  "agent_name": "FII",
  "action": "SELL",
  "conviction": 78,
  "reasoning": "DXY strengthening above 105...",
  "key_triggers": ["USD/INR breach of 84", "MSCI rebalancing window"],
  "position_size_signal": "reducing_exposure",
  "time_horizon": "2-4 weeks",
  "interaction_effects": {
    "amplifies": ["Retail panic if Nifty breaks 22000"],
    "dampens": ["DII SIP flows provide floor"]
  }
}
```

---

## Market Pressure Aggregator Logic

```
Final Score = Σ (agent_conviction × agent_weight × direction_sign)

Weights (tunable):
  FII:          0.30  (biggest market mover in India)
  DII:          0.25  (SIP flows are massive stabilizer)
  Retail F&O:   0.15  (noisy but significant in expiry weeks)
  Algo/HFT:     0.10  (short-term noise, mean-reverting)
  Promoter:     0.10  (low frequency, high signal)
  RBI/Policy:   0.10  (episodic but massive when active)

Direction mapping:
  STRONG_BUY = +1.0, BUY = +0.6, HOLD = 0, SELL = -0.6, STRONG_SELL = -1.0

Conflict detection:
  If top 2 agents disagree by > 1.2 direction gap → flag as "TUG OF WAR"
```

---

## Indian Market Data Sources (Phase 2)

| Data Point | Source | Update Frequency |
|-----------|--------|-----------------|
| Nifty/Sensex live price | NSE API / Yahoo Finance | Real-time |
| FII/DII daily flows | NSDL/CDSL website, moneycontrol | Daily (post-market) |
| Option chain (OI, Greeks) | NSE option chain API | Every 3 min during market hours |
| RBI policy announcements | RBI website RSS | Event-driven |
| USD/INR | RBI reference rate / Yahoo Finance | Daily |
| Bulk/Block deals | BSE/NSE corporate filings | Daily |
| SIP flow data | AMFI monthly reports | Monthly |
| India VIX | NSE | Real-time |
| SGX Nifty (Gift Nifty) | SGX/NSE IFSC | Pre-market |

---

## Preset Scenarios (Ship with these)

1. **RBI Rate Cut Day** — Repo rate cut by 25bps, inflation at 4.5%
2. **FII Mass Exodus** — $2B outflow in a week, DXY at 107
3. **Budget Day (Bull Case)** — No LTCG hike, capex push, defense boost
4. **Budget Day (Bear Case)** — STT doubled on F&O, new surcharge on HNIs
5. **Nifty Expiry Carnage** — Max pain at 22500, Nifty at 22800, massive call writing
6. **Global Contagion** — US bank failure, Nikkei -5%, SGX Nifty gap down
7. **Adani-style Shock** — Short-seller report on major index heavyweight
8. **Election Result Day** — NDA majority vs INDIA bloc surprise

---

## Test Plan

| Test Category | What to Test | Method |
|--------------|-------------|--------|
| Agent isolation | Each agent produces valid structured output | Unit tests with mocked Claude responses |
| Orchestrator | All 6 agents run in parallel, aggregate correctly | Integration test with fixture data |
| Pressure aggregator | Math is correct, conflict detection triggers properly | Unit tests with edge cases |
| API endpoints | /simulate returns valid response, handles bad input | FastAPI TestClient |
| Frontend rendering | Agent cards, heatmap, gauge render with sample data | React Testing Library |
| Scenario presets | All 8 presets load correct parameters | Snapshot tests |
| Rate limit handling | Graceful degradation when Claude API limits hit | Mock 429 responses |

---

## Build Sequence (Phased)

### Phase 1: MVP (Week 1-2)
1. Backend: Agent base class + 6 agent implementations with prompts
2. Backend: Orchestrator + Aggregator
3. Backend: FastAPI endpoints (/simulate, /presets)
4. Frontend: Scenario input form + preset buttons
5. Frontend: Agent result cards + direction gauge
6. End-to-end test with all 8 preset scenarios

### Phase 2: Polish + Data (Week 3-4)
7. Frontend: Pressure heatmap visualization
8. Frontend: Agent timeline / reasoning view
9. Backend: Simulation history (SQLite)
10. Backend: Real-time data integration (NSE, FII/DII flows)
11. Prompt tuning based on real scenario testing

### Phase 3: Advanced (Week 5+)
12. Backtesting: Run past scenarios, compare agent predictions vs actual
13. Custom agent creation (user-defined personas)
14. WebSocket streaming (show each agent's result as it completes)
15. Mobile-responsive design

---

## Review Readiness: GO

| Criterion | Status |
|-----------|--------|
| Architecture clear? | Yes — orchestrator pattern, well-separated agents |
| Scope bounded? | Yes — 6 agents, 8 presets, 2 phases |
| Data sources identified? | Yes — manual Phase 1, NSE/NSDL Phase 2 |
| Risk mitigated? | Yes — rate limits, conflict detection, fallbacks |
| Test plan exists? | Yes — unit, integration, E2E |
| NOT in scope defined? | Yes — no live trading, no mobile, no SaaS |

---

---

# PART 3: MIROFISH REFERENCE PATTERNS

## What to Borrow from MiroFish (github.com/666ghj/MiroFish)

MiroFish is a multi-agent swarm intelligence engine that builds "digital worlds" with thousands of autonomous agents. Here's what's directly applicable:

### 1. GraphRAG Knowledge Construction (BORROW)
MiroFish uses `graph_builder.py` + `ontology_generator.py` to extract entities and relationships from seed data. **Our adaptation:** Build a knowledge graph of Indian market relationships — which sectors are correlated, how FII flows impact specific large-caps, how RBI policy cascades through banking → NBFC → real estate. This makes agent reasoning grounded in real structural relationships, not just vibes.

### 2. Simulation Orchestrator Pattern (BORROW)
MiroFish separates concerns cleanly: `simulation_config_generator.py` → `simulation_runner.py` → `simulation_manager.py` → `simulation_ipc.py`. **Our adaptation:** Same pattern — config generation (scenario → agent parameters), runner (execute agents), manager (coordinate parallel runs), IPC (stream results to frontend).

### 3. Agent Memory via Zep (ADAPT)
MiroFish uses Zep Cloud for persistent agent memory (`zep_tools.py`, `zep_entity_reader.py`, `zep_graph_memory_updater.py`). Agents remember past interactions and evolve. **Our adaptation:** Store each agent's past predictions and accuracy. The FII agent should "remember" that last time DXY crossed 105, it recommended SELL and was correct. This builds compounding intelligence over time. Use SQLite for Phase 1 instead of Zep.

### 4. Profile Generator (BORROW)
`oasis_profile_generator.py` generates distinct agent personalities. **Our adaptation:** Each of our 6 agents gets a rich profile generated from real behavioral data — FII agent's profile is built from actual FII trading patterns, DII from mutual fund flow data, etc.

### 5. Report Agent (BORROW)
MiroFish has a dedicated `report_agent.py` that synthesizes findings from all agents. **Our adaptation:** Our Market Pressure Aggregator serves this role — takes all 6 agent outputs and produces the unified market direction call with confidence scoring.

### What NOT to Borrow
- **OASIS simulation framework** — overkill for 6 agents; we don't need thousands of agents
- **Vue.js frontend** — we're using React for better ecosystem/component availability
- **Zep Cloud dependency** — adds complexity and cost; SQLite → PostgreSQL is sufficient
- **Docker-first deployment** — Phase 1 should be simple local dev; containerize in Phase 2

---

## Updated File Structure (with MiroFish patterns)

```
gods-eye/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                  # API keys, model settings, agent weights
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py              # FastAPI endpoints
│   │   │   └── schemas.py             # Pydantic request/response models
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py          # BaseAgent ABC
│   │   │   ├── profile_generator.py   # ← from MiroFish pattern
│   │   │   ├── fii_agent.py
│   │   │   ├── dii_agent.py
│   │   │   ├── retail_fno_agent.py
│   │   │   ├── algo_agent.py
│   │   │   ├── promoter_agent.py
│   │   │   └── rbi_policy_agent.py
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py        # ← simulation_manager pattern
│   │   │   ├── runner.py              # ← simulation_runner pattern
│   │   │   ├── aggregator.py          # ← report_agent pattern
│   │   │   └── scenarios.py           # Preset Indian market scenarios
│   │   ├── knowledge/
│   │   │   ├── __init__.py
│   │   │   ├── market_graph.py        # ← graph_builder pattern
│   │   │   └── sector_relationships.py # Indian market sector correlations
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── agent_memory.py        # ← zep pattern (SQLite-based)
│   │   │   └── prediction_tracker.py  # Track accuracy over time
│   │   └── data/
│   │       ├── __init__.py
│   │       ├── manual_input.py        # Phase 1: user-provided data
│   │       └── live_feeds.py          # Phase 2: NSE/BSE/NSDL APIs
│   ├── run.py
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ScenarioInput.jsx
│   │   │   ├── PresetScenarios.jsx
│   │   │   ├── AgentCard.jsx
│   │   │   ├── PressureHeatmap.jsx
│   │   │   ├── DirectionGauge.jsx
│   │   │   ├── AgentTimeline.jsx
│   │   │   └── SimulationHistory.jsx
│   │   ├── hooks/
│   │   │   └── useSimulation.js
│   │   └── api/
│   │       └── client.js
│   ├── package.json
│   └── tailwind.config.js
└── README.md
```

---

## Recommendation

**Start with Phase 1.** Get the 6 India-specific agents producing structured analysis for the 8 preset scenarios. That alone is a compelling product. The dashboard makes it visual, but the agent reasoning is the core value.

**The single most important thing to get right:** The agent prompts. Each agent's persona, decision framework, and interaction logic is where the magic lives. Spend 60% of development time on prompt engineering, 40% on code.

**Key MiroFish takeaway:** Their separation of graph construction → profile generation → simulation running → report synthesis is a clean pattern. We're borrowing that pipeline shape while keeping it lightweight (6 agents, not thousands).

---

# PART 4: ACCURACY OVERHAUL

## The Core Problem with V1

The original design treats agents as pure LLM role-players. You describe market conditions in text, Claude pretends to be an FII, and gives you a text opinion. This is **narrative analysis, not market simulation**. It feels smart but has no feedback loop, no quantitative grounding, and no way to know if it's right or wrong.

The accuracy overhaul transforms this from "LLM role-play" into a **hybrid quantitative-narrative intelligence system**.

---

## Improvement 1: Quantitative Signal Layer (Before Agents Think)

**Problem:** Agents currently receive text descriptions of market conditions. "Nifty is at 22500, FII sold ₹3000 Cr yesterday" — but they have no numerical context for whether that's normal, extreme, or historically significant.

**Solution:** Build a **Signal Engine** that preprocesses raw market data into quantitative signals BEFORE sending to agents. Each agent receives both the raw data AND computed signals relevant to their archetype.

```
Raw Data (from APIs)
       │
       ▼
┌─────────────────────────────────────┐
│         SIGNAL ENGINE               │
│                                     │
│  For FII Agent:                     │
│  • FII 5-day flow Z-score: -2.3     │  ← "This is a 2.3σ selling event"
│  • USD/INR 20-day trend: +1.8%      │
│  • DXY percentile (52w): 87th       │
│  • India weight in MSCI EM: 18.2%   │
│  • Net FII F&O position: -₹14,200Cr │
│                                     │
│  For Retail F&O Agent:              │
│  • PCR (Put-Call Ratio): 0.72       │  ← "Retail is excessively bullish"
│  • Max Pain for current expiry:22200│
│  • Nifty distance from max pain:+300│
│  • Retail long/short ratio: 3.2:1   │
│  • Days to expiry: 2                │
│                                     │
│  For DII Agent:                     │
│  • Monthly SIP inflow: ₹21,000 Cr  │
│  • DII 5-day cumulative: +₹8,400 Cr│
│  • Nifty PE vs 5yr avg: 22.1/20.8  │
│  • Sector rotation signal: IT→Banks │
│                                     │
│  ... (similar for each agent)       │
└─────────────────────────────────────┘
```

**Why this matters:** When the FII agent sees "Z-score: -2.3", it knows this is a statistically extreme event, not just "FII sold a lot." The LLM's job shifts from guessing magnitude to interpreting context — which it's actually good at.

---

## Improvement 2: Multi-Round Agent Interaction (Agents React to Each Other)

**Problem:** In V1, all 6 agents analyze independently and we aggregate. But in reality, FII selling *causes* retail panic, and DII absorption *dampens* that panic. The agents don't interact.

**Solution:** Run simulation in **3 rounds**:

```
ROUND 1: Independent Analysis
  Each agent analyzes market data in isolation
  Output: Initial position + conviction

ROUND 2: Reaction Round
  Each agent receives Round 1 outputs of ALL other agents
  "FII is selling with 85% conviction. DII is buying with 70% conviction.
   Retail is panicking with 60% conviction."
  Each agent adjusts their position based on how they'd REACT to others' actions
  Output: Adjusted position + conviction + reasoning for adjustment

ROUND 3: Equilibrium Check
  If any agent changed direction between R1→R2, run one more round
  Otherwise, positions are stable — aggregate final results
  Output: Final consensus with interaction narrative
```

**Example of why this matters:**
- Round 1: FII says SELL (80%), Retail says BUY (65%)
- Round 2: Retail sees FII selling heavily → switches to SELL (55%), FII sees DII absorbing → reduces conviction to SELL (65%)
- Round 3: Stabilized — net bearish but with DII floor

This produces **emergent market dynamics** instead of 6 disconnected opinions.

---

## Improvement 3: Quantitative Anchoring with Technical Indicators

**Problem:** Claude is a language model, not a quant model. It can reason about narratives but doesn't natively compute RSI, MACD, or Bollinger Bands.

**Solution:** Pre-compute technical indicators and feed them as structured facts:

```python
# Computed BEFORE sending to agents
technical_signals = {
    "nifty": {
        "rsi_14": 72.3,           # Overbought territory
        "rsi_interpretation": "overbought — historically 68% chance of pullback within 5 sessions",
        "macd_signal": "bearish_crossover",  # MACD just crossed below signal line
        "macd_days_since_cross": 1,
        "bb_position": 0.92,      # 92% toward upper band
        "bb_interpretation": "near upper band — mean reversion likely",
        "vwap_deviation": "+1.2%", # Trading above VWAP
        "support_levels": [22100, 21800, 21500],
        "resistance_levels": [22600, 22800, 23000],
        "india_vix": 14.2,
        "india_vix_percentile_52w": 28,  # Low fear
        "advance_decline_ratio": 0.8,    # More decliners
        "fii_index_futures_oi_change": "-12%",
        "gift_nifty_premium": "+0.3%"
    }
}
```

Each agent receives the indicators relevant to their decision framework. The Algo agent gets all of them. The RBI agent gets mostly macro indicators. The retail agent gets PCR, max pain, and social sentiment scores.

---

## Improvement 4: Self-Learning Feedback Loop

This is the most critical accuracy improvement. The system tracks every prediction and learns from outcomes.

### 4a: Prediction Logging

Every simulation run is stored with a timestamp and a "check window":

```python
prediction_log = {
    "id": "sim_20260330_1",
    "timestamp": "2026-03-30T09:00:00+05:30",
    "scenario": "manual_input",
    "market_state_at_prediction": {
        "nifty_spot": 22500,
        "india_vix": 14.2,
        # ... full market snapshot
    },
    "agent_predictions": {
        "fii": {"direction": "SELL", "conviction": 78, "time_horizon": "1_week"},
        "dii": {"direction": "BUY", "conviction": 70, "time_horizon": "1_week"},
        # ... all agents
    },
    "aggregate_prediction": {
        "direction": "BEARISH",
        "score": -0.32,
        "confidence": 65
    },
    "check_windows": ["1_day", "3_day", "1_week", "2_week"],
    "actual_outcomes": {}  # Filled in later by the accuracy tracker
}
```

### 4b: Outcome Tracking (Automated)

A scheduled job checks predictions against actual outcomes:

```python
# Daily job at 3:45 PM IST (after market close)
for prediction in pending_predictions:
    for window in prediction["check_windows"]:
        if window_elapsed(prediction, window):
            actual = get_actual_outcome(prediction, window)
            prediction["actual_outcomes"][window] = {
                "nifty_close": actual["nifty_close"],
                "actual_direction": "UP" if actual["change"] > 0 else "DOWN",
                "actual_change_pct": actual["change_pct"],
                "prediction_correct": was_correct(prediction, actual, window)
            }
```

### 4c: Agent Weight Auto-Tuning

After accumulating 30+ predictions with outcomes:

```
For each agent:
  accuracy_score = correct_predictions / total_predictions (per time horizon)
  calibration_score = how well conviction % matches actual accuracy %

  If FII agent says "78% conviction SELL" and is correct 80% of the time
    at that conviction level → well calibrated

  If Retail F&O agent says "70% conviction BUY" but is correct only 40%
    → over-confident, reduce weight OR add a de-biasing instruction to prompt

Weight adjustment:
  new_weight = base_weight × (accuracy_score / avg_accuracy_all_agents)
  Capped at ±50% of base weight to prevent any single agent from dominating
```

### 4d: Prompt Evolution

The most powerful part: the system automatically adjusts agent prompts based on accuracy patterns.

```python
# Monthly prompt evolution
def evolve_agent_prompt(agent_name, accuracy_data):
    patterns = analyze_failure_patterns(agent_name, accuracy_data)

    # Example findings:
    # "FII agent is 90% accurate on SELL calls but only 55% on BUY calls"
    # "Retail F&O agent is accurate during expiry weeks but terrible mid-month"
    # "DII agent underestimates impact of global events"

    # Generate prompt patch
    prompt_patch = claude.messages.create(
        model="claude-opus-4-6",
        messages=[{
            "role": "user",
            "content": f"""
            You are optimizing the {agent_name} agent's system prompt.

            Current accuracy data:
            {json.dumps(accuracy_data)}

            Failure patterns identified:
            {json.dumps(patterns)}

            Current prompt:
            {current_prompt}

            Generate a revised prompt that addresses the failure patterns
            while preserving what's working well. Be specific about what
            decision rules to add or modify.
            """
        }]
    )
    return prompt_patch
```

---

## Improvement 5: Multi-Timeframe Analysis

Each agent provides views across 3 timeframes simultaneously:

```json
{
    "agent": "FII",
    "views": {
        "intraday": {
            "direction": "SELL",
            "conviction": 65,
            "reasoning": "Gift Nifty gap-down, likely selling pressure in first hour"
        },
        "weekly": {
            "direction": "SELL",
            "conviction": 78,
            "reasoning": "DXY strengthening trend, quarterly rebalancing window approaching"
        },
        "monthly": {
            "direction": "HOLD",
            "conviction": 55,
            "reasoning": "India macro fundamentals still strong, correction may be buying opportunity for FIIs re-entering"
        }
    }
}
```

The dashboard shows timeframe-specific consensus, so a trader can see: "Bearish today, bearish this week, but agents think the monthly picture is neutral-to-bullish." That's actionable nuance.

---

## Improvement 6: Sentiment Data Integration

Add real sentiment signals to feed agents:

| Source | What to Extract | For Which Agent |
|--------|----------------|-----------------|
| Twitter/X (#Nifty, #BankNifty) | Bullish/bearish ratio, panic keywords | Retail F&O |
| MoneyControl forums | Retail sentiment, stock-specific buzz | Retail F&O |
| Economic Times / Livemint | Institutional commentary, policy signals | FII, DII, RBI |
| SEBI circulars | Regulatory changes | All agents |
| Telegram trading groups | Retail positioning, tip activity | Retail F&O |
| FII/DII daily press releases | Actual flow numbers | FII, DII |
| RBI press conferences | Forward guidance keywords | RBI/Policy |

**Implementation:** Use a lightweight NLP pipeline (or Claude itself) to score sentiment from these sources as structured inputs before the simulation runs.

---

## Indian Market Data Stack (Recommended)

Based on research, here's the recommended data stack:

| Provider | What For | Cost | Priority |
|----------|---------|------|----------|
| **[Dhan API](https://dhanhq.co/docs/v2/option-chain/)** | Option chain (OI, Greeks, volume, bid/ask for all strikes) | Free with Dhan account | Phase 2 - High |
| **[TrueData](https://www.truedata.in/price)** Velocity Standard | Real-time NSE/BSE tick data, historical data | ~₹1,949/mo | Phase 2 - High |
| **[ICICI Breeze API](https://www.icicidirect.com/futures-and-options/api/breeze)** | 3 years historical LTP data, free access | Free with ICICI Direct account | Phase 1 - Medium |
| **[Global Datafeeds](https://globaldatafeeds.in/apis/)** | NSE-authorized real-time data, OI updates since 2010 | Contact for pricing | Phase 3 - Optional |
| **NSDL/CDSL website** | Daily FII/DII flow data | Free (scraping) | Phase 1 - High |
| **NSE India website** | India VIX, advance-decline, bulk/block deals | Free (scraping) | Phase 1 - High |
| **Yahoo Finance (yfinance)** | Nifty/Sensex daily data, USD/INR, DXY, global indices | Free | Phase 1 - Immediate |

**Total cost for full data stack: ~₹2,000-3,000/month** — that's well within "whatever it takes" territory.

---

## Updated Architecture with Accuracy Layer

```
                    ┌──────────────────┐
                    │   DATA FEEDS     │
                    │  TrueData, Dhan, │
                    │  NSE, NSDL, X    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  SIGNAL ENGINE   │
                    │  • Z-scores      │
                    │  • Technicals    │
                    │  • Sentiment     │
                    │  • Percentiles   │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │     ROUND 1: INDEPENDENT     │
              │  FII  DII  Retail  Algo  ... │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     ROUND 2: REACTION        │
              │  Each agent sees others'      │
              │  Round 1 positions            │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     ROUND 3: EQUILIBRIUM     │
              │  Stabilize or flag conflict   │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     AGGREGATOR + SCORING     │
              │  Multi-timeframe consensus   │
              └──────────────┬──────────────┘
                             │
                    ┌────────▼─────────┐
                    │   PREDICTION LOG  │
                    │   + Outcome Track │
                    │   + Weight Tuning │
                    │   + Prompt Evolve │
                    └──────────────────┘
```

---

## Accuracy Targets

| Metric | Phase 1 Target | Phase 2 Target | Phase 3 Target |
|--------|---------------|---------------|---------------|
| Directional accuracy (daily) | 55% | 62% | 68% |
| Directional accuracy (weekly) | 58% | 65% | 72% |
| Agent calibration error | <20% | <12% | <8% |
| Conflict detection (correctly flagging uncertain markets) | 60% | 75% | 85% |
| Time-to-insight (scenario → result) | <30s | <15s | <10s |

Note: Even 60-65% directional accuracy with good calibration is extremely valuable — it means the confidence scores are trustworthy. A system that says "I'm 80% sure" and is right 78% of the time is more useful than one that's right 70% of the time but claims 90% confidence.

---

# PART 5: HYBRID ARCHITECTURE (Quant + LLM)

## Why Hybrid?

Pure-LLM agents have a fundamental ceiling: Claude can reason about narratives beautifully, but it can't actually compute whether the current PCR of 0.72 is in the 15th or 85th percentile of the last 252 trading days. It guesses. And that guess might be wrong.

The hybrid approach splits agents by what they're actually good at:

```
┌────────────────────────────────────────────────────────────┐
│                    AGENT TYPE MATRIX                        │
│                                                             │
│  QUANT AGENTS (Python code, deterministic)                  │
│  ┌──────────────────────────────────────────────┐           │
│  │  Algo/HFT Agent                              │           │
│  │  • Computes: RSI, MACD, BB, VWAP deviation   │           │
│  │  • Computes: OI buildup/unwinding patterns    │           │
│  │  • Computes: PCR percentiles, max pain        │           │
│  │  • Computes: Support/resistance from pivots   │           │
│  │  • Output: Deterministic score + signals      │           │
│  │  • NO LLM involved — pure math               │           │
│  └──────────────────────────────────────────────┘           │
│  ┌──────────────────────────────────────────────┐           │
│  │  Retail Sentiment Agent                       │           │
│  │  • Computes: Twitter/X sentiment score        │           │
│  │  • Computes: Retail long/short ratio from OI  │           │
│  │  • Computes: Max pain deviation               │           │
│  │  • Computes: Expiry-week gamma exposure       │           │
│  │  • LLM LAYER: Interprets sentiment context    │           │
│  │    (is retail fear justified or overblown?)    │           │
│  └──────────────────────────────────────────────┘           │
│                                                             │
│  LLM AGENTS (Claude, narrative reasoning)                   │
│  ┌──────────────────────────────────────────────┐           │
│  │  FII Agent                                    │           │
│  │  • Needs: Geopolitical reasoning, Fed policy  │           │
│  │    interpretation, MSCI rebalancing logic,     │           │
│  │    cross-market correlation narrative          │           │
│  │  • Quant inputs: FII flow Z-scores, DXY data  │           │
│  │  • LLM does: "Given DXY at 105 and Fed        │           │
│  │    holding rates, FIIs will likely..."         │           │
│  └──────────────────────────────────────────────┘           │
│  ┌──────────────────────────────────────────────┐           │
│  │  DII Agent                                    │           │
│  │  • Needs: SIP flow trend interpretation,       │           │
│  │    sector rotation narrative, valuation        │           │
│  │    framework reasoning                         │           │
│  │  • Quant inputs: PE percentile, SIP data,      │           │
│  │    sector performance                          │           │
│  │  • LLM does: "DIIs are likely rotating from    │           │
│  │    IT to Banks because..."                     │           │
│  └──────────────────────────────────────────────┘           │
│  ┌──────────────────────────────────────────────┐           │
│  │  RBI/Policy Agent                             │           │
│  │  • Needs: Policy language interpretation,      │           │
│  │    inflation trajectory reasoning, global      │           │
│  │    central bank coordination analysis          │           │
│  │  • Quant inputs: CPI/WPI trends, repo rate     │           │
│  │    history, real rate calculations              │           │
│  │  • LLM does: "RBI's forward guidance suggests  │           │
│  │    a pause because..."                         │           │
│  └──────────────────────────────────────────────┘           │
│  ┌──────────────────────────────────────────────┐           │
│  │  Promoter/Insider Agent                       │           │
│  │  • Needs: Bulk/block deal pattern reading,     │           │
│  │    pledge ratio interpretation, SEBI filing    │           │
│  │    analysis                                    │           │
│  │  • Quant inputs: Pledge %, bulk deal volumes   │           │
│  │  • LLM does: "Promoter buying at 52-week low   │           │
│  │    with declining pledge suggests..."          │           │
│  └──────────────────────────────────────────────┘           │
└────────────────────────────────────────────────────────────┘
```

## The Key Insight

**Quant agents are deterministic and fast.** Same input = same output. Every time. They run in milliseconds. They're also verifiably correct — you can backtest their signals against historical data and know exactly how they performed.

**LLM agents are probabilistic and slow.** Same input ≈ similar output. They take 2-5 seconds per call. But they can do things quant models can't: interpret RBI governor's tone, assess geopolitical risk, reason about "what would a fund manager do if they saw this pattern."

**The hybrid aggregator gives the best of both:**

```python
class HybridAggregator:
    def aggregate(self, quant_signals, llm_analyses):
        # Quant signals get HIGHER base weight because they're verifiable
        # LLM analyses get weight that INCREASES as they prove accurate over time

        quant_weight = 0.45  # Fixed — these are math, not opinions
        llm_weight = 0.55    # Adjustable based on accuracy tracking

        # But here's the key: if quant and LLM AGREE, confidence goes up
        # If they DISAGREE, confidence goes DOWN and we flag the conflict

        agreement_score = self.measure_agreement(quant_signals, llm_analyses)

        if agreement_score > 0.7:
            # Quant math and LLM narrative both point same direction
            confidence_boost = 1.15
        elif agreement_score < 0.3:
            # Fundamental disagreement — flag as HIGH UNCERTAINTY
            confidence_boost = 0.70
            self.flag_conflict(quant_signals, llm_analyses)
        else:
            confidence_boost = 1.0

        final_score = (
            quant_weight * quant_composite +
            llm_weight * llm_composite
        ) * confidence_boost

        return final_score
```

## Algo Agent: Pure Quant Implementation

This agent is 100% Python — no LLM calls:

```python
class AlgoQuantAgent:
    """Pure quantitative agent. No LLM. Deterministic."""

    def analyze(self, market_data: MarketData) -> AgentResponse:
        signals = {}

        # Trend signals
        signals["rsi_14"] = self.compute_rsi(market_data.closes, 14)
        signals["rsi_signal"] = "overbought" if signals["rsi_14"] > 70 else "oversold" if signals["rsi_14"] < 30 else "neutral"

        # MACD
        macd, signal, hist = self.compute_macd(market_data.closes)
        signals["macd_crossover"] = "bullish" if hist[-1] > 0 and hist[-2] < 0 else "bearish" if hist[-1] < 0 and hist[-2] > 0 else "none"

        # Bollinger Band position (0 to 1, where 1 = upper band)
        signals["bb_position"] = self.compute_bb_position(market_data.closes)

        # VWAP deviation
        signals["vwap_dev"] = self.compute_vwap_deviation(market_data)

        # Options flow (from Dhan API)
        signals["pcr"] = market_data.put_oi / market_data.call_oi
        signals["pcr_percentile_252d"] = self.percentile(self.historical_pcr, signals["pcr"])
        signals["max_pain"] = self.compute_max_pain(market_data.option_chain)
        signals["max_pain_distance"] = (market_data.spot - signals["max_pain"]) / signals["max_pain"] * 100

        # India VIX regime
        signals["vix_regime"] = "low_fear" if market_data.india_vix < 14 else "elevated" if market_data.india_vix < 20 else "high_fear" if market_data.india_vix < 30 else "panic"

        # Composite score (-1 to +1)
        composite = self.compute_composite(signals)

        return AgentResponse(
            agent_name="Algo/Quant",
            agent_type="QUANT",  # Flag as deterministic
            direction=self.score_to_direction(composite),
            conviction=abs(composite) * 100,
            signals=signals,
            reasoning=self.generate_reasoning(signals),  # Template-based, not LLM
            reproducible=True  # Same input = same output, always
        )

    def compute_composite(self, signals):
        """Weighted composite of all quant signals"""
        weights = {
            "rsi": 0.15,
            "macd": 0.15,
            "bb": 0.10,
            "vwap": 0.10,
            "pcr": 0.15,
            "max_pain": 0.15,
            "vix": 0.10,
            "advance_decline": 0.10
        }
        # Each signal normalized to [-1, +1] before weighting
        return sum(
            weights[k] * self.normalize_signal(k, signals)
            for k in weights
        )
```

## Non-Determinism Fix for LLM Agents

For LLM agents, we address the inconsistency problem:

```python
class LLMAgent(BaseAgent):
    async def analyze(self, market_data, n_samples=3):
        """Run the same prompt multiple times and take consensus"""

        responses = await asyncio.gather(*[
            self._single_analysis(market_data, temperature=0.3)
            for _ in range(n_samples)
        ])

        # If all 3 runs agree on direction → high internal consistency
        # If 2/3 agree → moderate consistency
        # If all disagree → flag as uncertain

        directions = [r.direction for r in responses]
        consensus_direction = Counter(directions).most_common(1)[0][0]
        consistency = directions.count(consensus_direction) / len(directions)

        # Average conviction across agreeing runs
        avg_conviction = mean([
            r.conviction for r in responses
            if r.direction == consensus_direction
        ])

        # Penalize conviction if internal consistency is low
        adjusted_conviction = avg_conviction * consistency

        return AgentResponse(
            direction=consensus_direction,
            conviction=adjusted_conviction,
            internal_consistency=consistency,
            reasoning=self._merge_reasoning(responses),
            reproducible=False
        )
```

This means each LLM agent makes 3 parallel calls instead of 1, but we get a consistency score. If the FII agent can't even agree with itself across 3 runs, we know the signal is weak.

**Updated API cost per simulation:**
- Quant agents (Algo, partial Retail): 0 LLM calls
- LLM agents (FII, DII, RBI, Promoter, partial Retail): 5 agents × 3 samples × 3 rounds = 45 calls
- Using Sonnet at ~$0.003/call = ~$0.14 per full simulation
- ~4 simulations/day = ~$17/month in API costs

---

# PART 6: COLD-START VALIDATION

## Phase A: Historical Backtesting (Before Going Live)

Run the system against 20 major Indian market events from 2023-2026 where we know the actual outcomes. This gives us an initial accuracy baseline and reveals systematic biases.

### Historical Event Test Suite

| # | Event | Date | What Happened | Test Focus |
|---|-------|------|---------------|------------|
| 1 | Adani-Hindenburg crash | Jan 2023 | Nifty -4.5% in a week | Panic detection, FII behavior |
| 2 | US SVB bank collapse | Mar 2023 | Limited India impact (-1.5%) | Global contagion vs India resilience |
| 3 | RBI surprise pause | Apr 2023 | Market rallied +1.2% | RBI agent accuracy |
| 4 | Nifty hits 20,000 | Sep 2023 | Breakout rally continued | Round-number psychology, momentum |
| 5 | Israel-Hamas war start | Oct 2023 | Brief dip, quick recovery | Geopolitical shock absorption |
| 6 | State elections (BJP sweep) | Dec 2023 | Gap-up rally +2.5% | Political event, FII reaction |
| 7 | Interim Budget 2024 | Feb 2024 | Muted reaction | Budget agent, "no news is good news" |
| 8 | General Election 2024 | Jun 2024 | Massive volatility, NDA shock | Election scenario stress test |
| 9 | SEBI F&O regulation scare | Jul 2024 | Retail F&O sentiment crash | Regulatory shock, retail agent |
| 10 | US Fed rate cut cycle start | Sep 2024 | FII inflows resumed | FII agent, global macro |
| 11 | China stimulus rally | Sep 2024 | FII outflow from India to China | FII reallocation, DII absorption |
| 12 | Nifty correction (peak to -10%) | Oct-Nov 2024 | Sharp correction from ATH | Multi-agent interaction in drawdown |
| 13 | Trump tariff fears | Nov 2024 | Global uncertainty spike | Contagion scenario |
| 14 | RBI rate cut Feb 2025 | Feb 2025 | First cut in cycle | RBI agent, DII response |
| 15 | Budget 2025 | Feb 2025 | Tax relief, market rally | Budget scenario |
| 16 | FII selling wave Q1 2025 | Jan-Mar 2025 | ₹1.5L Cr FII outflow | Sustained selling, DII vs FII |
| 17 | RBI second rate cut Apr 2025 | Apr 2025 | Continued easing | Consecutive cut scenario |
| 18 | Nifty recovery rally May 2025 | May 2025 | V-shaped recovery | Bottom detection accuracy |
| 19 | Monsoon impact on markets | Jun-Jul 2025 | Seasonal pattern | Agricultural/rural demand narrative |
| 20 | US recession signals H2 2025 | Late 2025 | Global risk-off | Contagion + FII behavior |

### Backtesting Process

```python
class HistoricalBacktester:
    def run_backtest(self, event):
        # 1. Reconstruct market state as of event date
        market_state = self.get_historical_state(event.date)

        # 2. Run simulation with market state as input
        #    (agents only see data available BEFORE the event)
        prediction = self.simulate(market_state, event.scenario_context)

        # 3. Compare prediction to actual outcome
        actual = self.get_actual_outcome(event.date, windows=[1, 3, 5, 10])

        # 4. Score
        return BacktestResult(
            event=event,
            predicted_direction=prediction.direction,
            actual_direction=actual.direction,
            predicted_conviction=prediction.confidence,
            actual_magnitude=actual.change_pct,
            per_agent_accuracy={
                agent: self.score_agent(agent, prediction, actual)
                for agent in prediction.agents
            }
        )

    def run_full_suite(self):
        results = [self.run_backtest(event) for event in HISTORICAL_EVENTS]

        # Generate accuracy report
        report = {
            "overall_directional_accuracy": self.calc_accuracy(results),
            "per_agent_accuracy": self.calc_per_agent(results),
            "per_event_type_accuracy": self.calc_per_type(results),
            "calibration_curve": self.calc_calibration(results),
            "worst_predictions": self.find_worst(results, n=5),
            "best_predictions": self.find_best(results, n=5),
        }

        # Key insight: which agents are consistently wrong?
        # Which event types does the system struggle with?
        # Where do quant and LLM agents disagree most?
        return report
```

### What Backtesting Reveals

After running 20 events, we expect to find patterns like:

- "The FII agent is 80% accurate on selling events but only 50% on buying events" → **Bias: the FII prompt over-weights fear signals**
- "The Algo agent nails 3-day direction but is terrible at 1-day" → **The quant signals are lagging indicators, not leading**
- "The system completely missed the election volatility" → **Need a dedicated political event module**
- "When quant and LLM agents agree, accuracy jumps to 75%" → **Agreement = higher confidence is validated**

These findings feed directly into prompt tuning and weight adjustment before we go live.

## Phase B: Paper Trading (2-4 Weeks Live)

After backtesting, run the system live every morning at 8:45 AM IST (before market open) for 2-4 weeks:

```
Daily Paper Trading Routine:

8:30 AM  — System pulls Gift Nifty, global markets, overnight news
8:35 AM  — Signal Engine computes all quantitative signals
8:40 AM  — All agents run (3 rounds, 3 samples each)
8:45 AM  — Dashboard shows today's prediction
9:15 AM  — Market opens — start tracking
3:30 PM  — Market closes — record outcome
3:45 PM  — Auto-compare prediction vs actual

After 2 weeks (10 trading days):
  → Calculate running accuracy
  → Identify systematic biases
  → Tune agent weights based on live performance
  → Adjust prompts for agents that underperform

After 4 weeks (20 trading days):
  → Comprehensive accuracy report
  → Confidence calibration curve
  → Decision: ready for real use or needs more tuning?
```

### Paper Trading Dashboard Additions

The dashboard gets a "Paper Trading Mode" banner with:
- Running accuracy stats (updated daily)
- Per-agent accuracy leaderboard
- Calibration chart (predicted confidence vs actual accuracy)
- "System would have been correct on X of last Y trading days"
- Prediction history with green/red markers

## Graduation Criteria (Paper Trading → Live Use)

The system graduates from paper trading to trusted analysis when:

| Criterion | Threshold |
|-----------|-----------|
| Directional accuracy (1-day) | ≥ 57% over 20 sessions |
| Directional accuracy (1-week) | ≥ 60% over 4 weeks |
| Calibration error | < 15% (when it says 70%, it's right 55-85% of the time) |
| Quant-LLM agreement accuracy | ≥ 70% when both agree |
| No catastrophic miss | Didn't miss a >3% move with "high confidence" wrong call |
| Internal consistency | LLM agents agree with themselves ≥ 75% across 3 samples |

If any criterion fails, the system stays in paper trading mode with a diagnostic showing which agents or scenarios need work.
