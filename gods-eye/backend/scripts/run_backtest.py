#!/usr/bin/env python3
"""God's Eye backtest runner — real LLM agents, close-to-close structure.

Trade structure:
  Signal at 3:25 PM using T's close data → MOC entry at T's close → exit at T+1's close.
  Overnight gap (T close → T+1 open) is intentional strategy P&L, not leakage.
  Real Claude Haiku agents per day (configurable via GODS_EYE_BACKTEST_MODEL env var).

Run from backend root:
    python -m scripts.run_backtest [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--instrument NIFTY]

Cost estimate: ~248 days × 6 agents × ~$0.002/call ≈ $3 for a full FY2024-25 run.
Requires: ANTHROPIC_API_KEY (or LLM_API_KEY) set in environment.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engine.backtest_engine import BacktestEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gods_eye.backtest_runner")


async def main():
    parser = argparse.ArgumentParser(
        description="Run God's Eye backtest with real LLM agents (close-to-close strategy)"
    )
    parser.add_argument("--from", dest="from_date", default="2024-04-01",
                        help="Start date YYYY-MM-DD (default: 2024-04-01)")
    parser.add_argument("--to", dest="to_date", default="2025-03-31",
                        help="End date YYYY-MM-DD (default: 2025-03-31)")
    parser.add_argument("--instrument", default="NIFTY",
                        help="NIFTY or BANKNIFTY (default: NIFTY)")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("God's Eye Backtest — Real LLM, Close-to-Close")
    logger.info("=" * 70)
    logger.info(f"Instrument : {args.instrument}")
    logger.info(f"Date range : {args.from_date} → {args.to_date}")
    logger.info(f"LLM mode   : real agents (claude-haiku by default)")
    logger.info(f"Strategy   : close-to-close (MOC entry at T's close)")
    logger.info("Fixes active:")
    logger.info("  ✓ Real 5-day VIX data (seeded from yfinance)")
    logger.info("  ✓ VIX≥30 hard HOLD filter")
    logger.info("  ✓ Real PCR from pcr_store (1.0 fallback)")
    logger.info("  ✓ Real FII/DII in INR crores (no double conversion)")
    logger.info("  ✓ Stop loss: ATR×1.5 or 1.5% (whichever tighter)")
    logger.info("  ✓ Close-to-close P&L (overnight gap is intended alpha)")
    logger.info("=" * 70)

    engine = BacktestEngine()
    result = await engine.run_backtest(
        instrument=args.instrument,
        from_date=args.from_date,
        to_date=args.to_date,
    )

    # ── Summary output ────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 70)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 70)
    logger.info(f"Run ID          : {result.run_id}")
    logger.info(f"Days analyzed   : {len(result.days)}")
    logger.info(f"Tradeable days  : {result.total_trades}")
    logger.info(f"Stops hit       : {result.total_stops_hit}")
    logger.info(f"Stop loss active: {result.stop_loss_enabled}")
    logger.info("")
    logger.info(f"Direction accuracy : {result.overall_accuracy*100:.1f}%")
    logger.info(f"Hit rate           : {result.hit_rate_pct:.1f}%")
    logger.info(f"Total P&L          : {result.total_pnl_points:+.0f} pts")
    logger.info(f"Avg P&L / trade    : {result.avg_pnl_per_trade:+.1f} pts")
    logger.info(f"Max drawdown       : {result.max_drawdown_pct:.1f}%")
    logger.info(f"Sharpe ratio       : {result.sharpe_ratio:.2f}")
    logger.info("")

    # Per-agent accuracy
    logger.info("Per-agent accuracy:")
    for agent, acc in sorted(result.per_agent_accuracy.items(), key=lambda x: -x[1]):
        logger.info(f"  {agent:<25}: {acc*100:.1f}%")
    logger.info("")

    # Direction distribution
    logger.info("Direction distribution:")
    directions = [d.predicted_direction for d in result.days]
    for dir_name in ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]:
        count = directions.count(dir_name)
        pct = count / len(directions) * 100 if directions else 0
        logger.info(f"  {dir_name:<15}: {count:3d} days ({pct:.1f}%)")
    logger.info("")

    # P&L breakdown: stopped vs full
    stopped_days = [d for d in result.days if d.stop_loss_hit]
    full_days = [d for d in result.days if not d.stop_loss_hit and d.predicted_direction != "HOLD"]
    if stopped_days:
        stopped_pnl = sum(d.pnl_points for d in stopped_days)
        full_pnl = sum(d.pnl_points for d in full_days)
        logger.info("P&L breakdown:")
        logger.info(f"  Full exits ({len(full_days)} days): {full_pnl:+.0f} pts avg {full_pnl/len(full_days) if full_days else 0:+.1f}")
        logger.info(f"  Stop exits ({len(stopped_days)} days): {stopped_pnl:+.0f} pts avg {stopped_pnl/len(stopped_days) if stopped_days else 0:+.1f}")
        logger.info("")

    if result.total_pnl_points > 0:
        logger.info("✓ PROFITABLE — real agents find genuine alpha, close-to-close")
    else:
        logger.info("✗ UNPROFITABLE — check model, data quality, or strategy filters")
    logger.info("=" * 70)

    return result


if __name__ == "__main__":
    asyncio.run(main())
