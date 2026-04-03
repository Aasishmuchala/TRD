"""F&O Stock Universe — 30 most liquid NSE F&O stocks.

Dhan security IDs sourced from NSE F&O participant list.
Lot sizes as of April 2025 (SEBI revises periodically).
"""

from typing import Dict, Any

# (symbol -> {security_id, lot_size, sector, yf_ticker})
FNO_UNIVERSE: Dict[str, Dict[str, Any]] = {
    "RELIANCE":    {"security_id": "2885",  "lot_size": 250,  "sector": "Energy",       "yf_ticker": "RELIANCE.NS"},
    "HDFCBANK":    {"security_id": "1333",  "lot_size": 550,  "sector": "Banking",      "yf_ticker": "HDFCBANK.NS"},
    "INFY":        {"security_id": "1594",  "lot_size": 400,  "sector": "IT",           "yf_ticker": "INFY.NS"},
    "TCS":         {"security_id": "11536", "lot_size": 150,  "sector": "IT",           "yf_ticker": "TCS.NS"},
    "ICICIBANK":   {"security_id": "4963",  "lot_size": 700,  "sector": "Banking",      "yf_ticker": "ICICIBANK.NS"},
    "AXISBANK":    {"security_id": "5900",  "lot_size": 625,  "sector": "Banking",      "yf_ticker": "AXISBANK.NS"},
    "SBIN":        {"security_id": "3045",  "lot_size": 1500, "sector": "Banking",      "yf_ticker": "SBIN.NS"},
    "TATAMOTORS":  {"security_id": "3456",  "lot_size": 1425, "sector": "Auto",         "yf_ticker": "TATAMOTORS.NS"},
    "ITC":         {"security_id": "1660",  "lot_size": 3200, "sector": "FMCG",         "yf_ticker": "ITC.NS"},
    "LT":          {"security_id": "11483", "lot_size": 150,  "sector": "Infra",        "yf_ticker": "LT.NS"},
    "WIPRO":       {"security_id": "3787",  "lot_size": 1500, "sector": "IT",           "yf_ticker": "WIPRO.NS"},
    "HCLTECH":     {"security_id": "7229",  "lot_size": 700,  "sector": "IT",           "yf_ticker": "HCLTECH.NS"},
    "KOTAKBANK":   {"security_id": "1922",  "lot_size": 400,  "sector": "Banking",      "yf_ticker": "KOTAKBANK.NS"},
    "BAJFINANCE":  {"security_id": "317",   "lot_size": 125,  "sector": "NBFC",         "yf_ticker": "BAJFINANCE.NS"},
    "MARUTI":      {"security_id": "10999", "lot_size": 100,  "sector": "Auto",         "yf_ticker": "MARUTI.NS"},
    "ASIANPAINT":  {"security_id": "236",   "lot_size": 200,  "sector": "Paints",       "yf_ticker": "ASIANPAINT.NS"},
    "SUNPHARMA":   {"security_id": "3351",  "lot_size": 350,  "sector": "Pharma",       "yf_ticker": "SUNPHARMA.NS"},
    "ONGC":        {"security_id": "2475",  "lot_size": 1925, "sector": "Energy",       "yf_ticker": "ONGC.NS"},
    "POWERGRID":   {"security_id": "14977", "lot_size": 3400, "sector": "Utilities",    "yf_ticker": "POWERGRID.NS"},
    "NTPC":        {"security_id": "11630", "lot_size": 3000, "sector": "Utilities",    "yf_ticker": "NTPC.NS"},
    "ADANIPORTS":  {"security_id": "15083", "lot_size": 1250, "sector": "Infra",        "yf_ticker": "ADANIPORTS.NS"},
    "ULTRACEMCO":  {"security_id": "11532", "lot_size": 100,  "sector": "Cement",       "yf_ticker": "ULTRACEMCO.NS"},
    "HINDUNILVR":  {"security_id": "1394",  "lot_size": 300,  "sector": "FMCG",         "yf_ticker": "HINDUNILVR.NS"},
    "TITAN":       {"security_id": "3506",  "lot_size": 375,  "sector": "Consumer",     "yf_ticker": "TITAN.NS"},
    "BAJAJFINSV":  {"security_id": "16675", "lot_size": 125,  "sector": "NBFC",         "yf_ticker": "BAJAJFINSV.NS"},
    "DRREDDY":     {"security_id": "881",   "lot_size": 125,  "sector": "Pharma",       "yf_ticker": "DRREDDY.NS"},
    "CIPLA":       {"security_id": "694",   "lot_size": 650,  "sector": "Pharma",       "yf_ticker": "CIPLA.NS"},
    "GRASIM":      {"security_id": "1232",  "lot_size": 475,  "sector": "Diversified",  "yf_ticker": "GRASIM.NS"},
    "HINDALCO":    {"security_id": "1363",  "lot_size": 2150, "sector": "Metals",       "yf_ticker": "HINDALCO.NS"},
    "JSWSTEEL":    {"security_id": "11723", "lot_size": 1350, "sector": "Metals",       "yf_ticker": "JSWSTEEL.NS"},
}


def get_affordable(capital: int, max_premium_per_share: float = 25.0) -> Dict[str, Dict[str, Any]]:
    """Return stocks whose estimated 1-lot option cost fits within capital.

    Uses a conservative max_premium_per_share estimate (weekly OTM).
    Filters to stocks where lot_size * max_premium_per_share <= capital * 0.75.
    """
    budget = capital * 0.75
    return {
        sym: meta
        for sym, meta in FNO_UNIVERSE.items()
        if meta["lot_size"] * max_premium_per_share <= budget
    }
