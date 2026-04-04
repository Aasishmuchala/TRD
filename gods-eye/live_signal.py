"""
live_signal.py — God's Eye: Daily pre-market signal (live Dhan data)
=====================================================================
Fetches today's NIFTY + VIX from Dhan, builds market context from DB history,
runs all 8 agents, applies the VIX/trend gate, and prints the day's signal.

Run this before 9:15 AM IST each morning.

Usage:
    cd gods-eye/backend
    set -a && source .env && set +a
    export GODS_EYE_DB_PATH=/path/to/gods_eye.db
    python3 -u ../live_signal.py

Optional flags:
    --date 2026-04-04   Simulate as-if running on a past date (uses DB data, no Dhan call)
    --mock              Use mock agents (no LLM calls, instant)
    --no-color          Plain output (for piping to a log file)

Output:
    ══════════════════════════════════════════════════════
      GOD'S EYE SIGNAL  —  2026-04-04  09:05 IST
    ══════════════════════════════════════════════════════
      NIFTY : 23,450.25   VIX : 14.2   Trend : BEARISH -1.3%
      Context: weakness | trend:BEARISH -1.3%_vs_20dSMA

      ┌─ AGENT VOTES ─────────────────────────────────┐
      │  FII          BUY      conv=71  (wt 0.27)      │
      │  DII          HOLD     conv=63  (wt 0.22)      │
      ...

      CONSENSUS:  HOLD    conviction=67.4
      GATE:       HOLD    (below floor=78, BEARISH trend)

      FINAL SIGNAL:  ── HOLD ──   [no trade today]
    ══════════════════════════════════════════════════════
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Optional

sys.path.insert(0, ".")

CAPITAL        = 20_000.0
AGENT_STAGGER  = 1.5      # seconds between task creation
MAX_RETRIES    = 1

# ANSI colours
BOLD  = "\033[1m"
GREEN = "\033[92m"
RED   = "\033[91m"
CYAN  = "\033[96m"
YEL   = "\033[93m"
RST   = "\033[0m"

USE_COLOR = True   # overridden by --no-color

def C(code, text): return f"{code}{text}{RST}" if USE_COLOR else text
def bold(t):  return C(BOLD, t)
def green(t): return C(GREEN, t)
def red(t):   return C(RED, t)
def cyan(t):  return C(CYAN, t)
def yel(t):   return C(YEL, t)


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def call_agent(name, agent, market_input):
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            return await asyncio.wait_for(agent.analyze(market_input, round_num=1), timeout=70)
        except Exception as exc:
            if attempt <= MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
            else:
                print(f"    [{name}] failed: {exc!s:.60}", flush=True)
                return None


async def run_agents_staggered(engine, market_input):
    agents = engine.orchestrator.agents
    tasks  = []
    print(f"  Running {len(agents)} agents (staggered {AGENT_STAGGER}s)...", flush=True)
    for i, (name, agent) in enumerate(agents.items()):
        if i > 0:
            await asyncio.sleep(AGENT_STAGGER)
        tasks.append((name, asyncio.create_task(call_agent(name, agent, market_input), name=name)))
    results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)
    outputs = {}
    for (name, _), res in zip(tasks, results):
        if not isinstance(res, Exception) and res is not None:
            outputs[name] = res
    return outputs


def ist_now() -> str:
    """Current time in IST (UTC+5:30)."""
    utc_now = datetime.utcnow()
    ist = utc_now + timedelta(hours=5, minutes=30)
    return ist.strftime("%H:%M IST")


# ─── Live data fetch ──────────────────────────────────────────────────────────

async def fetch_live_spot(dhan_client) -> dict:
    """Fetch live NIFTY close + VIX from Dhan. Falls back to mock values."""
    try:
        nifty_data = await dhan_client.fetch_nifty50()
        vix_data   = await dhan_client.fetch_india_vix()

        nifty_close = nifty_data.get("ltp") or nifty_data.get("close") or 0
        india_vix   = vix_data.get("ltp")   or vix_data.get("close") or 15.0

        if nifty_close <= 0:
            raise ValueError(f"Invalid NIFTY close: {nifty_close}")

        print(f"  Live data: NIFTY={nifty_close:.2f}  VIX={india_vix:.2f}", flush=True)
        return {"nifty_close": float(nifty_close), "india_vix": float(india_vix)}

    except Exception as exc:
        print(f"  {yel('WARNING')}: Dhan live fetch failed ({exc}). Using last DB close.", flush=True)
        return None


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    global USE_COLOR

    ap = argparse.ArgumentParser(description="God's Eye live signal")
    ap.add_argument("--date",     default=None, help="Simulate on past date YYYY-MM-DD")
    ap.add_argument("--mock",     action="store_true", help="Use mock agents (no LLM)")
    ap.add_argument("--no-color", action="store_true", help="Disable ANSI color output")
    args = ap.parse_args()

    if args.no_color:
        USE_COLOR = False

    from app.engine.backtest_engine import BacktestEngine
    from app.config import config
    from app.data.historical_store import historical_store
    from app.data.dhan_client import DhanClient
    from app.data.event_calendar import get_event_for_date, is_pre_event_blackout

    config.SAMPLES_PER_AGENT = 1
    config.INTERACTION_ROUNDS = 1
    if args.mock:
        config.MOCK_MODE = True

    # Determine signal date
    signal_date = args.date if args.date else date.today().strftime("%Y-%m-%d")

    print(flush=True)
    print(bold("═" * 60))
    print(bold(f"  GOD'S EYE LIVE SIGNAL  —  {signal_date}  {ist_now()}"))
    print(bold("═" * 60))
    print(f"  Mode: {'MOCK (no LLM)' if args.mock else 'LIVE'}  |  "
          f"Capital: ₹{CAPITAL:,.0f}  |  Model: {config.MODEL}", flush=True)
    print(flush=True)

    # Load historical data
    print("  Loading NIFTY + VIX history...", end=" ", flush=True)
    all_ohlcv = await historical_store.get_ohlcv("NIFTY")
    vix_rows  = await historical_store.get_vix_closes()
    vix_map   = {r["date"]: r["close"] for r in vix_rows}
    print(f"NIFTY={len(all_ohlcv)} rows  VIX={len(vix_map)} rows", flush=True)

    engine = BacktestEngine()

    # Find today's row (or inject live data)
    today_rows = [r for r in all_ohlcv if r["date"] == signal_date]

    if not today_rows:
        # Today is not in DB yet — inject a synthetic row using live Dhan data
        if not args.date:
            print(f"  {signal_date} not in DB — fetching live from Dhan...", flush=True)
            dhan = DhanClient()
            live = await fetch_live_spot(dhan)
            if live:
                # Build a minimal row using live close; prev close from DB for OHLC
                prev_rows = [r for r in all_ohlcv if r["date"] < signal_date]
                if prev_rows:
                    prev = prev_rows[-1]
                    synthetic_row = {
                        "date":   signal_date,
                        "open":   prev["close"],
                        "high":   max(prev["close"], live["nifty_close"]),
                        "low":    min(prev["close"], live["nifty_close"]),
                        "close":  live["nifty_close"],
                        "volume": 0,
                    }
                    # Inject into all_ohlcv for SMA/momentum computation
                    all_ohlcv.append(synthetic_row)
                    vix_map[signal_date] = live["india_vix"]
                    today_rows = [synthetic_row]
                    print(f"  Injected live NIFTY={live['nifty_close']:.2f}  VIX={live['india_vix']:.2f}", flush=True)
                else:
                    print("  ERROR: No historical data to build context from.", flush=True)
                    sys.exit(1)
            else:
                print("  ERROR: Cannot fetch live data and date not in DB.", flush=True)
                sys.exit(1)
        else:
            print(f"  ERROR: {signal_date} not found in DB. Check the date.", flush=True)
            sys.exit(1)

    row = today_rows[0]
    nifty_close = row["close"]
    india_vix   = vix_map.get(signal_date, 15.0)

    # Build market input
    market_input = engine._build_market_input(row, vix_map, all_ohlcv)
    context      = market_input.context or ""
    event_risk   = market_input.event_risk or ""

    # Parse trend from context
    trend_part = ""
    for part in context.split("|"):
        if "trend:" in part:
            trend_part = part.strip()

    print(f"\n  NIFTY  : {bold(f'{nifty_close:,.2f}')}")
    print(f"  VIX    : {bold(f'{india_vix:.2f}')}", end="")
    if india_vix > 20:
        print(f"  {red('⚠ VIX > 20 — ALL TRADES BLOCKED')}", end="")
    elif india_vix > 16:
        print(f"  {yel('(HIGH — floor=78)')}", end="")
    elif india_vix > 14:
        print(f"  {yel('(ELEVATED — floor=72)')}", end="")
    else:
        print(f"  (NORMAL — floor=65)", end="")
    print()

    if trend_part:
        print(f"  Trend  : {bold(trend_part)}")
    if event_risk:
        print(f"  Event  : {yel(event_risk)}")

    ev = get_event_for_date(signal_date)
    if ev:
        print(f"  ⚑ Event: {red(ev.upper())} — pre-event blackout may apply")

    print(f"\n  Context: {context}\n", flush=True)

    # ── Run agents ────────────────────────────────────────────────────────────
    t0 = time.time()
    final_outputs = await run_agents_staggered(engine, market_input)
    elapsed = time.time() - t0

    if not final_outputs:
        print(f"\n  {red('ERROR')}: No agent outputs. Check LLM connectivity.", flush=True)
        sys.exit(1)

    # ── Per-agent results ─────────────────────────────────────────────────────
    from app.config import config as cfg
    weights = cfg.AGENT_WEIGHTS

    print(f"\n  ┌─ AGENT VOTES ({'mock' if args.mock else 'live'}, {elapsed:.0f}s) " + "─" * 28 + "┐")
    for name, resp in final_outputs.items():
        wt  = weights.get(name, 0)
        dir_raw = getattr(resp, "direction", "HOLD")
        conv    = getattr(resp, "conviction", 0.0)
        rat     = getattr(resp, "rationale", "")[:55]

        dir_colored = (green if "BUY" in dir_raw else red if "SELL" in dir_raw else yel)(f"{dir_raw:<13}")
        print(f"  │  {name:<18}  {dir_colored}  conv={conv:4.0f}  (wt {wt:.2f})  {rat}")
    print(f"  └" + "─" * 55 + "┘\n")

    # ── Consensus + gate ──────────────────────────────────────────────────────
    raw_dir, raw_conv = engine._compute_consensus(final_outputs)
    final_dir, final_conv = engine._apply_vix_event_gate(
        raw_dir, raw_conv,
        market_input.india_vix,
        market_input.event_risk,
        signal_date,
        context=market_input.context,
    )

    print(f"  Raw consensus : {bold(raw_dir):<13}  conviction={raw_conv:.1f}")

    gate_note = ""
    if final_dir == "HOLD" and raw_dir != "HOLD":
        if india_vix and india_vix > 20:
            gate_note = f"VIX={india_vix:.1f} > 20 — blocked"
        elif "trend:BEARISH" in context and "BUY" in raw_dir:
            gate_note = f"BEARISH trend — BUY floor=78, conv={raw_conv:.0f} insufficient"
        elif india_vix and india_vix > 16:
            gate_note = f"VIX HIGH — floor=78, conv={raw_conv:.0f} insufficient"
        elif india_vix and india_vix > 14:
            gate_note = f"VIX ELEVATED — floor=72, conv={raw_conv:.0f} insufficient"
        else:
            gate_note = f"below floor=65, conv={raw_conv:.0f} insufficient"
        print(f"  Gate          : {red('BLOCKED')}  ({gate_note})")
    else:
        print(f"  Gate          : {green('PASS')}  conviction={final_conv:.1f}")

    # ── Final signal ──────────────────────────────────────────────────────────
    print()
    print(bold("═" * 60))
    if final_dir == "HOLD":
        signal_str = yel("── HOLD ──   no trade today")
        action_str = "No position. Stay flat."
    elif final_dir in ("BUY", "STRONG_BUY"):
        signal_str = green(f"▲ {final_dir}   conviction={final_conv:.0f}")
        action_str = f"BUY ATM NIFTY CE  |  1 lot  |  capital ₹{CAPITAL:,.0f}"
    else:
        signal_str = red(f"▼ {final_dir}   conviction={final_conv:.0f}")
        action_str = f"BUY ATM NIFTY PE  |  1 lot  |  capital ₹{CAPITAL:,.0f}"

    print(bold(f"  FINAL SIGNAL:  {signal_str}"))
    print(f"  Action       :  {action_str}")
    print(bold("═" * 60))

    # ── Risk reminder ─────────────────────────────────────────────────────────
    print(f"\n  Max risk/trade: ₹{CAPITAL * 0.10:,.0f} (10% of capital)")
    print(f"  Stop-loss    : exit if option loses >50% of entry premium")
    print(f"  Target       : exit at 2x premium or by 3:15 PM IST")
    print(f"\n  Signal generated at: {ist_now()}", flush=True)
    print(flush=True)


if __name__ == "__main__":
    asyncio.run(main())
