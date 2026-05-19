# Plan: Fix options_pnl — Unit Bug + Weekly-First Strategy

**Goal:** Fix the systematically broken P&L model so backtest numbers reflect real tradeable edge.
**Root cause found:** Every trade loses ~₹79 because `nifty_point_move` is passed as a **% value** (e.g. `0.5`) instead of **NIFTY points** (e.g. `110`). The delta gain is 100× too small, so brokerage (₹80) always dominates.

---

## Phase 0: Findings Summary (DONE)

Source files read:
- `backend/app/engine/options_pnl.py`
- `backend/app/engine/backtest_engine.py`
- `bt_v3_run.py`

### Critical Bug — Unit Mismatch

**File:** `bt_v3_run.py` lines 181–192

```python
# actual_move is a % value (e.g. 0.5 for +0.5%)
actual_move = actual_move_pct if direction in buy_dirs else -actual_move_pct

# BUG: passes % directly where function expects NIFTY POINTS
t = compute_options_pnl(
    ...
    nifty_point_move=actual_move,   # ← passes 0.5, not 110 points
    ...
)
```

**Effect:** Delta gain = 0.45 × 0.5 = 0.225 per unit → ₹5.6 per lot → net -₹74 after ₹80 brokerage.
**Fix:** `nifty_point_move=actual_move * nifty_close / 100`

### Secondary Issue — DTE Selection Too Conservative

`select_dte()` returns 20 DTE (monthly) unless conviction ≥ 75. Most signals are 65–74 conviction, so they get 20 DTE. Monthly ATM premiums (~₹320) are expensive and too slow for 1-day close-to-close holds. Weekly (5 DTE) are cheaper and have better gamma for intraday/overnight holds.

**Fix:** Default to 5 DTE for this strategy; drop the conviction gate on DTE.

### Other Known Issues (lower priority)
- `ATM_DELTA = 0.45` hardcoded — no gamma adjustment
- No theta decay modeled for multi-day holds
- FII/DII fallback: `momentum × 1500/-800` magic numbers
- `max_affordable_lots` may allow trades beyond 30% risk cap

---

## Phase 1: Fix Unit Mismatch in bt_v3_run.py

**File to edit:** `bt_v3_run.py`
**Change:** One line — convert % to points before passing to `compute_options_pnl`.

```python
# BEFORE (line 192):
nifty_point_move=actual_move,

# AFTER:
nifty_point_move=actual_move * nifty_close / 100,
```

Where `nifty_close` is the T+1 close already in scope (used for `actual_move_pct` computation).

**Verification:**
- A +0.5% move with NIFTY at 22,000 → passes 110.0 (not 0.5)
- Delta gain: 0.45 × 110 = 49.5 per unit → ₹1,237 gross per lot → ~+₹1,157 net ✓
- A -0.5% wrong call → (−49.5) × 25 = -₹1,237 → stop-loss caps at 25% = -₹80 per unit = -₹2,000 + ₹80 brok
- Check that HOLD days still return ₹0 (no change needed)

**Anti-patterns:**
- Do NOT change `options_pnl.py` in this phase — isolate the bug fix
- Do NOT change the display `pnl_pts` line (that one already uses ×220 correctly)

---

## Phase 2: Weekly-First DTE in options_pnl.py

**File to edit:** `backend/app/engine/options_pnl.py`
**Change:** `select_dte()` — always return 5 DTE for this close-to-close strategy.

```python
# BEFORE:
def select_dte(conviction: float) -> int:
    return WEEKLY_DTE if conviction >= WEEKLY_CONVICTION_THRESHOLD else MONTHLY_DTE

# AFTER:
def select_dte(conviction: float) -> int:
    """
    Always weekly (5 DTE) for close-to-close 1-day hold strategy.
    Monthly options are too expensive relative to overnight moves.
    """
    return WEEKLY_DTE  # 5
```

**Why:**
- 5 DTE premium ~₹160 → 1 lot = ₹4,000 → fits in 30% of ₹20K capital
- 20 DTE premium ~₹320 → 1 lot = ₹8,000 → exceeds 30% risk budget (₹6,000)
- For a 1-day hold, theta difference between 5 and 20 DTE is minimal (we exit next day)

**Verification:**
- `select_dte(65.0)` returns 5
- `select_dte(76.0)` returns 5
- `estimate_atm_premium(22000, 13.0, 5)` ≈ 160–165
- 1 lot cost = 160 × 25 = ₹4,000 ≤ ₹6,000 (30% of ₹20K) → affordable ✓

**Anti-patterns:**
- Do NOT remove `MONTHLY_DTE` constant (keep for future reference)
- Do NOT change `estimate_atm_premium()` formula in this phase

---

## Phase 3: Re-Run 3-Month Validation

**Command (same as bt_v3_run):**
```bash
cd /path/to/gods-eye/backend
set -a && source .env && set +a
export GODS_EYE_DB_PATH=/tmp/gods_eye_bt_v2.db
PYTHONUNBUFFERED=1 python3 -u ../bt_v3_run.py > ../bt_v3_run_fixed.log 2>&1 &
```

**Expected outcomes after fix:**
- Winning trades (direction correct + move > 0.1%) → positive ₹P&L
- Losing trades (wrong direction) → capped at stop-loss
- Aug-2024 win rate was 73% — should produce net positive month after fix
- Sep-2024 win rate was 43% — likely still negative but less so

**Verification checklist:**
- At least 1 trade with positive ₹P&L
- Aug-2024: with 73% win rate and ~1,157 avg gain vs ~1,000 avg loss → expect positive
- Sep-2024: 43% win rate → near break-even or slight loss
- May-2024: VIX gate still blocks most days → minimal trades, small loss/gain

---

## Phase 4: Full FY2024-25 Backtest

After Phase 3 validates the fix on 3 months:

1. Extend `bt_v3_run.py` (or write `bt_full_run.py`) to cover Apr-2024 → Mar-2025
2. Compare full-year P&L vs the original `-₹29,430` baseline from Phase 1 profitability plan
3. Target: break-even or better over full year with VIX gate + event blackout + fixed options_pnl

---

## Decision Point After Phase 3

| Result | Next Action |
|--------|-------------|
| Aug still losing despite 73% win rate | Options premium model wrong; revisit `estimate_atm_premium()` |
| Win rate accuracy < 50% over 3 months | Direction signal problem; revisit agent weights or conviction threshold |
| P&L positive but marginal | Tighten VIX floor, raise conviction threshold |
| P&L solidly positive | Proceed to Phase 4 full-year run |
