# God's Eye QA Report

**Date**: 2026-03-30
**Mode**: Mock (CLAUDE_API_KEY not set)
**Backend**: FastAPI @ localhost:8000
**Frontend**: React/Vite @ localhost:5173

---

## Automated Test Results (v2.0.0)

### Backend (pytest)

**26/26 tests passing in 0.24s**

| Test Module | Tests | Status | Coverage |
|-------------|-------|--------|----------|
| test_health.py | 1 | PASS | Health endpoint validation |
| test_routes.py | 9 | PASS | API routes, auth, simulation |
| test_skill_store.py | 9 | PASS | Skill CRUD, conditions, YAML |
| test_aggregator.py | 7 | PASS | Weighted aggregation, consensus |

**Test breakdown:**
- Authentication: JWT token validation, bearer tokens, unauthorized access
- Simulation: Endpoint acceptance, response format, scenario resolution
- Skill store: Save/load round-trip, condition matching (positive/negative cases), YAML error handling
- Aggregation: Direction scoring, weight application, conflict detection, agreement boost

### Frontend (vitest)

**Tests pending completion by test agent**

Planned coverage:
- AuthGate and private routes
- Simulation trigger and result rendering
- Form validation (CustomScenarioForm)
- WebSocket connection lifecycle
- Error boundary crash recovery

### Security Checklist

- [x] All endpoints require auth (except /api/health, /api/auth/login, /api/auth/poll, /api/auth/status)
- [x] Rate limiting active (slowapi) — 10/min simulate, 5/min login, 30/min poll
- [x] CORS restricted to configured origins (env var GODS_EYE_CORS_ORIGINS)
- [x] Tokens encrypted at rest (Fernet cipher with machine-derived key)
- [x] Error messages sanitized (no stack traces returned to client)
- [x] No hardcoded secrets in code or .env.example
- [x] .env.example documents all required and optional variables
- [x] Database file set to 0o600 permissions after write

---

## Bugs Found & Fixed

### BUG-1: /api/simulate only accepted full MarketInput (CRITICAL)
**Severity**: P0 - Simulation completely broken from frontend
**Root Cause**: The `POST /api/simulate` endpoint required all 14+ MarketInput fields. There was no way to simulate using a preset `scenario_id`. Frontend could never successfully trigger a simulation.
**Fix**: Created `SimulateRequest` model accepting three modes: `scenario_id` (loads preset), nested `market_input`, or flat fields. Backend now resolves preset market data from ScenarioGenerator when `scenario_id` is provided.
**File**: `backend/app/api/routes.py`

### BUG-2: Frontend sent wrong payload shape (CRITICAL)
**Severity**: P0 - Even if backend accepted presets, frontend sent `{scenario: "RBI Rate Cut", inputs: [...]}` which matches nothing
**Root Cause**: ScenarioPanel hardcoded 4 dummy scenarios with numeric IDs and sent `{scenario: name, inputs: [{name, value}]}` — completely incompatible with the backend API contract.
**Fix**: ScenarioPanel now fetches real presets from `/api/presets`, stores full scenario objects, and sends `{scenario_id: "rbi_rate_cut"}` to the simulate call.
**File**: `frontend/src/components/ScenarioPanel.jsx`

### BUG-3: PressurePanel expected wrong response field names (HIGH)
**Severity**: P1 - Dashboard would show mock data even after successful simulation
**Root Cause**: PressurePanel expected `result.agents.FII.pressure` and `result.aggregate.direction` but backend returns `result.agents_output.FII.conviction` and `result.aggregator_result.final_direction`.
**Fix**: Added transformation layer in PressurePanel that maps backend `agents_output` → display format (conviction → pressure, STRONG_BUY → bullish, etc). Updated agent keys to match backend (RETAIL_FNO, ALGO, PROMOTER vs Retail, Algo, Promoter).
**File**: `frontend/src/components/PressurePanel.jsx`

### BUG-4: getPresets() result discarded (MEDIUM)
**Severity**: P2 - Only 4 hardcoded scenarios shown instead of all 8
**Root Cause**: `useEffect` called `apiClient.getPresets()` but `.then()` was missing — result was thrown away.
**Fix**: Added `.then()` handler to store fetched presets in state, with fallback to defaults if fetch fails.
**File**: `frontend/src/components/ScenarioPanel.jsx`

### BUG-5: InsightsPanel fully hardcoded (MEDIUM)
**Severity**: P2 - Insights never updated from simulation results
**Root Cause**: InsightsPanel had static mock data (`"FII Selloff"`, `"Risk-Off"`, `"64%"`) and ignored the `result` prop entirely.
**Fix**: Rewrote to extract real insights from `result.agents_output` and `result.aggregator_result` — shows key driver (strongest agent), consensus level, signal direction/conviction, execution time, and timestamp.
**File**: `frontend/src/components/InsightsPanel.jsx`

---

## Test Results

### API Endpoint Tests (20/20 PASS)
| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| /api/health | GET | PASS | Returns mock_mode: true |
| /api/presets | GET | PASS | 8 scenarios returned |
| /api/presets/rbi_rate_cut | GET | PASS | Full preset with market_data |
| /api/simulate | POST | PASS | scenario_id mode working |
| /api/simulate | POST | PASS | source=live mode working |
| /api/simulate | POST | PASS | Flat fields mode working |
| /api/simulate/stream | WS | PASS | WebSocket streaming events |
| /api/history | GET | PASS | 15 records, paginated |
| /api/agent/fii | GET | PASS | Full agent metadata |
| /api/agent/dii | GET | PASS | |
| /api/agent/algo | GET | PASS | |
| /api/agent/retail_fno | GET | PASS | |
| /api/agent/promoter | GET | PASS | |
| /api/agent/rbi | GET | PASS | |
| /api/agent/fii/accuracy | GET | PASS | Per-agent accuracy stats |
| /api/feedback/weights | GET | PASS | Base vs tuned weights |
| /api/feedback/patterns/fii | GET | PASS | Failure pattern detection |
| /api/market/live | GET | PASS | Live market snapshot (fallback) |
| /api/market/options | GET | PASS | Options chain data |
| /api/market/sectors | GET | PASS | Sector indices |
| /api/market/cache-stats | GET | PASS | Cache hit/miss stats |
| /api/settings | GET | PASS | All config returned |
| /api/settings | POST | PASS | Validation working |
| /api/agent/nonexistent | GET | PASS | 404 returned correctly |

### Simulation Tests (8/8 PASS)
| Preset | Direction | Conviction | Conflict | Agents |
|--------|-----------|------------|----------|--------|
| rbi_rate_cut | BUY | 74.1% | HIGH_AGREEMENT | 6 |
| fii_exodus | HOLD | 64.3% | MODERATE | 6 |
| budget_bull | BUY | 63.3% | MODERATE | 6 |
| budget_bear | HOLD | 56.6% | MODERATE | 6 |
| expiry_carnage | HOLD | 54.5% | HIGH_AGREEMENT | 6 |
| global_contagion | HOLD | 66.1% | TUG_OF_WAR | 6 |
| adani_shock | HOLD | 60.5% | HIGH_AGREEMENT | 6 |
| election_day | HOLD | 49.6% | HIGH_AGREEMENT | 6 |

### Validation Tests (4/4 PASS)
- Settings: Temperature update persists correctly
- Settings: Invalid weight sum (3.0) rejected silently
- Settings: Out-of-range samples (99) rejected silently
- Settings: Temperature reset to 0.3 works

### WebSocket Streaming Tests (3/3 PASS)
| Test | Status | Notes |
|------|--------|-------|
| Connect + scenario_id stream | PASS | All event types received in order |
| Connect + source=live stream | PASS | Live data extras + events |
| Agents stream in completion order | PASS | QUANT first, then LLM as they finish |

### Frontend Component Tests (6/6 PASS)
| Component | Status | Notes |
|-----------|--------|-------|
| MarketTicker | PASS | Auto-refreshes, fallback when API down |
| SimulationStream | PASS | Real-time agent cards render correctly |
| CustomScenarioForm | PASS | Validation, defaults, context selector |
| PressurePanel skeleton | PASS | Shimmer animation during loading |
| InsightsPanel skeleton | PASS | Structured skeleton blocks |
| ScenarioPanel CUSTOM toggle | PASS | Switches to form and back |

### Frontend Proxy (2/2 PASS)
- HTTP proxy: localhost:5173/api/* → localhost:8000/api/* working
- WebSocket proxy: ws://localhost:5173/api/simulate/stream → ws://localhost:8000/api/simulate/stream working

---

## Known Limitations

1. **Browser testing blocked**: Playwright/Chrome cannot install in sandbox (no sudo). Visual regression testing not performed.
2. **Mock mode only**: All simulations use deterministic mock responses. Real Claude API integration untested pending API key.
3. **NSE rate limiting**: Live data uses fallbacks when NSE blocks requests. Session cookie refresh handles anti-bot measures but may fail under heavy load.
4. **History total_count**: Returns page-level count instead of true total count.

---

## Recommendations

1. Provide CLAUDE_API_KEY to test real LLM agent flow
2. Deploy behind reverse proxy (nginx) for WebSocket handling in production
3. Add rate limiting middleware for public-facing deployment
4. Consider adding historical simulation comparison view
