"""Gap Risk Estimator — pre-market gap detection from global cues.

Data sources (layered, most-reliable first):
  1. Yahoo Finance: S&P 500 futures, DXY, Crude Oil, US 10Y yield
  2. Dhan pre-open session (9:00-9:08 AM IST) — most accurate but narrow window

Gap estimation logic:
  - S&P 500 overnight move is the strongest predictor of Nifty gap direction
  - INR weakness (DXY up) amplifies downside gaps
  - Crude oil spike (>2%) adds ~0.3% to gap magnitude
  - Historical correlation: Nifty gaps ~60-70% of S&P move magnitude

Conservative protection tiers:
  - Gap < 0.5%:  NORMAL  — no action needed
  - Gap 0.5-1%:  CAUTION — flag in simulation, widen stops
  - Gap 1-2%:    WARNING — halve position size, widen stops by gap%
  - Gap > 2%:    DANGER  — skip trade entirely
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import httpx

from app.data.cache import cache
logger = logging.getLogger("gods_eye.gap_risk")

# ---------------------------------------------------------------------------
# Yahoo Finance — reliable, free, no auth required
# ---------------------------------------------------------------------------
_YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# Tickers for global cue estimation
_GLOBAL_TICKERS = {
    "sp500_futures": "ES=F",     # S&P 500 E-mini futures
    "nasdaq_futures": "NQ=F",    # Nasdaq 100 futures
    "dxy": "DX-Y.NYB",          # US Dollar Index
    "crude_oil": "CL=F",        # WTI Crude Oil futures
    "us_10y": "^TNX",           # US 10-Year Treasury yield
    "gift_nifty": "0P0001BHKK.BO",  # GIFT Nifty (if available)
}

# How much Nifty tracks each global factor (empirical, approximate)
_NIFTY_BETA = {
    "sp500_futures": 0.65,   # Nifty moves ~65% of S&P overnight move
    "dxy": -0.30,            # Stronger dollar = weaker Nifty
    "crude_oil": -0.15,      # India is net oil importer
}

@dataclass
class GapEstimate:
    """Result of gap risk assessment."""
    estimated_gap_pct: float = 0.0       # Estimated gap % (positive = gap up, negative = gap down)
    gap_magnitude: float = 0.0           # Absolute gap size %
    risk_tier: str = "NORMAL"            # NORMAL | CAUTION | WARNING | DANGER
    confidence: float = 0.0              # 0-1 confidence in the estimate
    position_multiplier: float = 1.0     # 1.0 = full size, 0.5 = half, 0.0 = skip
    stop_buffer_pct: float = 0.0         # Additional stop-loss buffer %
    global_cues: Dict[str, float] = field(default_factory=dict)  # Raw overnight moves
    warnings: List[str] = field(default_factory=list)
    data_source: str = "none"            # "yahoo" | "dhan_preopen" | "both" | "none"
    timestamp: str = ""


class GapRiskEstimator:
    """Estimates pre-market gap risk from global cues."""

    def __init__(self):
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            headers={"User-Agent": "Mozilla/5.0 Gods-Eye/2.0"},
        )
    async def estimate(self, nifty_prev_close: float = 0.0) -> GapEstimate:
        """Estimate gap risk using all available data sources.

        Call this before market open (ideally 8:30-9:00 AM IST).
        """
        result = GapEstimate(timestamp=datetime.utcnow().isoformat())

        # Layer 1: Yahoo Finance global cues
        global_cues = await self._fetch_global_cues()
        if global_cues:
            result.global_cues = global_cues
            result.data_source = "yahoo"
            result.estimated_gap_pct = self._compute_gap_estimate(global_cues)
            result.confidence = 0.6  # Yahoo alone = moderate confidence
        else:
            result.warnings.append("Yahoo Finance data unavailable — gap estimate is zero")
            result.confidence = 0.0

        # Layer 2: Dhan pre-open (9:00-9:08 AM IST window)
        preopen_gap = await self._fetch_dhan_preopen(nifty_prev_close)
        if preopen_gap is not None:
            if result.data_source == "yahoo":
                result.estimated_gap_pct = preopen_gap * 0.7 + result.estimated_gap_pct * 0.3
                result.data_source = "both"
                result.confidence = 0.85
            else:
                result.estimated_gap_pct = preopen_gap
                result.data_source = "dhan_preopen"
                result.confidence = 0.75
        # Compute magnitude and tier
        result.gap_magnitude = abs(result.estimated_gap_pct)
        result.risk_tier = self._classify_tier(result.gap_magnitude)

        # Conservative position sizing
        if result.risk_tier == "DANGER":
            result.position_multiplier = 0.0
            result.stop_buffer_pct = result.gap_magnitude
            result.warnings.append(
                f"DANGER: Estimated gap {result.estimated_gap_pct:+.2f}% — "
                f"skip all new positions"
            )
        elif result.risk_tier == "WARNING":
            result.position_multiplier = 0.5
            result.stop_buffer_pct = result.gap_magnitude * 0.5
            result.warnings.append(
                f"WARNING: Estimated gap {result.estimated_gap_pct:+.2f}% — "
                f"halve position size, widen stops by {result.stop_buffer_pct:.1f}%"
            )
        elif result.risk_tier == "CAUTION":
            result.position_multiplier = 0.75
            result.stop_buffer_pct = result.gap_magnitude * 0.3
            result.warnings.append(
                f"CAUTION: Estimated gap {result.estimated_gap_pct:+.2f}% — "
                f"widen stops by {result.stop_buffer_pct:.1f}%"
            )
        else:
            result.position_multiplier = 1.0
            result.stop_buffer_pct = 0.0
        logger.info(
            "Gap estimate: %+.2f%% (%s), confidence=%.2f, position_mult=%.2f, source=%s",
            result.estimated_gap_pct, result.risk_tier, result.confidence,
            result.position_multiplier, result.data_source,
        )

        return result

    # ------------------------------------------------------------------
    # Yahoo Finance — global cues
    # ------------------------------------------------------------------

    async def _fetch_global_cues(self) -> Dict[str, float]:
        """Fetch overnight % changes for global indicators via Yahoo Finance."""
        cues = {}

        results = await asyncio.gather(
            *[self._fetch_yahoo_change(ticker) for ticker in _GLOBAL_TICKERS.values()],
            return_exceptions=True,
        )

        for (name, ticker), result in zip(_GLOBAL_TICKERS.items(), results):
            if isinstance(result, (int, float)) and result is not None:
                cues[name] = result
            else:
                logger.debug("Failed to fetch %s (%s): %s", name, ticker, result)

        return cues
    async def _fetch_yahoo_change(self, ticker: str) -> Optional[float]:
        """Fetch latest % change for a Yahoo Finance ticker."""
        cache_key = f"yahoo_{ticker}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{_YAHOO_BASE}/{ticker}"
            params = {
                "range": "2d",
                "interval": "1d",
                "includePrePost": "true",
            }
            resp = await self._http.get(url, params=params)
            if resp.status_code != 200:
                return None

            data = resp.json()
            chart = data.get("chart", {}).get("result", [{}])[0]
            closes = chart.get("indicators", {}).get("quote", [{}])[0].get("close", [])

            valid_closes = [c for c in closes if c is not None]
            if len(valid_closes) < 2:
                return None

            prev_close = valid_closes[-2]
            last_close = valid_closes[-1]

            if prev_close == 0:
                return None
            pct_change = ((last_close - prev_close) / prev_close) * 100

            # Cache for 5 minutes
            cache.set(cache_key, pct_change, ttl=300)
            return pct_change

        except Exception as e:
            logger.debug("Yahoo fetch error for %s: %s", ticker, e)
            return None

    # ------------------------------------------------------------------
    # Dhan pre-open session
    # ------------------------------------------------------------------

    async def _fetch_dhan_preopen(self, nifty_prev_close: float) -> Optional[float]:
        """Fetch Nifty pre-open price from Dhan (available 9:00-9:08 AM IST)."""
        if nifty_prev_close <= 0:
            return None

        now = datetime.now()
        hour_min = now.hour * 100 + now.minute
        if hour_min < 900 or hour_min > 915:
            return None

        try:
            from app.data.dhan_client import dhan_client
            quote = await dhan_client.get_market_quote("13", "IDX_I")
            if quote and quote.get("last_price"):
                preopen_price = quote["last_price"]
                gap_pct = ((preopen_price - nifty_prev_close) / nifty_prev_close) * 100
                logger.info(
                    "Dhan pre-open: Nifty=%s, prev_close=%s, gap=%.2f%%",
                    preopen_price, nifty_prev_close, gap_pct,
                )
                return gap_pct
        except Exception as e:
            logger.debug("Dhan pre-open fetch error: %s", e)

        return None

    # ------------------------------------------------------------------
    # Gap classification
    # ------------------------------------------------------------------

    def _compute_gap_estimate(self, cues: Dict[str, float]) -> float:
        """Estimate Nifty gap % from global cues using beta-weighted sum."""
        estimated = 0.0
        for factor, beta in _NIFTY_BETA.items():
            if factor in cues:
                estimated += cues[factor] * beta

        return round(estimated, 3)

    @staticmethod
    def _classify_tier(gap_magnitude: float) -> str:
        """Classify gap magnitude into risk tier."""
        if gap_magnitude >= 2.0:
            return "DANGER"
        elif gap_magnitude >= 1.0:
            return "WARNING"
        elif gap_magnitude >= 0.5:
            return "CAUTION"
        return "NORMAL"


# Module-level singleton
gap_risk_estimator = GapRiskEstimator()
