"""PaperTrader — full trade execution engine for automated paper trading.

Converts simulation signals (BUY/SELL/HOLD) into tracked paper trades with:
- Entry price (NIFTY spot at signal time)
- ATM option premium (CE for BUY, PE for SELL)
- Position sizing (conviction-based lots via options_pnl)
- Stop-loss and target levels
- Intraday monitoring for stop/target hits (next trading day)
- T+1 close settlement (matches backtest close-to-close structure)
- Daily loss guard integration

Uses SQLite for persistence. All P&L in ₹ (INR).
Capital: ₹20,000 (matches backtest configuration).
"""

import sqlite3
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta, time, date as _date_type
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

from app.config import config
from app.engine.options_pnl import (
    compute_options_pnl,
    estimate_atm_premium,
    max_affordable_lots,
    lot_size_for,
    STOP_LOSS_PCT,
    BROKERAGE_ROUND_TRIP,
    ATM_DELTA,
)
from app.engine.risk_manager import RiskManager
from app.engine.stop_loss_engine import StopLossEngine
from app.data.historical_store import historical_store
logger = logging.getLogger("gods_eye.paper_trader")

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

# Paper trading capital (matches backtest)
PAPER_CAPITAL = 20_000.0

# Daily max loss in ₹ — stop trading for the day after this
DAILY_MAX_LOSS_INR = 4_000.0  # 20% of capital

# Conviction floor — don't trade below this (matches config.CONVICTION_FLOOR)
MIN_CONVICTION = 55.0

# VIX gate — don't trade when VIX ≥ 30 (matches backtest VIX regime gate)
VIX_HOLD_THRESHOLD = 30.0


@dataclass
class PaperTrade:
    """A single paper trade record."""
    trade_id: str
    simulation_id: str
    prediction_id: str
    timestamp: str          # ISO format, when trade was opened
    date_ist: str           # YYYY-MM-DD in IST

    # Signal info
    direction: str          # BUY or SELL
    conviction: float       # 0-100
    # Instrument
    instrument: str         # NIFTY
    option_type: str        # CE or PE
    lot_size: int
    lots: int
    dte: int                # days to expiry

    # Prices
    entry_spot: float       # NIFTY spot at entry
    entry_premium: float    # option premium at entry (₹/unit)
    stop_price: float       # stop-loss premium level
    target_price: float     # target premium level
    stop_nifty: float       # NIFTY level where stop triggers
    target_nifty: float     # NIFTY level where target triggers

    # Entry cost
    entry_cost: float       # lots × lot_size × entry_premium

    # Exit (filled when trade closes)
    status: str             # OPEN, STOPPED, TARGET_HIT, CLOSED_EOD, CANCELLED
    exit_premium: Optional[float] = None
    exit_spot: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_reason: Optional[str] = None

    # P&L (filled when trade closes)
    exit_value: Optional[float] = None
    gross_pnl: Optional[float] = None
    brokerage: float = BROKERAGE_ROUND_TRIP
    net_pnl: Optional[float] = None
    return_pct: Optional[float] = None

class PaperTrader:
    """Manages paper trade lifecycle: open → monitor → close."""

    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        self._daily_pnl: float = 0.0
        self._daily_date: Optional[_date_type] = None
        self._init_db()

    def _init_db(self):
        """Create paper_trades table if not exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades (
                trade_id TEXT PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                prediction_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                date_ist TEXT NOT NULL,

                direction TEXT NOT NULL,
                conviction REAL NOT NULL,

                instrument TEXT NOT NULL,
                option_type TEXT NOT NULL,
                lot_size INTEGER NOT NULL,
                lots INTEGER NOT NULL,
                dte INTEGER NOT NULL,
                entry_spot REAL NOT NULL,
                entry_premium REAL NOT NULL,
                stop_price REAL NOT NULL,
                target_price REAL NOT NULL,
                stop_nifty REAL NOT NULL,
                target_nifty REAL NOT NULL,
                entry_cost REAL NOT NULL,

                status TEXT NOT NULL DEFAULT 'OPEN',
                exit_premium REAL,
                exit_spot REAL,
                exit_timestamp TEXT,
                exit_reason TEXT,

                exit_value REAL,
                gross_pnl REAL,
                brokerage REAL DEFAULT 80.0,
                net_pnl REAL,
                return_pct REAL
            )
        """)

        # Index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_paper_trades_date
            ON paper_trades(date_ist)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_paper_trades_status
            ON paper_trades(status)
        """)
        conn.commit()
        conn.close()
        logger.info("PaperTrader: DB initialized")

    # ── Daily Loss Guard ─────────────────────────────────────────────────

    def _reset_daily_if_needed(self):
        """Reset daily P&L tracker on new IST day."""
        today = datetime.now(IST).date()
        if self._daily_date != today:
            self._daily_pnl = 0.0
            self._daily_date = today
            # Also load today's realized P&L from DB
            self._daily_pnl = self._get_today_realized_pnl()

    def _get_today_realized_pnl(self) -> float:
        """Sum of net_pnl for today's closed trades."""
        today = datetime.now(IST).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(net_pnl), 0.0)
            FROM paper_trades
            WHERE date_ist = ? AND status != 'OPEN'
        """, (today,))
        result = cursor.fetchone()[0]
        conn.close()
        return result
    def is_daily_limit_hit(self) -> bool:
        """Check if daily loss limit has been reached."""
        self._reset_daily_if_needed()
        return self._daily_pnl <= -DAILY_MAX_LOSS_INR

    # ── Open Trade ───────────────────────────────────────────────────────

    def open_trade(
        self,
        simulation_id: str,
        prediction_id: str,
        direction: str,
        conviction: float,
        nifty_spot: float,
        vix: float,
        instrument: str = "NIFTY",
        gap_estimate=None,
    ) -> Optional[PaperTrade]:
        """Open a new paper trade from a simulation signal.

        Returns PaperTrade if trade was opened, None if skipped.
        Reasons for skip: HOLD signal, low conviction, daily loss limit,
        can't afford, gap risk too high.

        Args:
            gap_estimate: Optional GapEstimate from gap_risk module.
                          If provided, applies conservative position sizing
                          and stop-loss adjustments based on gap risk tier.
        """
        # Skip HOLD signals
        if direction not in ("BUY", "SELL", "STRONG_BUY", "STRONG_SELL"):
            logger.info("PaperTrader: skipping %s signal (no trade)", direction)
            return None

        # ── Gap Risk Gate (conservative) ─────────────────────────────────
        # DANGER (>2% gap): skip entirely
        # WARNING (1-2%): halve position
        # CAUTION (0.5-1%): widen stops
        position_multiplier = 1.0
        stop_buffer_pct = 0.0
        gap_tier = "NORMAL"

        if gap_estimate is not None:
            gap_tier = getattr(gap_estimate, "risk_tier", "NORMAL")
            position_multiplier = getattr(gap_estimate, "position_multiplier", 1.0)
            stop_buffer_pct = getattr(gap_estimate, "stop_buffer_pct", 0.0)
            gap_pct = getattr(gap_estimate, "estimated_gap_pct", 0.0)

            if gap_tier == "DANGER":
                logger.warning(
                    "PaperTrader: GAP DANGER (%.2f%%) — blocking trade entirely",
                    gap_pct,
                )
                return None

            if gap_tier in ("WARNING", "CAUTION"):
                logger.info(
                    "PaperTrader: GAP %s (%.2f%%) — position_mult=%.2f, stop_buffer=%.1f%%",
                    gap_tier, gap_pct, position_multiplier, stop_buffer_pct,
                )

        # Check conviction floor
        effective_conviction = conviction
        if effective_conviction < MIN_CONVICTION:
            logger.info("PaperTrader: conviction %.1f < %.1f floor, skip", conviction, MIN_CONVICTION)
            return None

        # Check daily loss limit
        if self.is_daily_limit_hit():
            logger.warning("PaperTrader: daily loss limit hit (₹%.0f), blocking trade", self._daily_pnl)
            return None

        # Check if we already have an open trade today
        today = datetime.now(IST).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM paper_trades
            WHERE date_ist = ? AND status = 'OPEN'
        """, (today,))
        open_count = cursor.fetchone()[0]
        conn.close()

        if open_count > 0:
            logger.info("PaperTrader: already have %d open trade(s) today, skip", open_count)
            return None

        # Compute option trade parameters
        option_type = "CE" if direction in ("BUY", "STRONG_BUY") else "PE"
        lot_size = lot_size_for(instrument)
        dte = 5  # Weekly options (matches backtest)
        entry_premium = estimate_atm_premium(nifty_spot, vix, dte)
        # Apply gap-adjusted capital (position_multiplier from gap risk)
        effective_capital = PAPER_CAPITAL * position_multiplier
        lots = max_affordable_lots(entry_premium, lot_size, effective_capital)
        if lots == 0:
            logger.warning(
                "PaperTrader: can't afford 1 lot (premium=%.1f, lot=%d, eff_capital=%.0f%s)",
                entry_premium, lot_size, effective_capital,
                f" [gap {gap_tier} reduced from ₹{PAPER_CAPITAL:.0f}]" if position_multiplier < 1.0 else "",
            )
            return None

        # Stop and target on premium — widen stop by gap buffer
        effective_stop_pct = STOP_LOSS_PCT + (stop_buffer_pct / 100.0)
        stop_price = round(entry_premium * (1.0 - effective_stop_pct), 2)

        # Target: 1.5x risk-reward on premium
        risk_per_unit = entry_premium - stop_price
        target_price = round(entry_premium + (risk_per_unit * 1.5), 2)

        # Corresponding NIFTY levels (for monitoring against spot price)
        # CE: entry_premium + delta * (nifty_move) = exit_premium
        # So nifty_move = (exit_premium - entry_premium) / delta
        stop_move = (stop_price - entry_premium) / ATM_DELTA  # negative for loss
        target_move = (target_price - entry_premium) / ATM_DELTA  # positive for profit

        if option_type == "CE":
            stop_nifty = round(nifty_spot + stop_move, 2)
            target_nifty = round(nifty_spot + target_move, 2)
        else:  # PE profits when market falls
            stop_nifty = round(nifty_spot - stop_move, 2)   # stop is ABOVE for PE
            target_nifty = round(nifty_spot - target_move, 2)  # target is BELOW for PE

        entry_cost = round(lots * lot_size * entry_premium, 2)
        trade = PaperTrade(
            trade_id=f"pt_{uuid.uuid4().hex[:8]}",
            simulation_id=simulation_id,
            prediction_id=prediction_id,
            timestamp=datetime.now(IST).isoformat(),
            date_ist=today,
            direction=direction,
            conviction=conviction,
            instrument=instrument,
            option_type=option_type,
            lot_size=lot_size,
            lots=lots,
            dte=dte,
            entry_spot=nifty_spot,
            entry_premium=entry_premium,
            stop_price=stop_price,
            target_price=target_price,
            stop_nifty=stop_nifty,
            target_nifty=target_nifty,
            entry_cost=entry_cost,
            status="OPEN",
        )

        # Save to DB
        self._save_trade(trade)

        logger.info(
            "PaperTrader: OPENED %s %s %s×%d @ ₹%.1f (spot=%.0f, stop=%.0f, target=%.0f, cost=₹%.0f)",
            trade.trade_id, direction, option_type, lots,
            entry_premium, nifty_spot, stop_nifty, target_nifty, entry_cost,
        )
        return trade

    # ── Monitor / Check Stops & Targets ──────────────────────────────────

    def check_open_trades(self, current_spot: float) -> List[PaperTrade]:
        """Check all open trades against current NIFTY spot for stop/target hits.

        Returns list of trades that were closed.
        """
        open_trades = self.get_open_trades()
        closed = []

        for trade in open_trades:
            hit = self._check_stop_target(trade, current_spot)
            if hit:
                closed.append(hit)

        return closed

    def _check_stop_target(self, trade: PaperTrade, current_spot: float) -> Optional[PaperTrade]:
        """Check if a trade's stop or target has been hit."""
        if trade.option_type == "CE":
            # CE: stop if spot drops below stop_nifty, target if above target_nifty
            if current_spot <= trade.stop_nifty:
                return self._close_trade(trade, current_spot, trade.stop_price, "STOPPED")
            elif current_spot >= trade.target_nifty:
                return self._close_trade(trade, current_spot, trade.target_price, "TARGET_HIT")
        else:
            # PE: stop if spot rises above stop_nifty, target if below target_nifty
            if current_spot >= trade.stop_nifty:
                return self._close_trade(trade, current_spot, trade.stop_price, "STOPPED")
            elif current_spot <= trade.target_nifty:
                return self._close_trade(trade, current_spot, trade.target_price, "TARGET_HIT")

        return None

    # ── Close Trade ──────────────────────────────────────────────────────

    def close_all_eod(self, closing_spot: float, closing_vix: float = 15.0) -> List[PaperTrade]:
        """Close open trades from PREVIOUS days at end of day (15:25 IST).

        Matches backtest close-to-close structure:
        - Signal at T → entry at T's close → exit at T+1's close.
        - Trades opened TODAY survive overnight; only trades opened
          before today are settled at this EOD.

        Uses current spot to estimate exit premium via delta scaling.
        """
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        open_trades = self.get_open_trades()
        closed = []

        for trade in open_trades:
            # Skip trades opened today — they exit TOMORROW's close
            if trade.date_ist >= today_str:
                logger.info(
                    "EOD: skipping trade %s (opened today %s, exits tomorrow)",
                    trade.trade_id, trade.date_ist,
                )
                continue
            # Estimate current premium from spot move
            spot_move = closing_spot - trade.entry_spot
            if trade.option_type == "CE":
                raw_exit = trade.entry_premium + (ATM_DELTA * spot_move)
            else:
                raw_exit = trade.entry_premium + (ATM_DELTA * -spot_move)

            # Floor at near-zero (can't go negative)
            exit_premium = max(0.05, round(raw_exit, 2))

            result = self._close_trade(trade, closing_spot, exit_premium, "CLOSED_EOD")
            if result:
                closed.append(result)

        return closed
    def _close_trade(
        self,
        trade: PaperTrade,
        exit_spot: float,
        exit_premium: float,
        reason: str,
    ) -> PaperTrade:
        """Close a trade and compute P&L."""
        exit_value = round(trade.lots * trade.lot_size * exit_premium, 2)
        gross_pnl = round(exit_value - trade.entry_cost, 2)
        net_pnl = round(gross_pnl - BROKERAGE_ROUND_TRIP, 2)
        return_pct = round((net_pnl / PAPER_CAPITAL) * 100.0, 2)

        trade.status = reason
        trade.exit_spot = exit_spot
        trade.exit_premium = exit_premium
        trade.exit_timestamp = datetime.now(IST).isoformat()
        trade.exit_reason = reason
        trade.exit_value = exit_value
        trade.gross_pnl = gross_pnl
        trade.net_pnl = net_pnl
        trade.return_pct = return_pct

        self._update_trade(trade)

        # Update daily P&L tracker
        self._reset_daily_if_needed()
        self._daily_pnl += net_pnl
        pnl_emoji = "✅" if net_pnl >= 0 else "❌"
        logger.info(
            "PaperTrader: %s CLOSED %s %s → ₹%.0f net P&L (%.1f%%) [%s]",
            pnl_emoji, trade.trade_id, reason, net_pnl, return_pct, trade.direction,
        )

        return trade

    # ── Database Operations ──────────────────────────────────────────────

    def _save_trade(self, trade: PaperTrade):
        """Insert a new trade into the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO paper_trades (
                trade_id, simulation_id, prediction_id, timestamp, date_ist,
                direction, conviction, instrument, option_type, lot_size, lots, dte,
                entry_spot, entry_premium, stop_price, target_price,
                stop_nifty, target_nifty, entry_cost,
                status, brokerage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.trade_id, trade.simulation_id, trade.prediction_id,
            trade.timestamp, trade.date_ist,
            trade.direction, trade.conviction,
            trade.instrument, trade.option_type, trade.lot_size, trade.lots, trade.dte,
            trade.entry_spot, trade.entry_premium, trade.stop_price, trade.target_price,
            trade.stop_nifty, trade.target_nifty, trade.entry_cost,
            trade.status, trade.brokerage,
        ))
        conn.commit()
        conn.close()

    def _update_trade(self, trade: PaperTrade):
        """Update an existing trade (close it)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE paper_trades SET
                status = ?,
                exit_premium = ?,
                exit_spot = ?,
                exit_timestamp = ?,
                exit_reason = ?,
                exit_value = ?,
                gross_pnl = ?,
                net_pnl = ?,
                return_pct = ?
            WHERE trade_id = ?
        """, (
            trade.status, trade.exit_premium, trade.exit_spot,
            trade.exit_timestamp, trade.exit_reason,
            trade.exit_value, trade.gross_pnl, trade.net_pnl, trade.return_pct,
            trade.trade_id,
        ))
        conn.commit()
        conn.close()

    # ── Query Methods ────────────────────────────────────────────────────
    def get_open_trades(self) -> List[PaperTrade]:
        """Get all currently open trades."""
        return self._query_trades("status = 'OPEN'")

    def get_today_trades(self) -> List[PaperTrade]:
        """Get all trades for today (IST)."""
        today = datetime.now(IST).strftime("%Y-%m-%d")
        return self._query_trades("date_ist = ?", (today,))

    def get_trade_history(self, limit: int = 50, offset: int = 0) -> List[PaperTrade]:
        """Get recent trade history."""
        return self._query_trades("1=1", (), limit=limit, offset=offset)

    def get_trade_by_id(self, trade_id: str) -> Optional[PaperTrade]:
        """Get a specific trade by ID."""
        trades = self._query_trades("trade_id = ?", (trade_id,), limit=1)
        return trades[0] if trades else None

    def _query_trades(
        self, where: str, params: tuple = (), limit: int = 100, offset: int = 0
    ) -> List[PaperTrade]:
        """Generic trade query."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT * FROM paper_trades
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (*params, limit, offset))
        rows = cursor.fetchall()
        conn.close()

        trades = []
        for row in rows:
            trades.append(PaperTrade(
                trade_id=row["trade_id"],
                simulation_id=row["simulation_id"],
                prediction_id=row["prediction_id"],
                timestamp=row["timestamp"],
                date_ist=row["date_ist"],
                direction=row["direction"],
                conviction=row["conviction"],
                instrument=row["instrument"],
                option_type=row["option_type"],
                lot_size=row["lot_size"],
                lots=row["lots"],
                dte=row["dte"],
                entry_spot=row["entry_spot"],
                entry_premium=row["entry_premium"],
                stop_price=row["stop_price"],
                target_price=row["target_price"],
                stop_nifty=row["stop_nifty"],
                target_nifty=row["target_nifty"],
                entry_cost=row["entry_cost"],
                status=row["status"],
                exit_premium=row["exit_premium"],
                exit_spot=row["exit_spot"],
                exit_timestamp=row["exit_timestamp"],
                exit_reason=row["exit_reason"],                exit_value=row["exit_value"],
                gross_pnl=row["gross_pnl"],
                brokerage=row["brokerage"],
                net_pnl=row["net_pnl"],
                return_pct=row["return_pct"],
            ))

        return trades

    # ── P&L Summary ──────────────────────────────────────────────────────

    def get_pnl_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get P&L summary for the last N days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.now(IST) - timedelta(days=days)).strftime("%Y-%m-%d")

        # Overall stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN net_pnl <= 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(net_pnl), 0) as total_pnl,
                COALESCE(AVG(CASE WHEN net_pnl > 0 THEN net_pnl END), 0) as avg_win,
                COALESCE(AVG(CASE WHEN net_pnl <= 0 THEN net_pnl END), 0) as avg_loss,
                COALESCE(MAX(net_pnl), 0) as largest_win,
                COALESCE(MIN(net_pnl), 0) as largest_loss,
                SUM(CASE WHEN status = 'STOPPED' THEN 1 ELSE 0 END) as stopped_count,
                SUM(CASE WHEN status = 'TARGET_HIT' THEN 1 ELSE 0 END) as target_count,
                SUM(CASE WHEN status = 'CLOSED_EOD' THEN 1 ELSE 0 END) as eod_count
            FROM paper_trades
            WHERE date_ist >= ? AND status != 'OPEN'
        """, (cutoff,))
        row = cursor.fetchone()

        total = row[0] or 0
        wins = row[1] or 0
        losses = row[2] or 0
        total_pnl = row[3] or 0.0
        avg_win = row[4] or 0.0
        avg_loss = row[5] or 0.0
        largest_win = row[6] or 0.0
        largest_loss = row[7] or 0.0
        stopped = row[8] or 0
        targets = row[9] or 0
        eod = row[10] or 0

        win_rate = (wins / total * 100) if total > 0 else 0

        # Daily P&L breakdown
        cursor.execute("""
            SELECT
                date_ist,
                COUNT(*) as trades,
                SUM(net_pnl) as day_pnl,
                SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) as day_wins
            FROM paper_trades            WHERE date_ist >= ? AND status != 'OPEN'
            GROUP BY date_ist
            ORDER BY date_ist DESC
        """, (cutoff,))
        daily_rows = cursor.fetchall()

        daily_pnl = []
        cumulative = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for drow in reversed(daily_rows):
            cumulative += drow[2]
            peak = max(peak, cumulative)
            drawdown = peak - cumulative
            max_drawdown = max(max_drawdown, drawdown)
            daily_pnl.append({
                "date": drow[0],
                "trades": drow[1],
                "pnl": round(drow[2], 2),
                "wins": drow[3],
                "cumulative": round(cumulative, 2),
            })

        # Open trades
        cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'OPEN'")
        open_count = cursor.fetchone()[0]

        conn.close()
        return {
            "period_days": days,
            "capital": PAPER_CAPITAL,
            "total_trades": total,
            "open_trades": open_count,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 1),
            "total_pnl_inr": round(total_pnl, 2),
            "total_return_pct": round((total_pnl / PAPER_CAPITAL) * 100, 2),
            "avg_win_inr": round(avg_win, 2),
            "avg_loss_inr": round(avg_loss, 2),
            "largest_win_inr": round(largest_win, 2),
            "largest_loss_inr": round(largest_loss, 2),
            "max_drawdown_inr": round(max_drawdown, 2),
            "max_drawdown_pct": round((max_drawdown / PAPER_CAPITAL) * 100, 2),
            "stopped_count": stopped,
            "target_hit_count": targets,
            "eod_close_count": eod,
            "profit_factor": round(abs(avg_win * wins) / abs(avg_loss * losses), 2) if losses > 0 and avg_loss != 0 else 0.0,
            "daily_pnl": list(reversed(daily_pnl)),
        }


# Module-level singleton
paper_trader = PaperTrader()