"""
bt_v3_run.py — God's Eye: Losing-Month Validation (Sequential Agent Calls)
===========================================================================
Validates that VIX gate + event blackout (built into BacktestEngine) rescue
the 3 losing months: May-2024, Aug-2024, Sep-2024.

Key difference from bt_v3.py:
  - Calls agents SEQUENTIALLY with 1s gap (not asyncio.gather)
  - Bypasses BacktestEngine.run_backtest() to get per-day streaming output
  - Uses BacktestEngine._build_market_input() + _apply_vix_event_gate() + _compute_consensus()
  - No asyncio.Semaphore — stable on Python 3.14

Run from gods-eye/backend:
    cd gods-eye/backend
    set -a && source .env && set +a
    export GODS_EYE_DB_PATH=/tmp/gods_eye_bt_v2.db
    python3 -u ../bt_v3_run.py 2>&1 | tee ../bt_v3_run.log
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, ".")

CAPITAL = 20_000.0
AGENT_STAGGER_S = 1.5  # seconds between task creation (staggered parallel, not sequential)
MAX_RETRIES = 1

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


async def call_agent_with_retry(agent_name, agent, market_input, round_num=1):
    """Call one agent with up to MAX_RETRIES attempts."""
    from app.engine.orchestrator import AgentResponse
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await asyncio.wait_for(
                agent.analyze(market_input, round_num=round_num),
                timeout=70,  # httpx cancels at 60s; this is a safety net
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
    """Stagger task creation by AGENT_STAGGER_S, then gather all results.

    This avoids hammering the proxy with 8 simultaneous connections while
    still running agents in parallel (much faster than fully sequential).
    """
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

    # Filter to signal rows in range
    signal_rows = [r for r in all_ohlcv if from_date <= r["date"] <= to_date]

    t0 = time.time()
    total_inr = 0.0
    trades = 0
    wins = 0
    holds = 0

    print(f"\n{'='*100}")
    print(f"  {label}  ({from_date} → {to_date})  [baseline: {fmt_pnl(baseline_inr)}]")
    print(f"{'='*100}")
    print(f"{'Date':<12} {'Dir':<13} {'Conv':>5}  {'VIX':>5}  {'Gate':<10}  "
          f"{'Event':<18}  {'Res':<4}  {'Pts':>7}  {'₹P&L':>9}  {'Ret%':>6}")
    print(f"{'-'*105}")

    for row in signal_rows:
        signal_date = row["date"]

        # Find next trading day
        full_indices = [j for j, r in enumerate(all_ohlcv) if r["date"] == signal_date]
        if not full_indices:
            continue
        full_idx = full_indices[0]
        if full_idx + 1 >= len(all_ohlcv):
            continue
        next_row = all_ohlcv[full_idx + 1]
        nifty_close = row["close"]
        nifty_next_close = next_row["close"]
        actual_move_pct = (nifty_next_close - nifty_close) / nifty_close * 100

        # Build market input
        market_input = engine._build_market_input(row, vix_map, all_ohlcv)
        vix_val = market_input.india_vix or 0.0
        event_risk = market_input.event_risk or ""

        # Gate labels for display
        gate_label = "OK"
        if vix_val > 20.0:
            gate_label = "VIX>20 BLK"
        elif vix_val > 16.0:
            gate_label = f"VIX-HIGH"
        elif vix_val > 14.0:
            gate_label = "VIX-ELEV"

        event_label = ""
        ev = get_event_for_date(signal_date)
        if ev:
            event_label = ev.lower()[:18]
        elif is_pre_event_blackout(signal_date):
            event_label = "pre_evt_blkout"

        day_t0 = time.time()
        # Run agents staggered-parallel
        final_outputs = await run_agents_staggered(engine, market_input)
        day_elapsed = time.time() - day_t0

        if not final_outputs:
            holds += 1
            print(f"{signal_date:<12} {'NO-SIGNAL':<13} {'--':>5}  {vix_val:5.1f}  "
                  f"{gate_label:<10}  {event_label:<18}  {'--':<4}", flush=True)
            continue

        # Consensus + VIX gate (engine method)
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

        # P&L
        buy_dirs = ("BUY", "STRONG_BUY")
        # Do NOT negate for SELL — compute_options_pnl already negates internally for PE
        # (see options_pnl.py: raw_exit = entry + ATM_DELTA * -nifty_point_move for PE).
        # Passing the raw market move lets options_pnl correctly lose on up-days for SELL.
        direction_correct = (
            (actual_move_pct > 0.1 and direction in buy_dirs) or
            (actual_move_pct < -0.1 and direction not in buy_dirs)
        )

        pnl_pts = actual_move_pct * (1 if direction in buy_dirs else -1) * 220  # ~Nifty pts proxy

        t = compute_options_pnl(
            date=signal_date,
            direction=direction,
            nifty_point_move=actual_move_pct * nifty_close / 100,  # raw market move, sign handled by options_pnl
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
    improvement = total_inr - baseline_inr

    status = "✓ PROFITABLE" if total_inr > 0 else ("▲ IMPROVED" if improvement > 0 else "✗ WORSE")
    print(
        f"\n  {label}: {fmt_pnl(total_inr):>10}  {fmt_ret(ret_pct):>7}  "
        f"Trades={trades}  HOLDs={holds}  WinRate={win_rate:.0f}%  Sel={selectivity:.0f}%  [{elapsed:.0f}s]",
        flush=True,
    )
    print(
        f"  Baseline: {fmt_pnl(baseline_inr):>10}   "
        f"Improvement: {fmt_pnl(improvement):>10}  {status}",
        flush=True,
    )

    return {
        "label": label, "inr": total_inr, "ret_pct": ret_pct,
        "trades": trades, "wins": wins, "holds": holds,
        "days": len(signal_rows), "baseline": baseline_inr, "improvement": improvement,
    }


async def main():
    from app.engine.backtest_engine import BacktestEngine
    from app.config import config
    from app.data.historical_store import historical_store

    # Backtest speed settings
    config.SAMPLES_PER_AGENT = 1
    config.INTERACTION_ROUNDS = 1
    config.MODEL = os.getenv("GODS_EYE_BACKTEST_MODEL", "claude-sonnet-4-6")

    print("=" * 100)
    print("  God's Eye — Losing-Month Validation (bt_v3_run: sequential agents, streaming output)")
    print("  Months: May-2024, Aug-2024, Sep-2024  |  VIX gate + event blackout active")
    print("=" * 100)
    print(f"  Capital  : ₹{CAPITAL:,.0f}   Model: {config.MODEL}   Mock: {config.MOCK_MODE}")
    print(f"  Agents   : {list(config.AGENT_WEIGHTS.keys())}")
    print(f"  Baseline : {fmt_pnl(BASELINE_TOTAL)}")
    print("=" * 100)
    print(flush=True)

    print("Loading NIFTY + VIX history...", end=" ", flush=True)
    all_ohlcv = await historical_store.get_ohlcv("NIFTY")
    vix_rows  = await historical_store.get_vix_closes()
    vix_map   = {r["date"]: r["close"] for r in vix_rows}
    print(f"NIFTY={len(all_ohlcv)} rows  VIX={len(vix_map)} rows", flush=True)

    engine = BacktestEngine()
    summaries = []

    for from_date, to_date, label, baseline in LOSING_MONTHS:
        try:
            s = await run_month(engine, from_date, to_date, label, baseline, vix_map, all_ohlcv)
            summaries.append(s)
        except Exception as exc:
            import traceback
            print(f"\n[ERROR] {label}: {exc}")
            traceback.print_exc()

    if summaries:
        new_total = sum(s["inr"] for s in summaries)
        improvement = new_total - BASELINE_TOTAL
        new_ret = new_total / CAPITAL * 100

        print(f"\n{'='*100}")
        print("  FINAL VALIDATION — VIX Gate + Event Blackout Effect on 3 Losing Months")
        print(f"{'='*100}")
        print(f"  {'Month':<12}  {'New P&L':>10}  {'Baseline':>10}  {'Improvement':>12}  Status")
        print(f"  {'-'*65}")
        for s in summaries:
            st = "✓ PROFITABLE" if s["inr"] > 0 else ("▲ IMPROVED" if s["improvement"] > 0 else "✗ WORSE")
            wr = (s["wins"] / s["trades"] * 100) if s["trades"] else 0.0
            print(f"  {s['label']:<12}  {fmt_pnl(s['inr']):>10}  {fmt_pnl(s['baseline']):>10}  "
                  f"{fmt_pnl(s['improvement']):>12}  {st}  WR={wr:.0f}%")
        print(f"  {'-'*65}")
        print(f"  {'TOTAL':<12}  {fmt_pnl(new_total):>10}  {fmt_pnl(BASELINE_TOTAL):>10}  "
              f"{fmt_pnl(improvement):>12}  {'✓ PROFITABLE' if new_total > 0 else '▲ IMPROVED'}")
        pct_rescued = improvement / abs(BASELINE_TOTAL) * 100
        print(f"\n  Capital: ₹{CAPITAL:,.0f}   3-month return: {fmt_ret(new_ret)}")
        print(f"  Losses rescued: {fmt_pnl(improvement)} ({pct_rescued:.0f}% of original losses)")
        print("=" * 100)
        print(flush=True)


if __name__ == "__main__":
    asyncio.run(main())
