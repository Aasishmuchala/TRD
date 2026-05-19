"""
bt_v2.py — God's Eye FY2024-25 Backtest (v2: VIX Gate + NewsEventAgent)
========================================================================
Runs BacktestEngine.run_backtest() month-by-month across FY2024-25.
Prints per-trade rows + monthly P&L summary as each month completes.

Capital: ₹20,000 per trade
Engine:  BacktestEngine.run_backtest() — uses asyncio.gather() correctly,
         includes VIX regime gate + NewsEventAgent veto.

Run from the gods-eye/backend directory:
    cd gods-eye/backend
    export $(grep -v '^#' .env | xargs)
    export GODS_EYE_DB_PATH=/tmp/gods_eye_bt_v2.db
    python3 ../bt_v2.py 2>&1 | tee /tmp/bt_v2.log
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, ".")

CAPITAL = 20_000.0

MONTHS = [
    ("2024-04-01", "2024-04-30", "Apr 2024"),
    ("2024-05-01", "2024-05-31", "May 2024"),
    ("2024-06-01", "2024-06-30", "Jun 2024"),
    ("2024-07-01", "2024-07-31", "Jul 2024"),
    ("2024-08-01", "2024-08-31", "Aug 2024"),
    ("2024-09-01", "2024-09-30", "Sep 2024"),
    ("2024-10-01", "2024-10-31", "Oct 2024"),
    ("2024-11-01", "2024-11-30", "Nov 2024"),
    ("2024-12-01", "2024-12-31", "Dec 2024"),
    ("2025-01-01", "2025-01-31", "Jan 2025"),
    ("2025-02-01", "2025-02-28", "Feb 2025"),
    ("2025-03-01", "2025-03-31", "Mar 2025"),
]


def fmt_pnl(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}₹{v:,.0f}"


def fmt_ret(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def get_event_label(date_str: str) -> str:
    """Return short event label for a date (uses event_calendar)."""
    from app.data.event_calendar import get_event_for_date, is_pre_event_blackout

    event = get_event_for_date(date_str)
    if event:
        return event.lower()[:18]
    if is_pre_event_blackout(date_str):
        return "pre_event_blkout"
    return ""


async def run_month(
    engine,
    from_date: str,
    to_date: str,
    label: str,
    vix_map: dict,
) -> dict:
    from app.engine.options_pnl import compute_options_pnl

    t0 = time.time()
    result = await engine.run_backtest(
        instrument="NIFTY",
        from_date=from_date,
        to_date=to_date,
    )
    elapsed = time.time() - t0

    total_inr = 0.0
    trades = 0
    wins = 0
    holds = 0

    print(f"\n{'='*80}")
    print(f"  {label}   ({from_date} → {to_date})   [{elapsed:.0f}s]")
    print(f"{'='*80}")
    print(
        f"{'Date':<12} {'Direction':<13} {'Conv':>5}  {'VIX':>5}  {'Event':<18}  "
        f"{'Result':<5}  {'Pts':>+7}  {'₹ P&L':>9}  {'Ret%':>6}"
    )
    print(f"{'-'*95}")

    for d in result.days:
        vix_val = vix_map.get(d.date, 0.0)
        event_label = get_event_label(d.date)

        if d.predicted_direction == "HOLD":
            holds += 1
            print(
                f"{d.date:<12} {'HOLD':<13} {d.predicted_conviction:5.1f}"
                f"  {vix_val:5.1f}  {event_label:<18}  {'--':<5}"
            )
            continue

        # Actual underlying point move for options P&L calculation
        buy_dirs = ("BUY", "STRONG_BUY")
        if d.predicted_direction in buy_dirs:
            actual_move = d.pnl_points   # positive = up = good for CE
        else:
            actual_move = -d.pnl_points  # positive = down = good for PE

        t = compute_options_pnl(
            date=d.date,
            direction=d.predicted_direction,
            nifty_point_move=actual_move,
            instrument="NIFTY",
            spot=d.nifty_close or 22_000.0,
            vix=vix_val if vix_val else 14.0,
            conviction=d.predicted_conviction,
            capital=CAPITAL,
        )
        inr = t.net_pnl if t else 0.0
        ret = t.return_pct if t else 0.0
        total_inr += inr
        trades += 1
        if d.direction_correct:
            wins += 1

        res = "WIN " if d.direction_correct else "LOSS"
        print(
            f"{d.date:<12} {d.predicted_direction:<13} {d.predicted_conviction:5.1f}"
            f"  {vix_val:5.1f}  {event_label:<18}  {res:<5}"
            f"  {d.pnl_points:>+7.1f}  {fmt_pnl(inr):>9}  {fmt_ret(ret):>6}"
        )

    print(f"{'-'*95}")
    win_rate = (wins / trades * 100) if trades else 0.0
    selectivity = (trades / len(result.days) * 100) if result.days else 0.0
    ret_pct = total_inr / CAPITAL * 100

    print(
        f"  {label}: {fmt_pnl(total_inr):>10}  {fmt_ret(ret_pct):>7}"
        f"   Trades={trades}  HOLDs={holds}  WinRate={win_rate:.0f}%"
        f"  Selectivity={selectivity:.0f}%"
    )

    return {
        "label": label,
        "inr": total_inr,
        "ret_pct": ret_pct,
        "trades": trades,
        "wins": wins,
        "holds": holds,
        "days": len(result.days),
    }


async def main():
    from app.engine.backtest_engine import BacktestEngine
    from app.config import config
    from app.data.historical_store import historical_store

    print("=" * 80)
    print("  God's Eye — FY2024-25 Full Backtest (v2: VIX Gate + NewsEventAgent)")
    print("=" * 80)
    print(f"  Capital         : ₹{CAPITAL:,.0f}")
    print(f"  Model           : {config.MODEL}")
    print(f"  Mock mode       : {config.MOCK_MODE}")
    print(f"  Conviction floor: {config.CONVICTION_FLOOR}")
    print(f"  Agents ({len(config.AGENT_WEIGHTS)}): {list(config.AGENT_WEIGHTS.keys())}")
    print(f"  Weight sum      : {sum(config.AGENT_WEIGHTS.values()):.2f}")
    print("=" * 80)
    print()

    # Fetch VIX data once up front for display purposes
    print("Fetching VIX history...", end=" ", flush=True)
    try:
        vix_rows = await historical_store.get_vix_closes()
        vix_map = {r["date"]: r["close"] for r in vix_rows}
        print(f"OK ({len(vix_map)} days)")
    except Exception as exc:
        print(f"WARN: {exc} — VIX column will show 0.0")
        vix_map = {}

    engine = BacktestEngine()
    summaries = []

    for from_date, to_date, label in MONTHS:
        try:
            s = await run_month(engine, from_date, to_date, label, vix_map)
            summaries.append(s)
        except Exception as exc:
            print(f"\n[ERROR] {label}: {exc}")
            import traceback
            traceback.print_exc()

    # Annual summary
    if summaries:
        total_inr = sum(s["inr"] for s in summaries)
        total_trades = sum(s["trades"] for s in summaries)
        total_wins = sum(s["wins"] for s in summaries)
        total_holds = sum(s["holds"] for s in summaries)
        total_days = sum(s["days"] for s in summaries)
        overall_wr = (total_wins / total_trades * 100) if total_trades else 0.0
        overall_sel = (total_trades / total_days * 100) if total_days else 0.0
        annual_ret = total_inr / CAPITAL * 100

        print(f"\n{'='*80}")
        print(f"  FY2024-25 ANNUAL SUMMARY")
        print(f"{'='*80}")
        print(
            f"  {'Month':<12}  {'P&L':>10}  {'Ret%':>7}  {'Trades':>7}"
            f"  {'WinRate':>8}  {'HOLDs':>6}"
        )
        print(f"  {'-'*62}")
        for s in summaries:
            wr = (s["wins"] / s["trades"] * 100) if s["trades"] else 0.0
            print(
                f"  {s['label']:<12}  {fmt_pnl(s['inr']):>10}  {fmt_ret(s['ret_pct']):>7}"
                f"  {s['trades']:>7}  {wr:>7.0f}%  {s['holds']:>6}"
            )
        print(f"  {'-'*62}")
        print(
            f"  {'TOTAL':<12}  {fmt_pnl(total_inr):>10}  {fmt_ret(annual_ret):>7}"
            f"  {total_trades:>7}  {overall_wr:>7.0f}%  {total_holds:>6}"
        )
        print(f"\n  Trading days: {total_days}  Selectivity: {overall_sel:.0f}%")
        print(f"  Annual return on ₹{CAPITAL:,.0f}: {fmt_ret(annual_ret)}")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
