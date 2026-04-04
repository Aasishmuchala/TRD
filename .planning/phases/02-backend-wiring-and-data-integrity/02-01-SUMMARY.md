---
phase: 02-backend-wiring-and-data-integrity
plan: "01"
subsystem: infra
tags: [skill-store, learning, config, env-var, seeding]

# Dependency graph
requires: []
provides:
  - "LEARNING_SKILL_DIR reads from GODS_EYE_LEARNING_SKILL_DIR env var (deployment-safe)"
  - "seed_skills.py populates SkillStore with 5 hand-authored skills across FII/DII/RETAIL_FNO/ALGO/ALL agents"
  - "build_skill_context() reliably returns a LEARNED PATTERNS block when any seeded skill triggers"
affects:
  - 02-backend-wiring-and-data-integrity
  - 04-deployment

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "os.getenv(ENV_VAR_NAME, fallback) pattern for all path config fields"
    - "Idempotent seed script: check existing names before saving, returns count saved"

key-files:
  created:
    - "TRD/gods-eye/backend/app/learning/seed_skills.py"
  modified:
    - "TRD/gods-eye/backend/app/config.py"

key-decisions:
  - "LEARNING_SKILL_DIR uses os.getenv() with same pattern as DATABASE_PATH — no new config infrastructure needed"
  - "seed_all() idempotency is name-based (not file-existence-based) so rename-on-disk won't cause re-seed"
  - "ALL agent key used for cross-agent Pre-Expiry Caution skill — load_skills() already returns ALL skills for every agent"

patterns-established:
  - "Seed scripts: define SEED_SKILLS list at module level, expose seed_all(base_dir=None) -> int, use __main__ with argparse"
  - "Idempotency check: load existing skill names into a set, skip matches before saving"

requirements-completed: [BACK-02, BACK-01]

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 02 Plan 01: SkillStore Path Fix and Skill Seeding Summary

**LEARNING_SKILL_DIR wired to GODS_EYE_LEARNING_SKILL_DIR env var; 5 hand-authored skills seeded across FII/DII/RETAIL_FNO/ALGO/ALL agents so build_skill_context() always returns a LEARNED PATTERNS block**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T12:47:14Z
- **Completed:** 2026-03-30T12:49:00Z
- **Tasks:** 2 of 2
- **Files modified:** 2

## Accomplishments

- Fixed hardcoded ~/.gods-eye/skills path in config.py to read from GODS_EYE_LEARNING_SKILL_DIR env var — non-root Railway containers can now write skills to a mounted volume path
- Created seed_skills.py with 5 realistic hand-authored skills (FII High VIX Caution, DII SIP Absorption, RETAIL_FNO Max Pain Pull, ALGO PCR Reversal Signal, ALL Pre-Expiry Caution)
- Verified end-to-end: build_skill_context('FII', {india_vix: 22.0, fii_flow_5d: -150.0}) returns "LEARNED PATTERNS (2 applicable): ..." with correct skill content

## Task Commits

Each task was committed atomically into the gods-eye sub-repo (TRD/gods-eye/.git):

1. **Task 1: Fix LEARNING_SKILL_DIR to read from env var** - `89c5aae` (fix)
2. **Task 2: Create seed_skills.py with 5 realistic skills** - `ec44eed` (feat)

**Plan metadata:** committed in outer TRD repo docs commit

## Files Created/Modified

- `TRD/gods-eye/backend/app/config.py` - LEARNING_SKILL_DIR now uses os.getenv("GODS_EYE_LEARNING_SKILL_DIR", fallback)
- `TRD/gods-eye/backend/app/learning/seed_skills.py` - Standalone seed script; exposes SEED_SKILLS list and seed_all(base_dir=None) -> int

## Decisions Made

- Used name-based idempotency check in seed_all() rather than file-existence check — more robust against file renames
- ALL agent key used for Pre-Expiry Caution skill (cross-agent) because load_skills() already merges ALL skills for every agent_key query
- No new dependencies added — PyYAML already in use by skill_store.py

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

For production deployment (Phase 4), set the following env vars in Railway:
- `GODS_EYE_LEARNING_SKILL_DIR=/app/skills` (on the Railway Volume, same mount as DB)
- Run `python -m app.learning.seed_skills` after first deploy to pre-populate skills

## Next Phase Readiness

- SkillStore is now deployment-safe (env var path, volume-compatible)
- Seed script is available to pre-populate skills before first simulation
- skill injection path (SkillStore -> build_skill_context -> ProfileGenerator) is ready for 02-02 wiring
- Blocker from STATE.md resolved: "SkillStore starts empty on fresh deploy; consider seeding 3-5 hand-authored skills per agent"

---
*Phase: 02-backend-wiring-and-data-integrity*
*Completed: 2026-03-30*

## Self-Check: PASSED

- FOUND: TRD/gods-eye/backend/app/config.py
- FOUND: TRD/gods-eye/backend/app/learning/seed_skills.py
- FOUND: .planning/phases/02-backend-wiring-and-data-integrity/02-01-SUMMARY.md
- FOUND commit: 89c5aae (fix LEARNING_SKILL_DIR env var)
- FOUND commit: ec44eed (feat seed_skills.py)
