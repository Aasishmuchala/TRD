---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Backtesting & Signal Engine
status: verifying
stopped_at: Completed 06-02-PLAN.md
last_updated: "2026-03-30T21:06:07.297Z"
last_activity: 2026-03-30
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 4
  completed_plans: 4
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-31)

**Core value:** Prove God's Eye has a tradeable edge on Nifty/Bank Nifty options before risking real money.
**Current focus:** Phase 06 — technical-signal-engine

## Current Position

Phase: 7
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-03-30

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity (v1.0 reference):**

- Total plans completed: 14
- Average duration: ~2 min/plan
- Total execution time: ~0.5 hours

**By Phase (v2.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 5 | TBD | - | - |
| 6 | TBD | - | - |
| 7 | TBD | - | - |
| 8 | TBD | - | - |
| 9 | TBD | - | - |

*Updated after each plan completion*
| Phase 05 P01 | 3 | 2 tasks | 2 files |
| Phase 05 P02 | 2 | 3 tasks | 2 files |
| Phase 06 P01 | 2 | 1 tasks | 3 files |
| Phase 06 P02 | 5 | 2 tasks | 2 files |

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

### Pending Todos

None yet.

### Blockers/Concerns

- [v2.0 Phase 7]: Backtest replays full 3-round LLM simulation per day — date ranges over ~30 days may be slow or costly; may need batching or a lighter replay mode
- [v2.0 Phase 5]: Dhan historical API rate limits unknown — backfill strategy should be conservative (daily granularity, one instrument at a time)

## Session Continuity

Last session: 2026-03-30T21:02:26.873Z
Stopped at: Completed 06-02-PLAN.md
Resume file: None
