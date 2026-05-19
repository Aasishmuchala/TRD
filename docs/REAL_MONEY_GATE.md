# REAL MONEY GATE

> **Read this before you connect this system to a real brokerage account.**
>
> This document exists because the agent that did the cleanup-and-harden
> pass refused to flip the live-trading switch in code. The reason: based
> on the audit in `docs/backtest_assumptions.md`, the reported backtest
> P&L cannot be trusted within ±20% of live results today. Every item on
> this list must be honestly true before you risk capital.

## How to use this gate

This is not a checklist you tick to feel good. It is a contract with
yourself. Each section has **objective, verifiable criteria** — you must
be able to point at evidence (test output, log file, broker statement)
that satisfies the criterion. If you can't point at evidence, the gate
is closed.

If you skip any section, you are gambling, not trading. That's a personal
choice. Be honest with yourself about which one you're doing.

---

## Section 1 — Backtest realism (load-bearing)

Status from latest audit (commit on cleanup-and-harden branch): **CLOSED**.

- [ ] Every cost in `docs/backtest_assumptions.md` rows 1–6 is modeled with
      a real value or has an explicit, justified zero (e.g. "free of stamp
      duty for intraday equity in state X" with a regulator source link).
      Brokerage / STT / exchange fees / SEBI / stamp / GST.
- [ ] Bid-ask spread is modeled. For options, this is non-negotiable — a
      ₹2 spread on a ₹100 premium is 2% per round-trip.
- [ ] Slippage is modeled (at minimum ½ × spread; ideally size-aware).
- [ ] Fill timing is realistic: signal at T close → entry at T+1 open
      (with T+1 open price, not T close). NO same-bar fills.
- [ ] Stop-loss is applied **inside** the backtest day-loop using the
      day's intraday high/low, not at the next-day close.
- [ ] Walk-forward is genuinely out-of-sample: the test fold has NEVER
      been touched during parameter selection. If you ran
      `bt_wfo_optimize.py` against 2024 and got "best params" — those
      params overfit 2024 and need to be re-validated on a held-out 2025
      fold that the optimizer never saw.
- [ ] Deflated Sharpe / multiple-testing correction applied. If you tried
      N parameter sets, your reported Sharpe must be reduced by the
      Bailey–López de Prado deflation. The raw maximum is misleading.
- [ ] Position sizing matches what you will actually do live. If you
      backtested 1 lot per signal but plan to deploy with Kelly sizing,
      you do not have a backtest of your live strategy.

**Closed until:** every item above is checked AND a fresh backtest with
all costs/slippage/fill timing modeled produces a Sharpe ≥ 1.0 AND a max
drawdown ≤ your personal risk tolerance, on a 2025 out-of-sample period
the optimizer never saw.

---

## Section 2 — Code correctness

Status: **OPEN with caveats** (see below).

- [x] Full test suite passes: 193 passed, 2 xfailed.
- [x] Property tests cover risk_manager, stop_loss_engine, aggregator
      (the three money-losing modules).
- [x] Two rounding-precision bugs in stop_loss_engine.py found and fixed
      by property tests on this branch.
- [ ] The two xfailed tests (Sharpe/MDD/win-loss-ratio on
      QuantBacktestRunResult; `lots` field on QuantBacktestDayResult) are
      either implemented or formally removed from the public contract.
- [ ] A second property-test pass on `live_trader.py`, `paper_trader.py`,
      `options_pnl.py`, `daily_loss_guard.py`. Not yet written.
- [ ] CI enforces test pass + coverage ≥ 80% on `app/engine/`. Not yet
      configured.

**Closed until:** the unchecked items here are addressed. Property tests
on live/paper trader and the daily loss guard are the minimum bar — these
are the modules that move money when you wire up a broker.

---

## Section 3 — Operational readiness

Status: **CLOSED** (none of this is built).

- [ ] **Kill switch.** A single command (CLI flag, ENV var, Redis key) that
      forces the live trader into HOLD-only mode without restarting. Tested
      end-to-end.
- [ ] **Daily loss guard.** Halts trading for the day at a fixed % drawdown.
      Already exists in code as `daily_loss_guard.py` — must be enabled,
      configured with YOUR personal threshold (default 1.5%? 2%? you
      decide), and tested by injecting a synthetic losing day.
- [ ] **Position size cap per trade.** A hard ceiling (₹ or % of capital)
      no matter what the model says.
- [ ] **Position size cap per day.** Total notional you're willing to be
      exposed to.
- [ ] **Consecutive loss circuit-breaker.** N losing trades in a row →
      auto-halt for 24h. Pick N (3? 5?) before deployment, not during a
      losing streak.
- [ ] **Data freshness gate.** If NIFTY/VIX is older than X seconds at the
      moment of signal generation, refuse to trade. Default: 60 seconds.
- [ ] **Broker failure handling.** Order rejection, partial fill, broker
      down — every case tested in paper mode with simulated failures.
- [ ] **Audit log.** Every signal, every order, every fill, every override —
      append-only, timestamped, content-addressed. You need this for tax,
      for debugging, and (if it ever comes to it) for SEBI.

**Closed until:** every item is implemented, tested, and you've personally
triggered each safety in paper mode at least once.

---

## Section 4 — Personal readiness

Status: **only you can answer**.

- [ ] You have run this in **paper trading for at least 30 consecutive
      market days** (≈ 6 weeks) with the EXACT signal logic and risk
      controls you intend to deploy. Not 30 backtest days — 30 real days
      with real live data, real signal latency, real RBI announcements,
      real expiry weeks.
- [ ] Paper-trading Sharpe on those 30 days matches backtest Sharpe within
      a reasonable band. If paper diverges meaningfully from backtest, the
      backtest is wrong (look-ahead, missing cost, etc.) and Section 1
      reopens.
- [ ] The amount of capital you plan to deploy is **money you can lose
      entirely** without affecting rent, food, family obligations, or your
      mental health. Indian markets close arbitrarily on holidays and
      reopen with gaps. Algos that look brilliant for 5 months blow up in
      week 26.
- [ ] You have a written policy for what you will do when:
      (a) the system is up 50% in a month
      (b) the system is down 20% in a month
      (c) the system has been flat for 3 months
      Write it down BEFORE you deploy. Future-you with skin in the game
      will not think clearly.
- [ ] You understand that this system uses LLMs whose behavior can drift
      between model versions. A silent prompt change on the provider side
      can change your strategy without you noticing. The agent calibration
      eval set (Phase A future work) is the only defense.

---

## Section 5 — Legal / compliance (India-specific)

- [ ] Algorithmic trading on NSE requires broker-approved APIs. Confirm
      your broker (Zerodha Kite, Dhan, Upstox, etc.) permits API-driven
      orders for your account type.
- [ ] If you intend to run this for anyone else's money, even informally,
      you need SEBI registration as an Investment Adviser / Portfolio
      Manager. Don't.
- [ ] Tax: every realized trade is a taxable event. Speculative income vs
      STCG vs business income classification affects your tax bill. Talk
      to a CA before, not after.
- [ ] Data licensing: NSE quote data has redistribution restrictions. The
      frontend that displays live NIFTY to anyone other than you may
      violate your broker's data license. Read the fine print.

---

## The deploy command

There is intentionally no `make deploy-live` target. Real-money trading
requires you to:

1. Re-read this document from the top.
2. Manually flip a config flag (`GODS_EYE_TRADING_MODE=live`) **on a
   machine you are physically present at**.
3. Manually run the live trader with a small `MAX_DAILY_NOTIONAL` for the
   first 5 trading days regardless of what backtest says is optimal.
4. Watch the first live trade fill in real time. If it does anything you
   don't understand, kill the process.

If steps 1–4 feel like friction, that's the point. The friction is the
feature.

---

*Last updated: cleanup-and-harden branch initial commit. Update this
file every time a section's status changes, with the date and the commit
that changed it.*
