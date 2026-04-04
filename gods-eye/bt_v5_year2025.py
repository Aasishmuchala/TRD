"""
bt_v5_year2025.py — God's Eye: Full Year 2025 Backtest (Jan 2025 – Dec 2025)
==============================================================================
Runs all 12 months of 2025 with the trend-aware gate (20D SMA + 5D momentum)
active. This is the first full-year validation of the system.

Run from gods-eye/backend:
    cd gods-eye/backend
    set -a && source .env && set +a
    python3 -u ../bt_v5_year2025.py 2>&1 | tee ../bt_v5_year2025.log
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, ".")

CAPITAL = 20_000.0
AGENT_STAGGER_S = 1.5
MAX_RETRIES = 1

MONTHS_2025 = [
    ("2025-01-01", "2025-01-31", "Jan-2025", 0),
    ("2025-02-01", "2025-02-28", "Feb-2025", 0),
    ("2025-03-01", "2025-03-31", "Mar-2025", 0),
    ("2025-04-01", "2025-04-30", "Apr-2025", 0),
    ("2025-05-01", "2025-05-31", "May-2025", 0),
    ("2025-06-01", "2025-06-30", "Jun-2025", 0),
    ("2025-07-01", "2025-07-31", "Jul-2025", 0),
    ("2025-08-01", "2025-08-31", "Aug-2025", 0),
    ("2025-09-01", "2025-09-30", "Sep-2025", 0),
    ("2025-10-01", "2025-10-31", "Oct-2025", 0),
    ("2025-11-01", "2025-11-30", "Nov-2025", 0),
    ("2025-12-01", "2025-12-31", "Dec-2025", 0),
]


def fmt_pnl(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}₹{v:,.0f}"


def fmt_ret(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


async def call_agent_with_retry(agent_name, agent, market_input, round_num=1):
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await asyncio.wait_for(
                agent.analyze(market_input, round_num=round_num),
                timeout=70,
            )
            return result
        except Exception as exc:
            last_exc = exc
            wait = 2 ** attempt
            if attempt < MAX_RETRIES:
                print(f"    [{agent_name}] attempt {attempt} failed: {exc!s:.60} — retry in {wait}s",
                      flush=True)
                await asyncio.sleep(wait)
    print(f"    [{agent_name}] all retries failed: {last_exc!s:.80}", flush=True)
    return None


async def run_agents_staggered(engine, market_input):
    agents = engine.orchestrator.agents
    tasks = []
    for i, (name, agent) in enumerate(agents.items()):
        if i > 0:
            await asyncio.sleep(AGENT_STAGGER_S)
        task = asyncio.create_task(
            call_agent_with_retry(name, agent, market_input),
            name=name,
        )
        tasks.append((name, task))
    results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)
    outputs = {}
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            print(f"    [{name}] failed: {result!s:.60}", flush=True)
        elif result is not None:
            outputs[name] = result
    return outputs


async def run_month(engine, from_date, to_date, label, baseline_inr, vix_map, all_ohlcv):
    from app.engine.options_pnl import compute_options_pnl
    from app.data.event_calendar import get_event_for_date, is_pre_event_blackout

    signal_rows = [r for r in all_ohlcv if from_date <= r["date"] <= to_date]

    if not signal_rows:
        print(f"\n  [{label}] No data in range {from_date} → {to_date}, skipping.")
        return None

    t0 = time.time()
    total_inr = 0.0
    trades = 0
    wins = 0
    holds = 0

    print(f"\n{'='*100}")
    print(f"  {label}  ({from_date} → {to_date})  [{len(signal_rows)} trading days]")
    print(f"{'='*100}")
    print(f"{'Date':<12} {'Dir':<13} {'Conv':>5}  {'VIX':>5}  {'Gate':<10}  "
          f"{'Event':<18}  {'Res':<4}  {'Pts':>7}  {'₹P&L':>9}  {'Ret%':>6}")
    print(f"{'-'*105}")

    for row in signal_rows:
        signal_date = row["date"]

        full_indices = [j for j, r in enumerate(all_ohlcv) if r["date"] == signal_date]
        if not full_indices:
            continue
        full_idx = full_indices[0]
        if full_idx + 1 >= len(all_ohlcv):
            print(f"{signal_date:<12} {'--LAST ROW--':<13}  no next-day data, skip", flush=True)
            continue
        next_row = all_ohlcv[full_idx + 1]
        nifty_close = row["close"]
        nifty_next_close = next_row["close"]
        actual_move_pct = (nifty_next_close - nifty_close) / nifty_close * 100

        market_input = engine._build_market_input(row, vix_map, all_ohlcv)
        vix_val = market_input.india_vix or 0.0
        event_risk = market_input.event_risk or ""

        gate_label = "OK"
        if vix_val > 20.0:
            gate_label = "VIX>20 BLK"
        elif vix_val > 16.0:
            gate_label = "VIX-HIGH"
        elif vix_val > 14.0:
            gate_label = "VIX-ELEV"

        event_label = ""
        ev = get_event_for_date(signal_date)
        if ev:
            event_label = ev.lower()[:18]
        elif is_pre_event_blackout(signal_date):
            event_label = "pre_evt_blkout"

        day_t0 = time.time()
        final_outputs = await run_agents_staggered(engine, market_input)
        day_elapsed = time.time() - day_t0

        if not final_outputs:
            holds += 1
            print(f"{signal_date:<12} {'NO-SIGNAL':<13} {'--':>5}  {vix_val:5.1f}  "
                  f"{gate_label:<10}  {event_label:<18}  {'--':<4}", flush=True)
            continue

        direction, conviction = engine._apply_vix_event_gate(
            *engine._compute_consensus(final_outputs),
            market_input.india_vix,
            market_input.event_risk,
            signal_date,
            context=market_input.context,
        )

        if direction == "HOLD":
            holds += 1
            print(f"{signal_date:<12} {'HOLD':<13} {conviction:5.1f}  {vix_val:5.1f}  "
                  f"{gate_label:<10}  {event_label:<18}  {'--':<4}  [gate/low conv] [{day_elapsed:.0f}s]",
                  flush=True)
            continue

        buy_dirs = ("BUY", "STRONG_BUY")
        direction_correct = (
            (actual_move_pct > 0.1 and direction in buy_dirs) or
            (actual_move_pct < -0.1 and direction not in buy_dirs)
        )

        t = compute_options_pnl(
            date=signal_date,
            direction=direction,
            nifty_point_move=actual_move_pct * nifty_close / 100,
            instrument="NIFTY",
            spot=nifty_close,
            vix=vix_val if vix_val else 14.0,
            conviction=conviction,
            capital=CAPITAL,
        )
        inr = t.net_pnl if t else 0.0
        ret = t.return_pct if t else 0.0
        total_inr += inr
        trades += 1
        if direction_correct:
            wins += 1

        res = "WIN " if direction_correct else "LOSS"
        print(
            f"{signal_date:<12} {direction:<13} {conviction:5.1f}  {vix_val:5.1f}  "
            f"{gate_label:<10}  {event_label:<18}  {res:<4}"
            f"  {actual_move_pct:>+7.2f}  {fmt_pnl(inr):>9}  {fmt_ret(ret):>6}"
            f"  [{day_elapsed:.0f}s]",
            flush=True,
        )

    elapsed = time.time() - t0
    print(f"{'-'*105}")
    win_rate = (wins / trades * 100) if trades else 0.0
    selectivity = (trades / len(signal_rows) * 100) if signal_rows else 0.0
    ret_pct = total_inr / CAPITAL * 100
    status = "✓ PROFITABLE" if total_inr > 0 else "✗ LOSS"

    print(
        f"\n  {label}: {fmt_pnl(total_inr):>10}  {fmt_ret(ret_pct):>7}  "
        f"Trades={trades}  HOLDs={holds}  WinRate={win_rate:.0f}%  Sel={selectivity:.0f}%  [{elapsed:.0f}s]  {status}",
        flush=True,
    )
    return {
        "label": label, "inr": total_inr, "ret_pct": ret_pct,
        "trades": trades, "wins": wins, "holds": holds,
        "days": len(signal_rows),
    }


async def main():
    from app.engine.backtest_engine import BacktestEngine
    from app.config import config
    from app.data.historical_store import historical_store

    config.SAMPLES_PER_AGENT = 1
    config.INTERACTION_ROUNDS = 1
    config.MODEL = os.getenv("GODS_EYE_BACKTEST_MODEL", "claude-opus-4-6")

    print("=" * 100)
    print("  God's Eye — Full Year 2025 Backtest (Jan 2025 → Dec 2025)")
    print("  Trend-aware gate: VIX + 20D SMA + 5D momentum  |  Real LLM via OpusCode Pro")
    print("=" * 100)
    print(f"  Capital  : ₹{CAPITAL:,.0f}   Model: {config.MODEL}   Mock: {config.MOCK_MODE}")
    print(f"  Agents   : {list(config.AGENT_WEIGHTS.keys())}")
    print("=" * 100)
    print(flush=True)

    print("Loading NIFTY + VIX history...", end=" ", flush=True)
    all_ohlcv = await historical_store.get_ohlcv("NIFTY")
    vix_rows  = await historical_store.get_vix_closes()
    vix_map   = {r["date"]: r["close"] for r in vix_rows}
    rows_2025 = [r for r in all_ohlcv if "2025-01-01" <= r["date"] <= "2025-12-31"]
    print(f"NIFTY={len(all_ohlcv)} rows  VIX={len(vix_map)} rows  "
          f"2025 rows={len(rows_2025)}  ({rows_2025[0]['date'] if rows_2025 else '?'} → {rows_2025[-1]['date'] if rows_2025 else '?'})",
          flush=True)

    engine = BacktestEngine()
    summaries = []

    for from_date, to_date, label, baseline in MONTHS_2025:
        try:
            s = await run_month(engine, from_date, to_date, label, baseline, vix_map, all_ohlcv)
            if s:
                summaries.append(s)
                # Print running total after each month
                running = sum(x["inr"] for x in summaries)
                print(f"  ── Running YTD: {fmt_pnl(running)} ({fmt_ret(running/CAPITAL*100)})", flush=True)
        except Exception as exc:
            import traceback
            print(f"\n[ERROR] {label}: {exc}")
            traceback.print_exc()

    if summaries:
        new_total = sum(s["inr"] for s in summaries)
        new_ret = new_total / CAPITAL * 100
        total_trades = sum(s["trades"] for s in summaries)
        total_wins = sum(s["wins"] for s in summaries)
        total_days = sum(s["days"] for s in summaries)
        overall_wr = (total_wins / total_trades * 100) if total_trades else 0.0
        overall_sel = (total_trades / total_days * 100) if total_days else 0.0

        print(f"\n{'='*100}")
        print("  FINAL — God's Eye Full Year 2025 Performance")
        print(f"{'='*100}")
        print(f"  {'Month':<12}  {'P&L':>10}  {'Return':>8}  {'Trades':>7}  {'WR':>6}  {'Sel':>6}  Status")
        print(f"  {'-'*70}")
        running = 0.0
        for s in summaries:
            wr = (s["wins"] / s["trades"] * 100) if s["trades"] else 0.0
            sel = (s["trades"] / s["days"] * 100) if s["days"] else 0.0
            running += s["inr"]
            st = "✓ PROFIT" if s["inr"] > 0 else "✗ LOSS"
            print(f"  {s['label']:<12}  {fmt_pnl(s['inr']):>10}  {fmt_ret(s['ret_pct']):>8}  "
                  f"{s['trades']:>7}  {wr:>5.0f}%  {sel:>5.0f}%  {st}   [YTD {fmt_pnl(running)}]")
        print(f"  {'-'*70}")
        print(f"  {'YEAR TOTAL':<12}  {fmt_pnl(new_total):>10}  {fmt_ret(new_ret):>8}  "
              f"{total_trades:>7}  {overall_wr:>5.0f}%  {overall_sel:>5.0f}%  "
              f"{'✓ PROFITABLE' if new_total > 0 else '✗ NET LOSS'}")
        print(f"\n  Capital: ₹{CAPITAL:,.0f}   Full Year Return: {fmt_ret(new_ret)}")
        print(f"  Period:  Jan 2025 → Dec 2025  ({total_days} trading days, {total_trades} trades taken)")
        print("=" * 100)
        print(flush=True)


if __name__ == "__main__":
    asyncio.run(main())
