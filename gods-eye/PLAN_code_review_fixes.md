# Plan: Fix All Code Review Issues
**God's Eye — Post-Review Hardening**
Created: 2026-04-04

## Context

Code review identified 10 issues across 3 severity tiers. This plan fixes them in 4 phases ordered by trading-safety impact. The WIN/LOSS label + P&L sign bug for SELL trades is promoted to Critical (not in original review) based on deeper analysis.

## Source Files Reference

All edits are in: `/sessions/trusting-wizardly-faraday/mnt/TRD/gods-eye/`

| File | Role |
|------|------|
| `backend/app/engine/options_pnl.py` | Options P&L math |
| `backend/app/engine/backtest_engine.py` | VIX gate, consensus, backtest loop |
| `backend/app/data/event_calendar.py` | Event blackout logic |
| `backend/app/config.py` | Agent weights, CORS, DB path |
| `backend/run.py` | FastAPI startup, CORS middleware |
| `bt_v3_run.py` | Standalone backtest script |
| `backend/requirements.txt` | Python dependencies |

---

## Phase 1 — Critical Trading Math & Config (Start Here)

> These bugs affect real ₹ P&L numbers. Fix before any live use.

### Task 1.1 — Fix Capital Mismatch in `options_pnl.py`

**Problem:** Module docstring says ₹10,000 but backtest uses ₹20,000. Default
parameter `capital=10_000.0` in both `max_affordable_lots()` and
`compute_options_pnl()` causes incorrect lot sizing if caller forgets to pass
capital explicitly.

**Files to edit:**
- `backend/app/engine/options_pnl.py` lines 1–10, 177, 219

**Exact changes:**

Line 2 — update docstring:
```python
# BEFORE:
"""Options P&L engine for ₹10,000 capital positional trades.

# AFTER:
"""Options P&L engine for ₹20,000 capital positional trades.
```

Line 177 — `max_affordable_lots()` default:
```python
# BEFORE:
    capital: float = 10_000.0,

# AFTER:
    capital: float = 20_000.0,
```

Line 219 — `compute_options_pnl()` default:
```python
# BEFORE:
    capital: float = 10_000.0,

# AFTER:
    capital: float = 20_000.0,
```

**Verification:**
```python
from backend.app.engine.options_pnl import max_affordable_lots, compute_options_pnl
assert max_affordable_lots(161.0, 25) == 1        # ₹4,025 < 30% of ₹20K = ₹6K → 1 lot ✓
assert max_affordable_lots(161.0, 25, capital=10_000.0) == 0  # ₹4,025 > 30% of ₹10K = ₹3K → 0 lots ✓
```

---

### Task 1.2 — Fix SELL Trade P&L Sign Bug in `bt_v3_run.py`

**Problem:** Line 181 in `bt_v3_run.py` negates `actual_move_pct` for SELL
direction before passing to `compute_options_pnl()`. But `compute_options_pnl()`
already handles directionality via the `direction` parameter (BUY → CALL, SELL
→ PUT). This double-negation causes SELL trades to report inverted P&L:
- NIFTY rises +1.89% → code passes -1.89 points → PUT gains → **false +₹5,213**
  (should be a loss)
- WIN/LOSS label is correct (uses raw `actual_move_pct`), creating an
  inconsistency where LOSS label + positive P&L appear together.

**File to edit:** `bt_v3_run.py` lines 180–192

**Exact change:**

```python
# BEFORE (lines 180–192):
        buy_dirs = ("BUY", "STRONG_BUY")
        actual_move = actual_move_pct if direction in buy_dirs else -actual_move_pct
        direction_correct = (
            (actual_move_pct > 0.1 and direction in buy_dirs) or
            (actual_move_pct < -0.1 and direction not in buy_dirs)
        )

        pnl_pts = actual_move_pct * (1 if direction in buy_dirs else -1) * 220

        t = compute_options_pnl(
            ...
            nifty_point_move=actual_move * nifty_close / 100,   # ← uses negated move

# AFTER:
        buy_dirs = ("BUY", "STRONG_BUY")
        # Do NOT negate for SELL — compute_options_pnl handles directionality
        # via the `direction` param (BUY→CALL, SELL→PUT). Passing raw market
        # move lets options_pnl correctly compute loss when market goes against trade.
        direction_correct = (
            (actual_move_pct > 0.1 and direction in buy_dirs) or
            (actual_move_pct < -0.1 and direction not in buy_dirs)
        )

        pnl_pts = actual_move_pct * (1 if direction in buy_dirs else -1) * 220

        t = compute_options_pnl(
            ...
            nifty_point_move=actual_move_pct * nifty_close / 100,  # ← raw market move
```

**Verification:** After this fix, re-run the 3-month validation. SELL trades on
up-days should show negative P&L. SELL trades on down-days should show positive
P&L. WIN/LOSS labels and P&L signs should now agree.

**Anti-pattern guard:** Do NOT add any sign flip inside `compute_options_pnl()`.
The function takes the raw market move and uses `direction` to buy the correct
leg (CE for BUY, PE for SELL).

---

### Task 1.3 — Add Production CORS Validation at Startup in `run.py`

**Problem:** If `GODS_EYE_CORS_ORIGINS` is not set on Railway, CORS defaults to
localhost origins. Frontend on `https://app.vercel.app` silently fails with CORS
errors. No warning is logged.

**File to edit:** `backend/run.py` — inside `startup_event()` (lines 216–243)

**Exact change — add after line 218 (`print(f"Starting God's Eye...")`:**

```python
    # Validate CORS config for production deployments
    _cors = config.CORS_ORIGINS
    _is_localhost_only = all("localhost" in o or "127.0.0.1" in o for o in _cors)
    _env = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("GODS_EYE_ENV", "development")
    if _is_localhost_only and _env not in ("development", "local", "test"):
        print(
            "WARNING: CORS_ORIGINS only contains localhost origins in a non-development "
            "environment. Set GODS_EYE_CORS_ORIGINS=https://your-app.vercel.app on Railway "
            "or all frontend API calls will be blocked by CORS policy."
        )
```

**Import needed:** `import os` is already in `run.py`.

**Verification:** Start the server with `RAILWAY_ENVIRONMENT=production` and no
`GODS_EYE_CORS_ORIGINS` set. Confirm the WARNING prints on startup. Then set
`GODS_EYE_CORS_ORIGINS=https://test.vercel.app` and confirm WARNING is gone.

---

## Phase 2 — Important: Reliability & Risk Management

### Task 2.1 — Add LLM Retry Logic to `backtest_engine.py`

**Problem:** `backtest_engine.py` lines 283–295 fire all agents in parallel with
`asyncio.gather(..., return_exceptions=True)` but has no retry. One API timeout
silently drops an agent from that day's consensus. `bt_v3_run.py` has a
battle-tested `call_agent_with_retry()` — copy the same pattern here.

**File to edit:** `backend/app/engine/backtest_engine.py`

**Step 1** — Add retry helper near the top of the `BacktestEngine` class (after
class constants, around line 602):

```python
    @staticmethod
    async def _call_agent_with_retry(
        agent_name: str,
        agent,
        market_input,
        round_num: int = 1,
        max_retries: int = 3,
    ):
        """Call one agent with exponential-backoff retry (up to max_retries)."""
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                return await agent.analyze(market_input, round_num=round_num)
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt
                if attempt < max_retries:
                    logger.warning(
                        "Agent %s attempt %d failed: %s — retry in %ds",
                        agent_name, attempt, exc, wait,
                    )
                    await asyncio.sleep(wait)
        logger.error("Agent %s all retries failed: %s", agent_name, last_exc)
        return None
```

**Step 2** — Replace the existing `asyncio.gather()` block (lines 283–295) with:

```python
                # Run all agents in staggered parallel with retry
                tasks = {}
                for i, (name, agent) in enumerate(self.orchestrator.agents.items()):
                    await asyncio.sleep(0.5 * i)  # 0.5s stagger
                    tasks[name] = asyncio.create_task(
                        self._call_agent_with_retry(name, agent, market_input, round_num=1)
                    )
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                final_outputs = {}
                for name, result in zip(tasks.keys(), results):
                    if result is not None and not isinstance(result, Exception):
                        final_outputs[name] = result
                    else:
                        logger.warning("Agent %s skipped for %s", name, signal_date)
```

**Verification:**
```bash
grep -n "_call_agent_with_retry" backend/app/engine/backtest_engine.py
# Should show 2 occurrences: definition + call site
```

---

### Task 2.2 — Fix Stop-Loss Risk Cap in `max_affordable_lots()`

**Problem:** `max_affordable_lots()` computes `budget = capital * 0.30` and
divides by entry cost. This means 30% of capital caps the *premium paid*, not
the *maximum loss*. With a 25% stop-loss, max loss is:
`lots × lot_size × premium × 0.25 + brokerage`. At 1 lot NIFTY weekly:
`1 × 25 × 161 × 0.25 + 80 = ₹1,086` — well within ₹6K budget. But if premium
is ₹240 (high VIX): `1 × 25 × 240 × 0.25 + 80 = ₹1,580`. Also fine. The
existing logic works in practice for the current setup, but it should enforce
the *loss cap* not the *entry cost cap* for correctness.

**File to edit:** `backend/app/engine/options_pnl.py` — `max_affordable_lots()` (lines 175–203)

**Add a secondary check after the lot calculation:**

```python
def max_affordable_lots(
    entry_premium: float,
    lot_size: int,
    capital: float = 20_000.0,
    max_risk_pct: float = 0.30,
    stop_loss_pct: float = STOP_LOSS_PCT,   # 0.25
    brokerage: float = BROKERAGE_ROUND_TRIP, # 80.0
) -> int:
    """Calculate how many lots can be bought without exceeding max_risk_pct loss.

    Risk = lots × lot_size × entry_premium × stop_loss_pct + brokerage
    (not just entry cost — this correctly caps the downside, not the premium paid)
    """
    if entry_premium <= 0 or lot_size <= 0:
        return 0

    max_loss_budget = capital * max_risk_pct

    # Binary search / iterative: find max lots where max_loss ≤ budget
    # (Simple loop is fine — lots is always small, typically 1–3)
    lots = 0
    while True:
        candidate = lots + 1
        max_loss = (candidate * lot_size * entry_premium * stop_loss_pct) + brokerage
        if max_loss > max_loss_budget:
            break
        lots = candidate
        if lots > 20:  # safety cap — never more than 20 lots
            break

    return lots
```

**Verification:**
```python
# ₹161 premium, 25 lot NIFTY, 25% stop, ₹80 brokerage, ₹20K capital:
# 1 lot max_loss = 25 × 161 × 0.25 + 80 = ₹1,086 < ₹6K → allows 1 lot
# 5 lots max_loss = 5 × 25 × 161 × 0.25 + 80 = ₹5,113 < ₹6K → allows 5 lots
# 6 lots max_loss = 6 × 25 × 161 × 0.25 + 80 = ₹6,095 > ₹6K → stops at 5 lots
assert max_affordable_lots(161.0, 25) == 5   # was 1 with old entry-cost logic

# High premium scenario (₹240, VIX elevated):
# 4 lots max_loss = 4 × 25 × 240 × 0.25 + 80 = ₹6,080 > ₹6K → allows 3 lots
assert max_affordable_lots(240.0, 25) == 3
```

**Note:** This may increase lot count (and therefore P&L) vs the current
1-lot-per-trade setup. Run a quick sanity backtest on May 2024 after this change
to confirm returns remain reasonable.

---

### Task 2.3 — Enforce Railway Volume Path at Startup

**Problem:** `config.py` defaults `DATABASE_PATH` to `~/gods_eye.db`. On
Railway, the container filesystem is ephemeral — every deploy wipes the DB. No
warning is raised if the path isn't on a mounted volume.

**File to edit:** `backend/run.py` — inside `startup_event()`, after the CORS
validation added in Task 1.3.

```python
    # Validate database path for production deployments
    _db_path = config.DATABASE_PATH
    _env = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("GODS_EYE_ENV", "development")
    if _env not in ("development", "local", "test"):
        if not _db_path.startswith("/app/data"):
            print(
                f"WARNING: DATABASE_PATH={_db_path!r} is not under /app/data. "
                "On Railway, this path is ephemeral and will be wiped on redeploy. "
                "Set GODS_EYE_DB_PATH=/app/data/gods_eye.db and mount a Railway Volume at /app/data."
            )
    else:
        print(f"Database path: {_db_path}")
```

**Verification:** Start with `RAILWAY_ENVIRONMENT=production` and no
`GODS_EYE_DB_PATH`. Confirm WARNING prints. Set
`GODS_EYE_DB_PATH=/app/data/gods_eye.db` and confirm WARNING is gone.

---

## Phase 3 — Documentation & Polish

### Task 3.1 — Document 8-Agent Weight Change in `config.py` and `CLAUDE.md`

**Problem:** CLAUDE.md documents 6-agent weights but code has 8 agents. A
developer reading CLAUDE.md gets wrong expectations.

**File to edit:** `backend/app/config.py` lines 85–95

Add block comment before the weights dict:

```python
            # Agent weights (8-agent spec — evolved from original 6-agent plan).
            # Redistribution rationale:
            #   PROMOTER/RBI reduced (0.10→0.05 each): low-frequency signals,
            #     limited backtest signal quality.
            #   ALGO raised (0.10→0.17): backtest-validated quant accuracy.
            #   STOCK_OPTIONS (0.04) + NEWS_EVENT (0.07) added: options flow
            #     and binary event gating added material edge in 3-month validation.
            # Sum: 0.27+0.22+0.13+0.17+0.05+0.05+0.04+0.07 = 1.00 ✓
            self.AGENT_WEIGHTS = {
```

**File to edit:** `CLAUDE.md` — find the Constraints section and update the weights line:

```markdown
# BEFORE:
- **Agent Architecture**: 6 agents with specific weights (FII 0.30, DII 0.25, Retail 0.15, Algo 0.10, Promoter 0.10, RBI 0.10)

# AFTER:
- **Agent Architecture**: 8 agents (FII 0.27, DII 0.22, RETAIL_FNO 0.13, ALGO 0.17, PROMOTER 0.05, RBI 0.05, STOCK_OPTIONS 0.04, NEWS_EVENT 0.07). Sum=1.00. See config.py for rationale.
```

---

### Task 3.2 — Increase Event Blackout Lookahead to 2 Days

**Problem:** `is_pre_event_blackout()` defaults to `lookahead_days=1`. Multi-day
events (e.g., India election with results the next calendar day) may not be
caught if the signal date is 2 days before results.

**File to edit:** `backend/app/data/event_calendar.py` line 125

```python
# BEFORE:
def is_pre_event_blackout(date_str: str, lookahead_days: int = 1) -> bool:

# AFTER:
def is_pre_event_blackout(date_str: str, lookahead_days: int = 2) -> bool:
```

Update docstring line 128:
```python
# BEFORE:
        lookahead_days: How many calendar days ahead to check (default 1).

# AFTER:
        lookahead_days: How many calendar days ahead to check (default 2).
                        2 days covers the T-1 session before a binary event
                        and the session of the event itself (results day).
```

**Verification:** Check that Jun 3, 2024 (day before election results Jun 4)
now triggers blackout:
```python
from backend.app.data.event_calendar import is_pre_event_blackout
assert is_pre_event_blackout("2024-06-03") == True  # 2 days before Jun 4 results? Check calendar
assert is_pre_event_blackout("2024-06-02") == True  # day before results
```

---

### Task 3.3 — Add VIX Boundary Unit Tests

**Problem:** VIX gate has 4 boundary conditions (VIX = 14.0, 16.0, 20.0 exactly)
with no test coverage. A refactor could silently break the `>=` vs `>` logic.

**File to create:** `backend/tests/test_vix_gate.py`

```python
"""Unit tests for VIX regime gate boundary conditions."""
import pytest
from unittest.mock import MagicMock, patch
from app.engine.backtest_engine import BacktestEngine


def make_engine():
    with patch("app.engine.backtest_engine.Orchestrator"), \
         patch("app.engine.backtest_engine.SignalScorer"), \
         patch("app.engine.backtest_engine.StopLossEngine"):
        engine = BacktestEngine.__new__(BacktestEngine)
        engine.VIX_EXTREME_THRESHOLD = 20.0
        engine.VIX_HIGH_FLOOR = 78.0
        engine.VIX_ELEVATED_FLOOR = 72.0
        return engine


class TestVIXGateBoundaries:
    def setup_method(self):
        self.engine = make_engine()

    def test_hold_passes_through_unchanged(self):
        dir_, conv = self.engine._apply_vix_event_gate("HOLD", 50.0, 15.0, None, "2024-01-01")
        assert dir_ == "HOLD"
        assert conv == 50.0

    def test_pre_event_blackout_forces_hold(self):
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 80.0, 12.0, "pre_event_blackout", "2024-01-01")
        assert dir_ == "HOLD"

    def test_vix_exactly_20_blocks_trade(self):
        """VIX=20.0 should block (> threshold check means 20.0 is blocked)."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 80.0, 20.0, None, "2024-01-01")
        assert dir_ == "HOLD"

    def test_vix_just_below_20_uses_high_floor(self):
        """VIX=19.9 uses VIX_HIGH_FLOOR=78."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 77.9, 19.9, None, "2024-01-01")
        assert dir_ == "HOLD"  # 77.9 < 78 floor

        dir_, _ = self.engine._apply_vix_event_gate("BUY", 78.1, 19.9, None, "2024-01-01")
        assert dir_ == "BUY"   # 78.1 >= 78 floor

    def test_vix_exactly_16_uses_high_floor(self):
        """VIX=16.0 should use VIX_HIGH_FLOOR=78 (>= 16.0 condition)."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 77.9, 16.0, None, "2024-01-01")
        assert dir_ == "HOLD"  # 77.9 < 78

    def test_vix_just_below_16_uses_elevated_floor(self):
        """VIX=15.9 uses VIX_ELEVATED_FLOOR=72."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 71.9, 15.9, None, "2024-01-01")
        assert dir_ == "HOLD"  # 71.9 < 72

        dir_, _ = self.engine._apply_vix_event_gate("BUY", 72.1, 15.9, None, "2024-01-01")
        assert dir_ == "BUY"   # 72.1 >= 72

    def test_vix_exactly_14_uses_elevated_floor(self):
        """VIX=14.0 uses VIX_ELEVATED_FLOOR=72 (>= 14.0 condition)."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 71.9, 14.0, None, "2024-01-01")
        assert dir_ == "HOLD"  # 71.9 < 72

    def test_vix_below_14_uses_normal_floor(self):
        """VIX=13.9 uses config.CONVICTION_FLOOR=65."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 64.9, 13.9, None, "2024-01-01")
        assert dir_ == "HOLD"  # 64.9 < 65

        dir_, _ = self.engine._apply_vix_event_gate("BUY", 65.1, 13.9, None, "2024-01-01")
        assert dir_ == "BUY"   # 65.1 >= 65
```

**Run tests:**
```bash
cd backend && pytest tests/test_vix_gate.py -v
```

---

## Phase 4 — Final Verification

### Checklist

**After Phase 1:**
- [ ] `options_pnl.py` module docstring says ₹20,000 (not ₹10,000)
- [ ] Both `max_affordable_lots()` and `compute_options_pnl()` default `capital=20_000.0`
- [ ] `bt_v3_run.py` line 181: `actual_move = actual_move_pct` (no negation)
- [ ] Run a quick 1-month backtest (Aug 2024) and confirm SELL trade P&L signs
  are consistent with WIN/LOSS labels
- [ ] Startup warning fires when CORS is localhost-only + RAILWAY_ENVIRONMENT set

**After Phase 2:**
- [ ] `grep -n "_call_agent_with_retry" backend/app/engine/backtest_engine.py` → 2 hits
- [ ] `max_affordable_lots(161.0, 25)` returns `5` (not `1`)
- [ ] Startup warning fires when DB path is not under `/app/data` + prod env

**After Phase 3:**
- [ ] `config.py` agent weights block has a comment explaining the 8-agent change
- [ ] `CLAUDE.md` Constraints section shows 8-agent weights
- [ ] `is_pre_event_blackout("2024-06-02")` returns True (2 days before Jun 4)
- [ ] `pytest backend/tests/test_vix_gate.py -v` passes all 8 boundary tests

**Final sanity backtest:**
```bash
# Re-run 3-month validation to confirm P&L changes from Task 1.2 and 2.2
python bt_v3_run.py --months 2024-05,2024-08,2024-09 2>&1 | tee bt_v3_run_phase4.log
# Compare totals vs previous run (+₹9,503 from last run)
# SELL trades should now show negative P&L on up-days
```

---

## Execution Order Summary

| Phase | Tasks | Est. Time | Priority |
|-------|-------|-----------|----------|
| 1 | 1.1 Capital fix, 1.2 SELL P&L fix, 1.3 CORS warning | 30 min | 🔴 Critical |
| 2 | 2.1 LLM retry, 2.2 Risk cap, 2.3 DB path warning | 45 min | 🟠 Important |
| 3 | 3.1 Doc 8-agent, 3.2 Blackout lookahead, 3.3 Tests | 30 min | 🟡 Polish |
| 4 | Verification run | 20 min | ✅ Required |

**Do not proceed to Phase 2 until Phase 1 verification passes.** The SELL P&L
fix (Task 1.2) will change backtest numbers — establish the new baseline before
adding more changes.
