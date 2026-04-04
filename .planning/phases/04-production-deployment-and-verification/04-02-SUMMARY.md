---
phase: 04-production-deployment-and-verification
plan: "02"
subsystem: infra
tags: [vercel, vite, react, websocket, spa, deployment, env-vars]

# Dependency graph
requires:
  - phase: 04-production-deployment-and-verification
    provides: Railway backend deployed with WebSocket endpoint at /api/simulate/stream
provides:
  - vercel.json SPA catch-all rewrite (fixes 404 on deep links)
  - VITE_WS_BASE-aware WebSocket URL construction (connects frontend to Railway backend)
affects:
  - vercel-deployment
  - frontend-websocket-streaming
  - production-connectivity

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "VITE_WS_BASE env var pattern: import.meta.env.VITE_WS_BASE with same-host fallback for local dev"
    - "vercel.json SPA rewrite: source /(.*) destination /index.html for React Router deep link support"

key-files:
  created:
    - TRD/gods-eye/frontend/vercel.json
  modified:
    - TRD/gods-eye/frontend/src/hooks/useStreamingSimulation.js

key-decisions:
  - "VITE_WS_BASE is optional — when unset, same-host fallback preserves local dev behavior via Vite proxy"
  - "vercel.json uses source /(.*) catch-all rewrite so all React Router paths (including /welcome, /dashboard) load index.html"
  - "outputDirectory is dist (Vite default, no custom outDir in vite.config.js)"
  - "No API routes in vercel.json — backend lives on Railway, not Vercel serverless"

patterns-established:
  - "VITE_* env var pattern: import.meta.env.VITE_* with fallback for dev (same as VITE_API_BASE pattern in client.js)"
  - "Vercel SPA fix: catch-all rewrite to /index.html in vercel.json"

requirements-completed:
  - DEP-02
  - DEP-03

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 4 Plan 02: Vercel SPA Rewrite and WebSocket URL Fix Summary

**vercel.json SPA catch-all rewrite added and WebSocket URL updated to use VITE_WS_BASE env var so production frontend routes deep links correctly and connects WebSocket to Railway backend**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-30T13:28:10Z
- **Completed:** 2026-03-30T13:29:49Z
- **Tasks:** 2 completed
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- Fixed WebSocket URL in `useStreamingSimulation.js` to prefer `VITE_WS_BASE` (Railway URL) over `window.location.host` (Vercel domain) in production
- Local dev WebSocket preserved: falls back to same-host when `VITE_WS_BASE` is not set (Vite proxy routes `/api/*` to `localhost:8000`)
- Created `vercel.json` with SPA catch-all rewrite so all paths (`/welcome`, `/dashboard`, `/agents`, `/history`, `/paper-trading`, `/settings`, `/skills`) resolve to `index.html` instead of 404

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix WebSocket URL to use VITE_WS_BASE env var** - `03c7d9e` (feat)
2. **Task 2: Create vercel.json with SPA rewrite** - `a5cfc6f` (feat)

## Files Created/Modified
- `TRD/gods-eye/frontend/src/hooks/useStreamingSimulation.js` - WebSocket URL reads `VITE_WS_BASE` from Vite env; falls back to same-host for local dev
- `TRD/gods-eye/frontend/vercel.json` - SPA catch-all rewrite, buildCommand/outputDirectory/framework fields for Vercel deployment

## Decisions Made
- `VITE_WS_BASE` is optional: when unset local dev falls back to `window.location.host` (no env var changes needed for development)
- No `devCommand` or `installCommand` in `vercel.json` — Vercel auto-detects npm
- No API routes in `vercel.json` — backend is Railway, not Vercel serverless

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Discovered that `TRD/` sub-directory has its own git repo (`TRD/TRD/.git`) and `gods-eye` has a further nested git repo (`TRD/TRD/gods-eye/.git`). Previous phase commits were in the `gods-eye` sub-repo so Task commits were made there for consistency.

## User Setup Required
**Vercel environment variable required before deployment:**
- Set `VITE_WS_BASE=wss://your-railway-backend.up.railway.app` in Vercel project settings under Environment Variables → Production
- Without this, the frontend WebSocket will attempt to connect to the Vercel domain instead of Railway

## Next Phase Readiness
- Frontend is ready for Vercel deployment: `vercel.json` is in place, WebSocket URL is production-correct
- Backend CORS must be set to `https://your-app.vercel.app` (not `*`) before final production launch
- `VITE_API_BASE` also needs to be set in Vercel to point to the Railway backend REST API

---
*Phase: 04-production-deployment-and-verification*
*Completed: 2026-03-30*
