"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class MarketInput(BaseModel):
    """Market data input for simulation."""

    nifty_spot: float = Field(..., description="Nifty 50 current price")
    nifty_open: Optional[float] = Field(default=None, description="Nifty 50 open price")
    nifty_high: Optional[float] = Field(default=None, description="Nifty 50 high price")
    nifty_low: Optional[float] = Field(default=None, description="Nifty 50 low price")
    nifty_close: Optional[float] = Field(default=None, description="Nifty 50 close price")

    india_vix: float = Field(default=15.0, description="India VIX level")

    fii_flow_5d: float = Field(default=0.0, description="5-day FII flow in USD millions")
    dii_flow_5d: float = Field(default=0.0, description="5-day DII flow in USD millions")

    usd_inr: float = Field(default=83.5, description="USD/INR exchange rate")
    dxy: float = Field(default=104.0, description="US Dollar Index")

    pcr_index: float = Field(default=1.0, description="Put-Call Ratio for index options")
    pcr_stock: float = Field(default=1.0, description="Put-Call Ratio for stocks")

    max_pain: Optional[float] = Field(default=None, description="Max pain level for current expiry")
    dte: int = Field(default=5, description="Days to expiration for current contract")

    rsi_14: Optional[float] = Field(default=None, description="RSI(14) value")
    macd_signal: Optional[float] = Field(default=None, description="MACD signal line")

    context: str = Field(
        default="normal",
        description="Market context (normal, expiry, budget, election, etc.)",
    )

    historical_prices: Optional[List[float]] = Field(
        default=None, description="Historical closing prices for last N days"
    )


class TimeframeView(BaseModel):
    """Multi-timeframe view from an agent."""

    timeframe: str  # "intraday", "weekly", "monthly"
    direction: str  # "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    conviction: float
    key_levels: Dict[str, float]
    resistance: float
    support: float


class AgentResponse(BaseModel):
    """Response from a single agent."""

    agent_name: str
    agent_type: str  # "QUANT" or "LLM"
    direction: str  # "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    conviction: float = Field(..., ge=0, le=100, description="Conviction 0-100")
    reasoning: str
    key_triggers: List[str]
    time_horizon: str  # "Intraday", "Weekly", "Quarterly", "Yearly"

    views: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Multi-timeframe views"
    )
    interaction_effects: Dict[str, List[str]] = Field(
        default_factory=lambda: {"amplifies": [], "dampens": []},
        description="Effects on other agents' views",
    )

    internal_consistency: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Consistency score for LLM agents"
    )
    reproducible: bool = Field(
        default=False, description="True for deterministic agents"
    )
    sample_variance: float = Field(
        default=0.0, description="Variance across multiple samples"
    )


class AggregatorResult(BaseModel):
    """Final aggregated market view."""

    final_direction: str
    final_conviction: float
    consensus_score: float = Field(
        ..., ge=-100, le=100, description="Weighted consensus score"
    )
    conflict_level: str  # "HIGH_AGREEMENT", "MODERATE", "TUG_OF_WAR"
    conflict_gap: float
    quant_consensus: str
    llm_consensus: str
    agreement_boost: float
    quant_llm_agreement: Optional[float] = Field(
        default=None,
        description="0-1 score of how much quant and LLM sub-systems agree",
    )
    agent_breakdown: Dict[str, Dict[str, Any]]


class SimulationResult(BaseModel):
    """Complete simulation result."""

    model_config = {"protected_namespaces": ()}

    simulation_id: str
    timestamp: datetime
    market_input: MarketInput
    agents_output: Dict[str, AgentResponse]
    round_history: List[Dict[str, Any]]
    aggregator_result: AggregatorResult
    execution_time_ms: float
    model_used: str
    feedback_active: bool = Field(default=False, description="Whether accuracy feedback engine is active")
    tuned_weights: Optional[Dict[str, float]] = Field(default=None, description="Accuracy-tuned agent weights")


class PresetScenario(BaseModel):
    """Preset market scenario."""

    scenario_id: str
    name: str
    description: str
    market_data: MarketInput
    expected_direction: str = Field(
        default="UNKNOWN", description="Expected market direction"
    )


class PredictionLog(BaseModel):
    """Stored prediction for accuracy tracking."""

    prediction_id: str
    simulation_id: str
    timestamp: datetime
    market_input: MarketInput
    predicted_direction: str
    predicted_conviction: float
    agents_output: Dict[str, AgentResponse]
    actual_direction: Optional[str] = None
    check_timestamp: Optional[datetime] = None
    accuracy: Optional[bool] = None
    notes: Optional[str] = None


class SimulationHistory(BaseModel):
    """Paginated history of simulations."""

    total_count: int
    page: int
    page_size: int
    items: List[SimulationResult]


# ── Phase 7: Backtest Engine ──────────────────────────────────────────────────

# ── Phase 8: Signal Scoring ───────────────────────────────────────────────────

class SignalScoreSchema(BaseModel):
    """Pydantic representation of a SignalScorer.ScoreResult."""
    score: float
    tier: str               # "strong" | "moderate" | "skip"
    direction: str
    contributing_factors: List[str]
    suggested_instrument: str


class BacktestDayResponse(BaseModel):
    """Single day result in a backtest run."""
    date: str
    next_date: str
    nifty_close: float
    nifty_next_close: float
    actual_move_pct: float
    predicted_direction: str
    predicted_conviction: float
    direction_correct: Optional[bool]   # None when HOLD
    pnl_points: float
    cumulative_pnl_points: float        # running total up to this day
    per_agent_directions: Dict[str, str]
    signals: Dict[str, Any]
    signal_score: Optional[SignalScoreSchema] = None  # None for pre-Phase-8 persisted runs
    # round_history omitted from list response — heavy; available via detail endpoint


class BacktestRunRequest(BaseModel):
    """Request body for POST /api/backtest/run."""
    instrument: str = Field(default="NIFTY", description="NIFTY or BANKNIFTY")
    from_date: str = Field(..., description="Start date YYYY-MM-DD (inclusive)")
    to_date: str = Field(..., description="End date YYYY-MM-DD (inclusive)")
    mock_mode: bool = Field(
        default=True,
        description="True = fast mock agents (default); False = real LLM calls"
    )


class BacktestRunSummary(BaseModel):
    """Summary metrics for a completed backtest run."""
    run_id: str
    instrument: str
    from_date: str
    to_date: str
    mock_mode: bool
    day_count: int
    overall_accuracy: float             # 0-1 fraction of correct directional calls
    win_rate_pct: float                 # overall_accuracy * 100 (convenience field)
    per_agent_accuracy: Dict[str, float]  # agent_key -> 0-1
    total_pnl_points: float
    created_at: str


class BacktestRunResponse(BaseModel):
    """Complete response for POST /api/backtest/run and GET /api/backtest/results/{id}."""
    summary: BacktestRunSummary
    days: List[BacktestDayResponse]


# ── Phase 10: Quantitative Signal Engine ─────────────────────────────────────


class QuantFactorSchema(BaseModel):
    """Per-factor breakdown from QuantSignalEngine."""

    points: int
    threshold_hit: bool
    side: Optional[str]


class QuantSignalResponse(BaseModel):
    """Response for GET /api/signal/quant/{instrument}/{date}."""

    instrument: str
    date: str
    total_score: int
    direction: str
    tier: str
    buy_points: int
    sell_points: int
    factors: Dict[str, QuantFactorSchema]
    instrument_hint: str


class QuantBacktestDaySchema(BaseModel):
    """Single day result in a quant backtest run (factors omitted to keep payload small)."""

    date: str
    direction: str
    total_score: int
    tier: str
    buy_points: int
    sell_points: int
    actual_move_pct: Optional[float]
    is_correct: Optional[bool]
    pnl_points: float


class QuantBacktestRequest(BaseModel):
    """Request body for POST /api/backtest/quant-run."""

    instrument: str = Field(default="NIFTY", description="NIFTY or BANKNIFTY")
    from_date: str = Field(..., description="Start date YYYY-MM-DD (inclusive)")
    to_date: str = Field(..., description="End date YYYY-MM-DD (inclusive)")


class QuantBacktestRunResponse(BaseModel):
    """Response for POST /api/backtest/quant-run."""

    instrument: str
    from_date: str
    to_date: str
    total_days: int
    tradeable_days: int
    correct_days: int
    win_rate_pct: Optional[float]
    total_pnl_points: float
    elapsed_seconds: float
    days: List[QuantBacktestDaySchema]


# ── Phase 12: Hybrid Scoring and LLM Validator ───────────────────────────────

class AgentBreakdownEntrySchema(BaseModel):
    direction: str
    conviction: float


# ── Phase 13: Risk Management ─────────────────────────────────────────────────

class RiskParamsSchema(BaseModel):
    """Position sizing and stop/target levels computed by RiskManager."""
    lots: int
    stop_distance: float
    target_distance: float
    stop_level: float
    target_level: float
    vix_used: float
    risk_reward: float   # always 1.5


class HybridSignalResponse(BaseModel):
    """Response for POST /api/signal/hybrid/{instrument}/{date}."""
    model_config = {"protected_namespaces": ()}

    instrument: str
    date: str
    direction: str                               # Quant direction (locked)
    hybrid_score: float                          # 0-100 fused score
    conviction: float                            # Post-validation conviction
    tradeable: bool                              # False if skip or score < 50
    tier: str                                    # "strong" | "moderate" | "skip"
    instrument_hint: str                         # e.g. "NIFTY_CE"
    quant_breakdown: Dict[str, Any]              # score, direction, tier, factors
    agent_breakdown: Dict[str, AgentBreakdownEntrySchema]
    agent_consensus_score: float
    validator_verdict: str                       # "confirm" | "adjust" | "skip"
    validator_reasoning: str
    risk_params: RiskParamsSchema                # Position sizing and stop/target levels
    risk_blocked: bool                           # True if daily loss limit reached before this signal
    risk_block_reason: Optional[str] = None      # Human-readable explanation when blocked
