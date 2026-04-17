"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


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

    VALID_CONTEXTS = frozenset({
        "normal", "expiry", "budget", "election", "rbi_policy", "global_crisis",
        "pre_budget", "post_budget", "pre_election", "post_election",
        "pre_rbi", "post_rbi", "earnings_season", "ipo_heavy",
        "low_vix", "normal_vix", "elevated_vix", "high_vix",
        "macro_shock", "us_election", "pre_event_blackout",
        "post_india_election", "post_rbi_policy",
    })

    context: str = Field(
        default="normal",
        description="Market context (normal, expiry, budget, election, etc.)",
    )

    @field_validator("context")
    @classmethod
    def validate_context(cls, v: str) -> str:
        if v not in cls.VALID_CONTEXTS:
            raise ValueError(
                f"Invalid context '{v}'. Must be one of: {sorted(cls.VALID_CONTEXTS)}"
            )
        return v

    historical_prices: Optional[List[float]] = Field(
        default=None, description="Historical closing prices for last N days"
    )

    # Options intelligence fields (Phase 4 — all optional for backward compatibility)
    iv_rank: Optional[float] = Field(
        default=None,
        description="IV rank 0–100: (current_VIX − 52w_low) / (52w_high − 52w_low) × 100. "
                    "<30 = cheap premium (buy), >70 = expensive (avoid)",
    )
    iv_percentile: Optional[float] = Field(
        default=None,
        description="% of days in past year where VIX was lower than today. "
                    "Complements IV rank — low percentile = options historically cheap",
    )
    atm_call_premium: Optional[float] = Field(
        default=None,
        description="Current NIFTY ATM CE premium in ₹/unit (estimated or live)",
    )
    atm_put_premium: Optional[float] = Field(
        default=None,
        description="Current NIFTY ATM PE premium in ₹/unit (estimated or live)",
    )
    weekly_expiry_date: Optional[str] = Field(
        default=None,
        description="Next weekly expiry date in YYYY-MM-DD format (Thursday)",
    )
    top_stock_setups: Optional[str] = Field(
        default=None,
        description="Comma-separated stock options setups, e.g. 'RELIANCE:CE,INFY:PE'. "
                    "Pre-screened by StockOptionsAgent from prior simulation round.",
    )

    # Event risk context (Phase: VIX+News fix)
    event_risk: Optional[str] = Field(
        default=None,
        description="Event risk context for this date: 'india_election', 'rbi_policy', "
                    "'budget', 'macro_shock', 'us_election', 'pre_event_blackout', "
                    "'post_india_election', 'post_rbi_policy', etc. "
                    "Set by BacktestEngine from event_calendar. Drives NewsEventAgent veto.",
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
    data_warnings: List[str] = Field(default_factory=list, description="Warnings about stale or missing data sources")


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

    # Stop loss fields (Profitability Roadmap v2)
    stop_loss_hit: bool = False
    stop_price: Optional[float] = None
    stop_distance_pts: Optional[float] = None

    # Latency fields
    entry_price: float = 0.0             # T+1 open — actual execution price
    overnight_gap_pct: float = 0.0       # T close → T+1 open gap (%)


class BacktestRunRequest(BaseModel):
    """Request body for POST /api/backtest/run."""
    instrument: str = Field(default="NIFTY", description="NIFTY or BANKNIFTY")
    from_date: str = Field(..., description="Start date YYYY-MM-DD (inclusive)")
    to_date: str = Field(..., description="End date YYYY-MM-DD (inclusive)")
    # mock_mode removed — backtests always use real LLM agents (close-to-close strategy)


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

    # Phase 3 performance metrics
    hit_rate_pct: float = 0.0
    avg_pnl_per_trade: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    regime_accuracy: Dict[str, Dict[str, float]] = Field(default_factory=dict)

    # Stop loss stats (Profitability Roadmap v2)
    total_stops_hit: int = 0
    stop_loss_enabled: bool = False

    # Latency stats
    avg_overnight_gap_pct: float = 0.0   # mean |gap| across tradeable days


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
