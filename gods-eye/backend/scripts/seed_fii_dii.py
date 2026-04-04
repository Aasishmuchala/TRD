#!/usr/bin/env python3
"""Seed FII/DII historical data into SQLite store.

This script attempts to fetch historical FII/DII data from NSE.
If NSE is blocked/unavailable, generates realistic synthetic data
based on NIFTY price movements for backtesting.

Synthetic data generation:
- Download NIFTY price history via yfinance
- Generate FII/DII flows with mean reversion + random noise
- Avoid circular proxy (momentum * 500) — use different method
- Insert all data into fii_dii_store

Run from backend root:
    python -m scripts.seed_fii_dii
"""

import asyncio
import logging
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.fii_dii_store import fii_dii_store
from app.data.nse_fii_dii import fetch_fii_dii_activity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed_fii_dii")


def generate_synthetic_fii_dii(start_date: date, end_date: date) -> dict:
    """Generate realistic synthetic FII/DII data for backtest period.

    Uses a realistic model instead of circular proxy:
    - Base flows around mean (FII +500 Cr, DII -200 Cr typical)
    - Mean reversion: flows tend back to average
    - Random noise: ±200-300 Cr daily
    - Correlation to NIFTY: larger moves on volatile days
    - Trend: slight positive FII bias, slight negative DII bias

    Args:
        start_date: "YYYY-MM-DD" or date object
        end_date: "YYYY-MM-DD" or date object

    Returns:
        {date_str: {"fii_net_cr": float, "dii_net_cr": float, ...}}
    """
    import random
    import math

    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date).date()
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date).date()

    logger.info(f"Generating synthetic FII/DII data from {start_date} to {end_date}")

    # Try to fetch NIFTY data to correlate flows
    nifty_prices = {}
    nifty_volatility = {}
    try:
        import yfinance as yf
        logger.info("Fetching NIFTY price history from yfinance...")
        nifty = yf.download(
            "^NSEI",
            start=start_date - timedelta(days=30),
            end=end_date + timedelta(days=1),
            progress=False,
        )
        for idx, row in nifty.iterrows():
            d = idx.date()
            close_price = float(row["Close"].iloc[0]) if hasattr(row["Close"], 'iloc') else float(row["Close"])
            nifty_prices[d] = close_price
            # Estimate daily volatility (high-low range as % of close)
            if close_price > 0:
                high_price = float(row["High"].iloc[0]) if hasattr(row["High"], 'iloc') else float(row["High"])
                low_price = float(row["Low"].iloc[0]) if hasattr(row["Low"], 'iloc') else float(row["Low"])
                nifty_volatility[d] = abs(high_price - low_price) / close_price
        logger.info(f"Retrieved {len(nifty_prices)} NIFTY price points")
    except ImportError:
        logger.warning("yfinance not installed — using pure random generation (no price correlation)")
    except Exception as e:
        logger.warning(f"Failed to fetch NIFTY data: {e} — using pure random generation")

    # Generate FII/DII data
    data = {}
    current = start_date
    fii_level = 500.0  # Mean FII flow (inflow positive)
    dii_level = -200.0  # Mean DII flow (outflow negative)

    while current <= end_date:
        # Skip weekends (very basic — real code should check NSE trading calendar)
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        # Mean reversion
        fii_reversion = (500.0 - fii_level) * 0.05  # 5% revert to mean per day
        dii_reversion = (-200.0 - dii_level) * 0.05

        # Volatility correlation: larger flows on high volatility days
        volatility_factor = 1.0
        if current in nifty_volatility:
            volatility_factor = 1.0 + nifty_volatility[current] * 3  # ±3x boost on vol days

        # Random noise: ±250 Cr typical
        fii_noise = random.gauss(0, 150) * volatility_factor
        dii_noise = random.gauss(0, 100) * volatility_factor

        # Trend: slight positive FII bias, negative DII bias
        fii_trend = 5.0  # +5 Cr/day drift
        dii_trend = -2.0  # -2 Cr/day drift

        # Calculate new levels
        fii_level += fii_reversion + fii_noise + fii_trend
        dii_level += dii_reversion + dii_noise + dii_trend

        # Clamp to reasonable ranges (avoid extreme values)
        fii_level = max(-1000, min(2000, fii_level))
        dii_level = max(-1000, min(500, dii_level))

        # Buy/Sell split (roughly 50-50 with slight variation)
        fii_buy = abs(fii_level) * 0.5 + random.gauss(0, 50)
        fii_sell = abs(fii_level) * 0.5 + random.gauss(0, 50)
        dii_buy = max(0, abs(dii_level) * 0.5 + random.gauss(0, 30))
        dii_sell = max(0, abs(dii_level) * 0.5 + random.gauss(0, 30))

        data[current.isoformat()] = {
            "fii_net_cr": round(fii_level, 2),
            "dii_net_cr": round(dii_level, 2),
            "fii_buy_cr": round(fii_buy, 2),
            "fii_sell_cr": round(fii_sell, 2),
            "dii_buy_cr": round(dii_buy, 2),
            "dii_sell_cr": round(dii_sell, 2),
        }

        current += timedelta(days=1)

    logger.info(f"Generated {len(data)} synthetic FII/DII records")
    return data


async def try_fetch_real_fii_dii(lookback_days: int = 30) -> dict:
    """Attempt to fetch recent real FII/DII data from NSE.

    Args:
        lookback_days: how many days back to attempt

    Returns:
        {date_str: {"fii_net_cr": float, ...}} or {} if fetch fails
    """
    logger.info(f"Attempting to fetch recent FII/DII from NSE (last {lookback_days} days)...")

    data = {}
    today = date.today()

    for i in range(lookback_days):
        check_date = today - timedelta(days=i)

        # Skip weekends
        if check_date.weekday() >= 5:
            continue

        # Fetch live data (includes current date's flows)
        result = await fetch_fii_dii_activity()

        if result.get("error"):
            logger.debug(f"NSE fetch failed for {check_date}: {result['error']}")
            continue

        # If we got valid data, map it to the date
        # Note: NSE API endpoint gives "today" data, not historical per-date
        # So we can only get the most recent trading day
        data[check_date.isoformat()] = {
            "fii_net_cr": result.get("fii_net_value", 0.0),
            "dii_net_cr": result.get("dii_net_value", 0.0),
            "fii_buy_cr": result.get("fii_buy_value", 0.0),
            "fii_sell_cr": result.get("fii_sell_value", 0.0),
            "dii_buy_cr": result.get("dii_buy_value", 0.0),
            "dii_sell_cr": result.get("dii_sell_value", 0.0),
        }

        # NSE endpoint gives current date only, so break after first success
        if data:
            logger.info(f"Fetched real FII/DII data from NSE: {data}")
            break

    return data


async def main():
    """Main seed workflow."""
    logger.info("Starting FII/DII data seeding...")

    # Backtest period: Apr 2024 - Mar 2026
    backtest_start = date(2024, 4, 1)
    backtest_end = date(2026, 3, 31)

    # First, try to fetch recent real data from NSE
    real_data = await try_fetch_real_fii_dii(lookback_days=7)

    # Generate synthetic data for the full backtest period
    synthetic_data = generate_synthetic_fii_dii(backtest_start, backtest_end)

    # Merge: real data overrides synthetic where available
    all_data = {**synthetic_data, **real_data}

    logger.info(f"Total records to insert: {len(all_data)}")
    logger.info(f"  - Synthetic: {len(synthetic_data)}")
    logger.info(f"  - Real (from NSE): {len(real_data)}")

    # Insert into store
    inserted_count = 0
    for date_str, flows in sorted(all_data.items()):
        try:
            fii_dii_store.store_daily(
                date_str=date_str,
                fii_net_cr=flows["fii_net_cr"],
                dii_net_cr=flows["dii_net_cr"],
                fii_buy_cr=flows.get("fii_buy_cr", 0.0),
                fii_sell_cr=flows.get("fii_sell_cr", 0.0),
                dii_buy_cr=flows.get("dii_buy_cr", 0.0),
                dii_sell_cr=flows.get("dii_sell_cr", 0.0),
                source="synthetic" if date_str not in real_data else "nse_api",
            )
            inserted_count += 1
        except Exception as e:
            logger.error(f"Failed to insert {date_str}: {e}")

    # Summary
    total_stored = fii_dii_store.count_rows()
    logger.info("=" * 70)
    logger.info("FII/DII Seeding Complete")
    logger.info("=" * 70)
    logger.info(f"Inserted: {inserted_count} records")
    logger.info(f"Total in store: {total_stored} records")
    logger.info(f"Date range: {backtest_start} to {backtest_end}")

    # Show statistics
    sample = fii_dii_store.get_range(
        backtest_start.isoformat(),
        (backtest_start + timedelta(days=30)).isoformat(),
    )
    if sample:
        fii_values = [r["fii_net_cr"] for r in sample]
        dii_values = [r["dii_net_cr"] for r in sample]
        logger.info(f"Sample stats (first month):")
        logger.info(f"  FII: mean={sum(fii_values)/len(fii_values):.2f} Cr, min={min(fii_values):.2f} Cr, max={max(fii_values):.2f} Cr")
        logger.info(f"  DII: mean={sum(dii_values)/len(dii_values):.2f} Cr, min={min(dii_values):.2f} Cr, max={max(dii_values):.2f} Cr")

    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
