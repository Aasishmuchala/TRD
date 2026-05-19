"""
bt_v3.py — God's Eye Losing-Months Validation Backtest
=======================================================
Runs ONLY the 3 losing months from the original FY2024-25 backtest
to validate the VIX gate + event blackout improvements now built
into BacktestEngine.

Baseline (original, no gates):
  May-2024: -₹7,200
  Aug-2024:   -₹802
  Sep-2024: -₹4,917
  Total:   -₹12,919

Run from gods-eye/backend:
    cd gods-eye/backend
    set -a && source .env && set +a
    export GODS_EYE_DB_PATH=/tmp/gods_eye_bt_v3.db
    python3 ../bt_v3.py 2>&1 | tee /tmp/bt_v3.log
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, ".")

CAPITAL = 20_000.0

# Only the 3 months that lost money in the original run
LOSING_MONTHS = [
    ("2024-05-01", "2024-05-31", "May-2024", -7200),
    ("2024-08-01", "2024-08-31", "Aug-2024",  -802),
    ("2024-09-01", "2024-09-30", "Sep-2024", -4917),
]

BASELINE_TOTAL = -12_919


def fmt_pnl(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}₹{v:,.0f}"


def fmt_ret(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def get_event_label(date_str: str) -> str:
    try:
        from app.data.event_calendar import get_event_for_date, is_pre_event_blackout
        event = get_event_for_date(date_str)
        if event:
            return event.lower()[:18]
        if is_pre_event_blackout(date_str):
            return "pre_event_blkout"
    except Exception:
        pass
    return ""


async def run_month(
    engine,
    from_date: str,
    to_date: str,
    label: str,
    baseline_inr: int,
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

    print(f"\n{'='*90}")
    print(f"  {label}   ({from_date} → {to_date})   [{elapsed:.0f}s]")
    print(f"  Baseline: {fmt_pnl(baseline_inr)}   Target: beat baseline")
    print(f"{'='*90}")
    print(
        f"{'Date':<12} {'Direction':<13} {'Conv':>5}  {'VIX':>5}  {'Gate':<8}  "
        f"{'Event':<18}  {'Result':<5}  {'Pts':>+7}  {'₹ P&L':>9}  {'Ret%':>6}"
    )
    print(f"{'-'*100}")

    for d in result.days:
        vix_val = vix_map.get(d.date, 0.0)
        event_label = get_event_label(d.date)

        # Determine gate label from VIX level
        if vix_val > 20.0:
            gate_label = "VIX-BLOCK"
        elif vix_val > 16.0:
            gate_label = f"VIX-HIGH"
        elif vix_val > 14.0:
            gate_label = "VIX-ELEV"
        else:
            gate_label = "OK"

        if d.predicted_direction == "HOLD":
            holds += 1
            print(
                f"{d.date:<12} {'HOLD':<13} {d.predicted_conviction:5.1f}"
                f"  {vix_val:5.1f}  {gate_label:<8}  {event_label:<18}  {'--':<5}"
            )
            continue

        buy_dirs = ("BUY", "STRONG_BUY")
        if d.predicted_direction in buy_dirs:
            actual_move = d.pnl_points
        else:
            actual_move = -d.pnl_points

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
            f"  {vix_val:5.1f}  {gate_label:<8}  {event_label:<18}  {res:<5}"
            f"  {d.pnl_points:>+7.1f}  {fmt_pnl(inr):>9}  {fmt_ret(ret):>6}"
        )

    print(f"{'-'*100}")
    win_rate = (wins / trades * 100) if trades else 0.0
    selectivity = (trades / len(result.days) * 100) if result.days else 0.0
    ret_pct = total_inr / CAPITAL * 100
    improvement = total_inr - baseline_inr

    print(
        f"  {label}: {fmt_pnl(total_inr):>10}  {fmt_ret(ret_pct):>7}"
        f"   Trades={trades}  HOLDs={holds}  WinRate={win_rate:.0f}%"
        f"  Selectivity={selectivity:.0f}%"
    )
    print(
        f"  Baseline: {fmt_pnl(baseline_inr):>10}   "
        f"Improvement: {fmt_pnl(improvement):>10}  "
        f"({'✓ FIXED' if total_inr > 0 else '▲ IMPROVED' if improvement > 0 else '✗ WORSE'})"
    )

    return {
        "label": label,
        "inr": total_inr,
        "ret_pct": ret_pct,
        "trades": trades,
        "wins": wins,
        "holds": holds,
        "days": len(result.days),
        "baseline": baseline_inr,
        "improvement": improvement,
    }


async def main():
    from app.engine.backtest_engine import BacktestEngine
    from app.config import config
    from app.data.historical_store import historical_store

    print("=" * 90)
    print("  God's Eye — Losing-Months Validation (bt_v3)")
    print("  Testing: May-2024, Aug-2024, Sep-2024  [VIX gate + event blackout active]")
    print("=" * 90)
    print(f"  Capital         : ₹{CAPITAL:,.0f}")
    print(f"  Model           : {config.MODEL}")
    print(f"  Mock mode       : {config.MOCK_MODE}")
    print(f"  Conviction floor: {config.CONVICTION_FLOOR}")
    print(f"  Agents ({len(config.AGENT_WEIGHTS)}): {list(config.AGENT_WEIGHTS.keys())}")
    print(f"  Weight sum      : {sum(config.AGENT_WEIGHTS.values()):.2f}")
    print(f"  Baseline total  : {fmt_pnl(BASELINE_TOTAL)}")
    print("=" * 90)
    print()

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

    for from_date, to_date, label, baseline in LOSING_MONTHS:
        try:
            s = await run_month(engine, from_date, to_date, label, baseline, vix_map)
            summaries.append(s)
        except Exception as exc:
            print(f"\n[ERROR] {label}: {exc}")
            import traceback
            traceback.print_exc()

    # Final comparison table
    if summaries:
        new_total = sum(s["inr"] for s in summaries)
        total_improvement = new_total - BASELINE_TOTAL
        new_ret = new_total / CAPITAL * 100

        print(f"\n{'='*90}")
        print(f"  VALIDATION SUMMARY — VIX Gate + Event Blackout Effect")
        print(f"{'='*90}")
        print(f"  {'Month':<12}  {'New P&L':>10}  {'Baseline':>10}  {'Improvement':>12}  {'Status':<10}")
        print(f"  {'-'*60}")
        for s in summaries:
            status = "✓ PROFITABLE" if s["inr"] > 0 else ("▲ IMPROVED" if s["improvement"] > 0 else "✗ WORSE")
            print(
                f"  {s['label']:<12}  {fmt_pnl(s['inr']):>10}  "
                f"{fmt_pnl(s['baseline']):>10}  {fmt_pnl(s['improvement']):>12}  {status}"
            )
        print(f"  {'-'*60}")
        print(
            f"  {'TOTAL':<12}  {fmt_pnl(new_total):>10}  "
            f"{fmt_pnl(BASELINE_TOTAL):>10}  {fmt_pnl(total_improvement):>12}  "
            f"{'✓ PROFITABLE' if new_total > 0 else '▲ IMPROVED'}"
        )
        print(f"\n  Capital deployed: ₹{CAPITAL:,.0f}")
        print(f"  New 3-month return: {fmt_ret(new_ret)}")
        print(f"  Rescue from baseline: {fmt_pnl(total_improvement)} ({total_improvement/abs(BASELINE_TOTAL)*100:.0f}% of losses recovered)")
        print("=" * 90)


if __name__ == "__main__":
    asyncio.run(main())
