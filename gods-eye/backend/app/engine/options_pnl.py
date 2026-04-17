"""Options P&L engine for ₹20,000 capital positional trades.

Converts NIFTY/stock point moves into actual ₹ P&L accounting for:
- Lot sizes (instrument-specific)
- ATM premium estimation (VIX-based Black-Scholes approximation)
- Delta scaling (near-ATM ≈ 0.45)
- 25% premium stop-loss (was 40%, tightened for better risk control)
- Round-trip brokerage (₹80 flat — Dhan/Zerodha)
- Expiry selection: always weekly (5 DTE) for close-to-close 1-day hold strategy
"""

import math
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Lot sizes (NSE-defined, as of FY2024-25)
# ---------------------------------------------------------------------------

NIFTY_LOT_SIZE = 25
BANKNIFTY_LOT_SIZE = 15
FINNIFTY_LOT_SIZE = 40

# Top 25 NIFTY50 stocks by options open interest (liquid names only)
STOCK_LOT_SIZES: dict = {
    "RELIANCE":    250,
    "TCS":         150,
    "HDFCBANK":    550,
    "INFY":        300,
    "ICICIBANK":   700,
    "SBIN":       1500,
    "AXISBANK":    625,
    "BAJFINANCE":  125,
    "HINDUNILVR":  300,
    "WIPRO":      1500,
    "LT":          150,
    "MARUTI":      100,
    "TATAMOTORS": 1425,
    "NTPC":       3000,
    "POWERGRID":  2700,
    "BHARTIARTL":  950,
    "ASIANPAINT":  200,
    "ULTRACEMCO":  100,
    "SUNPHARMA":   350,
    "KOTAKBANK":   400,
    "TITAN":       375,
    "TECHM":       600,
    "ONGC":       2975,
    "COALINDIA":  2700,
    "NESTLEIND":    40,
}

INDEX_LOT_SIZES: dict = {
    "NIFTY": NIFTY_LOT_SIZE,
    "BANKNIFTY": BANKNIFTY_LOT_SIZE,
    "FINNIFTY": FINNIFTY_LOT_SIZE,
}

# ₹ flat brokerage per complete round trip (entry + exit)
BROKERAGE_ROUND_TRIP = 80.0

# ATM option delta approximation (near-ATM call or put)
# TRD-M10: Fixed delta ignores gamma — in reality, delta changes with the
# underlying price (gamma effect). For ATM weekly options near expiry (DTE=5),
# gamma is very high (~0.003-0.005 per point), meaning delta can shift from
# 0.45 to 0.60+ on a 50-pt move. This underestimates P&L on large correct
# calls and overestimates it on wrong ones. A proper model would use
# Black-Scholes delta recalculated at exit price and DTE-1.
ATM_DELTA = 0.45

# 25% premium stop-loss threshold (exit when option loses 25% of entry premium)
# Previously 40% — was too loose, triggered only at ~308 NIFTY pts adverse move
# (delta=0.45, DTE=20). 25% triggers at ~193 pts, catching moves like Apr 10
# 2024 (-234 pts Iran-Israel selloff).
STOP_LOSS_PCT = 0.25

# Conviction thresholds for expiry selection
WEEKLY_CONVICTION_THRESHOLD = 75.0   # ≥ 75 → weekly (high-conviction, max leverage)
WEEKLY_DTE = 5                        # ~1 trading week
MONTHLY_DTE = 20                      # ~1 trading month


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class OptionsTrade:
    """Full P&L breakdown for a single options trade."""

    date: str
    instrument: str           # "NIFTY", "RELIANCE", etc.
    option_type: str          # "CE" or "PE"
    dte: int                  # days to expiry at entry
    lot_size: int
    lots: int
    entry_premium: float      # ₹/unit at entry
    exit_premium: float       # ₹/unit at exit (may be stop-loss price)
    stop_price: float         # 25% stop-loss level (entry × 0.75)
    stop_triggered: bool      # True if exit was at stop price, not target

    entry_cost: float         # lots × lot_size × entry_premium
    exit_value: float         # lots × lot_size × exit_premium
    gross_pnl: float          # exit_value − entry_cost
    brokerage: float          # BROKERAGE_ROUND_TRIP
    net_pnl: float            # gross_pnl − brokerage
    return_pct: float         # net_pnl / capital × 100


@dataclass
class BacktestOptionsMetrics:
    """Monthly and cumulative options metrics for a backtest run."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float

    total_net_pnl_inr: float       # total ₹ P&L after brokerage
    avg_win_inr: float
    avg_loss_inr: float
    largest_win_inr: float
    largest_loss_inr: float

    monthly_return_pct: float      # total_net_pnl_inr / capital × 100 (per month)
    max_drawdown_pct: float        # peak-to-trough on cumulative ₹ P&L / capital
    profit_factor: float           # gross_wins / gross_losses


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def lot_size_for(instrument: str) -> int:
    """Return NSE lot size for the given instrument."""
    key = instrument.upper()
    if key in INDEX_LOT_SIZES:
        return INDEX_LOT_SIZES[key]
    if key in STOCK_LOT_SIZES:
        return STOCK_LOT_SIZES[key]
    # Unknown instrument — use a conservative default
    return 500


def estimate_atm_premium(spot: float, vix: float, dte: int) -> float:
    """Estimate ATM option premium using Black-Scholes approximation.

    Formula: premium ≈ spot × σ × √(T) × 0.4
    where σ = VIX/100 (annualised), T = dte/252.

    The 0.4 factor approximates N(d1)−N(d2) for an ATM option.
    This is a proxy — actual market premiums vary with skew and supply/demand.

    Args:
        spot: underlying index/stock spot price
        vix: India VIX (annualised vol in %)
        dte: days to expiry

    Returns:
        Estimated premium per unit in ₹
    """
    if vix <= 0 or dte <= 0 or spot <= 0:
        return 50.0  # fallback
    sigma = vix / 100.0
    t = dte / 252.0
    premium = spot * sigma * math.sqrt(t) * 0.4
    return max(10.0, round(premium, 1))


def select_dte(conviction: float) -> int:
    """Select DTE for close-to-close 1-day hold strategy.

    Always weekly (5 DTE) — monthly options cost ~₹320/unit (₹8,025/lot) which
    exceeds the 30% risk budget on ₹20K capital. Weekly options at ~₹160/unit
    (₹4,000/lot) fit the budget and have better gamma for overnight holds.
    MONTHLY_DTE kept for reference / future multi-day strategies.
    """
    return WEEKLY_DTE


def max_affordable_lots(
    entry_premium: float,
    lot_size: int,
    capital: float = 20_000.0,
    max_risk_pct: float = 0.10,
    stop_loss_pct: float = STOP_LOSS_PCT,
    brokerage: float = BROKERAGE_ROUND_TRIP,
) -> int:
    """Calculate how many lots can be bought without exceeding max_risk_pct loss.

    Two constraints must both be satisfied:
    1. Risk = lots × lot_size × entry_premium × stop_loss_pct + brokerage ≤ max_risk_pct × capital
    2. Entry cost = lots × lot_size × entry_premium ≤ capital  (can't spend more than you have)

    Args:
        entry_premium: ATM premium per unit in ₹
        lot_size: NSE lot size for the instrument
        capital: available trading capital in ₹ (default ₹20,000)
        max_risk_pct: maximum fraction of capital to risk per trade (default 10%)
        stop_loss_pct: stop-loss fraction of entry premium (default 25%)
        brokerage: round-trip brokerage cost in ₹ (default ₹80)

    Returns:
        Number of lots (≥ 0; 0 means trade is unaffordable even at 1 lot)
    """
    if entry_premium <= 0 or lot_size <= 0:
        return 0

    max_loss_budget = capital * max_risk_pct

    # Find max lots where both constraints are satisfied
    lots = 0
    while True:
        candidate = lots + 1
        max_loss = (candidate * lot_size * entry_premium * stop_loss_pct) + brokerage
        entry_cost = candidate * lot_size * entry_premium
        # Constraint 1: risk must be within budget
        # Constraint 2: total entry cost must not exceed available capital
        if max_loss > max_loss_budget or entry_cost > capital:
            break
        lots = candidate
        if lots >= 20:  # safety cap — never more than 20 lots
            break

    return lots


# ---------------------------------------------------------------------------
# Main P&L computation
# ---------------------------------------------------------------------------

def compute_options_pnl(
    date: str,
    direction: str,          # "BUY"/"STRONG_BUY" → CE; "SELL"/"STRONG_SELL" → PE
    nifty_point_move: float, # actual underlying move (+ = up, - = down)
    instrument: str = "NIFTY",
    spot: float = 22_000.0,
    vix: float = 15.0,
    conviction: float = 72.0,
    capital: float = 20_000.0,
) -> Optional[OptionsTrade]:
    """Compute options trade P&L for a given directional signal.

    For BUY/STRONG_BUY: buys a CE (profits when market rises).
    For SELL/STRONG_SELL: buys a PE (profits when market falls).
    HOLD: returns None (no trade).

    Stop-loss: 25% of entry premium (entry × 0.75).
    Exit premium: entry + (delta × underlying_move), floored at stop price.

    Args:
        date: signal date (YYYY-MM-DD)
        direction: agent consensus direction
        nifty_point_move: actual T+1 point change
        instrument: "NIFTY" or stock name
        spot: underlying spot price at signal time
        vix: India VIX at signal time
        conviction: consensus conviction (0–100)
        capital: available capital in ₹

    Returns:
        OptionsTrade with full P&L, or None for HOLD signals.
    """
    if direction not in {"BUY", "STRONG_BUY", "SELL", "STRONG_SELL"}:
        return None  # HOLD — no trade

    option_type = "CE" if direction in {"BUY", "STRONG_BUY"} else "PE"
    lot_size = lot_size_for(instrument)
    dte = select_dte(conviction)
    entry_premium = estimate_atm_premium(spot, vix, dte)
    lots = max_affordable_lots(entry_premium, lot_size, capital)

    if lots == 0:
        # Can't afford even 1 lot — skip trade
        return None

    # Stop-loss level (25% below entry)
    stop_price = entry_premium * (1.0 - STOP_LOSS_PCT)

    # Option price movement: CE profits when market rises, PE when it falls
    if option_type == "CE":
        raw_exit = entry_premium + (ATM_DELTA * nifty_point_move)
    else:
        raw_exit = entry_premium + (ATM_DELTA * -nifty_point_move)

    # Apply stop-loss floor (can't exit below stop price)
    exit_premium = max(stop_price, raw_exit)
    exit_premium = max(0.05, exit_premium)  # option can't go below near-zero
    stop_triggered = raw_exit < stop_price

    entry_cost = lots * lot_size * entry_premium
    exit_value = lots * lot_size * exit_premium
    gross_pnl = exit_value - entry_cost
    net_pnl = gross_pnl - BROKERAGE_ROUND_TRIP
    return_pct = (net_pnl / capital) * 100.0

    return OptionsTrade(
        date=date,
        instrument=instrument,
        option_type=option_type,
        dte=dte,
        lot_size=lot_size,
        lots=lots,
        entry_premium=round(entry_premium, 2),
        exit_premium=round(exit_premium, 2),
        stop_price=round(stop_price, 2),
        stop_triggered=stop_triggered,
        entry_cost=round(entry_cost, 2),
        exit_value=round(exit_value, 2),
        gross_pnl=round(gross_pnl, 2),
        brokerage=BROKERAGE_ROUND_TRIP,
        net_pnl=round(net_pnl, 2),
        return_pct=round(return_pct, 2),
    )


def compute_iv_rank(vix_series: list, current_vix: float) -> float:
    """Compute IV rank: where current VIX sits in its 52-week range.

    IV rank = (current − 52w_low) / (52w_high − 52w_low) × 100

    < 30  → IV cheap → good time to BUY premium
    > 70  → IV expensive → avoid buying, wait for IV crush
    30–70 → neutral

    Args:
        vix_series: list of historical VIX closes (up to 252 entries)
        current_vix: today's VIX

    Returns:
        IV rank 0–100
    """
    if not vix_series:
        return 50.0
    window = vix_series[-252:]
    low_52w = min(window)
    high_52w = max(window)
    if high_52w == low_52w:
        return 50.0
    rank = (current_vix - low_52w) / (high_52w - low_52w) * 100.0
    return round(max(0.0, min(100.0, rank)), 1)
