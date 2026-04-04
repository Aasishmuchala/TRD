---
phase: 04-production-deployment-and-verification
plan: "01"
subsystem: backend-deployment
tags: [railway, docker, gunicorn, deployment, config]
dependency_graph:
  requires: []
  provides: [railway-deploy-config, dockerfile-production-ready, skills-volume-aligned]
  affects: [backend-runtime, skillstore-persistence, docker-compose-local]
tech_stack:
  added: []
  patterns: [railway-toml-dockerfile-builder, gunicorn-single-worker, volume-mount-alignment]
key_files:
  created:
    - TRD/gods-eye/backend/railway.toml
  modified:
    - TRD/gods-eye/backend/Dockerfile
    - TRD/gods-eye/backend/app/config.py
    - TRD/gods-eye/docker-compose.yml
decisions:
  - "gunicorn -w 1 is the authoritative worker count in both Dockerfile CMD and railway.toml startCommand — dual specification prevents drift"
  - "railway.toml startCommand uses $PORT instead of hardcoded 8000 — Railway assigns dynamic port at runtime"
  - "LEARNING_SKILL_DIR default changed to /app/skills string literal — no expanduser() needed in containerized environment"
  - "GODS_EYE_CORS_ORIGINS in docker-compose uses ${VAR:-fallback} substitution — host env takes precedence for production Vercel URL"
metrics:
  duration: 128s
  completed: "2026-03-30"
  tasks_completed: 2
  files_modified: 4
---

# Phase 04 Plan 01: Railway Deployment Config and Dockerfile Fixes Summary

Railway deployment configuration created and two pre-deploy bugs fixed: gunicorn multi-worker crash (mutable singleton) and SkillStore writing to ephemeral /root/.gods-eye/skills instead of /app/skills.

## What Was Built

### Task 1: Fix Dockerfile (workers + skills dir) and create railway.toml
**Commit:** b9951a8

Two targeted fixes to `backend/Dockerfile`:
- Changed `RUN mkdir -p /app/data` to `RUN mkdir -p /app/data /app/skills` — both dirs must exist at image build time so Railway volume mounts attach correctly.
- Changed `-w 4` to `-w 1` in CMD — StreamingOrchestrator and config are module-level singletons; multiple workers corrupt state (previously recorded as a Phase 4 blocker).

Created `backend/railway.toml`:
- `builder = "dockerfile"` with `dockerfilePath = "./Dockerfile"` — Railway knows to use the existing Dockerfile.
- `startCommand` uses `$PORT` (Railway injects a dynamic port, not always 8000) and explicitly sets `-w 1`.
- `healthcheckPath = "/api/health"` — Railway waits for health endpoint before routing traffic.
- `restartPolicyType = "on_failure"` with 3 max retries for resilience.

### Task 2: Fix LEARNING_SKILL_DIR default and docker-compose skills volume
**Commit:** b10261d

In `backend/app/config.py`:
- Changed `LEARNING_SKILL_DIR` default from `os.path.join(os.path.expanduser("~"), ".gods-eye", "skills")` (resolves to `/root/.gods-eye/skills` in container — ephemeral, not volume-mounted) to the string literal `"/app/skills"` (matches the Railway volume mount point).
- Env var name `GODS_EYE_LEARNING_SKILL_DIR` unchanged — local dev can still override.

In `docker-compose.yml`:
- Changed `skills-data:/root/.gods-eye/skills` to `skills-data:/app/skills` — now matches config.py default and the Railway volume target.
- Changed `GODS_EYE_CORS_ORIGINS=http://localhost,http://localhost:80` to `GODS_EYE_CORS_ORIGINS=${GODS_EYE_CORS_ORIGINS:-http://localhost,http://localhost:80}` — production Vercel URL can be injected from host environment without editing the file.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files exist:
- `TRD/gods-eye/backend/railway.toml` — created
- `TRD/gods-eye/backend/Dockerfile` — modified
- `TRD/gods-eye/backend/app/config.py` — modified
- `TRD/gods-eye/docker-compose.yml` — modified

### Commits exist:
- b9951a8 — feat(04-01): fix Dockerfile workers + dirs and create railway.toml
- b10261d — fix(04-01): fix LEARNING_SKILL_DIR default and docker-compose skills volume

## Self-Check: PASSED
