# God's Eye — Live Roadmap

This is the **one** living roadmap. All historical plan docs are in `docs/archive/`
and `gods-eye/docs/archive/` for reference but should not be treated as current.

## Status snapshot (auto-updated by cleanup-and-harden branch)

- Backend: FastAPI + SQLite, 23K LOC Python, 8 agents (6 LLM + quant + news/options)
- Frontend: React + Vite, 8K LOC, 7 pages
- Backtest engines: `bt_v5_year2025.py` (current), `bt_wfo_optimize.py` (WFO),
  `bt_wfo_capture.py`. Older generations archived under
  `gods-eye/archive/backtests/`.
- Deployment surfaces: Cloudflare Workers proxy + Vercel proxy + Docker compose.

## Phases (current)

### Phase A — Correctness (in progress on cleanup-and-harden branch)
- [x] Repo housekeeping: build artifacts purged, tests relocated, old backtests
      archived, plan-doc sprawl consolidated.
- [ ] Split `api/routes.py` (2071 lines) into per-resource modules.
- [ ] Fix 9 pre-existing failing tests (`test_aggregator`, `test_backtest_engine`,
      `test_health`, `test_vix_gate`, `test_vix_regime_filter`).
- [ ] Property-based tests on risk_manager, stop_loss_engine, aggregator.
- [ ] Backtest realism audit → `docs/backtest_assumptions.md`.

### Phase B — Performance
- [ ] Parallelize agents within a round (asyncio.gather).
- [ ] Cache identical (scenario, market_context) → agent output for N seconds.
- [ ] Tier the model: cheap model for Round 1 surveying, premium only Round 3.
- [ ] Log $/simulation and ms/simulation as first-class metrics.

### Phase C — Observability
- [ ] Prometheus `/metrics` endpoint.
- [ ] Structured logs with request_id correlation.
- [ ] Live-vs-backtest signal divergence alert.

### Phase D — Real-money gate (NEVER cross without satisfying every item in
      `docs/REAL_MONEY_GATE.md`).

## Decision log

Use `docs/decisions/NNNN-<slug>.md` ADR format for new architectural decisions.
Don't open new PLAN_*.md files at the repo root.
