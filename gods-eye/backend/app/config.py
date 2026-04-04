"""Configuration settings for God's Eye simulation engine."""

import os
from dataclasses import dataclass, field
from typing import List


def _default_cors_origins():
    """Get default CORS origins from environment or use sensible defaults."""
    return [o.strip() for o in os.getenv("GODS_EYE_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")]


@dataclass
class Config:
    """Main configuration for the simulation."""

    # LLM Provider Configuration
    # Provider: "anthropic" (OpusCode Pro) | "openai" | "nous" | "custom"
    LLM_PROVIDER: str = os.getenv("GODS_EYE_LLM_PROVIDER", "anthropic")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", os.getenv("ANTHROPIC_API_KEY", os.getenv("OPENAI_API_KEY", "")))
    LLM_INFERENCE_URL: str = os.getenv("LLM_INFERENCE_URL", "")  # Override inference base URL
    MODEL: str = os.getenv("GODS_EYE_MODEL", "claude-sonnet-4-6")
    MOCK_MODE: bool = os.getenv("GODS_EYE_MOCK", "false").lower() in ("true", "1", "yes")

    # Legacy Claude support (backward compat — maps to LLM_API_KEY)
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")

    # Agent Configuration
    AGENT_WEIGHTS: dict = None
    SAMPLES_PER_AGENT: int = 3
    INTERACTION_ROUNDS: int = 3
    TEMPERATURE: float = 0.3
    QUANT_LLM_BALANCE: float = 0.45  # 0.0 = pure LLM, 1.0 = pure quant

    # Database Configuration
    DATABASE_PATH: str = os.getenv(
        "GODS_EYE_DB_PATH",
        os.path.join(os.path.expanduser("~"), "gods_eye.db")
    )

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENV: str = os.getenv("GODS_EYE_ENV", "development")
    RELOAD: bool = os.getenv("GODS_EYE_ENV", "development") == "development"
    LOG_LEVEL: str = os.getenv("GODS_EYE_LOG_LEVEL", "info")

    # CORS Configuration
    CORS_ORIGINS: List[str] = field(default_factory=_default_cors_origins)

    # Market Configuration
    DEFAULT_LOOKBACK_DAYS: int = 252  # 1 year

    # Auto-learning configuration
    LEARNING_ENABLED: bool = os.getenv("GODS_EYE_LEARNING", "true").lower() in ("true", "1", "yes")
    LEARNING_MIN_TURNS: int = 3  # Min simulation rounds before review
    LEARNING_SKILL_DIR: str = os.getenv(
        "GODS_EYE_LEARNING_SKILL_DIR",
        os.path.join(os.path.expanduser("~"), ".gods-eye", "skills")
    )

    # VIX Regime Filter Configuration (Phase 3 Profitability)
    VIX_FILTER_ENABLED: bool = os.getenv("GODS_EYE_VIX_FILTER_ENABLED", "true").lower() in ("true", "1", "yes")
    VIX_HIGH_THRESHOLD: float = float(os.getenv("GODS_EYE_VIX_HIGH_THRESHOLD", "30.0"))
    VIX_ELEVATED_THRESHOLD: float = float(os.getenv("GODS_EYE_VIX_ELEVATED_THRESHOLD", "20.0"))
    VIX_ELEVATED_CONVICTION_MULTIPLIER: float = float(os.getenv("GODS_EYE_VIX_ELEVATED_CONVICTION_MULTIPLIER", "0.6"))

    # Conviction Filter Configuration
    # Only take a trade when the consensus score exceeds HOLD_BAND and
    # the aggregated conviction is at or above CONVICTION_FLOOR.
    # Widening HOLD_BAND (default 20) and raising CONVICTION_FLOOR (default 55)
    # reduces selectivity from 100% → ~25-35%, improving R/R and shrinking drawdown.
    HOLD_BAND: float = float(os.getenv("GODS_EYE_HOLD_BAND", "20.0"))          # half-width of HOLD zone (was 8)
    CONVICTION_FLOOR: float = float(os.getenv("GODS_EYE_CONVICTION_FLOOR", "55.0"))  # min conviction to trade

    # Stop Loss Configuration (Profitability Roadmap v2)
    # STOP_LOSS_ENABLED=false disables stop loss for backtests (lets you see baseline vs SL impact)
    STOP_LOSS_ENABLED: bool = os.getenv("GODS_EYE_STOP_LOSS_ENABLED", "true").lower() in ("true", "1", "yes")
    STOP_LOSS_ATR_MULTIPLIER: float = float(os.getenv("GODS_EYE_STOP_LOSS_ATR_MULTIPLIER", "1.5"))
    STOP_LOSS_PCT: float = float(os.getenv("GODS_EYE_STOP_LOSS_PCT", "1.5"))
    STOP_LOSS_ATR_PERIOD: int = int(os.getenv("GODS_EYE_STOP_LOSS_ATR_PERIOD", "14"))

    def __post_init__(self):
        if self.AGENT_WEIGHTS is None:
            # 8-agent spec — evolved from original 6-agent plan (FII 0.30, DII 0.25,
            # RETAIL 0.15, ALGO 0.10, PROMOTER 0.10, RBI 0.10).
            # Redistribution rationale (validated in 3-month backtest Apr–Sep 2024):
            #   PROMOTER/RBI reduced (0.10→0.05 each): low-frequency signals,
            #     limited backtest signal quality on daily timeframe.
            #   ALGO raised (0.10→0.17): quant accuracy improved with VIX gate.
            #   STOCK_OPTIONS (0.04) + NEWS_EVENT (0.07) added: options flow and
            #     binary event gating provided material edge (rescued ₹22,422 in
            #     3 losing months; 174% of original losses).
            # Sum: 0.27+0.22+0.13+0.17+0.05+0.05+0.04+0.07 = 1.00 ✓
            self.AGENT_WEIGHTS = {
                "FII":          0.27,  # Reduced from 0.30 — still dominant flow signal
                "DII":          0.22,  # Slightly raised — domestic counterbalance to FII
                "RETAIL_FNO":   0.13,  # Reduced from 0.15 — contrarian signal
                "ALGO":         0.17,  # Raised from 0.10 — quant, backtest-validated
                "PROMOTER":     0.05,  # Reduced from 0.10 — insider signal, infrequent
                "RBI":          0.05,  # Reduced from 0.10 — policy moves, infrequent
                "STOCK_OPTIONS": 0.04, # New — stock options desk, IV rank, catalysts
                "NEWS_EVENT":   0.07,  # New — event gatekeeper, VIX regime veto
            }

        # If no LLM_API_KEY but CLAUDE_API_KEY exists, use that
        if not self.LLM_API_KEY and self.CLAUDE_API_KEY:
            self.LLM_API_KEY = self.CLAUDE_API_KEY

        # Auto-detect mock mode: only if explicitly set or no auth available
        if not self.MOCK_MODE and not self.LLM_API_KEY:
            # Will be overridden if device auth tokens exist
            self.MOCK_MODE = True

    def validate(self) -> bool:
        """Validate configuration."""
        total_weight = sum(self.AGENT_WEIGHTS.values())
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError(f"Agent weights must sum to 1.0, got {total_weight}")

        return True


# Global config instance
config = Config()
# Validate lazily — only enforce API key when actually running simulations
# config.validate() is called explicitly before first simulation
