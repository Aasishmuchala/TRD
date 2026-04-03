"""Stock screener for F&O universe.

Given a market direction (BUY/SELL) from God's Eye, ranks F&O stocks
by a composite micro-signal score using:
  - Relative strength vs Nifty (5-day)
  - Volume ratio (today / 20-day avg)
  - RSI-14
  - OI ratio (call_oi / put_oi — wired, live data deferred)
  - Affordability for given capital

Only returns stocks whose estimated lot cost fits within capital budget.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

import yfinance as yf

from app.data.fno_universe import FNO_UNIVERSE, get_affordable
from app.data.technical_signals import TechnicalSignals

logger = logging.getLogger(__name__)

_HISTORY_DAYS = 30


class StockSignal:
    def __init__(self, symbol, sector, lot_size, direction_aligned,
                 rs_5d, volume_ratio, rsi, oi_ratio,
                 screener_score, est_premium_per_share, est_lot_cost):
        self.symbol = symbol
        self.sector = sector
        self.lot_size = lot_size
        self.direction_aligned = direction_aligned
        self.rs_5d = rs_5d
        self.volume_ratio = volume_ratio
        self.rsi = rsi
        self.oi_ratio = oi_ratio
        self.screener_score = screener_score
        self.est_premium_per_share = est_premium_per_share
        self.est_lot_cost = est_lot_cost

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "sector": self.sector,
            "lot_size": self.lot_size,
            "direction_aligned": self.direction_aligned,
            "rs_5d_pct": round(self.rs_5d, 2),
            "volume_ratio": round(self.volume_ratio, 2),
            "rsi": round(self.rsi, 1),
            "oi_ratio": round(self.oi_ratio, 2) if self.oi_ratio is not None else None,
            "screener_score": round(self.screener_score, 1),
            "est_premium_per_share": round(self.est_premium_per_share, 2),
            "est_lot_cost": self.est_lot_cost,
        }


async def _fetch_ohlcv(yf_ticker: str, days: int = _HISTORY_DAYS) -> List[Dict]:
    try:
        end = date.today()
        start = end - timedelta(days=days + 10)
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(yf_ticker, start=start.isoformat(),
                                 end=end.isoformat(), progress=False, auto_adjust=True)
        )
        if df.empty:
            return []
        rows = []
        for idx, row in df.iterrows():
            rows.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            })
        return sorted(rows, key=lambda r: r["date"])
    except Exception as e:
        logger.warning("yfinance fetch failed for %s: %s", yf_ticker, e)
        return []


async def _fetch_nifty_closes(days: int = _HISTORY_DAYS) -> List[float]:
    try:
        end = date.today()
        start = end - timedelta(days=days + 10)
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: yf.download("^NSEI", start=start.isoformat(),
                                 end=end.isoformat(), progress=False, auto_adjust=True)
        )
        if df.empty:
            return []
        return [float(r["Close"]) for _, r in df.sort_index().iterrows()]
    except Exception as e:
        logger.warning("Nifty fetch for RS failed: %s", e)
        return []


def _relative_strength_5d(stock_closes: List[float], nifty_closes: List[float]) -> float:
    if len(stock_closes) < 6 or len(nifty_closes) < 6:
        return 0.0
    stock_ret = (stock_closes[-1] / stock_closes[-6] - 1) * 100
    nifty_ret = (nifty_closes[-1] / nifty_closes[-6] - 1) * 100
    return round(stock_ret - nifty_ret, 2)


def _volume_ratio(rows: List[Dict]) -> float:
    if len(rows) < 2:
        return 1.0
    vols = [r["volume"] for r in rows]
    avg20 = sum(vols[:-1][-20:]) / min(20, len(vols) - 1) if len(vols) > 1 else vols[-1]
    return round(vols[-1] / avg20, 2) if avg20 > 0 else 1.0


def _estimate_premium(ltp: float, direction: str) -> float:
    return round(ltp * 0.01, 2)


def _score(direction, rs_5d, volume_ratio, rsi, oi_ratio) -> float:
    score = 0.0
    is_buy = direction in ("BUY", "STRONG_BUY")

    # RS component (35 pts)
    if is_buy:
        score += max(0, min(35, rs_5d * 7))
    else:
        score += max(0, min(35, -rs_5d * 7))

    # Volume component (25 pts)
    score += max(0, min(25, (volume_ratio - 1.0) * 25))

    # RSI component (25 pts)
    if is_buy:
        if 40 <= rsi <= 65:
            score += 25
        elif 30 <= rsi < 40:
            score += 15
        elif rsi > 70:
            score += 0
        else:
            score += 10
    else:
        if 35 <= rsi <= 60:
            score += 25
        elif rsi > 60:
            score += 15
        elif rsi < 30:
            score += 0
        else:
            score += 10

    # OI component (15 pts)
    if oi_ratio is not None:
        if is_buy and oi_ratio > 1.2:
            score += 15
        elif is_buy and oi_ratio > 0.9:
            score += 7
        elif not is_buy and oi_ratio < 0.8:
            score += 15
        elif not is_buy and oi_ratio < 1.1:
            score += 7

    return min(100.0, score)


async def screen_stocks(direction: str, capital: int = 10000, top_n: int = 3) -> List[Dict]:
    """Screen F&O universe and return top_n affordable candidates."""
    if direction == "HOLD":
        return []

    affordable = get_affordable(capital, max_premium_per_share=25.0)
    if not affordable:
        return []

    nifty_closes = await _fetch_nifty_closes()

    results: List[StockSignal] = []

    async def process(symbol: str, meta: Dict) -> Optional[StockSignal]:
        rows = await _fetch_ohlcv(meta["yf_ticker"])
        if len(rows) < 6:
            return None
        closes = [r["close"] for r in rows]
        ltp = closes[-1]
        rs_5d = _relative_strength_5d(closes, nifty_closes)
        vol_ratio = _volume_ratio(rows)
        rsi = TechnicalSignals.compute_rsi(closes)
        oi_ratio = None
        is_buy = direction in ("BUY", "STRONG_BUY")
        direction_aligned = (is_buy and rs_5d > 0) or (not is_buy and rs_5d < 0)
        composite = _score(direction, rs_5d, vol_ratio, rsi, oi_ratio)
        est_premium = _estimate_premium(ltp, direction)
        est_cost = int(meta["lot_size"] * est_premium)
        return StockSignal(
            symbol=symbol, sector=meta["sector"], lot_size=meta["lot_size"],
            direction_aligned=direction_aligned, rs_5d=rs_5d, volume_ratio=vol_ratio,
            rsi=rsi, oi_ratio=oi_ratio, screener_score=composite,
            est_premium_per_share=est_premium, est_lot_cost=est_cost,
        )

    tasks = [process(sym, meta) for sym, meta in affordable.items()]
    signals = await asyncio.gather(*tasks, return_exceptions=True)

    for sig in signals:
        if isinstance(sig, StockSignal):
            results.append(sig)

    results.sort(key=lambda s: (not s.direction_aligned, -s.screener_score))
    return [s.to_dict() for s in results[:top_n]]
