"""LiveTrader — real order execution engine via Dhan API.

Mirrors PaperTrader structure but places REAL orders through Dhan's order API.
Same risk guards (daily loss limit, conviction floor, VIX filter, gap risk)
plus additional safety: DHAN_ORDERS_ENABLED env gate, order status tracking.

Uses SQLite `live_trades` table (separate from `paper_trades`).
All P&L in INR.

Capital: configurable via GODS_EYE_LIVE_CAPITAL (default 50,000).
Daily max loss: configurable via GODS_EYE_LIVE_MAX_LOSS (default 10,000 = 20%).

IMPORTANT: Dhan requires Static IP whitelisting for order APIs.
"""

import asyncio
import sqlite3
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta, date as _date_type
from dataclasses import dataclass
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
from app.data.dhan_client import dhan_client, NIFTY_50_SECURITY_ID

logger = logging.getLogger("gods_eye.live_trader")

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

# Configurable capital and risk limits
LIVE_CAPITAL = float(os.getenv("GODS_EYE_LIVE_CAPITAL", "50000"))
DAILY_MAX_LOSS_INR = float(os.getenv("GODS_EYE_LIVE_MAX_LOSS", "10000"))

# Conviction floor — don't trade below this
MIN_CONVICTION = 55.0

# VIX gate — block trades at extreme VIX
VIX_HOLD_THRESHOLD = 30.0


@dataclass
class LiveTrade:
    """A single live trade record with Dhan order tracking."""
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
    entry_premium: float    # option premium at entry
    stop_price: float       # stop-loss premium level
    target_price: float     # target premium level
    stop_nifty: float       # NIFTY level where stop triggers
    target_nifty: float     # NIFTY level where target triggers

    # Entry cost
    entry_cost: float       # lots x lot_size x entry_premium

    # Dhan order tracking
    dhan_order_id: Optional[str] = None
    dhan_exit_order_id: Optional[str] = None
    trading_mode: str = "live"
    order_status: str = "PENDING"

    # Security ID for Dhan
    security_id: Optional[str] = None

    # Exit (filled when trade closes)
    status: str = "OPEN"    # OPEN, STOPPED, TARGET_HIT, CLOSED_EOD, CANCELLED, ORDER_FAILED
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


class LiveTrader:
    """Manages live trade lifecycle: open -> monitor -> close via Dhan."""

    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        self._daily_pnl: float = 0.0
        self._daily_date: Optional[_date_type] = None
        self._trade_lock = asyncio.Lock()  # Serialize open_trade to prevent race conditions
        self._init_db()

    def _init_db(self):
        """Create live_trades table if not exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS live_trades (
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

                dhan_order_id TEXT,
                dhan_exit_order_id TEXT,
                trading_mode TEXT NOT NULL DEFAULT 'live',
                order_status TEXT NOT NULL DEFAULT 'PENDING',
                security_id TEXT,

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

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_live_trades_date
            ON live_trades(date_ist)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_live_trades_status
            ON live_trades(status)
        """)
        conn.commit()
        conn.close()
        logger.info("LiveTrader: DB initialized")

    # -- ATM Security ID Lookup -----------------------------------------------

    async def _get_atm_security_id(
        self, nifty_spot: float, option_type: str
    ) -> Optional[str]:
        """Find the ATM strike's Dhan security ID from the option chain.

        Uses dhan_client.get_option_chain() to fetch the chain, then finds
        the strike closest to nifty_spot for the given option_type (CE/PE).
        """
        chain_data = await dhan_client.get_option_chain(NIFTY_50_SECURITY_ID)
        if not chain_data:
            logger.error("LiveTrader: could not fetch option chain for ATM lookup")
            return None

        inner = chain_data.get("data")
        if not isinstance(inner, dict):
            return None

        oc = inner.get("oc")
        if not isinstance(oc, dict) or not oc:
            return None

        # Find closest strike to spot
        best_strike = None
        best_diff = float("inf")
        best_sid = None
        opt_key = "ce" if option_type == "CE" else "pe"

        for strike_str, opts in oc.items():
            if not isinstance(opts, dict):
                continue
            try:
                strike = float(strike_str)
            except (ValueError, TypeError):
                continue

            opt_data = opts.get(opt_key, {})
            if not isinstance(opt_data, dict):
                continue

            sid = opt_data.get("security_id") or opt_data.get("securityId") or opt_data.get("SEM_CUSTOM_SYMBOL")
            diff = abs(strike - nifty_spot)
            if diff < best_diff and sid:
                best_diff = diff
                best_strike = strike
                best_sid = str(sid)

        if best_sid:
            logger.info(
                "LiveTrader: ATM %s strike=%.0f security_id=%s (spot=%.0f)",
                option_type, best_strike, best_sid, nifty_spot,
            )
        else:
            logger.warning("LiveTrader: could not find ATM security_id for %s near %.0f", option_type, nifty_spot)

        return best_sid

    # -- Daily Loss Guard -----------------------------------------------------

    def _reset_daily_if_needed(self):
        """Reset daily P&L tracker on new IST day."""
        today = datetime.now(IST).date()
        if self._daily_date != today:
            self._daily_pnl = 0.0
            self._daily_date = today
            self._daily_pnl = self._get_today_realized_pnl()

    def _get_today_realized_pnl(self) -> float:
        """Sum of net_pnl for today's closed trades."""
        today = datetime.now(IST).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(net_pnl), 0.0)
            FROM live_trades
            WHERE date_ist = ? AND status != 'OPEN'
        """, (today,))
        result = cursor.fetchone()[0]
        conn.close()
        return result

    def is_daily_limit_hit(self) -> bool:
        """Check if daily loss limit has been reached."""
        self._reset_daily_if_needed()
        return self._daily_pnl <= -DAILY_MAX_LOSS_INR

    # -- Open Trade -----------------------------------------------------------

    async def open_trade(
        self,
        simulation_id: str,
        prediction_id: str,
        direction: str,
        conviction: float,
        nifty_spot: float,
        vix: float,
        instrument: str = "NIFTY",
        gap_estimate=None,
    ) -> Optional[LiveTrade]:
        """Open a new live trade from a simulation signal.

        Same risk guards as PaperTrader, but places a real order via Dhan.
        Returns LiveTrade if order was placed, None if skipped or order failed.

        Uses asyncio.Lock to prevent concurrent requests from bypassing
        the open trade count check and placing duplicate orders.
        """
        async with self._trade_lock:
            return await self._open_trade_inner(
                simulation_id, prediction_id, direction, conviction,
                nifty_spot, vix, instrument, gap_estimate,
            )

    async def _open_trade_inner(
        self,
        simulation_id: str,
        prediction_id: str,
        direction: str,
        conviction: float,
        nifty_spot: float,
        vix: float,
        instrument: str = "NIFTY",
        gap_estimate=None,
    ) -> Optional[LiveTrade]:
        """Inner open_trade logic — called under _trade_lock."""
        # Skip HOLD signals
        if direction not in ("BUY", "SELL", "STRONG_BUY", "STRONG_SELL"):
            logger.info("LiveTrader: skipping %s signal (no trade)", direction)
            return None

        # Gap risk gate
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
                    "LiveTrader: GAP DANGER (%.2f%%) — blocking trade entirely",
                    gap_pct,
                )
                return None

            if gap_tier in ("WARNING", "CAUTION"):
                logger.info(
                    "LiveTrader: GAP %s (%.2f%%) — position_mult=%.2f, stop_buffer=%.1f%%",
                    gap_tier, gap_pct, position_multiplier, stop_buffer_pct,
                )

        # Check conviction floor
        if conviction < MIN_CONVICTION:
            logger.info("LiveTrader: conviction %.1f < %.1f floor, skip", conviction, MIN_CONVICTION)
            return None

        # VIX gate
        if vix >= VIX_HOLD_THRESHOLD:
            logger.warning("LiveTrader: VIX %.1f >= %.1f threshold, blocking trade", vix, VIX_HOLD_THRESHOLD)
            return None

        # Check daily loss limit
        if self.is_daily_limit_hit():
            logger.warning("LiveTrader: daily loss limit hit (%.0f), blocking trade", self._daily_pnl)
            return None

        # Check for existing open trades today
        today = datetime.now(IST).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM live_trades
            WHERE date_ist = ? AND status = 'OPEN'
        """, (today,))
        open_count = cursor.fetchone()[0]
        conn.close()

        if open_count > 0:
            logger.info("LiveTrader: already have %d open trade(s) today, skip", open_count)
            return None

        # Compute option trade parameters
        option_type = "CE" if direction in ("BUY", "STRONG_BUY") else "PE"
        lot_size = lot_size_for(instrument)
        dte = 5  # Weekly options
        entry_premium = estimate_atm_premium(nifty_spot, vix, dte)

        # Apply gap-adjusted capital
        effective_capital = LIVE_CAPITAL * position_multiplier
        lots = max_affordable_lots(entry_premium, lot_size, effective_capital)
        if lots == 0:
            logger.warning(
                "LiveTrader: can't afford 1 lot (premium=%.1f, lot=%d, eff_capital=%.0f)",
                entry_premium, lot_size, effective_capital,
            )
            return None

        # Stop and target on premium
        effective_stop_pct = STOP_LOSS_PCT + (stop_buffer_pct / 100.0)
        stop_price = round(entry_premium * (1.0 - effective_stop_pct), 2)
        risk_per_unit = entry_premium - stop_price
        target_price = round(entry_premium + (risk_per_unit * 1.5), 2)

        # Corresponding NIFTY levels
        stop_move = (stop_price - entry_premium) / ATM_DELTA
        target_move = (target_price - entry_premium) / ATM_DELTA

        if option_type == "CE":
            stop_nifty = round(nifty_spot + stop_move, 2)
            target_nifty = round(nifty_spot + target_move, 2)
        else:
            stop_nifty = round(nifty_spot - stop_move, 2)
            target_nifty = round(nifty_spot - target_move, 2)

        entry_cost = round(lots * lot_size * entry_premium, 2)

        # Look up ATM security ID from Dhan option chain
        security_id = await self._get_atm_security_id(nifty_spot, option_type)
        if not security_id:
            logger.error("LiveTrader: could not resolve ATM security_id — aborting trade")
            return None

        # Place the order via Dhan
        quantity = lots * lot_size
        order_result = await dhan_client.place_order(
            transaction_type="BUY",
            exchange_segment="NSE_FNO",
            product_type="INTRADAY",
            order_type="MARKET",
            security_id=security_id,
            quantity=quantity,
            correlation_id=f"ge_{uuid.uuid4().hex[:8]}",
        )

        dhan_order_id = None
        order_status = "ORDER_FAILED"

        if order_result:
            dhan_order_id = order_result.get("orderId")
            order_status = order_result.get("orderStatus", "PENDING")
        else:
            logger.error("LiveTrader: Dhan order placement FAILED for %s %s", direction, option_type)

        trade = LiveTrade(
            trade_id=f"lt_{uuid.uuid4().hex[:8]}",
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
            dhan_order_id=dhan_order_id,
            dhan_exit_order_id=None,
            trading_mode="live",
            order_status=order_status,
            security_id=security_id,
            status="OPEN" if dhan_order_id else "ORDER_FAILED",
        )

        self._save_trade(trade)

        if dhan_order_id:
            logger.info(
                "LiveTrader: OPENED %s %s %sx%d @ est. %.1f (spot=%.0f, dhan_order=%s)",
                trade.trade_id, direction, option_type, lots,
                entry_premium, nifty_spot, dhan_order_id,
            )
        else:
            logger.error("LiveTrader: trade %s saved with ORDER_FAILED status", trade.trade_id)

        return trade

    # -- Close Trade ----------------------------------------------------------

    async def close_trade(
        self,
        trade: LiveTrade,
        exit_spot: float,
        exit_premium: float,
        reason: str,
    ) -> LiveTrade:
        """Close a trade: place exit order via Dhan and compute P&L.

        SAFETY: Only places exit SELL if the entry order was actually TRADED
        (filled) by the exchange. If the entry was REJECTED/CANCELLED/PENDING,
        we mark the trade closed without placing an exit order to avoid
        creating a naked short position.
        """
        # Check if Dhan orders are still enabled (could be turned off mid-session)
        dhan_enabled = os.getenv("DHAN_ORDERS_ENABLED", "").lower() in ("true", "1", "yes")

        # Only place exit order if entry was actually filled at the exchange
        entry_filled = trade.order_status in ("TRADED", "TRANSIT")
        can_place_exit = (
            trade.security_id
            and trade.dhan_order_id
            and entry_filled
            and dhan_enabled
        )

        if trade.dhan_order_id and not entry_filled:
            logger.warning(
                "LiveTrader: skipping exit order for %s — entry order_status=%s (not filled)",
                trade.trade_id, trade.order_status,
            )

        if trade.dhan_order_id and entry_filled and not dhan_enabled:
            logger.error(
                "LiveTrader: DHAN_ORDERS_ENABLED is OFF but trade %s has a filled entry! "
                "Position remains open at Dhan — close manually.",
                trade.trade_id,
            )

        if can_place_exit:
            quantity = trade.lots * trade.lot_size
            exit_result = await dhan_client.place_order(
                transaction_type="SELL",
                exchange_segment="NSE_FNO",
                product_type="INTRADAY",
                order_type="MARKET",
                security_id=trade.security_id,
                quantity=quantity,
                correlation_id=f"ge_exit_{trade.trade_id[-8:]}",
            )
            if exit_result:
                trade.dhan_exit_order_id = exit_result.get("orderId")
                logger.info("LiveTrader: exit order placed: %s", trade.dhan_exit_order_id)
            else:
                logger.error("LiveTrader: exit order FAILED for trade %s", trade.trade_id)

        # Compute P&L
        exit_value = round(trade.lots * trade.lot_size * exit_premium, 2)
        gross_pnl = round(exit_value - trade.entry_cost, 2)
        net_pnl = round(gross_pnl - BROKERAGE_ROUND_TRIP, 2)
        return_pct = round((net_pnl / LIVE_CAPITAL) * 100.0, 2)

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

        logger.info(
            "LiveTrader: CLOSED %s %s -> net P&L %.0f (%.1f%%) [%s]",
            trade.trade_id, reason, net_pnl, return_pct, trade.direction,
        )
        return trade

    # -- Monitor / Check Stops & Targets --------------------------------------

    async def check_open_trades(self, current_spot: float) -> List[LiveTrade]:
        """Check all open trades against current NIFTY spot for stop/target hits.

        Returns list of trades that were closed.
        """
        open_trades = self.get_open_trades()
        closed = []

        for trade in open_trades:
            hit = await self._check_stop_target(trade, current_spot)
            if hit:
                closed.append(hit)

        return closed

    async def _check_stop_target(self, trade: LiveTrade, current_spot: float) -> Optional[LiveTrade]:
        """Check if a trade's stop or target has been hit."""
        if trade.option_type == "CE":
            if current_spot <= trade.stop_nifty:
                return await self.close_trade(trade, current_spot, trade.stop_price, "STOPPED")
            elif current_spot >= trade.target_nifty:
                return await self.close_trade(trade, current_spot, trade.target_price, "TARGET_HIT")
        else:
            if current_spot >= trade.stop_nifty:
                return await self.close_trade(trade, current_spot, trade.stop_price, "STOPPED")
            elif current_spot <= trade.target_nifty:
                return await self.close_trade(trade, current_spot, trade.target_price, "TARGET_HIT")
        return None

    # -- EOD Close ------------------------------------------------------------

    async def close_all_eod(self, closing_spot: float, closing_vix: float = 15.0) -> List[LiveTrade]:
        """Close all open trades from previous days at EOD (15:25 IST).

        Same close-to-close structure as PaperTrader.
        """
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        open_trades = self.get_open_trades()
        closed = []

        for trade in open_trades:
            if trade.date_ist >= today_str:
                logger.info(
                    "EOD: skipping live trade %s (opened today %s, exits tomorrow)",
                    trade.trade_id, trade.date_ist,
                )
                continue

            spot_move = closing_spot - trade.entry_spot
            if trade.option_type == "CE":
                raw_exit = trade.entry_premium + (ATM_DELTA * spot_move)
            else:
                raw_exit = trade.entry_premium + (ATM_DELTA * -spot_move)

            exit_premium = max(0.05, round(raw_exit, 2))
            result = await self.close_trade(trade, closing_spot, exit_premium, "CLOSED_EOD")
            if result:
                closed.append(result)

        return closed

    # -- Sync Order Status ----------------------------------------------------

    async def sync_order_status(self) -> List[LiveTrade]:
        """Poll Dhan for order fill status on all open trades.

        Updates order_status field from Dhan's order book.
        Returns list of trades whose status changed.
        """
        open_trades = self.get_open_trades()
        updated = []

        for trade in open_trades:
            if not trade.dhan_order_id:
                continue

            order_info = await dhan_client.get_order_by_id(trade.dhan_order_id)
            if not order_info:
                continue

            new_status = order_info.get("orderStatus", trade.order_status)
            if new_status != trade.order_status:
                trade.order_status = new_status
                self._update_order_status(trade)
                updated.append(trade)
                logger.info(
                    "LiveTrader: order %s status changed to %s",
                    trade.dhan_order_id, new_status,
                )

                # If order was rejected/cancelled by exchange, mark trade
                if new_status in ("REJECTED", "CANCELLED"):
                    trade.status = "CANCELLED"
                    trade.exit_reason = f"Order {new_status} by exchange"
                    trade.exit_timestamp = datetime.now(IST).isoformat()
                    self._update_trade(trade)

        return updated

    # -- Database Operations --------------------------------------------------

    def _save_trade(self, trade: LiveTrade):
        """Insert a new trade into the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO live_trades (
                trade_id, simulation_id, prediction_id, timestamp, date_ist,
                direction, conviction, instrument, option_type, lot_size, lots, dte,
                entry_spot, entry_premium, stop_price, target_price,
                stop_nifty, target_nifty, entry_cost,
                dhan_order_id, dhan_exit_order_id, trading_mode, order_status, security_id,
                status, brokerage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.trade_id, trade.simulation_id, trade.prediction_id,
            trade.timestamp, trade.date_ist,
            trade.direction, trade.conviction,
            trade.instrument, trade.option_type, trade.lot_size, trade.lots, trade.dte,
            trade.entry_spot, trade.entry_premium, trade.stop_price, trade.target_price,
            trade.stop_nifty, trade.target_nifty, trade.entry_cost,
            trade.dhan_order_id, trade.dhan_exit_order_id,
            trade.trading_mode, trade.order_status, trade.security_id,
            trade.status, trade.brokerage,
        ))
        conn.commit()
        conn.close()

    def _update_trade(self, trade: LiveTrade):
        """Update an existing trade (close it)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE live_trades SET
                status = ?,
                exit_premium = ?,
                exit_spot = ?,
                exit_timestamp = ?,
                exit_reason = ?,
                exit_value = ?,
                gross_pnl = ?,
                net_pnl = ?,
                return_pct = ?,
                dhan_exit_order_id = ?,
                order_status = ?
            WHERE trade_id = ?
        """, (
            trade.status, trade.exit_premium, trade.exit_spot,
            trade.exit_timestamp, trade.exit_reason,
            trade.exit_value, trade.gross_pnl, trade.net_pnl, trade.return_pct,
            trade.dhan_exit_order_id, trade.order_status,
            trade.trade_id,
        ))
        conn.commit()
        conn.close()

    def _update_order_status(self, trade: LiveTrade):
        """Update only the order_status field."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE live_trades SET order_status = ? WHERE trade_id = ?
        """, (trade.order_status, trade.trade_id))
        conn.commit()
        conn.close()

    # -- Query Methods --------------------------------------------------------

    def get_open_trades(self) -> List[LiveTrade]:
        """Get all currently open trades."""
        return self._query_trades("status = 'OPEN'")

    def get_today_trades(self) -> List[LiveTrade]:
        """Get all trades for today (IST)."""
        today = datetime.now(IST).strftime("%Y-%m-%d")
        return self._query_trades("date_ist = ?", (today,))

    def get_trade_history(self, limit: int = 50, offset: int = 0) -> List[LiveTrade]:
        """Get recent trade history."""
        return self._query_trades("1=1", (), limit=limit, offset=offset)

    def get_trade_by_id(self, trade_id: str) -> Optional[LiveTrade]:
        """Get a specific trade by ID."""
        trades = self._query_trades("trade_id = ?", (trade_id,), limit=1)
        return trades[0] if trades else None

    def _query_trades(
        self, where: str, params: tuple = (), limit: int = 100, offset: int = 0
    ) -> List[LiveTrade]:
        """Generic trade query."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT * FROM live_trades
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (*params, limit, offset))
        rows = cursor.fetchall()
        conn.close()

        trades = []
        for row in rows:
            trades.append(LiveTrade(
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
                dhan_order_id=row["dhan_order_id"],
                dhan_exit_order_id=row["dhan_exit_order_id"],
                trading_mode=row["trading_mode"],
                order_status=row["order_status"],
                security_id=row["security_id"],
                status=row["status"],
                exit_premium=row["exit_premium"],
                exit_spot=row["exit_spot"],
                exit_timestamp=row["exit_timestamp"],
                exit_reason=row["exit_reason"],
                exit_value=row["exit_value"],
                gross_pnl=row["gross_pnl"],
                brokerage=row["brokerage"],
                net_pnl=row["net_pnl"],
                return_pct=row["return_pct"],
            ))

        return trades

    # -- P&L Summary ----------------------------------------------------------

    def get_pnl_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get P&L summary for the last N days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.now(IST) - timedelta(days=days)).strftime("%Y-%m-%d")

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
                SUM(CASE WHEN status = 'CLOSED_EOD' THEN 1 ELSE 0 END) as eod_count,
                SUM(CASE WHEN status = 'ORDER_FAILED' THEN 1 ELSE 0 END) as failed_count
            FROM live_trades
            WHERE date_ist >= ? AND status NOT IN ('OPEN', 'PENDING', 'CANCELLED', 'ORDER_FAILED')
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
        # failed_count from this query is always 0 since we excluded ORDER_FAILED above
        # Query separately for display purposes
        cursor.execute("""
            SELECT
                SUM(CASE WHEN status = 'ORDER_FAILED' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END)
            FROM live_trades WHERE date_ist >= ?
        """, (cutoff,))
        fail_row = cursor.fetchone()
        failed = (fail_row[0] or 0) if fail_row else 0
        cancelled = (fail_row[1] or 0) if fail_row else 0

        win_rate = (wins / total * 100) if total > 0 else 0

        # Daily P&L breakdown
        cursor.execute("""
            SELECT
                date_ist,
                COUNT(*) as trades,
                SUM(net_pnl) as day_pnl,
                SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) as day_wins
            FROM live_trades
            WHERE date_ist >= ? AND status NOT IN ('OPEN', 'PENDING', 'ORDER_FAILED')
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
        cursor.execute("SELECT COUNT(*) FROM live_trades WHERE status = 'OPEN'")
        open_count = cursor.fetchone()[0]

        conn.close()

        return {
            "period_days": days,
            "capital": LIVE_CAPITAL,
            "trading_mode": "live",
            "total_trades": total,
            "open_trades": open_count,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 1),
            "total_pnl_inr": round(total_pnl, 2),
            "total_return_pct": round((total_pnl / LIVE_CAPITAL) * 100, 2) if LIVE_CAPITAL > 0 else 0,
            "avg_win_inr": round(avg_win, 2),
            "avg_loss_inr": round(avg_loss, 2),
            "largest_win_inr": round(largest_win, 2),
            "largest_loss_inr": round(largest_loss, 2),
            "max_drawdown_inr": round(max_drawdown, 2),
            "max_drawdown_pct": round((max_drawdown / LIVE_CAPITAL) * 100, 2) if LIVE_CAPITAL > 0 else 0,
            "stopped_count": stopped,
            "target_hit_count": targets,
            "eod_close_count": eod,
            "order_failed_count": failed,
            "profit_factor": round(abs(avg_win * wins) / abs(avg_loss * losses), 2) if losses > 0 and avg_loss != 0 else 0.0,
            "daily_pnl": list(reversed(daily_pnl)),
        }


# Module-level singleton
live_trader = LiveTrader()
