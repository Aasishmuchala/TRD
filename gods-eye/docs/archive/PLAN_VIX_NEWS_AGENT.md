# Plan: VIX Regime Gate + NewsEventAgent + Rerun Backtest
**Goal:** Fix the system's worst failure mode — getting whipsawed on high-VIX binary event days (May election, Aug Japan crash, Nov US election). Three coordinated changes: tiered VIX conviction gate, event calendar blackout, and a new NewsEventAgent with veto power.

**Codebase root:** `/Users/aasish/Desktop/CLAUDE PROJECTS/TRD/TRD/gods-eye/backend`

---

## Phase 0: Discovery — Confirmed APIs & Patterns

### Files confirmed to exist:
- `app/api/schemas.py` — `MarketInput` (Pydantic), `AgentResponse`
- `app/agents/base_agent.py` — `BaseAgent(ABC)` with `async def analyze(market_data, round_num, other_agents_output, enriched_context) -> AgentResponse`
- `app/agents/fii_agent.py` — canonical LLM agent pattern to copy
- `app/engine/backtest_engine.py` — `BacktestEngine` with `_build_market_input()`, `_compute_consensus()`, `run_backtest()`
- `app/engine/orchestrator.py` — `Orchestrator` with `self.agents` dict
- `app/config.py` — `Config` dataclass with `AGENT_WEIGHTS`, `CONVICTION_FLOOR`, `VIX_ELEVATED_THRESHOLD`

### Key signatures:
```python
# MarketInput fields relevant to us:
india_vix: float          # already populated from vix_map in backtest
context: str              # "normal", "correction", "weakness" etc — we extend this
event_risk: Optional[str] # NEW FIELD to add

# _compute_consensus(final_outputs: Dict) -> Tuple[str, float]
# Called in run_backtest() loop AFTER agent results gathered
# VIX available via market_input (need to thread through)

# BaseAgent.analyze() returns AgentResponse with:
# direction: str, conviction: float, reasoning: str, key_triggers: List[str]

# Orchestrator.agents dict (7 agents currently):
# "ALGO", "FII", "DII", "RETAIL_FNO", "PROMOTER", "RBI", "STOCK_OPTIONS"
```

### Confirmed anti-patterns:
- Do NOT touch `STOP_LOSS_PCT` in options_pnl.py (already set to 0.25)
- Do NOT change `SAMPLES_PER_AGENT` or `INTERACTION_ROUNDS` defaults
- Do NOT use `config.AGENT_WEIGHTS` dict directly in new agent — pass via Orchestrator

---

## Phase 1: Event Calendar Module

**File to create:** `app/data/event_calendar.py`

**What it does:** Provides a lookup of all major binary events in FY2024-25 that should trigger either a HOLD blackout (pre-event) or a directional context string (post-event).

```python
# Event types:
# "RBI_POLICY"    — RBI MPC rate decisions
# "INDIA_ELECTION" — Lok Sabha / state elections
# "BUDGET"        — Union Budget
# "MACRO_SHOCK"   — Japan crash, geopolitical shocks
# "US_ELECTION"   — US presidential election
# "EXPIRY_WEEK"   — Monthly F&O expiry (last Thursday of month)

EVENT_CALENDAR: Dict[str, str] = {
    # April 2024
    "2024-04-05": "EXPIRY_WEEK",
    "2024-04-10": "MACRO_SHOCK",   # Iran-Israel escalation
    # May 2024 — India General Election (Lok Sabha)
    "2024-05-07": "INDIA_ELECTION",  # Phase 3
    "2024-05-13": "INDIA_ELECTION",  # Phase 4
    "2024-05-20": "INDIA_ELECTION",  # Phase 5
    "2024-05-25": "INDIA_ELECTION",  # Phase 6
    "2024-06-01": "INDIA_ELECTION",  # Phase 7 (last phase)
    "2024-06-04": "INDIA_ELECTION",  # RESULTS DAY
    # June 2024
    "2024-06-07": "RBI_POLICY",
    # August 2024
    "2024-08-05": "MACRO_SHOCK",   # Japan Nikkei -12%, global carry unwind
    "2024-08-08": "RBI_POLICY",
    # October 2024
    "2024-10-09": "RBI_POLICY",
    # November 2024
    "2024-11-05": "US_ELECTION",   # Trump vs Harris
    # February 2025
    "2025-02-01": "BUDGET",        # Union Budget FY2026
    "2025-02-07": "RBI_POLICY",
}

def get_event_for_date(date_str: str) -> Optional[str]:
    """Return event type string if this date is a known event, else None."""

def is_pre_event_blackout(date_str: str, lookahead_days: int = 1) -> bool:
    """True if a binary event (ELECTION, BUDGET, MACRO_SHOCK, US_ELECTION) 
    falls within lookahead_days ahead of date_str."""

def get_post_event_context(date_str: str, lookback_days: int = 2) -> Optional[str]:
    """If a major event occurred within lookback_days before date_str, 
    return a string like 'post_election_result' or 'post_rbi_policy'.
    Used by NewsEventAgent to give directional context after event resolves."""
```

**Verification:** `python3 -c "from app.data.event_calendar import is_pre_event_blackout; assert is_pre_event_blackout('2024-06-03'); print('OK')`

---

## Phase 2: Add `event_risk` to MarketInput + wire into `_build_market_input()`

**File to modify:** `app/api/schemas.py`

Add one optional field to `MarketInput`:
```python
event_risk: Optional[str] = Field(
    default=None,
    description="Event risk context: 'pre_election', 'rbi_policy_day', 'post_budget', etc."
)
```

**File to modify:** `app/engine/backtest_engine.py`

In `_build_market_input()`, import and call event_calendar:
```python
from app.data.event_calendar import get_event_for_date, is_pre_event_blackout, get_post_event_context

# Near the bottom of _build_market_input(), before `return MarketInput(...)`:
event_on_day = get_event_for_date(signal_date)
pre_blackout = is_pre_event_blackout(signal_date)
post_ctx = get_post_event_context(signal_date)

event_risk = None
if event_on_day:
    event_risk = event_on_day.lower()
elif pre_blackout:
    event_risk = "pre_event_blackout"
elif post_ctx:
    event_risk = post_ctx

# Add to MarketInput(...) call:
# event_risk=event_risk,
```

Also update the existing `context` field logic to incorporate event info:
```python
# If event_risk is set, override context with it for agent awareness
if event_risk:
    context = event_risk
```

**Verification:** Print `market_input.event_risk` for "2024-06-04" — should be "india_election".

---

## Phase 3: Tiered VIX Conviction Gate in BacktestEngine

**File to modify:** `app/engine/backtest_engine.py`

Add new method `_apply_vix_event_gate()` and call it in `run_backtest()` loop after `_compute_consensus()`:

```python
# VIX threshold constants (tuned from backtest analysis)
VIX_NORMAL_FLOOR = 65.0          # <14% VIX: standard conviction floor
VIX_ELEVATED_FLOOR = 72.0        # 14-16%: raise floor slightly
VIX_HIGH_FLOOR = 78.0            # 16-20%: only very high conviction trades
VIX_EXTREME_HOLD_THRESHOLD = 20.0  # >20%: no trades, force HOLD

def _apply_vix_event_gate(
    self,
    direction: str,
    conviction: float,
    india_vix: float,
    event_risk: Optional[str],
    signal_date: str,
) -> Tuple[str, float]:
    """Apply tiered VIX conviction escalation and event blackout.

    Rules:
    1. event_risk == 'pre_event_blackout' → force HOLD (known binary event incoming)
    2. india_vix > 20 → force HOLD (premium too expensive, direction unreliable)
    3. india_vix 16-20 → conviction must be >= 78 to trade
    4. india_vix 14-16 → conviction must be >= 72 to trade
    5. india_vix < 14 → standard conviction floor (65)
    """
    if direction == "HOLD":
        return direction, conviction

    # Rule 1: pre-event blackout
    if event_risk == "pre_event_blackout":
        logger.debug("VIX gate: pre-event blackout on %s → HOLD", signal_date)
        return "HOLD", 50.0

    # Rule 2: VIX > 20 — extreme regime, force HOLD
    if india_vix > self.VIX_EXTREME_HOLD_THRESHOLD:
        logger.debug("VIX gate: VIX=%.1f > 20 on %s → HOLD", india_vix, signal_date)
        return "HOLD", 50.0

    # Rule 3: elevated VIX — tiered conviction floor
    if india_vix >= 16.0:
        floor = self.VIX_HIGH_FLOOR  # 78
    elif india_vix >= 14.0:
        floor = self.VIX_ELEVATED_FLOOR  # 72
    else:
        floor = config.CONVICTION_FLOOR  # 65 (standard)

    if conviction < floor:
        logger.debug(
            "VIX gate: VIX=%.1f conviction=%.1f < floor=%.1f on %s → HOLD",
            india_vix, conviction, floor, signal_date
        )
        return "HOLD", 50.0

    return direction, conviction
```

In `run_backtest()` loop, add after `_compute_consensus()`:
```python
predicted_direction, predicted_conviction = self._compute_consensus(final_outputs)

# Apply VIX + event gate (NEW)
predicted_direction, predicted_conviction = self._apply_vix_event_gate(
    predicted_direction,
    predicted_conviction,
    market_input.india_vix,
    market_input.event_risk,
    signal_date,
)
```

**Verification:** Days with VIX > 20 (e.g., May 13-31 2024) should show HOLD. Days with VIX 16-20 and conviction < 78 should show HOLD.

---

## Phase 4: NewsEventAgent

**File to create:** `app/agents/news_event_agent.py`

Pattern: copy from `fii_agent.py` structure. This agent is LLM-powered and:
- Reads `market_data.event_risk` and `market_data.india_vix` and `market_data.context`
- In its prompt, it reasons about: is this a pre-event / post-event / shock scenario?
- Outputs HOLD when: event_risk contains blackout or vix > 18
- Outputs directional when: post-event with clear outcome signal

```python
class NewsEventAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="News & Event Risk Analyst",
            persona="Macro event specialist tracking binary event risk and news flow for Indian markets",
            decision_framework="Event calendar, VIX regime, news flow, post-event drift analysis",
            risk_appetite="Conservative",
            time_horizon="Weekly",
            agent_type="LLM",
        )

    async def analyze(self, market_data, round_num=1, ...):
        # If mock mode
        if config.MOCK_MODE:
            return MockResponseGenerator.generate("NEWS_EVENT", ...)
        
        prompt = self._build_prompt(market_data, round_num, other_context, enriched_context)
        # Single sample (SAMPLES_PER_AGENT=1 in backtest)
        response_text = await self._call_llm(prompt)
        return self._parse_response(response_text)
    
    def _build_prompt(self, market_data, round_num, other_context, enriched_context):
        # Key inputs to give the agent:
        # - market_data.event_risk (e.g. "india_election", "pre_event_blackout")
        # - market_data.india_vix
        # - market_data.context
        # - Date context
        # Agent should reason: 
        #   "Is this a high-risk event day? Should we avoid trading?"
        #   "If post-event, what's the directional bias?"
        ...
```

**File to modify:** `app/engine/orchestrator.py`

Add NewsEventAgent import and register with weight 0.07. Rebalance weights:
```python
from app.agents.news_event_agent import NewsEventAgent

self.agents = {
    "ALGO": AlgoQuantAgent(),
    "FII": FIIAgent(),
    "DII": DIIAgent(),
    "RETAIL_FNO": RetailFNOAgent(),
    "PROMOTER": PromoterAgent(),
    "RBI": RBIPolicyAgent(),
    "STOCK_OPTIONS": StockOptionsAgent(),
    "NEWS_EVENT": NewsEventAgent(),   # NEW — weight 0.07
}
```

**File to modify:** `app/config.py`

Update `AGENT_WEIGHTS` default to include NEWS_EVENT and rebalance:
```python
# New weights (sum = 1.0):
# FII 0.27, DII 0.22, RETAIL_FNO 0.13, ALGO 0.17, 
# PROMOTER 0.05, RBI 0.05, STOCK_OPTIONS 0.04, NEWS_EVENT 0.07
```

**Veto logic in `_compute_consensus()`:**
After computing direction/conviction, check if NEWS_EVENT output is HOLD:
```python
# NEWS_EVENT veto: if news agent says HOLD, respect it regardless of others
news_output = final_outputs.get("NEWS_EVENT")
if news_output and news_output.direction == "HOLD" and winning_direction != "HOLD":
    # Only veto if news agent conviction is >= 70 (don't veto on weak signals)
    if news_output.conviction >= 70:
        return "HOLD", 50.0
```

**Verification:** Run a test with Jun 4 2024 data — NewsEventAgent should output HOLD (election results day).

---

## Phase 5: New Standalone Backtest Runner

**File to create:** `/tmp/bt_v2.py` (on the user's Mac)

Same pattern as the previous `bt_progress2.py` but upgraded:
- Uses BacktestEngine (with VIX gate + NewsEventAgent already wired in)
- CAPITAL = ₹20,000
- DATE RANGE = 2024-04-01 → 2025-03-31
- Same staggered-agent + retry-backoff pattern
- Same per-day output format + monthly summaries
- Outputs to `/tmp/bt_v2.log`
- Writes PID to `/tmp/bt_v2_pid.txt`

```python
# Key constants
FROM_DATE = "2024-04-01"
TO_DATE = "2025-03-31"
CAPITAL = 20_000
LOG_FILE = "/tmp/bt_v2.log"
PID_FILE = "/tmp/bt_v2_pid.txt"

# Staggered agent calls: 1.5s gap between agent launches
# Retry with exponential backoff: start=5s, max=60s, max_retries=5
```

Output format (same as before):
```
Date         Direction       Conv  Result       Pts     Rs P&L    Ret%
2024-04-01   BUY             71.9  WIN        +80.0     Rs+820   +4.1%  (48s)
...
=== APRIL 2024 SUMMARY ===
Trades: 18  Wins: 10  Losses: 8  Win%: 55.6%
Net P&L: Rs+3418  Return: +17.1%
```

---

## Phase 6: Run Backtest + Compare Results

After implementing phases 1-5:
1. Launch `python3 -u /tmp/bt_v2.py > /tmp/bt_v2.log 2>&1 &`
2. Write PID to `/tmp/bt_v2_pid.txt`
3. Monitor same way as before (`tail -30 /tmp/bt_v2.log`)
4. Compare monthly P&L vs old run:
   - Expect May 2024 to improve significantly (VIX gate kills most election-week trades)
   - Expect Aug 2024 to avoid the Aug 5-6 Japan crash worst days
   - Expect Nov 2024 to avoid US election week

---

## Execution Order

1. `app/data/event_calendar.py` — new file, no deps
2. `app/api/schemas.py` — add `event_risk` field
3. `app/engine/backtest_engine.py` — wire event_risk in `_build_market_input()`, add `_apply_vix_event_gate()`, update loop
4. `app/agents/news_event_agent.py` — new agent file
5. `app/engine/orchestrator.py` — add NEWS_EVENT agent
6. `app/config.py` — update AGENT_WEIGHTS
7. `/tmp/bt_v2.py` — new standalone runner
8. Launch backtest, verify first 5 days output correctly

## Anti-Patterns to Avoid
- Do NOT modify `options_pnl.py` STOP_LOSS_PCT (already fixed to 0.25)
- Do NOT change INTERACTION_ROUNDS or SAMPLES_PER_AGENT defaults 
- Do NOT use `config.AGENT_WEIGHTS` in the new agent's __init__ — weights are applied by orchestrator/consensus
- Do NOT import from `app.engine.orchestrator` inside agent files (circular import)
- Do NOT use `asyncio.run()` inside BacktestEngine methods — already inside async context
