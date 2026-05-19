# Backtest Realism Audit — God's Eye

**Audit scope:** Every backtest script in the repo.
**Audit question:** Are the reported P&L numbers trustworthy enough to deploy real capital?
**Audit posture:** Unflinchingly honest. If a backtest is misleading, this document says so.

**TL;DR verdict at a glance**

| File | Verdict | One-liner |
|---|---|---|
| `bt_v5_year2025.py` | **PARTIAL** | Best P&L model in the repo (`options_pnl.py`) but still missing 80%+ of Indian taxes/fees and has a structurally optimistic fill assumption. |
| `bt_wfo_optimize.py` | **MISLEADING** | Self-admitted p-hacking on 13,800 configs against a single train split with a crude `gross - ₹200/lot` cost model. The "optimised" parameters cannot be trusted. |
| `bt_wfo_capture.py` | **N/A (no P&L)** | Only persists raw pre-gate LLM signals to CSV. Inherits look-ahead profile of `_build_market_input` (mostly clean). |
| `backend/app/engine/backtest_engine.py` | **MISLEADING** | P&L is a 3× leverage point proxy with `# Transaction costs are NOT modeled here` literally in the code (line 864). Sharpe computed on raw index points. |
| `backend/app/engine/quant_backtest.py` | **MISLEADING** | P&L is a synthetic `+50 / -30 points` constant per trade (line 156). It does not simulate a strategy, it simulates an accuracy score. |
| `backend/app/engine/hybrid_backtest.py` | **MISLEADING** | Trades raw NIFTY notional (`lots × LOT_SIZE × actual_move_pts`) with **zero** brokerage, STT, slippage, or options premium dynamics. |

**Headline answer: Can the reported P&L be trusted to within ±20% of live results?**

> **No — and it is not even close.** The headline `bt_v5_year2025.py` "+218%" figure could realistically come in 40–80 percentage points lower in live trading after honest costs, slippage, and the broken fill-timing assumption are corrected. The other five backtests should not be used for capital-allocation decisions at all.

---

## 1. `bt_v5_year2025.py` — Full Year 2025 Backtest

**Role:** Top-of-funnel "is the system profitable" claim. Uses real LLM agents + the comparatively richer `options_pnl.compute_options_pnl()` for P&L.

| Concern | Modeled? | Value/Method | Source line |
|---|---|---|---|
| Brokerage (₹/order or %) | PARTIAL | ₹80 flat round-trip per trade (Dhan/Zerodha proxy). Does **not** scale per lot. | `options_pnl.py:61` (`BROKERAGE_ROUND_TRIP = 80.0`) used at `options_pnl.py:295` |
| STT (Securities Transaction Tax) | **NOT MODELED** | Missing. Options STT is 0.0625% on sell side of premium — material at lot scale. | — (acknowledged in `backtest_engine.py:866` TRD-M4 but not fixed) |
| Exchange transaction fees | **NOT MODELED** | NSE charges ~₹3,500 per crore of premium turnover. | — |
| SEBI fees | **NOT MODELED** | ₹10/crore turnover. | — |
| Stamp duty | **NOT MODELED** | 0.003% on buy side for options. | — |
| GST on charges | **NOT MODELED** | 18% on (brokerage + exchange + SEBI). | — |
| Bid-ask spread | **NOT MODELED** | Premium is computed deterministically from `spot × σ × √T × 0.4`. No spread cost. | `options_pnl.py:146-168` `estimate_atm_premium` |
| Slippage (% or points) | **NOT MODELED** | Entry and exit both at theoretical fair value. | — |
| Market impact (size-aware) | **NOT MODELED** | Caps at 20 lots (`options_pnl.py:223`) but no impact cost. | — |
| Look-ahead avoidance | MOSTLY OK | Signal builds from rows `<= signal_date` (`backtest_engine.py:513-519`). Event calendar uses `exclude_shocks=True` to avoid macro lookahead (line 586). | `backtest_engine.py:513`, `586` |
| Survivorship bias | N/A | Only trades NIFTY index — no constituent universe. | — |
| Realistic fill timing | **NO — STRUCTURAL ISSUE** | Signal computed from T's close (3:30 PM data); entry assumed at T's close via MOC (3:29 PM). This is temporally impossible — agent calls take 24+ seconds of ramp alone (line 23) and the LLM signal is not available until after 3:30 PM. Real fill would be next day's open. The overnight gap is currently booked as profit. | `bt_v5_year2025.py:128-130`, `185`; `backtest_engine.py:278-283` |
| Out-of-sample / walk-forward | PARTIAL | 2025 is a held-out validation year vs. the 2023-2024 WFO-tuned gate parameters. However, the rest of the system (agent weights, conviction floors, NEWS_EVENT veto threshold) was developed iteratively against the same 2025 data. | `backtest_engine.py:632-637` |
| Multiple-testing correction | **NOT MODELED** | No deflated Sharpe. Reported Sharpe is raw. | — |
| Position sizing | Risk-budget | `max_affordable_lots` solves for max lots s.t. 10% max-loss + ₹80 brokerage ≤ capital. Conviction does **not** scale sizing here (unlike `bt_wfo_optimize`). | `options_pnl.py:182-226` |
| Stop-loss applied during backtest | YES (premium-based) | 25% premium stop: option exits at `entry × 0.75` floor. Applied as a `max()` floor on exit premium — not as an intraday trigger. | `options_pnl.py:76, 279-290` |
| Options-specific: IV smile, OI liquidity | **NOT MODELED** | ATM premium uses a single fixed delta (0.45) and a constant 0.4 scaler. No skew, no smile, no OI check, no liquidity filter. Gamma ignored — flagged in TRD-M10 comment. | `options_pnl.py:64-70, 146-168` |
| Holiday/weekend handling | Implicit | Iterates over actual trading days returned by `historical_store.get_ohlcv` — non-trading days are absent from the dataset. ✓ | `bt_v5_year2025.py:117-127` |

**Additional concerns specific to this file:**

- ATM delta is **constant 0.45** and exit premium is `entry + delta × point_move` (`options_pnl.py:283`). This linearises an option's payoff and ignores gamma, theta (no time decay for the overnight hold), and vega.
- "Correctness" threshold is 0.1% (`backtest_engine.py:56`) — explicitly flagged in code as below round-trip costs (TRD-L1).
- Conviction comes from real LLM agent runs — there is no in-sample fitting *within this script*, but the agent prompts, weights, and gate parameters were all tuned offline.

**Verdict:** **PARTIAL.** This is the most defensible backtest in the repo but its headline P&L should be deflated by **15–25 percentage points for missing fees/STT/slippage**, and the close-to-close fill model is structurally optimistic by another **10–20 percentage points** depending on overnight gap behaviour in 2025.

---

## 2. `bt_wfo_optimize.py` — Grid-Search Gate Parameters

**Role:** Replays captured 2023-2024 LLM signals through ~13,800 gate-parameter combinations and picks the "best" Sharpe.

| Concern | Modeled? | Value/Method | Source line |
|---|---|---|---|
| Brokerage | PARTIAL | `cost = 200 * lots` flat, comment says "slippage + brokerage ~₹200/lot round-trip". | `bt_wfo_optimize.py:116-118` |
| STT | **NOT MODELED** | — | — |
| Exchange transaction fees | **NOT MODELED** | — | — |
| SEBI fees | **NOT MODELED** | — | — |
| Stamp duty | **NOT MODELED** | — | — |
| GST on charges | **NOT MODELED** | — | — |
| Bid-ask spread | **NOT MODELED** | — | — |
| Slippage | LUMPED into the ₹200/lot cost — not a separate model. | `bt_wfo_optimize.py:116` |  |
| Market impact (size-aware) | **NOT MODELED** | — | — |
| Look-ahead avoidance | OK at signal layer (signals are from capture phase) but the *optimisation* loop sees all 2023-2024 outcomes simultaneously — that's the p-hacking attack surface. | `bt_wfo_optimize.py:127-150` |
| Survivorship bias | N/A | NIFTY only. | — |
| Realistic fill timing | **NO** | Uses `actual_nifty_pct` from the capture (close-to-close). Inherits the same fill problem as `bt_v5`. | `bt_wfo_capture.py:154` |
| Out-of-sample / walk-forward | **NOT MODELED — DESPITE THE NAME** | Self-admitted in docstring: *"This is not true walk-forward optimization. The train window (2023-2024) and validation window (2025) are fixed."* TRD-H4 ON HOLD. | `bt_wfo_optimize.py:12-17` |
| Multiple-testing correction | **NOT MODELED — SELF-ADMITTED** | Docstring: *"P-hacking risk — the grid search evaluates ~13,800 parameter combinations on a single train/test split."* TRD-H5 ON HOLD. | `bt_wfo_optimize.py:19-23` |
| Position sizing | Fixed risk pct | `RISK_PCT = 0.10` of capital; lots = `int(max_risk / max_loss_per_lot)`; conviction scaler `min(1.0, conviction/90)` on gross P&L. | `bt_wfo_optimize.py:91-114` |
| Stop-loss applied | PARTIAL | `max(-atm_entry, point_move * 0.7)` caps loss at premium paid — a degenerate "stop". | `bt_wfo_optimize.py:111-114` |
| Options-specific: IV smile, OI liquidity | **NOT MODELED** | `iv_adj = max(1.0, vix/20.0)`; `atm_entry = nifty_close * 0.01 * iv_adj` — extremely crude. | `bt_wfo_optimize.py:94-96` |
| Holiday/weekend handling | Implicit (inherits capture) | — | — |

**Critical concerns:**

- The P&L approximator (`approx_options_pnl`) is **not** the same engine as `options_pnl.compute_options_pnl()` used by `bt_v5_year2025.py`. The two diverge in entry premium model, sizing logic, and cost model. Parameters "optimal" under the approximator may not be optimal under the production engine.
- Sharpe formula on line 159: `(avg/std) * sqrt(252 / max(1, len(signals)))`. This is **mathematically wrong** for annualisation when iterating over `trades` (not days). It under-annualises Sharpe when selectivity is high.
- The selection criterion is "Sharpe with P&L tiebreak". With ~13,800 configurations on one fixed test window, the top-1 Sharpe is heavily inflated by selection bias. With no Bonferroni / White's Reality Check / SPA / deflated Sharpe, **the "best" config's expected out-of-sample performance is much lower than reported**.

**Verdict:** **MISLEADING.** The script's own docstring warns about this. Treat the "recommended parameters" output as a hypothesis to be validated, not a result.

---

## 3. `bt_wfo_capture.py` — Capture Pre-Gate LLM Signals

**Role:** Persistence-only script. Runs agents per day in 2023-2024 and writes raw pre-gate consensus (direction, conviction, VIX, context) to CSV.

| Concern | Modeled? | Value/Method | Source line |
|---|---|---|---|
| Brokerage | N/A (no P&L computed) | — | — |
| STT | N/A | — | — |
| Exchange fees | N/A | — | — |
| SEBI fees | N/A | — | — |
| Stamp duty | N/A | — | — |
| GST | N/A | — | — |
| Bid-ask spread | N/A | — | — |
| Slippage | N/A | — | — |
| Market impact | N/A | — | — |
| Look-ahead avoidance | OK | Uses `_build_market_input(row, vix_map, all_ohlcv)` which slices to `<= signal_date`. `actual_nifty_pct` is forward-looking but stored separately as ground truth, not fed back to the agent. | `bt_wfo_capture.py:157, 152-154` |
| Survivorship bias | N/A | NIFTY index only. | — |
| Realistic fill timing | N/A (only captures signals) | `nifty_close`/`nifty_next_close` columns enable downstream close-to-close P&L, which is the same optimistic fill profile as elsewhere. | `bt_wfo_capture.py:181-191` |
| Out-of-sample / walk-forward | N/A | — | — |
| Multiple-testing correction | N/A | — | — |
| Position sizing | N/A | — | — |
| Stop-loss | N/A | — | — |
| Options: IV smile, OI liquidity | N/A | — | — |
| Holiday/weekend handling | Implicit via DB iteration | — | `bt_wfo_capture.py:116-120` |

**Concern:** Resume logic (`done_dates` from existing CSV at line 101-106) is safe but does **not** validate that captured rows came from the same model/prompt version. If you re-run after changing the agent prompt, you will silently mix two distributions of signals. There is no `model_version` or `prompt_hash` column in `CSV_FIELDS` (line 46-49). This is a data-hygiene risk for the WFO downstream.

**Verdict:** **PARTIAL** (acceptable for its narrow role; no P&L claims to challenge). Add `model_id`/`prompt_hash` columns before treating this CSV as a long-lived asset.

---

## 4. `backend/app/engine/backtest_engine.py` — Production Engine (Mock-Era P&L)

**Role:** The reusable engine class consumed by API routes and the WFO/full-year scripts for the *simulation step*. **Its own internal `_compute_pnl` is the proxy that other scripts often bypass** (e.g. `bt_v5_year2025.py` calls `compute_options_pnl` instead). But the engine's `BacktestRunResult.total_pnl_points` and Sharpe are still surfaced by the `/backtest/run` API.

| Concern | Modeled? | Value/Method | Source line |
|---|---|---|---|
| Brokerage | **NOT MODELED** | Explicit comment: *"Transaction costs are NOT modeled here."* | `backtest_engine.py:864-870` (TRD-M4) |
| STT | **NOT MODELED** | Acknowledged in same comment. | `backtest_engine.py:866` |
| Exchange transaction fees | **NOT MODELED** | — | — |
| SEBI fees | **NOT MODELED** | — | — |
| Stamp duty | **NOT MODELED** | — | — |
| GST | **NOT MODELED** | — | — |
| Bid-ask spread | **NOT MODELED** | — | — |
| Slippage | **NOT MODELED** | Acknowledged in TRD-M4 comment. | `backtest_engine.py:867` |
| Market impact | **NOT MODELED** | — | — |
| Look-ahead avoidance | MOSTLY OK | Signals computed from `<= signal_date`. Event calendar uses `exclude_shocks=True` (line 586). FII/DII pulled point-in-time. Hardcoded `usd_inr=84.0` and `dxy=103.0` (lines 615-616) — TRD-L5 acknowledges these should be historical. | `backtest_engine.py:513-519, 586, 615` |
| Survivorship bias | N/A for index | — | — |
| Realistic fill timing | **NO — STRUCTURAL** | Same problem: `entry_price = nifty_close` (T's close) + `actual_move_pct = (T+1 close − T close) / T close`. Docstring claims "MOC entry at 3:29 PM" but the LLM signal cannot exist before 3:30 PM. | `backtest_engine.py:192-196, 278-283` |
| Out-of-sample / walk-forward | NO | Same date range used end-to-end. | — |
| Multiple-testing correction | **NOT MODELED** | Sharpe is raw, computed on point P&L not %. | `backtest_engine.py:951-977` (TRD-M6 comment acknowledges this distortion) |
| Position sizing | Fixed 1-lot (implicit) | `_compute_pnl` is `actual_move_pct × 3 × (close/100)` — leverage proxy, not a sized trade. | `backtest_engine.py:872-877` |
| Stop-loss applied | YES (configurable) | `StopLossEngine.compute_stop_for_day` with ATR/percent. Gap-open stop checked at T+1 open; intraday stop checked against T+1 high/low. P&L overridden when hit. | `backtest_engine.py:337-388` |
| Options: IV smile, OI liquidity | **NOT MODELED** | The 3× leverage is a degenerate options proxy. | `backtest_engine.py:58-59, 872-877` |
| Holiday/weekend handling | Implicit via DB | — | `backtest_engine.py:255-271` |

**Critical concerns:**

- `_compute_pnl` at line 855-877 is essentially `(actual_move_pct × 3 × close/100)` — a leveraged point proxy with **no cost, no premium dynamics, no theta, no gamma**. Any API consumer that reads `total_pnl_points` from `BacktestRunResult` is reading a fantasy number.
- Sharpe ratio (line 951-977) is computed on raw index points, not returns. TRD-M6 acknowledges this. A favourable bull-market period inflates Sharpe purely by the index level rising.
- Globals mutation pattern (line 242-250 + line 428-432 restore) is documented as not thread-safe — fine for `--workers 1` deployment but a footgun.
- Consensus algorithm (line 664-761) diverges from `aggregator.py`'s live algorithm (TRD-H2 acknowledged). **The backtest is not testing the same logic as production.**

**Verdict:** **MISLEADING** when consumed via its native P&L. The engine is useful as a *signal generator* but its `total_pnl_points`/`sharpe_ratio` outputs are not investible numbers.

---

## 5. `backend/app/engine/quant_backtest.py` — Quant-Only Backtest

**Role:** Rules-only, deterministic, fast (250 days in <10s). Used for unit tests and quick sanity checks.

| Concern | Modeled? | Value/Method | Source line |
|---|---|---|---|
| Brokerage | **NOT MODELED** | — | — |
| STT | **NOT MODELED** | — | — |
| Exchange fees | **NOT MODELED** | — | — |
| SEBI fees | **NOT MODELED** | — | — |
| Stamp duty | **NOT MODELED** | — | — |
| GST | **NOT MODELED** | — | — |
| Bid-ask spread | **NOT MODELED** | — | — |
| Slippage | **NOT MODELED** | — | — |
| Market impact | **NOT MODELED** | — | — |
| Look-ahead avoidance | OK | `closes_up_to = [r['close'] for r in all_rows if r['date'] <= date]` and `prev_vix = [... if d < date]` (strict). Signal uses today's close, outcome uses next-day close. | `quant_backtest.py:109-110, 119` |
| Survivorship bias | N/A | — | — |
| Realistic fill timing | UNCLEAR | Signal from T close → outcome is `next_close/today_close − 1` (close-to-close). Same optimistic profile. | `quant_backtest.py:141-146` |
| Out-of-sample / walk-forward | **NOT MODELED** | Single pass over date range. | — |
| Multiple-testing correction | **NOT MODELED** | No statistics computed beyond win-rate. | — |
| Position sizing | **SYNTHETIC** | **P&L is hardcoded `+50 points if correct else -30 points`.** This is not a strategy — it is a per-trade accuracy proxy with arbitrary asymmetric reward. | `quant_backtest.py:156` |
| Stop-loss applied | **NOT MODELED** | — | — |
| Options: IV smile, OI liquidity | **NOT MODELED** | — | — |
| Holiday/weekend handling | Implicit via DB | — | — |

**Critical concern:** The P&L at line 156 is *literally* `pnl_points = 50.0 if is_correct else -30.0`. This means `total_pnl_points` is a function of win rate only, with hardcoded payoffs. It does not correspond to any tradeable strategy. Any number reported by this engine is **not a P&L** — it is a "win-rate × 50 − loss-rate × 30" scaled score. **Do not treat as money.**

Also: FII/DII are *synthesised from 5-day momentum* (`fii_net_cr=momentum_5d * 1500`, line 130) rather than pulled from the FII/DII store like `backtest_engine.py` does. This makes the "quant" backtest a function of price alone — it cannot validate any FII/DII edge claim.

**Verdict:** **MISLEADING** if interpreted as P&L. Acceptable as a development-time sanity check on the rules engine.

---

## 6. `backend/app/engine/hybrid_backtest.py` — Quant + LLM + Validator + RiskManager

**Role:** Full daily pipeline. Runs quant score → 6 parallel agents → HybridScorer → LLMValidator → RiskManager and produces a "risk-adjusted P&L".

| Concern | Modeled? | Value/Method | Source line |
|---|---|---|---|
| Brokerage | **NOT MODELED** | — | — |
| STT | **NOT MODELED** | — | — |
| Exchange fees | **NOT MODELED** | — | — |
| SEBI fees | **NOT MODELED** | — | — |
| Stamp duty | **NOT MODELED** | — | — |
| GST | **NOT MODELED** | — | — |
| Bid-ask spread | **NOT MODELED** | — | — |
| Slippage | **NOT MODELED** | — | — |
| Market impact | **NOT MODELED** | RiskManager sizes lots but no impact cost on entry/exit. | — |
| Look-ahead avoidance | OK | Same `<= date` slicing; strict `d < date` for VIX 5-day avg. | `hybrid_backtest.py:140-152` |
| Survivorship bias | N/A | — | — |
| Realistic fill timing | **NO** | `actual_move_pct = (next_close/nifty_close − 1) * 100`. P&L = `actual_move_pts × lots × LOT_SIZE`. Same close-to-close fudge — **and worse**, because it books the full notional gap as profit. | `hybrid_backtest.py:213-218, 241-245` |
| Out-of-sample / walk-forward | **NOT MODELED** | — | — |
| Multiple-testing correction | **NOT MODELED** | Sharpe/drawdown/win-loss ratio are reported but never deflated. | `hybrid_backtest.py:265-305` |
| Position sizing | Tier-driven | `RiskManager.compute(tier, direction, nifty_close, vix)` returns `lots`. | `hybrid_backtest.py:239` |
| Stop-loss applied | **NOT MODELED IN P&L** | RiskManager produces stop/target but they are not checked against next-day high/low. | — |
| Options: IV smile, OI liquidity | **NOT MODELED — AND NOT EVEN OPTIONS** | P&L treats trade as buying *spot NIFTY* sized by option lot count. This is structurally wrong for an options system: no premium paid, no premium decay, no delta, no IV. | `hybrid_backtest.py:241-245` |
| Holiday/weekend handling | Implicit via DB | — | — |

**Critical concerns:**

- P&L formula at line 243: `pnl_points = actual_move_pts * lots * NIFTY_LOT` is the **underlying** point move times lot count times lot size. For a BUY signal with a +50-pt NIFTY move at 2 lots, this books `50 × 2 × 25 = 2,500 points`. In options reality, you would have paid ~₹4,000/lot premium, captured ~22 points of premium gain (delta 0.45 × 50), netted ~₹550/lot, and paid ₹80 + STT + GST. The hybrid backtest's reported P&L is overstated by an order of magnitude for options trading.
- FII/DII are still synthesised from momentum (line 163-164) — same flaw as `quant_backtest.py`.
- Validator is wrapped in try/except → confirm fallback (line 200-208). When the validator silently degrades to "confirm", you may not notice in the result aggregate.

**Verdict:** **MISLEADING.** The P&L formula does not model the instrument the system claims to trade. The win rate may be informative; the rupee P&L is not.

---

## Top 5 Fixes (Ordered by Impact on Realism)

1. **Move signal from T-close to T+1-open (fix the fill-timing fiction).** Currently every backtest computes the signal from T's close *and* enters at T's close. In production the LLM signal will not exist until after T's close (post 3:30 PM IST), so the realistic entry is T+1 open. Re-running `bt_v5_year2025.py` with this change will almost certainly remove a large fraction of the headline P&L — the overnight gap is currently free money in the backtest. **Estimated impact: 10–25 percentage points of annual return.**

2. **Implement a full Indian cost model in `options_pnl.py`.** Add: STT (0.0625% on sell premium), NSE exchange fees (~₹3,500/cr premium turnover), SEBI fee (₹10/cr), stamp duty (0.003% on buy notional), GST (18% on brokerage+exchange+SEBI). Also model slippage as 1–2% of premium for ATM weeklies (wider near events). Backport into `compute_options_pnl`. **Estimated impact: 8–18 percentage points of annual return.**

3. **Replace `_compute_pnl` (3×-leverage point proxy), `quant_backtest._compute_pnl` (`+50/-30`), and `hybrid_backtest` notional formula with calls into `compute_options_pnl`.** Right now the engine consumed by the API surfaces P&L numbers that don't correspond to any tradeable strategy. **Estimated impact: deletes a class of false confidence; aligns API outputs with the only honest P&L path in the repo.**

4. **Fix the WFO process: rolling-window train/validate + multiple-testing correction.** Current `bt_wfo_optimize.py` is grid search on a single fixed train split (2023-2024) and a single fixed test (2025). Implement (a) walk-forward expanding windows, (b) deflated Sharpe ratio (López de Prado) or White's Reality Check before declaring a "best" config. The current "WFO-optimised" parameters baked into `backtest_engine.py:632-637` should be regarded as provisional until this is done. **Estimated impact: re-evaluates whether the +218% number is real or selection bias.**

5. **Add a Black-Scholes (or local-vol) option pricing model with vega/theta/gamma, and an OI/liquidity gate.** The current `estimate_atm_premium = spot × σ × √T × 0.4` plus a fixed 0.45 delta misses: smile/skew, theta decay over the overnight hold (~5–7% premium burn on a weekly), and OI/depth filtering. Without this, P&L on volatile or event days is unreliable. **Estimated impact: tightens realism in the 20% of trading days that contribute most of the variance.**

---

## One-Line Trust Answer

> **NO — the reported P&L cannot be trusted to within ±20% of live results.** The best backtest (`bt_v5_year2025.py`) is plausibly within ±40–60 percentage points after correcting for missing Indian transaction costs (~5–10% drag annually), missing slippage/spread on weekly options (~3–6%), and the structurally optimistic same-bar fill (~10–20% of the gap-captured P&L), and even that depends on whether the WFO parameters survive a proper walk-forward + deflated-Sharpe validation. **To get to ±20% confidence:** implement Fixes #1, #2, and #4 above and re-run the full year. Until then, treat all reported P&L as upper bounds, not expected outcomes.

---

*Audit produced by reading the full source of all six files. Line numbers reference the versions of those files as of this commit. Where the code itself flags a known issue (TRD-Mxx, TRD-Hxx comments), this document quotes the relevant line so the owner can cross-check.*
