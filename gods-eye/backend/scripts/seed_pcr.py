"""Seed PCR data from synthetic but realistic distribution.

Since Dhan doesn't have historical option chain data, we generate synthetic PCR
correlated with India VIX for 2 years of backtest data.

Correlation logic:
  - VIX > 20: PCR tends higher (1.0-1.5, more put-buying = fear)
  - VIX 14-20: PCR neutral (0.8-1.2, balanced)
  - VIX < 14: PCR tends lower (0.6-0.9, more call-buying = greed)

Run:
    cd /sessions/trusting-wizardly-faraday/mnt/TRD/gods-eye/backend
    python scripts/seed_pcr.py
"""

import sys
import os
from datetime import datetime, date, timedelta
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import random

import yfinance as yf

from app.data.pcr_store import pcr_store

logger = logging.getLogger("gods_eye.seed_pcr")
logging.basicConfig(level=logging.INFO)

# Synthetic but realistic PCR distribution function
def _generate_pcr_for_vix(vix: float) -> float:
    """Generate synthetic PCR correlated with VIX.

    Args:
        vix: VIX value

    Returns:
        PCR value (put-call ratio)
    """
    import random

    # Base PCR logic
    if vix > 20:
        # High volatility = fear = more puts
        base_pcr = 1.15
        noise = random.uniform(-0.15, 0.25)  # Asymmetric noise
    elif vix > 14:
        # Normal volatility = neutral
        base_pcr = 0.95
        noise = random.uniform(-0.15, 0.15)
    else:
        # Low volatility = greed = more calls
        base_pcr = 0.80
        noise = random.uniform(-0.20, 0.10)  # Asymmetric noise

    # Smooth correlation with VIX level
    vix_adjustment = (vix - 16.0) * 0.03  # Subtle slope: +0.03 per VIX point

    pcr = max(0.5, min(2.0, base_pcr + vix_adjustment + noise))  # Clamp to [0.5, 2.0]
    return round(pcr, 3)


def seed_pcr_historical():
    """Generate and store 2 years of synthetic PCR data.

    Fetches VIX historical data and generates correlated PCR.
    """
    logger.info("Starting PCR historical seeding...")

    # Fetch VIX data from Yahoo Finance (Dhan doesn't support IDX_I historical)
    try:
        logger.info("Fetching India VIX from Yahoo Finance...")
        vix_df = yf.download("^INDIAVIX", period="2y", interval="1d", progress=False)
        if hasattr(vix_df.columns, 'levels') and len(vix_df.columns.levels) > 1:
            vix_df = vix_df.droplevel(1, axis=1)

        if vix_df.empty:
            logger.warning("No VIX data from Yahoo Finance. Skipping PCR seeding.")
            return

        vix_data = []
        for idx, row in vix_df.iterrows():
            d = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]
            vix_data.append({"date": d, "close": float(row["Close"])})

        logger.info(f"Fetched {len(vix_data)} VIX data points")

        # Generate synthetic PCR for each VIX date
        stored_count = 0
        for row in vix_data:
            date_str = row["date"]
            vix_close = row["close"]

            # Generate correlated PCR
            pcr = _generate_pcr_for_vix(vix_close)

            # Generate synthetic OI values (proportional to VIX)
            # Higher VIX = larger OI swings
            base_call_oi = 1_000_000 * (20.0 / vix_close)  # Inverse correlation
            base_put_oi = base_call_oi * pcr  # PCR determines put OI

            call_oi = int(base_call_oi + (1000 * (vix_close - 16)))
            put_oi = int(base_put_oi + (1000 * (vix_close - 16)))

            # Max pain is pseudo-random around current Nifty level
            # (real max pain requires option chain, so we approximate)
            max_pain = 24_000 + (vix_close - 16) * 100  # Rough approximation

            # Store
            pcr_store.store_pcr(
                date=date_str,
                pcr=pcr,
                total_call_oi=call_oi,
                total_put_oi=put_oi,
                max_pain=max_pain,
                nifty_close=0.0,  # Not available in VIX data
                expiry_date=None,
                source="synthetic",
            )
            stored_count += 1

            # Log every 50 rows
            if stored_count % 50 == 0:
                logger.info(f"Stored {stored_count} PCR snapshots...")

        logger.info(f"Seeding complete! Stored {stored_count} PCR snapshots")

        # Verify
        latest = pcr_store.get_latest()
        if latest:
            logger.info(f"Latest PCR snapshot: {latest['date']} = {latest['pcr']}")

    except Exception as e:
        logger.error(f"Error seeding PCR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    seed_pcr_historical()
