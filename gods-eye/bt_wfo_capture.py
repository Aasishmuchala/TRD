"""
bt_wfo_capture.py — God's Eye: WFO Phase 1 — Capture pre-gate LLM signals
===========================================================================
Runs agents on every trading day in 2023-2024 and saves the raw (pre-gate)
consensus to a CSV. The CSV is the input for bt_wfo_optimize.py.

Why this two-phase approach?
  LLM calls are expensive (~45s per day). By capturing once and replaying
  thousands of gate configurations instantly, we find optimal parameters
  without re-running the LLM. Clean walk-forward: train on 2023-2024,
  validate on 2025 (bt_v5_year2025.py).

Fields saved per day:
  date, direction, conviction, india_vix, event_risk, context,
  actual_nifty_pct, nifty_close, nifty_next_close

Usage:
    cd gods-eye/backend
    set -a && source .env && set +a
    export GODS_EYE_DB_PATH=/path/to/gods_eye.db
    python3 -u ../bt_wfo_capture.py 2>&1 | tee ../bt_wfo_capture.log

Output:
    ../bt_wfo_signals.csv   (append-mode — safe to resume if interrupted)
"""

import asyncio
import csv
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

# ─── Config ───────────────────────────────────────────────────────────────────

CAPITAL        = 20_000.0
AGENT_STAGGER  = 3.0      # was 1.5 — more breathing room for OpusCode 1req/s limit
MAX_RETRIES    = 3         # was 1 — gives 2 real retry attempts per agent
CAPTURE_FILE   = Path(__file__).parent / "bt_wfo_signals.csv"

# All trading days we want to capture (2023 from DB start, full 2024)
CAPTURE_RANGE = ("2023-04-05", "2024-12-31")

CSV_FIELDS = [
    "date", "direction", "conviction", "india_vix", "event_risk",
    "context", "actual_nifty_pct", "nifty_close", "nifty_next_close",
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def fmt(v): return f"+{v:,.0f}" if v >= 0 else f"{v:,.0f}"


async def call_agent(name, agent, market_input):
    from app.engine.orchestrator import AgentResponse
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            return await asyncio.wait_for(agent.analyze(market_input, round_num=1), timeout=160)
        except Exception as exc:
            if attempt <= MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
            else:
                print(f"    [{name}] failed: {exc!s:.60}", flush=True)
                return None


async def run_agents(engine, market_input):
    agents = engine.orchestrator.agents
    tasks  = []
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


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    from app.engine.backtest_engine import BacktestEngine
    from app.config import config
    from app.data.historical_store import historical_store

    config.SAMPLES_PER_AGENT = 1
    config.INTERACTION_ROUNDS = 1
    config.MODEL = os.getenv("GODS_EYE_BACKTEST_MODEL", "claude-sonnet-4-6")

    print("=" * 90)
    print("  God's Eye — WFO Capture: 2023-2024 pre-gate signals")
    print(f"  Output: {CAPTURE_FILE}")
    print("=" * 90)

    # Load existing captures so we can skip already-done days
    done_dates: set[str] = set()
    if CAPTURE_FILE.exists():
        with open(CAPTURE_FILE) as f:
            reader = csv.DictReader(f)
            done_dates = {row["date"] for row in reader}
        print(f"  Resuming: {len(done_dates)} days already captured, skipping those.", flush=True)

    # Load NIFTY + VIX history
    print("Loading history...", end=" ", flush=True)
    all_ohlcv = await historical_store.get_ohlcv("NIFTY")
    vix_rows  = await historical_store.get_vix_closes()
    vix_map   = {r["date"]: r["close"] for r in vix_rows}
    print(f"NIFTY={len(all_ohlcv)} rows  VIX={len(vix_map)} rows", flush=True)

    start_date, end_date = CAPTURE_RANGE
    signal_rows = [
        r for r in all_ohlcv
        if start_date <= r["date"] <= end_date
        and r["date"] not in done_dates
    ]
    total_remaining = len(signal_rows)
    print(f"  Days to capture: {total_remaining}  (of {sum(1 for r in all_ohlcv if start_date <= r['date'] <= end_date)} total in range)", flush=True)
    print(flush=True)

    engine = BacktestEngine()

    # Open CSV (append mode so we can resume)
    write_header = not CAPTURE_FILE.exists() or CAPTURE_FILE.stat().st_size == 0
    csv_file = open(CAPTURE_FILE, "a", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    if write_header:
        writer.writeheader()

    captured = 0
    skipped  = 0
    t0_total = time.time()

    try:
        for i, row in enumerate(signal_rows):
            signal_date = row["date"]

            # Find next trading day
            full_indices = [j for j, r in enumerate(all_ohlcv) if r["date"] == signal_date]
            if not full_indices:
                skipped += 1
                continue
            full_idx = full_indices[0]
            if full_idx + 1 >= len(all_ohlcv):
                skipped += 1
                continue
            next_row = all_ohlcv[full_idx + 1]
            nifty_close      = row["close"]
            nifty_next_close = next_row["close"]
            actual_move_pct  = (nifty_next_close - nifty_close) / nifty_close * 100

            # Build market input
            market_input = engine._build_market_input(row, vix_map, all_ohlcv)
            vix_val      = market_input.india_vix or 0.0
            event_risk   = market_input.event_risk or ""
            context      = market_input.context or ""

            day_t0 = time.time()
            print(f"  [{i+1:3d}/{total_remaining}] {signal_date}  VIX={vix_val:.1f}  ctx={context[:40]!r}", flush=True)

            # Run agents — capture raw LLM consensus (no gate)
            final_outputs = await run_agents(engine, market_input)

            if not final_outputs:
                print(f"    → no outputs, skipping", flush=True)
                skipped += 1
                continue

            direction, conviction = engine._compute_consensus(final_outputs)

            elapsed = time.time() - day_t0
            print(
                f"    → {direction:<13} conv={conviction:.1f}  actual={actual_move_pct:+.2f}%  [{elapsed:.0f}s]",
                flush=True,
            )

            writer.writerow({
                "date":             signal_date,
                "direction":        direction,
                "conviction":       round(conviction, 2),
                "india_vix":        round(vix_val, 2),
                "event_risk":       event_risk,
                "context":          context,
                "actual_nifty_pct": round(actual_move_pct, 4),
                "nifty_close":      round(nifty_close, 2),
                "nifty_next_close": round(nifty_next_close, 2),
            })
            csv_file.flush()
            captured += 1

            # Progress every 20 days
            if captured % 20 == 0:
                elapsed_total = time.time() - t0_total
                rate = captured / elapsed_total * 60
                eta_min = (total_remaining - captured) / rate if rate else 0
                print(f"\n  ── Progress: {captured}/{total_remaining} captured  "
                      f"({rate:.1f}/min  ETA {eta_min:.0f}min) ──\n", flush=True)

    finally:
        csv_file.close()

    total_elapsed = time.time() - t0_total
    print(f"\n{'='*90}")
    print(f"  Capture complete: {captured} days saved to {CAPTURE_FILE}")
    print(f"  Skipped: {skipped}  |  Total elapsed: {total_elapsed/60:.1f} min")
    print(f"  Next step: python3 bt_wfo_optimize.py")
    print(f"{'='*90}")


if __name__ == "__main__":
    asyncio.run(main())
