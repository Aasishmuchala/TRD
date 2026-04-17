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

    # LLM Resilience — streaming SSE keeps connections alive through OpusMax
    # nginx proxy; concurrency = 7 matches the number of LLM agents so all
    # agents in a round fire simultaneously (~90s/round instead of ~14min).
    LLM_MAX_CONCURRENT: int = int(os.getenv("GODS_EYE_LLM_MAX_CONCURRENT", "7"))
    LLM_MAX_RETRIES: int = int(os.getenv("GODS_EYE_LLM_MAX_RETRIES", "3"))
    LLM_RETRY_BASE_DELAY: float = float(os.getenv("GODS_EYE_LLM_RETRY_BASE_DELAY", "1.0"))

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
    HOLD_BAND: float = float(os.getenv("GODS_EYE_HOLD_BAND", "20.0"))
    CONVICTION_FLOOR: float = float(os.getenv("GODS_EYE_CONVICTION_FLOOR", "55.0"))

    # Automated Paper Trading Scheduler
    SCHEDULER_ENABLED: bool = os.getenv("GODS_EYE_SCHEDULER_ENABLED", "false").lower() in ("true", "1", "yes")

    # Paper Trading Risk Management
    RISK_MAX_DAILY_LOSS: float = float(os.getenv("GODS_EYE_MAX_DAILY_LOSS", "200.0"))  # points

    # Stop Loss Configuration (Profitability Roadmap v2)
    STOP_LOSS_ENABLED: bool = os.getenv("GODS_EYE_STOP_LOSS_ENABLED", "true").lower() in ("true", "1", "yes")
    STOP_LOSS_ATR_MULTIPLIER: float = float(os.getenv("GODS_EYE_STOP_LOSS_ATR_MULTIPLIER", "1.5"))
    STOP_LOSS_PCT: float = float(os.getenv("GODS_EYE_STOP_LOSS_PCT", "1.5"))
    STOP_LOSS_ATR_PERIOD: int = int(os.getenv("GODS_EYE_STOP_LOSS_ATR_PERIOD", "14"))
    def __post_init__(self):
        if self.AGENT_WEIGHTS is None:
            self.AGENT_WEIGHTS = {
                "FII":          0.27,
                "DII":          0.22,
                "RETAIL_FNO":   0.13,
                "ALGO":         0.17,
                "PROMOTER":     0.05,
                "RBI":          0.05,
                "STOCK_OPTIONS": 0.04,
                "NEWS_EVENT":   0.07,
            }

        # If no LLM_API_KEY but CLAUDE_API_KEY exists, use that
        if not self.LLM_API_KEY and self.CLAUDE_API_KEY:
            self.LLM_API_KEY = self.CLAUDE_API_KEY

        # Auto-detect mock mode: only if explicitly set or no auth available
        if not self.MOCK_MODE and not self.LLM_API_KEY:
            self.MOCK_MODE = True

    def validate(self) -> bool:
        """Validate configuration."""
        total_weight = sum(self.AGENT_WEIGHTS.values())
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError(f"Agent weights must sum to 1.0, got {total_weight}")

        return True

# Global config instance
config = Config()
