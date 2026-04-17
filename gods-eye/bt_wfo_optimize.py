"""
bt_wfo_optimize.py — God's Eye: WFO Phase 2 — Grid-search gate parameters
==========================================================================
Loads bt_wfo_signals.csv (captured LLM outputs, no gate applied) and
replays every day through thousands of gate configurations instantly.
Finds the parameter set that maximises risk-adjusted returns on 2023-2024.

Then prints the top configurations so you can update backtest_engine.py.

Metrics ranked by: Sharpe ratio (annualised), with tiebreak on total P&L.

TODO (TRD-H4): This is not true walk-forward optimization. The train window
(2023-2024) and validation window (2025) are fixed — a proper WFO would use
rolling/expanding windows (e.g. train on months 1-6, validate on month 7,
then train on months 2-7, validate on month 8, etc.). The current approach
risks overfitting to the specific 2023-2024 regime. ON HOLD — changing the
optimizer methodology requires re-running all WFO experiments.

TODO (TRD-H5): P-hacking risk — the grid search evaluates ~13,800 parameter
combinations on a single train/test split. With that many comparisons, some
configurations will appear profitable by chance alone. Consider applying
Bonferroni correction (alpha / n_comparisons) or permutation testing to
establish statistical significance of the top configurations. ON HOLD.

Usage:
    python3 bt_wfo_optimize.py                  # uses bt_wfo_signals.csv
    python3 bt_wfo_optimize.py --top 20         # show top 20 configs
    python3 bt_wfo_optimize.py --quick          # small grid for fast testing

Output:
    Console table + bt_wfo_results.csv
"""

import argparse
import csv
import itertools
import math
import os
import sys
from pathlib import Path

CAPTURE_FILE = Path(__file__).parent / "bt_wfo_signals.csv"
RESULTS_FILE = Path(__file__).parent / "bt_wfo_results.csv"
CAPITAL      = 20_000.0

# ─── Gate logic (mirrors backtest_engine.py exactly) ──────────────────────────

def apply_gate(direction: str, conviction: float, india_vix: float,
               event_risk: str, context: str, p: dict) -> tuple[str, float]:
    """Returns (final_direction, conviction) after applying gate params p."""

    # Rule 1: VIX > block_cutoff → no trade
    if india_vix and india_vix > p["vix_block_cutoff"]:
        return "HOLD", conviction

    # Rule 2: explicit blackout event
    if event_risk and "blackout" in event_risk.lower():
        return "HOLD", conviction

    # Determine base floor from VIX regime
    if india_vix and india_vix > p["vix_high_cutoff"]:
        floor = p["vix_high_floor"]
    elif india_vix and india_vix > p["vix_elevated_cutoff"]:
        floor = p["vix_elevated_floor"]
    else:
        floor = p["vix_normal_floor"]

    # Rule 6: trend-asymmetric gate (BUY signals need higher conviction in downtrends)
    buy_family = {"BUY", "STRONG_BUY"}
    bearish_trend   = "trend:BEARISH" in context
    momentum_weak   = any(kw in context for kw in ("correction", "weakness"))
    if direction in buy_family and (bearish_trend or momentum_weak):
        floor = max(floor, p["trend_buy_floor"])

    if conviction < floor:
        return "HOLD", conviction

    return direction, conviction


# ─── Options P&L approximation (fast — avoids importing the full engine) ──────

def approx_options_pnl(direction: str, conviction: float, nifty_pct: float,
                        nifty_close: float, vix: float) -> float:
    """
    Fast approximation of compute_options_pnl without importing the engine.
    Uses the same ATM CE/PE logic: 1 lot (25), entry ~1% of spot, max-loss cap.
    Returns net P&L in INR.
    """
    LOT_SIZE   = 25
    RISK_PCT   = 0.10       # max 10% of capital per trade
    max_risk   = CAPITAL * RISK_PCT

    # ATM option entry (approximation: ~1% of spot + IV premium)
    iv_adj     = max(1.0, vix / 20.0)
    atm_entry  = nifty_close * 0.01 * iv_adj

    # Size: how many lots can we afford given max_risk
    max_loss_per_lot = atm_entry * LOT_SIZE
    lots = max(1, int(max_risk / max_loss_per_lot))

    # Actual point move
    point_move = nifty_pct * nifty_close / 100

    # Conviction scaling (high conviction → trade larger slice of budget)
    conv_scale = min(1.0, conviction / 90.0)

    # P&L per lot
    if direction in ("BUY", "STRONG_BUY"):
        # Long CE: profit if market goes up
        gross = max(-atm_entry, point_move * 0.7) * LOT_SIZE * lots * conv_scale
    else:
        # Long PE: profit if market goes down
        gross = max(-atm_entry, -point_move * 0.7) * LOT_SIZE * lots * conv_scale

    # Costs: slippage + brokerage ~₹200/lot round-trip
    cost = 200 * lots
    return gross - cost


# ─── Evaluate one parameter configuration ─────────────────────────────────────

def evaluate(signals: list[dict], p: dict) -> dict:
    pnl_list   = []
    trades = wins = holds = 0

    for s in signals:
        direction   = s["direction"]
        conviction  = s["conviction"]
        india_vix   = s["india_vix"]
        event_risk  = s["event_risk"]
        context     = s["context"]
        nifty_pct   = s["actual_nifty_pct"]
        nifty_close = s["nifty_close"]

        final_dir, final_conv = apply_gate(direction, conviction, india_vix,
                                           event_risk, context, p)
        if final_dir == "HOLD":
            holds += 1
            continue

        pnl = approx_options_pnl(final_dir, final_conv, nifty_pct, nifty_close, india_vix)
        pnl_list.append(pnl)
        trades += 1

        buy_family = {"BUY", "STRONG_BUY"}
        correct = (nifty_pct > 0.1 and final_dir in buy_family) or \
                  (nifty_pct < -0.1 and final_dir not in buy_family)
        if correct:
            wins += 1

    if not pnl_list:
        return {"total_pnl": 0, "sharpe": -99, "win_rate": 0,
                "trades": 0, "holds": holds, "selectivity": 0}

    total_pnl = sum(pnl_list)
    avg       = total_pnl / len(pnl_list)
    std       = math.sqrt(sum((x - avg) ** 2 for x in pnl_list) / len(pnl_list)) if len(pnl_list) > 1 else 1e-9
    sharpe    = (avg / std) * math.sqrt(252 / max(1, len(signals)))  # annualised
    wr        = wins / trades * 100 if trades else 0
    sel       = trades / len(signals) * 100

    return {
        "total_pnl":   round(total_pnl, 0),
        "sharpe":      round(sharpe, 4),
        "win_rate":    round(wr, 1),
        "trades":      trades,
        "holds":       holds,
        "selectivity": round(sel, 1),
    }


# ─── Parameter grids ──────────────────────────────────────────────────────────

FULL_GRID = {
    "vix_normal_floor":    [60, 62, 65, 67, 70],
    "vix_elevated_floor":  [68, 70, 72, 74, 76],
    "vix_high_floor":      [74, 76, 78, 80, 82],
    "vix_elevated_cutoff": [13.0, 14.0, 15.0],
    "vix_high_cutoff":     [15.0, 16.0, 17.0],
    "vix_block_cutoff":    [19.0, 20.0, 21.0],
    "trend_buy_floor":     [72, 75, 78, 80, 83],
}

QUICK_GRID = {
    "vix_normal_floor":    [62, 65, 68],
    "vix_elevated_floor":  [70, 72, 75],
    "vix_high_floor":      [76, 78, 80],
    "vix_elevated_cutoff": [14.0],
    "vix_high_cutoff":     [16.0],
    "vix_block_cutoff":    [20.0],
    "trend_buy_floor":     [75, 78, 81],
}

# Current production params (baseline comparison)
CURRENT_PARAMS = {
    "vix_normal_floor":    65.0,
    "vix_elevated_floor":  72.0,
    "vix_high_floor":      78.0,
    "vix_elevated_cutoff": 14.0,
    "vix_high_cutoff":     16.0,
    "vix_block_cutoff":    20.0,
    "trend_buy_floor":     78.0,
}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top",   type=int, default=10, help="Show top N configs")
    ap.add_argument("--quick", action="store_true",  help="Use small grid for fast testing")
    ap.add_argument("--file",  default=str(CAPTURE_FILE), help="Path to signals CSV")
    args = ap.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found. Run bt_wfo_capture.py first.")
        sys.exit(1)

    # ── Load signals ──────────────────────────────────────────────────────────
    signals = []
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            signals.append({
                "date":            row["date"],
                "direction":       row["direction"],
                "conviction":      float(row["conviction"]),
                "india_vix":       float(row["india_vix"]),
                "event_risk":      row["event_risk"],
                "context":         row["context"],
                "actual_nifty_pct": float(row["actual_nifty_pct"]),
                "nifty_close":     float(row["nifty_close"]),
                "nifty_next_close": float(row["nifty_next_close"]),
            })

    print(f"\n{'='*90}")
    print(f"  God's Eye — WFO Optimizer  |  {len(signals)} trading days  |  Capital: ₹{CAPITAL:,.0f}")
    print(f"  Signals file: {csv_path}")
    print(f"{'='*90}\n")

    # ── Baseline (current production params) ──────────────────────────────────
    baseline = evaluate(signals, CURRENT_PARAMS)
    print(f"  CURRENT PARAMS baseline:")
    print(f"  P&L=₹{baseline['total_pnl']:,.0f}  Sharpe={baseline['sharpe']:.3f}  "
          f"WR={baseline['win_rate']:.0f}%  Trades={baseline['trades']}  Sel={baseline['selectivity']:.0f}%\n")

    # ── Grid search ───────────────────────────────────────────────────────────
    grid = QUICK_GRID if args.quick else FULL_GRID
    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    total_combos = len(combos)
    print(f"  Grid size: {total_combos:,} combinations  ({'quick' if args.quick else 'full'} grid)")
    print(f"  Running...  (this should take <30s)\n")

    results = []
    for i, values in enumerate(combos):
        p = dict(zip(keys, values))
        # Skip invalid configs (floors must be increasing)
        if not (p["vix_normal_floor"] <= p["vix_elevated_floor"] <= p["vix_high_floor"]):
            continue
        if not (p["vix_elevated_cutoff"] < p["vix_high_cutoff"] < p["vix_block_cutoff"]):
            continue

        metrics = evaluate(signals, p)
        results.append({**p, **metrics})

        if (i + 1) % 500 == 0:
            print(f"  {i+1:,}/{total_combos:,} done...", flush=True)

    # ── Sort by Sharpe, then P&L ───────────────────────────────────────────────
    results.sort(key=lambda x: (x["sharpe"], x["total_pnl"]), reverse=True)

    # ── Print top N ───────────────────────────────────────────────────────────
    top_n = min(args.top, len(results))
    print(f"\n{'='*90}")
    print(f"  TOP {top_n} PARAMETER CONFIGURATIONS  (ranked by Sharpe ratio)")
    print(f"{'='*90}")
    print(f"  {'#':>3}  {'P&L':>10}  {'Sharpe':>7}  {'WR%':>5}  {'Trades':>6}  {'Sel%':>5}  "
          f"  nF   eF   hF    eC   hC   bC   tF")
    print(f"  {'-'*88}")

    for rank, r in enumerate(results[:top_n], 1):
        marker = " ← current" if (
            r["vix_normal_floor"]   == CURRENT_PARAMS["vix_normal_floor"] and
            r["vix_elevated_floor"] == CURRENT_PARAMS["vix_elevated_floor"] and
            r["vix_high_floor"]     == CURRENT_PARAMS["vix_high_floor"] and
            r["trend_buy_floor"]    == CURRENT_PARAMS["trend_buy_floor"]
        ) else ""
        pnl_str = f"₹{r['total_pnl']:,.0f}"
        improvement = r["total_pnl"] - baseline["total_pnl"]
        imp_str = f"(+{improvement:,.0f})" if improvement > 0 else f"({improvement:,.0f})"
        print(
            f"  {rank:>3}  {pnl_str:>10} {imp_str:>10}  {r['sharpe']:>7.3f}  {r['win_rate']:>5.1f}  "
            f"{r['trades']:>6}  {r['selectivity']:>5.1f}  "
            f"  {r['vix_normal_floor']:>3.0f}  {r['vix_elevated_floor']:>3.0f}  {r['vix_high_floor']:>3.0f}"
            f"  {r['vix_elevated_cutoff']:>4.1f}  {r['vix_high_cutoff']:>4.1f}  {r['vix_block_cutoff']:>4.1f}"
            f"  {r['trend_buy_floor']:>3.0f}{marker}"
        )

    # ── Legend ────────────────────────────────────────────────────────────────
    print(f"\n  Legend:")
    print(f"    nF  = vix_normal_floor     (conviction needed when VIX < elevated_cutoff)")
    print(f"    eF  = vix_elevated_floor   (conviction needed when VIX in elevated zone)")
    print(f"    hF  = vix_high_floor       (conviction needed when VIX in high zone)")
    print(f"    eC  = vix_elevated_cutoff  (VIX threshold: normal → elevated regime)")
    print(f"    hC  = vix_high_cutoff      (VIX threshold: elevated → high regime)")
    print(f"    bC  = vix_block_cutoff     (VIX above this: block all trades)")
    print(f"    tF  = trend_buy_floor      (conviction needed for BUY in BEARISH trend)")

    # ── Recommended update ────────────────────────────────────────────────────
    best = results[0]
    print(f"\n{'='*90}")
    print(f"  RECOMMENDED UPDATE to backtest_engine.py:")
    print(f"{'='*90}")
    print(f"    DIRECTIONAL_WEIGHT_THRESHOLD = 0.25  # unchanged")
    print(f"    VIX_NORMAL_FLOOR    = {best['vix_normal_floor']:.1f}")
    print(f"    VIX_ELEVATED_FLOOR  = {best['vix_elevated_floor']:.1f}")
    print(f"    VIX_HIGH_FLOOR      = {best['vix_high_floor']:.1f}")
    print(f"    # VIX regime cutoffs:")
    print(f"    # VIX < {best['vix_elevated_cutoff']:.0f}  → NORMAL   (floor={best['vix_normal_floor']:.0f})")
    print(f"    # VIX {best['vix_elevated_cutoff']:.0f}-{best['vix_high_cutoff']:.0f} → ELEVATED (floor={best['vix_elevated_floor']:.0f})")
    print(f"    # VIX {best['vix_high_cutoff']:.0f}-{best['vix_block_cutoff']:.0f} → HIGH     (floor={best['vix_high_floor']:.0f})")
    print(f"    # VIX > {best['vix_block_cutoff']:.0f} → BLOCKED")
    print(f"    # trend_buy_floor = {best['trend_buy_floor']:.0f}  (BUY conviction floor in BEARISH regime)")
    print(f"\n  Expected improvement over current: ₹{best['total_pnl'] - baseline['total_pnl']:+,.0f}  "
          f"Sharpe: {baseline['sharpe']:.3f} → {best['sharpe']:.3f}")
    print(f"{'='*90}\n")

    # ── Save all results to CSV ───────────────────────────────────────────────
    with open(RESULTS_FILE, "w", newline="") as f:
        fieldnames = keys + ["total_pnl", "sharpe", "win_rate", "trades", "holds", "selectivity"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r[k] for k in fieldnames})
    print(f"  Full results saved: {RESULTS_FILE}  ({len(results):,} configs)")


if __name__ == "__main__":
    main()
