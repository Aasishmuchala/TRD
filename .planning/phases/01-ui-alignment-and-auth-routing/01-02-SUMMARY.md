---
phase: 01-ui-alignment-and-auth-routing
plan: 02
subsystem: frontend-routing
tags: [auth, routing, react-router, welcome-page]
dependency_graph:
  requires: []
  provides: [/welcome-route-accessible, authgate-redirects-to-welcome]
  affects: [TRD/gods-eye/frontend/src/App.jsx, TRD/gods-eye/frontend/src/components/AuthGate.jsx]
tech_stack:
  added: []
  patterns: [react-router-v6-nested-routes, localStorage-auth-check, useNavigate-redirect]
key_files:
  created: []
  modified:
    - TRD/gods-eye/frontend/src/App.jsx
    - TRD/gods-eye/frontend/src/components/AuthGate.jsx
decisions:
  - "Use Router as outermost component so useNavigate works inside AuthGate"
  - "AuthGate checks localStorage.getItem('godsEyeApiKey') directly — no async API call needed"
  - "Render null (not a spinner) in AuthGate while redirecting to prevent flash of protected content"
metrics:
  duration: 2 minutes
  completed_date: "2026-03-30"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 01 Plan 02: Auth Routing — Welcome Page as Unauthenticated Entry Point Summary

**One-liner:** Restructured App.jsx routing and stripped AuthGate to a 21-line localStorage-based redirect guard, making /welcome the unauthenticated entry point.

## What Was Built

Wired up the pre-existing Welcome.jsx as the app's unauthenticated entry point by:
1. Moving Router outside AuthGate in App.jsx (so useNavigate works inside AuthGate)
2. Adding a public `/welcome` route outside the AuthGate wrapper
3. Rewriting AuthGate from a 244-line device-code OAuth component to a 21-line localStorage redirect guard

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Restructure App.jsx — add /welcome route outside AuthGate | `06cb569` | `frontend/src/App.jsx` |
| 2 | Simplify AuthGate — redirect to /welcome instead of inline login form | `ed7f520` | `frontend/src/components/AuthGate.jsx` |

## Key Changes

**App.jsx** (`TRD/gods-eye/frontend/src/App.jsx`):
- Router is now the outermost component (was wrapped inside AuthGate)
- `/welcome` route added as a public route (no auth gate)
- All other routes (`/`, `/dashboard`, `/agents`, `/history`, `/paper-trading`, `/settings`) remain inside AuthGate via a `/*` catch-all route
- Welcome imported from `./pages/Welcome`

**AuthGate.jsx** (`TRD/gods-eye/frontend/src/components/AuthGate.jsx`):
- Removed entire device-code OAuth flow (PROVIDERS, startLogin, startPolling, pollTimer cleanup)
- Removed all inline login UI (provider selection card, device code display, loading spinners)
- Now: checks `localStorage.getItem('godsEyeApiKey')` — if exists, renders children; if not, navigates to /welcome
- Uses `useNavigate` (not window.location) for React Router compatibility
- Renders `null` while redirecting (no flash of protected content)
- Reduced from 244 lines to 21 lines

## Must-Haves Verification

| Truth | Status |
|-------|--------|
| Unauthenticated users navigating to app are redirected to /welcome | PASS — AuthGate redirects via useNavigate when no key in localStorage |
| Welcome.jsx renders at /welcome without requiring auth | PASS — /welcome route is outside AuthGate in App.jsx |
| Entering valid API key on Welcome stores it and navigates to /dashboard | PASS — Welcome.jsx already handles this (unchanged) |
| Clicking 'ENTER MOCK MODE' navigates to /dashboard in mock mode | PASS — Welcome.jsx already handles this (unchanged) |
| AuthGate no longer renders its own login UI | PASS — AuthGate is now 21 lines, renders null or children only |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files Exist
- `TRD/gods-eye/frontend/src/App.jsx` — exists, contains `/welcome` route
- `TRD/gods-eye/frontend/src/components/AuthGate.jsx` — exists, 21 lines, contains `navigate('/welcome')`

### Commits Exist
- `06cb569` — feat(01-02): restructure App.jsx — add /welcome route outside AuthGate
- `ed7f520` — feat(01-02): simplify AuthGate — redirect to /welcome instead of inline login form

## Self-Check: PASSED
