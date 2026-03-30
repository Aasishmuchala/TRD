# Pitfalls Research

**Domain:** Multi-agent AI market simulation — MVP-to-production polish and deployment
**Researched:** 2026-03-30
**Confidence:** HIGH (grounded in codebase inspection + verified with current sources)

---

## Critical Pitfalls

### Pitfall 1: WebSocket Streaming Breaks on Vercel Frontend + Railway Backend Split

**What goes wrong:**
The project uses WebSocket streaming (`/api/simulate/stream`) as the primary way the dashboard receives real-time agent output. If the frontend is deployed to Vercel (serverless) and points its WebSocket connection at a Railway/Render backend, the connection works in development but fails or degrades silently in production. Specifically: Vercel's serverless functions cannot host WebSocket servers (connections are killed at timeout boundaries), and even when Vercel is used purely for the frontend (no WS server-side), the `VITE_API_BASE` env var at build time must point to the full backend URL — not `/api`. If `VITE_API_BASE` is left unset or set to `/api`, the frontend's WebSocket constructor uses `ws://localhost` in production.

**Why it happens:**
Vite's dev proxy (`proxy: { '/api': { target: 'http://localhost:8000', ws: true } }`) only runs during local development. It does not apply to the production build. The frontend `client.js` already handles this correctly with `import.meta.env.VITE_API_BASE || '/api'`, but if `VITE_API_BASE` is not set in the Vercel dashboard environment variables, it silently falls back to `/api` — which means the browser tries to open `ws://your-vercel-app.vercel.app/api/simulate/stream`, which does not exist.

**How to avoid:**
1. Set `VITE_API_BASE=https://your-railway-backend.railway.app` in Vercel environment variables before first deploy.
2. The WebSocket URL in `SimulationStream.jsx` must be derived from `VITE_API_BASE`, not hardcoded or defaulted. Audit every place `ws://` or `wss://` is constructed.
3. Use Railway or Render (not Vercel Functions) for the FastAPI backend — both support persistent long-running processes required for WebSocket connections.
4. Test WebSocket connectivity end-to-end with `wss://` (HTTPS backend requires `wss://` not `ws://`) before any UX work.

**Warning signs:**
- `SimulationStream` shows connecting spinner indefinitely in production but works locally.
- Browser console shows `WebSocket connection to 'ws://...' failed: Error in connection establishment`.
- Network tab shows a 400 or 502 response to the WebSocket upgrade request.
- `VITE_API_BASE` not listed in Vercel environment variables.

**Phase to address:** Deployment phase (infrastructure setup), before any live demo or user testing.

---

### Pitfall 2: Stitch Design Divergence Bleeds Into Production as Permanent Technical Debt

**What goes wrong:**
The 32 documented differences between Stitch HTML mockups and the plan spec are not just cosmetic. Several are functional bugs that will confuse any user who reads the plan spec:
- Agent names inconsistent across screens (Welcome, Paper Trading, Settings use wrong names while Dashboard is correct).
- Quant/LLM slider defaults to 70% LLM in the Settings UI while backend config enforces 45/55.
- Graduation criteria in the UI show thresholds that differ from what the backend actually enforces (57% vs 60% directional accuracy).

If these are not reconciled before deployment, the UI will contradict the backend, users will see numbers that don't match what the engine reports, and the Settings page will show a slider that has no effect on the real calculation.

**Why it happens:**
Stitch generated plausible-looking but spec-incorrect UI. The React components then referenced Stitch HTML as visual reference without catching the data discrepancies. The divergence compound because each new component built "to match Stitch" drifts further from the plan spec without anyone doing a systematic reconcile pass.

**How to avoid:**
The stitch-vs-plan-comparison.md document already catalogues all 32 differences with clear recommendations. The fix is to execute all 10 decisions in Section 9 of that document as a single dedicated phase before touching any other feature. Specifically:
1. Update agent names in Welcome.jsx (hexagon nodes), PaperTrading.jsx (agent circles), and Settings.jsx (weight sliders).
2. Update Quant/LLM default slider value to 45 (not 70) in Settings UI. Wire it to the real `quant_weight` config value.
3. Update GraduationChecklist.jsx to use the plan's 6 criteria with exact thresholds.
4. Remove sidebar items: Portfolio, Execute Trade, Markets.

**Warning signs:**
- Settings.jsx slider initial value is not 45.
- Agent names differ between the Dashboard's PressurePanel (correct: FII/DII) and Settings weight sliders.
- GraduationChecklist shows 5 items instead of 6.
- Sidebar renders a "Portfolio" or "Execute Trade" link anywhere.

**Phase to address:** UI alignment phase — must be first, before auth routing or deployment.

---

### Pitfall 3: SQLite on Railway/Render Loses Data on Redeploy Without Persistent Volume

**What goes wrong:**
The backend uses SQLite at `~/.gods-eye/` or at the path from `GODS_EYE_DB_PATH`. On Railway and Render, the ephemeral filesystem is wiped on every redeploy. This means all simulation history, agent accuracy records, learned skills, and agent memory are lost every time the backend is redeployed — silently, with no error.

Skills stored under `LEARNING_SKILL_DIR = ~/.gods-eye/skills` are also ephemeral. The auto-learning system would accumulate patterns, then lose them on the next deploy.

**Why it happens:**
SQLite works perfectly in development where files persist between runs. Cloud platforms with ephemeral containers don't persist the container filesystem unless a persistent volume is explicitly mounted. The docker-compose.yml already handles this correctly (volumes: `db-data`, `skills-data`), but Railway and Render require separate volume configuration that does not automatically derive from docker-compose volumes.

**How to avoid:**
1. On Railway: Add a Volume at `/app/data` (backend Dockerfile writes DB to `/app/data/gods_eye.db`) and a second Volume at `/root/.gods-eye` (skills directory).
2. On Render: Add a Persistent Disk attached to `/app/data` and `/root/.gods-eye`.
3. Set `GODS_EYE_DB_PATH=/app/data/gods_eye.db` and `GODS_EYE_LEARNING_SKILL_DIR=/app/data/skills` (both pointing inside the mounted volume).
4. Verify by redeploying deliberately and checking that the history count persists.

**Warning signs:**
- `/api/history` returns 0 records after a redeploy that was previously showing populated history.
- `/api/agent/fii/accuracy` resets to 0% after deploy.
- No error in logs — the database is simply recreated fresh on each boot.
- `docker-compose.yml` volumes exist but no corresponding Railway/Render volume is configured.

**Phase to address:** Deployment phase — before any production data accumulates.

---

### Pitfall 4: Auth Flow Sends Users to a Blank Screen Because Welcome.jsx Is Not Routed

**What goes wrong:**
`Welcome.jsx` exists in `/pages/` and implements the OAuth device code auth flow UI (device code display, polling, auth success animation). But `App.jsx` does not import or route to it. The current `AuthGate` component wraps all routes — if auth fails or the token is not present, the user sees... nothing, because there is no route to render the Welcome/auth screen.

In production, a user with no token hits the app, `AuthGate` blocks all routes, and there is no fallback rendering. The browser shows a blank page with no instructions on how to authenticate.

**Why it happens:**
Welcome.jsx was built as a component but the routing wiring step was left incomplete. The component exists but is orphaned from the routing tree. This is a common "looks done but isn't" failure — the file exists, it renders in isolation, but the user can never reach it via normal navigation.

**How to avoid:**
1. Add a `/welcome` route in `App.jsx`: `<Route path="/welcome" element={<Welcome />} />`.
2. Update `AuthGate` to redirect to `/welcome` instead of rendering nothing when no auth token exists.
3. On successful auth in `Welcome.jsx`, navigate to `/dashboard`.
4. Test the full flow: clear auth token, open app, confirm redirect to Welcome, complete device flow, confirm redirect to Dashboard.

**Warning signs:**
- `App.jsx` has no `import Welcome from './pages/Welcome'`.
- `AuthGate.jsx` renders `null` or an empty div when unauthenticated.
- Device code or "Authenticate" UI is invisible to users who don't know the direct URL.
- The auth token check passes in dev (because token file already exists from earlier sessions) but fails fresh in production.

**Phase to address:** Auth routing phase — second priority after UI alignment, before deployment.

---

### Pitfall 5: NSE Data Scraping Fails Under Anti-Bot Defenses in Production

**What goes wrong:**
The live market data layer scrapes NSE India's website using cookie-based sessions (`_ensure_session()`). In development this works fine because requests are infrequent. In production, after 10-50 requests the NSE session cookie expires, NSE's anti-bot detection triggers, and all subsequent calls silently return fallback mock data — without the user or system knowing the data is stale.

The QA report already documents this: "NSE rate limiting: Live data uses fallbacks when NSE blocks requests." In production, this means simulations that appear to use "live" data are actually running on hardcoded fallback values (Nifty: 22,400, VIX: 14.2, etc.) that haven't changed since the fallback was written.

A secondary issue: `USD/INR` falls back to 83.5 and `DXY` falls back to 104.0 (hardcoded constants) whenever the forex fetch fails. On any given trading day, if INR/DXY have moved significantly, agent conviction levels that depend on these inputs will be systematically miscalibrated.

**Why it happens:**
NSE's public API is not a licensed data product — it's a web interface with anti-scraping protections. The QA/LAUNCH_PLAN.md acknowledges this but defers the fix. In production, without a real data contract, the fallback becomes the de facto data source after the first few requests.

**How to avoid:**
1. Add a `data_source` field to every simulation response (the backend already populates this: `"nse_live"` vs `"fallback"`). Surface this clearly in the dashboard UI — a banner or badge that says "using cached data" when `data_source == "fallback"`.
2. Cache NSE session cookies and implement automatic cookie refresh before expiry (every 20-30 minutes during market hours).
3. For forex: replace hardcoded fallbacks with a free tier API (exchangerate.host, fixer.io free tier) with proper caching. Log when using fallback with the fallback value and timestamp so users know it's stale.
4. Add a `/api/market/data-freshness` endpoint that the dashboard polls to show a staleness indicator.

**Warning signs:**
- All simulations show identical market data values across different runs.
- `data_source: "fallback"` appears in API responses but is not surfaced in UI.
- NSE fetch errors appear in logs shortly after deployment then disappear (replaced by silent fallback).
- USD/INR in simulation inputs is always exactly 83.5.

**Phase to address:** Data integrity phase — before deployment, especially if the tool is meant to be used at market open.

---

### Pitfall 6: Skill Injection Is Wired But Produces Zero Effect Without Seeded Skills

**What goes wrong:**
The auto-learning pipeline is architecturally complete: `ProfileGenerator.build_context()` calls `skill_store.build_skill_context()`, which injects learned patterns into agent prompts. However, this only produces an effect if skills exist on disk at `~/.gods-eye/skills/`. On a fresh deployment (new server, new volume, first launch), the skills directory is empty. The `SimulationReviewEngine` only creates skills after simulations run, and skills only get created when certain pattern conditions are met (direction changes, conviction calibration anomalies, consensus anomalies). The system starts with zero intelligence and accumulates slowly.

A related issue: if the skills directory is not backed by a persistent volume (see Pitfall 3), every redeploy resets all accumulated skills back to zero — undoing weeks of accumulated learning.

Additionally, the `LAUNCH_PLAN.md` notes that `skill_store.py` condition matching (line 58-87) may have inverted logic. If that bug is present in the current code, `get_applicable_skills()` returns an incorrect set, meaning the skill injection silently applies wrong patterns.

**Why it happens:**
The auto-learning system bootstraps from zero. There's no seed data, no initial skill set, and no way for users to see how the system improves over time until they've run dozens of simulations.

**How to avoid:**
1. Seed the skills directory with 3-5 hand-authored skills per agent covering obvious India market patterns (VIX > 22 → lower conviction, expiry week → retail panic, budget day → policy volatility). These serve as both initial intelligence and as a reference for what good skills look like.
2. Expose the skills count in the `/api/health` endpoint and display it in the Settings UI so users know the system is learning.
3. Verify the `matches_context()` logic with a unit test before deployment: a skill with `india_vix > 22` should NOT match when `india_vix = 15`.
4. Ensure the persistent volume covers both `/app/data` (SQLite) and `/root/.gods-eye/skills` (skill files).

**Warning signs:**
- `/api/learning/skills` returns an empty array after many simulations.
- Agent prompt context never includes "LEARNED PATTERNS" section.
- Skill files never appear in `~/.gods-eye/skills/` even after 20+ simulations.
- Settings UI has no indication of how many skills exist.

**Phase to address:** Learning system phase — seed skills during deployment setup.

---

### Pitfall 7: CORS Configuration Breaks the Deployed Split Between Vercel Frontend and Railway Backend

**What goes wrong:**
The backend CORS is configured via `GODS_EYE_CORS_ORIGINS` env var. The default is `"http://localhost:5173,http://localhost:3000"`. In production, the Vercel frontend URL (e.g., `https://gods-eye.vercel.app`) is not in this list. Every API call from the production frontend will be blocked by the browser with a CORS error — the backend is reachable but refuses all browser requests.

The `docker-compose.yml` hardcodes CORS as `"http://localhost,http://localhost:80"` — correct for the Docker scenario but wrong for Vercel+Railway.

**Why it happens:**
CORS configuration is typically an afterthought because it doesn't surface in local development (frontend and backend share the same origin via Vite proxy). The split-origin deployment pattern only reveals it at first production deploy.

**How to avoid:**
1. Set `GODS_EYE_CORS_ORIGINS=https://gods-eye.vercel.app` (exact Vercel URL, no trailing slash) in Railway environment variables before deploying.
2. The `config.py` already reads from this env var correctly — the fix is purely operational, not code.
3. If using a custom domain: include both the Vercel auto-generated URL and the custom domain.
4. WebSocket also requires CORS — verify `proxy_set_header Origin` is correctly passed in any nginx layer.

**Warning signs:**
- Browser console shows `CORS policy: No 'Access-Control-Allow-Origin' header` on API calls.
- Backend `/api/health` returns 200 when hit via curl but frontend shows all requests failing.
- Network tab shows pre-flight `OPTIONS` request returning 403 or missing headers.
- The `.env` on Railway still has default `localhost` CORS origins.

**Phase to address:** Deployment phase — set before first production deploy, verify immediately.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Mock mode as default when no API key | System "works" without an API key | Production silently uses fake data if env var not set; users see realistic-looking but fabricated agent analysis | Only in tests; never as production default without visible indicator |
| SQLite for simulation history | Zero setup, works locally | Concurrent writes from 4 gunicorn workers can cause lock contention; no query-level backup; completely lost on ephemeral deployment without explicit volume mount | Acceptable Phase 1 with persistent volume; migrate to PostgreSQL for Phase 2 |
| `str(e)` in exception handlers | Shows something in error response | Leaks internal paths, class names, and exception chains to the browser; creates security surface and confuses users | Never in production; always sanitize before returning to client |
| `except Exception: pass` in skill injection | Prevents skill failures from breaking simulation | Silent skill system failures; hard to diagnose why learning isn't working; no way to know the feature is broken | Acceptable with a `logger.debug()` inside the pass; never fully silent |
| Hardcoded fallback market data | System runs offline | Users can't tell if they're using real or fake data; simulation accuracy tracking becomes meaningless when based on synthetic inputs | Acceptable if a visible "OFFLINE DATA" badge is shown; never silently |
| Sub-repo `.git` inside workspace | Independent version history for gods-eye/ | Two git repos = commit hygiene issues; CI/CD must know which repo to watch; PR workflow becomes confusing | Acceptable if deployment CI points to the inner repo exclusively |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Claude/OpenAI API via `LLM_API_KEY` | Setting `CLAUDE_API_KEY` but not `LLM_API_KEY`; the legacy compat path only fires in `__post_init__` | Set `LLM_API_KEY` directly; the legacy `CLAUDE_API_KEY` fallback works but is not guaranteed to persist across config refactors |
| NSE market data | Assuming session cookie lasts for the trading day | NSE sessions expire in ~20-30 mins under load; implement proactive cookie refresh, not just on-error refresh |
| WebSocket in production | Using `ws://` with an HTTPS backend | HTTPS backends require `wss://`; mixed content (HTTPS page opening `ws://`) is blocked by all modern browsers |
| Vercel frontend deploy | Relying on Vite proxy at runtime | Vite proxy is dev-only; `VITE_API_BASE` must be set to the full backend URL at Vercel build time (environment variables panel) |
| Railway SQLite volume | Mounting volume only at `/app/data` | Skills directory is at `/root/.gods-eye/skills` by default (config.py); requires a second mount or override `GODS_EYE_LEARNING_SKILL_DIR` to `/app/data/skills` |
| OAuth device flow in production | Testing auth only with existing token present locally | Clear `~/.gods-eye/auth.json` and test the full unauthenticated → device code → poll → success flow before deploying |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 3-round LLM simulation is synchronous per round | Each of 3 rounds waits for all 6 agents to complete before the next round starts; streaming helps UX but not throughput | Rounds 2 and 3 could be parallelized per-agent (they only need the previous round's aggregate, not each other's raw output) | At >3 concurrent users; each simulation blocks an async worker for 15-30s |
| SQLite concurrent writes under gunicorn | Random `database is locked` errors under concurrent simulation requests | Set `PRAGMA journal_mode=WAL` in SQLite connection init; WAL mode allows concurrent reads + one writer | At >2 concurrent simulations hitting gunicorn workers simultaneously |
| In-memory skill cache invalidated on every save | `_cache = None` is set on every `save_skill()` call; next load scans all files; under frequent simulation + learning this is constant disk I/O | Add a file-count check before invalidating; or move to SQLite-backed skill storage | At >100 learned skills across all agents (~100+ disk reads per simulation) |
| NSE data fetched fresh per simulation | Every simulation triggers multiple NSE HTTP calls (Nifty, VIX, FII/DII, options chain, sectors) | The `cache.py` module exists — verify its TTL is applied and not bypassed by the `get_live_snapshot()` call path | Immediately if NSE anti-bot triggers; should be cached at 5-minute TTL minimum |
| WebSocket sends every agent event as a separate message | 6 agents × 3 rounds × 3 messages each = 54+ WebSocket frames per simulation | Batch events where possible; ensure the WebSocket message handler in the frontend can queue events without blocking the React render loop | At >5 concurrent WebSocket connections; more of a UX than throughput issue |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| `LLM_API_KEY` in Vite build | If `LLM_API_KEY` is passed as a `VITE_*` variable, it gets embedded in the production JS bundle and is visible to any user who views source | LLM API key must ONLY exist as a Railway/Render environment variable (backend only). The frontend needs only `VITE_API_BASE`. Never prefix the LLM key with `VITE_`. |
| Auth token file readable by other processes | `~/.gods-eye/auth.json` contains bearer tokens; LAUNCH_PLAN.md notes it was originally plaintext | QA report confirms Fernet encryption is implemented; verify on deployment that file permission is `0o600` and the encryption key derivation is deterministic (not random on each boot, which would invalidate tokens on restart) |
| Simulation endpoint without rate limiting in production | A malicious user could trigger 100 simulations/minute, exhausting the LLM API budget in minutes | LAUNCH_PLAN.md says rate limiting is implemented (slowapi); verify `10/min per IP` for `/api/simulate` is active and not accidentally disabled via env var |
| CORS wildcard during debugging | `*` CORS origin used temporarily "just to see if it works" during deployment debugging; gets committed or left in place | Configure exact origins via env var; never use `*` even temporarily in a deployment that has a real API key |
| Anthropic/OpenAI API key exposed in logs | Stack traces that include `Authorization: Bearer sk-...` headers in debug logging | Ensure `LOG_LEVEL` defaults to `info` in production, not `debug`; audit logging_config.py to confirm headers are not logged |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Simulation runs with no progress feedback then returns result | User clicks "Run Simulation" and sees nothing for 15-30 seconds, assumes it's broken; clicks again, triggering concurrent simulations | SimulationStream's WebSocket streaming is the right pattern — but the loading state must trigger the moment the button is clicked, before the first WebSocket event arrives |
| "OFFLINE DATA" mode is invisible | User runs simulation using fallback market data (because NSE is blocked) and treats the result as a real analysis; builds conviction based on synthetic numbers | Add a persistent orange banner: "Running on cached data from [timestamp]" whenever `data_source == "fallback"` |
| Graduation criteria shown but not linked to backend reality | The GraduationChecklist UI shows criteria with thresholds; if these don't match what the backend actually measures, user will "graduate" without actually meeting real thresholds | Wire `GraduationChecklist.jsx` to fetch actual thresholds from the API (`/api/settings` or a new `/api/graduation/status`) rather than hardcoding them in JSX |
| Auth wall shows blank screen | First-time user has no API key configured and sees a blank white page, no instructions | Welcome.jsx must be the first screen shown; AuthGate should redirect to `/welcome`, not render `null` |
| Settings page slider has no confirmation | User moves Quant/LLM slider, navigates away without saving; the change is lost silently | Show an "unsaved changes" indicator and a Save button that is visually prominent when values have been modified |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Welcome.jsx:** File exists and renders in isolation — verify it is imported and routed in `App.jsx` and reachable from `AuthGate` when no token exists.
- [ ] **Skill injection:** `ProfileGenerator.build_context()` calls skill store — verify that `skill_store.build_skill_context()` actually returns non-empty content (requires skills on disk); confirm by checking `enriched_context` parameter in a real agent `analyze()` call.
- [ ] **Settings Quant/LLM slider:** Slider renders with a value — verify the initial value reflects `config.quant_weight` (should be 45) not a hardcoded HTML `value="70"` from Stitch.
- [ ] **Graduation criteria:** `GraduationChecklist.jsx` renders 6 items — verify item 4 ("Quant-LLM agreement ≥70% when both agree") and item 6 ("LLM agents agree ≥75% across 3 samples") are present, not just the 5 Stitch items.
- [ ] **Auth token encryption:** Token is stored encrypted — verify `~/.gods-eye/auth.json` is not plaintext JSON; cat the file after auth to confirm it contains ciphertext not `{"access_token": "sk-..."}`.
- [ ] **CORS in production:** Backend returns CORS headers — hit the deployed backend from a browser on the Vercel domain; confirm `Access-Control-Allow-Origin` header is present in responses.
- [ ] **WebSocket wss://:* WebSocket URL in production build — open browser devtools in production and confirm connection is to `wss://` (not `ws://`).
- [ ] **SQLite persistence:** DB survives redeploy — after deploying, run 5 simulations, redeploy without changes, check `/api/history` still shows 5 records.
- [ ] **Mock mode not active in production:** Check `/api/health` in production; confirm `"mock_mode": false` and `"llm_provider"` is not `"mock"`.
- [ ] **Data freshness visible:** When NSE is blocked (simulate by running outside market hours or blocking the NSE URL in hosts), verify the UI shows an indicator that data is stale/fallback.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| WebSocket broken in production | MEDIUM | 1. Set `VITE_API_BASE` in Vercel env, 2. Trigger redeploy, 3. Verify `wss://` in browser devtools — no code change needed |
| SQLite data lost on redeploy | HIGH | 1. Attach persistent volume on Railway/Render, 2. Re-run initial simulations to rebuild history; skills can be hand-seeded from backup if exported |
| CORS blocking all API calls | LOW | 1. Add Vercel URL to `GODS_EYE_CORS_ORIGINS` in Railway env vars, 2. Restart backend service — no deploy needed if env var is hot-reloaded |
| Stitch divergence shipped to production | MEDIUM | 1. Use stitch-vs-plan-comparison.md Section 9 as a checklist, 2. Fix 10 items in a single PR to avoid partial state; the changes are localized to 4-5 component files |
| Skills accumulated then lost on redeploy | MEDIUM | 1. Export skills via `/api/learning/skills` before redeploy, 2. Mount persistent volume, 3. Re-import skills as seed files |
| Mock mode active in production silently | LOW | 1. Confirm `LLM_API_KEY` is set in Railway env, 2. Restart backend — mock mode auto-detects absence of key on startup |
| Auth shows blank screen in production | LOW | 1. Add `/welcome` route and `AuthGate` redirect (single PR), 2. Redeploy — Welcome.jsx already exists and renders correctly in isolation |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| WebSocket broken on Vercel | Deployment setup phase | Open browser devtools on production URL; confirm `wss://` connection succeeds |
| Stitch divergence in production | UI alignment phase (first phase) | Audit all 10 decisions from stitch-vs-plan-comparison.md Section 9 as a checklist |
| SQLite data loss on redeploy | Deployment setup phase | Deliberate redeploy + history count check |
| Auth blank screen | Auth routing phase (second phase) | Clear local token, open app, confirm redirect to Welcome page |
| NSE fallback data invisible | Data integrity / dashboard polish phase | Run simulation during market hours; check `data_source` field in response |
| Skill injection no effect | Learning system phase | Check `enriched_context` in an agent `analyze()` call contains "LEARNED PATTERNS" text |
| CORS blocking production | Deployment setup phase | First browser request to deployed backend from Vercel URL |
| Mock mode silent in production | Deployment verification phase | Check `/api/health` for `"mock_mode": false` |
| Graduation criteria mismatch | UI alignment phase | Compare all 6 plan criteria thresholds against GraduationChecklist.jsx source |
| SQL concurrent write contention | Testing/load phase | Run 5 concurrent simulation requests; zero `database is locked` errors |

---

## Sources

- Codebase inspection: `/TRD/TRD/gods-eye/` — direct code analysis of `App.jsx`, `config.py`, `skill_store.py`, `profile_generator.py`, `market_data.py`, `vite.config.js`
- `stitch-vs-plan-comparison.md` — 32 documented divergences, Section 9 decisions
- `LAUNCH_PLAN.md` — documented bugs (Phase 0), data issues (Phase 2), deployment steps (Phase 5)
- `QA_REPORT.md` — known limitations including NSE rate limiting and mock-mode-only testing
- `DEPLOYMENT.md` — Docker architecture, volume configuration, environment variables
- [7 Ways Multi-Agent AI Fails in Production](https://www.techaheadcorp.com/blog/ways-multi-agent-ai-fails-in-production/) — MEDIUM confidence
- [Why AI Agent Pilots Fail in Production (Composio)](https://composio.dev/blog/why-ai-agent-pilots-fail-2026-integration-roadmap) — MEDIUM confidence
- [Vercel WebSocket Limitation](https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections) — HIGH confidence (official Vercel docs)
- [Agent Drift in Multi-Agent LLM Systems](https://arxiv.org/html/2601.04170v1) — MEDIUM confidence
- [NSE India scraping legality and anti-bot](https://www.quora.com/Is-data-scraping-from-NSE-and-BSE-website-illegal) — LOW confidence (community source)
- [FastAPI Railway deployment](https://docs.railway.com/guides/fastapi) — HIGH confidence (official Railway docs)

---
*Pitfalls research for: Multi-agent Indian market simulation — MVP to production*
*Researched: 2026-03-30*
