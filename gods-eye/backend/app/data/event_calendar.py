"""India market event calendar for FY2024-25.

Provides binary event awareness to the backtest engine and NewsEventAgent.
Events are classified by type and severity to drive:
  - Pre-event blackout (force HOLD 1 day before high-impact events)
  - VIX regime context (agents aware of WHY VIX is elevated)
  - Post-event directional context (amplify signal after event resolves)
"""

from datetime import date, timedelta
from typing import Optional, Set

# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

RBI_POLICY       = "RBI_POLICY"        # RBI MPC rate decisions
INDIA_ELECTION   = "INDIA_ELECTION"    # Lok Sabha / state election phases + results
BUDGET           = "BUDGET"            # Union Budget
MACRO_SHOCK      = "MACRO_SHOCK"       # Unexpected global/geopolitical shocks
US_ELECTION      = "US_ELECTION"       # US presidential election
EXPIRY_WEEK      = "EXPIRY_WEEK"       # Monthly F&O expiry week (last Thu of month)
QUARTERLY_RESULT = "QUARTERLY_RESULT"  # Major earnings season start

# Events that trigger pre-event blackout (binary outcome, can't predict direction)
BLACKOUT_EVENT_TYPES: Set[str] = {
    INDIA_ELECTION,
    BUDGET,
    US_ELECTION,
    MACRO_SHOCK,
    RBI_POLICY,
}

# ---------------------------------------------------------------------------
# FY2024-25 Event Calendar (April 2024 – March 2025)
# ---------------------------------------------------------------------------
# Format: "YYYY-MM-DD": EVENT_TYPE
# For multi-day events (election phases), each relevant day is listed separately.
# ---------------------------------------------------------------------------

EVENT_CALENDAR: dict = {
    # ---- April 2024 ----
    "2024-04-10": MACRO_SHOCK,      # Iran missile attack on Israel, Nifty -234 pts
    "2024-04-17": EXPIRY_WEEK,      # Apr F&O monthly expiry (Thu)

    # ---- May 2024 — India General Election (Lok Sabha 18th) ----
    "2024-04-19": INDIA_ELECTION,   # Phase 1 voting
    "2024-04-26": INDIA_ELECTION,   # Phase 2 voting
    "2024-05-07": INDIA_ELECTION,   # Phase 3 voting
    "2024-05-13": INDIA_ELECTION,   # Phase 4 voting
    "2024-05-20": INDIA_ELECTION,   # Phase 5 voting
    "2024-05-25": INDIA_ELECTION,   # Phase 6 voting
    "2024-05-30": EXPIRY_WEEK,      # May F&O monthly expiry (Thu)
    "2024-06-01": INDIA_ELECTION,   # Phase 7 (final phase) voting
    "2024-06-04": INDIA_ELECTION,   # RESULTS DAY — massive binary event

    # ---- June 2024 ----
    "2024-06-07": RBI_POLICY,       # RBI MPC June 2024 decision
    "2024-06-27": EXPIRY_WEEK,      # Jun F&O monthly expiry (Thu)

    # ---- July 2024 ----
    "2024-07-23": BUDGET,           # Union Budget FY2025 (presented by FM)
    "2024-07-25": EXPIRY_WEEK,      # Jul F&O monthly expiry (Thu)

    # ---- August 2024 ----
    "2024-08-05": MACRO_SHOCK,      # Japan Nikkei -12.4% (yen carry unwind), global crash
    "2024-08-06": MACRO_SHOCK,      # Day 2 of Japan contagion crash
    "2024-08-08": RBI_POLICY,       # RBI MPC August 2024 decision
    "2024-08-29": EXPIRY_WEEK,      # Aug F&O monthly expiry (Thu)

    # ---- September 2024 ----
    "2024-09-18": MACRO_SHOCK,      # US Fed rate cut (50bps surprise) — EM sentiment shift
    "2024-09-26": EXPIRY_WEEK,      # Sep F&O monthly expiry (Thu)

    # ---- October 2024 ----
    "2024-10-09": RBI_POLICY,       # RBI MPC October 2024 decision
    "2024-10-31": EXPIRY_WEEK,      # Oct F&O monthly expiry (Thu)

    # ---- November 2024 ----
    "2024-11-05": US_ELECTION,      # US Presidential Election Day (Trump vs Harris)
    "2024-11-06": US_ELECTION,      # Results confirmation day
    "2024-11-28": EXPIRY_WEEK,      # Nov F&O monthly expiry (Thu)

    # ---- December 2024 ----
    "2024-12-06": RBI_POLICY,       # RBI MPC December 2024 decision
    "2024-12-26": EXPIRY_WEEK,      # Dec F&O monthly expiry (Thu)

    # ---- January 2025 ----
    "2025-01-30": EXPIRY_WEEK,      # Jan F&O monthly expiry (Thu)

    # ---- February 2025 ----
    "2025-02-01": BUDGET,           # Union Budget FY2026 presentation
    "2025-02-07": RBI_POLICY,       # RBI MPC February 2025 decision
    "2025-02-27": EXPIRY_WEEK,      # Feb F&O monthly expiry (Thu)

    # ---- March 2025 ----
    "2025-03-27": EXPIRY_WEEK,      # Mar F&O monthly expiry (Thu) — financial year end
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_event_for_date(date_str: str) -> Optional[str]:
    """Return event type string if this exact date is a known event, else None.

    Args:
        date_str: Date in "YYYY-MM-DD" format.

    Returns:
        Event type constant (e.g. "RBI_POLICY") or None.
    """
    return EVENT_CALENDAR.get(date_str)


def is_pre_event_blackout(date_str: str, lookahead_days: int = 2) -> bool:
    """True if a HIGH-IMPACT binary event falls within lookahead_days of date_str.

    Only blackout-class events (INDIA_ELECTION, BUDGET, US_ELECTION,
    MACRO_SHOCK, RBI_POLICY) trigger a blackout. EXPIRY_WEEK does not.

    Args:
        date_str: Signal date "YYYY-MM-DD"
        lookahead_days: How many calendar days ahead to check (default 2).
                        2 days covers the T-1 session before a binary event
                        and the event day itself (e.g., election results).

    Returns:
        True if a blackout event is imminent, False otherwise.
    """
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return False

    for offset in range(1, lookahead_days + 1):
        future_date = (d + timedelta(days=offset)).isoformat()
        event = EVENT_CALENDAR.get(future_date)
        if event and event in BLACKOUT_EVENT_TYPES:
            return True
    return False


def get_post_event_context(date_str: str, lookback_days: int = 2) -> Optional[str]:
    """If a major event occurred within lookback_days before date_str, return context string.

    Used by NewsEventAgent to provide directional bias context after an event resolves.

    Args:
        date_str: Current signal date "YYYY-MM-DD"
        lookback_days: How many calendar days back to look (default 2).

    Returns:
        String like "post_india_election", "post_rbi_policy", etc., or None.
    """
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return None

    for offset in range(1, lookback_days + 1):
        past_date = (d - timedelta(days=offset)).isoformat()
        event = EVENT_CALENDAR.get(past_date)
        if event and event in BLACKOUT_EVENT_TYPES:
            return f"post_{event.lower()}"
    return None


def classify_vix_regime(vix: float) -> str:
    """Classify India VIX into a named regime.

    Regimes:
      low      VIX < 13    — calm, cheap premium, trend-following works well
      normal   13 <= VIX < 16 — standard conditions
      elevated 16 <= VIX < 20 — caution, raise conviction bar
      high     20 <= VIX < 25 — event-driven or stress, mostly HOLD
      extreme  VIX >= 25   — panic / crisis, no directional trades

    Args:
        vix: Current India VIX value.

    Returns:
        Regime name string.
    """
    if vix < 13.0:
        return "low"
    elif vix < 16.0:
        return "normal"
    elif vix < 20.0:
        return "elevated"
    elif vix < 25.0:
        return "high"
    else:
        return "extreme"


def get_event_description(event_type: str) -> str:
    """Human-readable description of an event type for agent prompts."""
    descriptions = {
        RBI_POLICY:       "RBI Monetary Policy Committee decision — rate change risk, binary outcome",
        INDIA_ELECTION:   "India General/State Election — results unknown, extreme binary event",
        BUDGET:           "Union Budget presentation — fiscal policy, sector-specific shocks",
        MACRO_SHOCK:      "Unexpected macro shock (geopolitical, global markets crash) — high uncertainty",
        US_ELECTION:      "US Presidential Election — global risk sentiment shift, EM capital flow impact",
        EXPIRY_WEEK:      "Monthly F&O expiry week — gamma exposure, pin risk near max pain",
        QUARTERLY_RESULT: "Quarterly earnings season — stock-specific moves, index volatility elevated",
    }
    return descriptions.get(event_type, "Unknown event type")
