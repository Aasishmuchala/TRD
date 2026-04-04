#!/bin/bash
# God's Eye — Short Backtest Runner
# Run this from your terminal: bash run_backtest.sh
# Results saved to /tmp/gods_eye_backtest.log

cd "$(dirname "$0")/backend" || exit 1

echo "Loading .env..."
export $(grep -v '^#' .env | xargs)
export GODS_EYE_DB_PATH=/tmp/gods_eye_local.db
export GODS_EYE_CONVICTION_FLOOR=70
export GODS_EYE_HOLD_BAND=20
export GODS_EYE_MOCK=false

echo "Starting April 2024 short backtest (20 days)..."
echo "Logs: /tmp/gods_eye_backtest.log"
echo ""

python3 - << 'PYEOF' 2>&1 | tee /tmp/gods_eye_backtest.log
import sys, os, asyncio
sys.path.insert(0, '.')

from app.engine.backtest_engine import BacktestEngine
from app.engine.options_pnl import compute_options_pnl
from app.config import config

async def main():
    print(f"Config: CONVICTION_FLOOR={config.CONVICTION_FLOOR} MOCK={config.MOCK_MODE} MODEL={config.MODEL}")
    print(f"Agents: {list(config.AGENT_WEIGHTS.keys())}  sum={sum(config.AGENT_WEIGHTS.values()):.2f}")
    print()

    engine = BacktestEngine()
    result = await engine.run_backtest(
        instrument='NIFTY',
        from_date='2024-04-01',
        to_date='2024-04-30'
    )

    total  = len(result.days)
    holds  = sum(1 for d in result.days if d.predicted_direction == 'HOLD')
    trades = total - holds

    print(f"=== April 2024 Backtest Results ===")
    print(f"Days={total}  Trades={trades}  HOLDs={holds}  Selectivity={trades/total*100 if total else 0:.0f}%")
    print(f"Win rate={result.hit_rate_pct:.1f}%  P&L pts={result.total_pnl_points:.1f}")
    print()

    print(f"{'Date':<12} {'Direction':<13} {'Conv':>5}  {'Result':<5}  {'Pts':>7}  {'₹ P&L':>8}  {'Ret%':>6}")
    print('-' * 68)
    total_inr = 0.0
    for d in result.days:
        if d.predicted_direction == 'HOLD':
            print(f"{d.date:<12} {'HOLD':<13} {d.predicted_conviction:5.1f}  {'--':<5}  {'':>7}")
        else:
            # pnl_points is directional gain; for options_pnl we need actual underlying move
            # BUY: pnl_points = nifty_next - nifty_close  (positive = up, already correct)
            # SELL: pnl_points = nifty_close - nifty_next  (positive = down, needs flip)
            buy_dirs = ('BUY', 'STRONG_BUY')
            actual_move = d.pnl_points if d.predicted_direction in buy_dirs else -d.pnl_points
            t = compute_options_pnl(
                date=d.date, direction=d.predicted_direction,
                nifty_point_move=actual_move,
                instrument='NIFTY', spot=d.nifty_close or 22000,
                vix=14.0, conviction=d.predicted_conviction, capital=10000
            )
            res = 'WIN ' if d.direction_correct else 'LOSS'
            inr = t.net_pnl if t else 0.0
            ret = t.return_pct if t else 0.0
            total_inr += inr
            print(f"{d.date:<12} {d.predicted_direction:<13} {d.predicted_conviction:5.1f}  {res:<5}  {d.pnl_points:>+7.1f}  ₹{inr:>7.0f}  {ret:>+5.1f}%")

    print('-' * 68)
    print(f"TOTAL ₹: {total_inr:+.0f}  ({total_inr/10000*100:+.1f}% on ₹10k)")
    print()
    print("Per-agent accuracy:")
    for agent, acc in sorted(result.per_agent_accuracy.items()):
        print(f"  {agent:<16}: {acc:.0%}")

asyncio.run(main())
PYEOF

echo ""
echo "Done. Results saved to /tmp/gods_eye_backtest.log"
