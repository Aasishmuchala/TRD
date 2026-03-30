# Phase 4: Production Deployment and Verification - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

God's Eye is live and accessible at public Railway and Vercel URLs, with SQLite and SkillStore data persisting across redeploys, WebSocket streaming working over wss://, CORS configured for the production frontend domain, and all environment variables documented.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — deployment infrastructure phase. Key requirements:
- DEP-01: Backend deployed to Railway with persistent SQLite volume at /app/data
- DEP-02: Frontend deployed to Vercel with SPA rewrite and VITE_API_BASE configured
- DEP-03: WebSocket streaming works in production (wss:// to Railway backend)
- DEP-04: CORS configured for production Vercel domain (not wildcard)
- DEP-05: Skills directory uses persistent volume at /app/skills
- DEP-06: .env.example documents all required environment variables

NOTE: Actual Railway/Vercel deployment requires user credentials and cannot be automated by Claude. This phase creates all deployment configuration files and documentation. The user will run the actual deploy commands.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- TRD/gods-eye/backend/Dockerfile — exists but may need updates
- TRD/gods-eye/docker-compose.yml — exists with volume config
- TRD/gods-eye/backend/app/config.py — env var configuration
- TRD/gods-eye/frontend/vite.config.js — build configuration

### Established Patterns
- Backend uses uvicorn for ASGI
- Config via os.getenv() with defaults
- Docker multi-stage builds

### Integration Points
- Railway: Dockerfile-based deploy, needs volume mounts
- Vercel: Static site from dist/, needs vercel.json SPA rewrite
- CORS: app/config.py CORS_ORIGINS setting
- WebSocket: frontend SimulationStream connects to /api/simulate/stream

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
