---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Hybrid Trading Engine
status: executing
stopped_at: Completed 11-01-PLAN.md
last_updated: "2026-03-31T19:39:43.503Z"
last_activity: 2026-03-31 -- Phase 11 execution started
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 5
  completed_plans: 4
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-31)

**Core value:** Combine quantitative rules (fast, consistent) with qualitative AI analysis (contextual, explainable) for Nifty/Bank Nifty options.
**Current focus:** Phase 11 — agent-signal-rewrite

## Current Position

Phase: 11 (agent-signal-rewrite) — EXECUTING
Plan: 1 of ?
Status: Executing Phase 11
Last activity: 2026-03-31 -- Phase 11 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity (v2.0 reference):**

- Total plans completed: 11
- Average duration: ~100 sec/plan
- Total execution time: ~18 minutes

**By Phase (v3.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 10 | TBD | - | - |
| 11 | TBD | - | - |
| 12 | TBD | - | - |
| 13 | TBD | - | - |
| 14 | TBD | - | - |
| 15 | TBD | - | - |

*Updated after each plan completion*
| Phase 10 P01 | 190 | 2 tasks | 4 files |
| Phase 10 P02 | 1145 | 2 tasks | 3 files |
| Phase 11 P02 | 2 | 1 tasks | 2 files |
| Phase 11 P01 | 900 | 2 tasks | 5 files |

## Accumulated Context

### Decisions

- [v1.0]: Dhan as sole data source — NSE scraping unreliable; clean errors on failure, no silent fallback
- [v1.0]: Nifty/Bank Nifty options focus — start narrow, prove edge, then expand
- [v1.0]: SQLite at /app/data on Railway — persistent volume, survives redeploys
- [v1.0]: Single worker gunicorn (-w 1) — mutable config singleton breaks multi-worker
- [Phase 05]: DhanFetchError in dhan_client.py so raise site and definition are co-located; historical_store imports from there
- [Phase 05]: BACKFILL_YEARS=2 guarantees 252+ trading days accounting for Indian market holidays
- [Phase 05]: fetched_at column stores fetch timestamp (not price date) — enables same-day cache freshness check
- [Phase 05]: DhanFetchError maps to HTTP 502 (not 500) to signal upstream dependency failure explicitly
- [Phase 05]: Startup backfill uses < 10 row threshold to handle prior partial backfills; Dhan failure logs WARNING not crash
- [Phase 06]: technical_signals.py is a separate module from signal_engine.py — live simulation uses low_fear/high_fear labels; backtest uses low/normal/elevated/high labels. They coexist.
- [Phase 06]: classify_vix_regime raises ValueError on negative VIX — real VIX cannot be negative; makes bad data fail loudly
- [Phase 06]: compute_signals_for_date slices rows using YYYY-MM-DD string comparison (lexicographically correct) to prevent future data leakage
- [Phase 06]: store_oi_snapshot and get_oi_snapshot are sync methods — OI capture is not latency-sensitive, no async needed
- [Phase 06]: Signal endpoint returns oi: null (not 404) when OI snapshot missing — historical dates before capture are valid
- [Phase 06]: No rate limit on GET /market/signals endpoint — called in tight loops by Phase 7 backtest engine
- [Phase 07]: mock_mode saves/restores config.MOCK_MODE via try/finally — clean even on exception
- [Phase 07]: backtest_runs stored in same SQLite file (config.DATABASE_PATH) — no second DB file needed
- [Phase 07]: Next-day lookup from full OHLCV dataset so last signal day is never skipped
- [Phase 07]: cumulative_pnl_points computed in API layer so BacktestEngine stays pure — API owns the equity curve shape
- [Phase 07]: BacktestRunSummary.win_rate_pct convenience field (overall_accuracy * 100) spares Phase 9 dashboard from client-side multiplication
- [Phase 07]: round_history omitted from BacktestDayResponse — heavy field not needed for aggregate dashboard equity curves
- [Phase 08]: SignalScorer.score() is a pure static method — no instance state, no side effects; makes it trivially testable and safe to call from any context
- [Phase 08]: HOLD direction always produces 0 sentiment score regardless of conviction — max score 40, always tier=skip unless 3+ technicals align
- [Phase 08]: ScoreResult uses @dataclass not Pydantic BaseModel — no HTTP boundary at engine layer; dataclass is lighter and appropriate
- [Phase 08]: vars(score_result) converts ScoreResult dataclass to plain dict at engine boundary — JSON-serializable, consistent with asdict() pattern
- [Phase 08]: Optional[SignalScoreSchema] = None on BacktestDayResponse allows pre-Phase-8 persisted runs to deserialise gracefully without 422
- [Phase 08]: Inline VIX classify + PCR-to-OI-sentiment helpers in routes.py simulate handler — no separate module needed for 3-line helpers used in one place
- [Phase 09]: Backtest nav item placed between History and Skills per plan spec (Dashboard > Agents > History > Backtest > Skills > Paper Trading > Settings)
- [Phase 09]: Backtest results area left as placeholder — Plans 02/03 will inject BacktestSummary, StatsPanel, AgentAccuracyTable, EquityCurve, DayDetailModal components
- [Phase 09]: Inline AGENT_LABELS/AGENT_COLORS in AgentAccuracyTable to avoid dependency on constants file
- [Phase 09]: Sample variance (n-1) for Sharpe stddev — handles small backtests; N/A when < 2 active data points
- [Phase 09]: onDayClick wired at LineChart level — chart onClick provides activePayload reliably across all chart areas
- [Phase 09]: DayDetailModal placed before closing Layout tag — z-50 fixed overlay sits above sidebar and scrollable content
- [v3.0 Roadmap]: Quant engine (Phase 10) is standalone — no agent system, no LLM client; designed so FBT rules-only path never touches LLM stack
- [v3.0 Roadmap]: Algo agent (AGENT-05) is pure quant computation inside agent framework — no LLM call, but participates in consensus as a data point
- [v3.0 Roadmap]: LLM validator (Phase 12) is a single post-scoring call; validator cannot flip direction, only reduce conviction or skip
- [v3.0 Roadmap]: Risk rules (Phase 13) are deterministic — VIX-scaled stops and 1.5x target are computed values, not LLM suggestions
- [v3.0 Roadmap]: FBT rules-only backtest target is <10 seconds for 1 year; hybrid target is <5 minutes for 1 month — these are observable success criteria, not aspirational
- [Phase 10]: Bidirectional rules (fii_flow, pcr, rsi, vix, supertrend) use single factor key with side field (buy/sell) to indicate which threshold fired — avoids double-keying and matches Plan 02 import contract
- [Phase 10]: factors dict built for EVERY evaluated rule (threshold_hit=False when rule did not fire) — downstream consumers can inspect all 6 factors without KeyError
- [Phase 10]: Direction boundary: strictly > 50 required (50 == HOLD, 51 == tradeable) — confirmed by plan spec wording
- [Phase 10]: QuantBacktestRequest(BaseModel) used for quant-run POST body — BacktestRunRequest pattern already in schemas.py, typed validation at boundary
- [Phase 10]: factors dict omitted from QuantBacktestDaySchema — keeps bulk payload small while full factors available in-memory if needed later
- [Phase 10]: vix_5d_avg excludes current-day VIX (uses strict d < date filter) — prevents same-day data contamination in 5-day average
- [Phase 11]: supertrend inferred from RSI: RSI > 50 = bearish, else bullish — conservative fallback matching Phase 10 engine intent
- [Phase 11]: conviction = QuantScoreResult.total_score (int cast to float, 0-100) — direct engine output, no rescaling
- [Phase 11]: Phase 11 prompts ignore round_num and other_context parameters — single-pass design; parameters kept in signature for interface compatibility
- [Phase 11]: Retail F&O max pain distance computed inline in Python before interpolation — LLM receives concrete pts-above/below label, not two raw numbers
- [Phase 11]: All Phase 11 agent prompts use explicit IF→THEN decision rules in prompt body — concrete decision tree, not role persona

### Pending Todos

None yet.

### Blockers/Concerns

- [v3.0 Phase 11]: Parallel agent execution requires asyncio.gather or concurrent.futures — existing agent runner may be sequential; plan must audit and rewrite dispatch
- [v3.0 Phase 14]: Hybrid backtest (1 month, ~22 trading days) makes up to 22 validator LLM calls — token cost and latency need benchmarking before declaring <5 min target achievable
- [v3.0 Phase 13]: Max-loss-per-day guard needs a session concept — clarify whether "day" = calendar day, trading session, or user-defined window before implementing

## Session Continuity

Last session: 2026-03-31T19:39:43.498Z
Stopped at: Completed 11-01-PLAN.md
Resume file: None
