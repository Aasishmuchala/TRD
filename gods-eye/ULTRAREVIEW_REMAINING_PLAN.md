# Ultrareview: Remaining ON HOLD Items — Rectification Plan

**Date:** April 17, 2026
**Status:** 91 of 98 findings fixed. 1 excluded (auth gate). 6 remaining.

---

## 1. FE-C3: localStorage → sessionStorage for API Key

**Risk:** Moving to sessionStorage would log users out when opening a new tab.
**Current state:** `localStorage.getItem('godsEyeApiKey')` in client.js, AuthGate.jsx, Welcome.jsx

**Plan (2 hours):**
1. Keep localStorage for the API key (single-user tool, acceptable risk)
2. Add a `beforeunload` listener that clears the key only on browser close (not tab close)
3. Alternative: use an in-memory variable in client.js with a module-level `let apiKey = localStorage.getItem(...)` — reads once on load, never re-reads from storage. This reduces the window for XSS exfiltration while keeping tab persistence.

**Safe to implement:** Yes — no functionality change, just a defense-in-depth wrapper.

---

## 2. FE-L2: React.lazy Code Splitting

**Risk:** React.lazy + Suspense can cause flash-of-loading or break if component structure changes.
**Current state:** All 8 pages eagerly imported in App.jsx (~350KB bundle)

**Plan (1 hour):**
1. Wrap each page import with `React.lazy(() => import('./pages/Dashboard'))` etc.
2. Add a `<Suspense fallback={<div className="flex items-center justify-center h-screen"><div className="animate-spin ...">Loading...</div></div>}>` wrapper around the Routes block
3. Keep ErrorBoundary above Suspense (it catches lazy load failures)
4. Test: Verify each route loads. If any lazy import fails (e.g., circular dependency), revert that specific page to eager import.

**Safe to implement:** Yes — React.lazy is a standard React pattern. Test each route after.

---

## 3. FE-M2: React.memo on Heavy Components

**Risk:** Memoization with wrong comparison can mask state bugs.
**Current state:** Zero React.memo, useMemo, or useCallback in rendering components. Every SSE event re-renders the entire agent grid.

**Plan (1.5 hours):**
1. **Phase 1 (safe):** Add `React.memo` to these pure display components:
   - `AgentPressureBar` — renders once per agent, pure props
   - `DirectionGauge` — pure visualization
   - `BacktestSummary` — static after data loads
   - `EquityCurve` — Recharts component, heavy
2. **Phase 2 (careful):** Add `useMemo` to expensive computations:
   - Dashboard agent grid map — memoize the agent results list
   - SimulationStream event list — already capped at 200, but memoize render
3. **Do NOT memo:** Components with internal state (ScenarioPanel, Settings, PaperTrading)
4. Test: Verify SSE streaming still updates in real-time after memoizing.

**Safe to implement:** Yes, if limited to Phase 1. Phase 2 needs testing.

---

## 4. FE-M6: Coordinate 4 Competing Polling Intervals

**Risk:** Unifying intervals could make some data stale or cause all fetches to fire simultaneously.
**Current state:**
- MarketTicker: 30s
- Dashboard paper trades: 10s
- PaperTrading: 15s
- ScenarioPanel live check: 15s

**Plan (2 hours):**
1. Create a `usePolling(callback, intervalMs)` hook in `hooks/usePolling.js`:
   - Uses `useRef` for the callback (avoids stale closures)
   - Adds ±2s jitter to prevent synchronized fetches
   - Pauses when tab is not visible (`document.hidden`)
   - Accepts a `condition` param to enable/disable
2. Replace all 4 `setInterval` patterns with `usePolling`
3. Standardize intervals: MarketTicker 30s, PaperTrading 15s, Dashboard 15s, ScenarioPanel 30s
4. Add visibility check: no polling when browser tab is backgrounded

**Safe to implement:** Yes — the polling behavior is identical, just better organized. The jitter and visibility pause are strictly improvements.

---

## 5. ARCH-C1: Agent Code Deduplication (6 LLM Agents)

**Risk:** Highest risk item. All 6 LLM agents duplicate ~100 lines of identical logic (_call_llm, _parse_response, _consensus_direction, _fallback_response, analyze). Refactoring could break agent-specific prompt construction.
**Current state:** Each agent overrides only `_build_prompt()`. Everything else is copy-pasted.

**Plan (4 hours, needs thorough testing):**
1. Move these 4 shared methods into `BaseAgent`:
   - `_call_llm(prompt, market_data)` — shared LLM client call with retry
   - `_parse_response(raw_response)` — JSON extraction + direction validation (already standardized in ARCH-H4 fix)
   - `_consensus_direction(directions)` — majority vote
   - `_fallback_response(market_data, error)` — HOLD/25 with error reasoning
2. Move the shared `analyze()` orchestration into BaseAgent:
   ```python
   async def analyze(self, market_data, round_num, other_agents, enriched_context=None):
       if config.MOCK_MODE:
           return self._mock_response(market_data)
       prompt = self._build_prompt(market_data, round_num, other_agents, enriched_context)
       raw = await self._call_llm(prompt, market_data)
       return self._parse_response(raw)
   ```
3. Each agent only keeps:
   - `__init__` with agent_name and agent_type
   - `_build_prompt()` — the unique system prompt
   - `_mock_response()` — agent-specific mock data
4. **Validation:** After refactoring, run a mock simulation and a live simulation. Compare outputs character-by-character with pre-refactor outputs. Any difference → investigate before merging.

**Safe to implement:** Only with a feature branch + testing. Do NOT do this on main directly.

---

## 6. TRD-H2: Unify Consensus Algorithms (aggregator vs backtest)

**Risk:** The WFO optimizer (bt_wfo_optimize.py) was tuned against the backtest's _compute_consensus. Changing the algorithm invalidates all optimized parameters.
**Current state:**
- **aggregator.py** (live): score-based with conviction^0.8 exponent, score normalization
- **backtest_engine.py** (backtest): weight-threshold approach (BUY family vs SELL family, threshold=0.25), no conviction exponent

**Plan (3 hours + WFO re-run):**
1. Extract a shared `compute_consensus(agents_output, weights)` function into a new file `backend/app/engine/consensus.py`
2. This function uses the aggregator's algorithm (score-based with conviction dampening) — it's the more nuanced approach
3. Replace both:
   - `aggregator._standard_aggregate` calls → uses shared consensus
   - `backtest_engine._compute_consensus` → uses shared consensus
4. **Critical:** After unifying, re-run the WFO optimizer to find new optimal parameters against the unified algorithm. The old parameters (HOLD_BAND, CONVICTION_FLOOR, etc.) may need recalibration.
5. Compare backtest results before/after. If win rate drops >5%, keep the old backtest algorithm and add an adapter layer instead.

**Safe to implement:** Only after WFO re-run validates the new parameters. Budget a full day for this.

---

## Recommended Execution Order

| Priority | Item | Effort | Risk | When |
|----------|------|--------|------|------|
| 1 | FE-M6: usePolling hook | 2h | Low | This week |
| 2 | FE-L2: React.lazy | 1h | Low | This week |
| 3 | FE-C3: API key wrapper | 2h | Low | This week |
| 4 | FE-M2: React.memo Phase 1 | 1.5h | Low | This week |
| 5 | ARCH-C1: Agent dedup | 4h | High | Feature branch, next week |
| 6 | TRD-H2: Consensus unify | 3h+WFO | High | After agent dedup, needs WFO re-run |

**Total estimated effort:** ~13.5 hours + WFO re-run time

---

*Generated from Gods Eye Ultrareview (98 findings, April 17, 2026)*
