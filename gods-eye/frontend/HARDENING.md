# God's Eye Frontend Production Hardening

## Summary of Changes

This document outlines all hardening improvements made to the frontend for production readiness.

### 1. Error Boundary Component
**File**: `src/components/ErrorBoundary.jsx`
- Created a class-based error boundary to catch React component errors
- Displays user-friendly error message instead of white screen
- Provides "Try Again" button for recovery
- Logs errors to console for debugging

**Integration**: Wrapped entire Router in `App.jsx` with `<ErrorBoundary>`

### 2. API Client Robustness
**File**: `src/api/client.js`
- Added **30-second request timeout** using AbortController
- Implemented **3-retry logic with exponential backoff** (1s, 2s, 4s)
- Retries only on:
  - 5xx server errors
  - Network/timeout errors
- Does NOT retry on 4xx client errors (to prevent wasting requests)
- Made API_BASE configurable via `VITE_API_BASE` environment variable

### 3. Build Optimizations
**File**: `vite.config.js`
- Added manual chunk splitting for better caching:
  - `vendor`: React, React DOM, React Router
  - `charts`: Recharts library
- Reduces initial bundle and improves parallel loading

### 4. Accessibility (WCAG Basics)

#### AuthGate.jsx
- Added `role="status"` and `aria-live="polite"` to loading states
- Added `aria-label` to all interactive buttons
- Added `role="alert"` to error messages
- Added `aria-hidden="true"` to decorative SVGs

#### ScenarioPanel.jsx
- Added `aria-label` to Live Market button
- Added `aria-live="polite"` to market data availability indicator
- Added `aria-label` to Run Simulation button
- Disabled Live Market button when data unavailable

#### TopNav.jsx
- Added `aria-label` to time display
- Added `aria-live="polite"` to market hours indicator
- Added `aria-hidden="true"` to decorative status indicator

#### CustomScenarioForm.jsx
- Properly associated labels with inputs using `htmlFor` and `id`
- Added `aria-invalid` and `aria-describedby` to form fields with errors
- Added `role="alert"` to error messages
- Changed context selector to `<fieldset>` with `<legend>`
- Added `aria-pressed` to context toggle buttons
- Added `aria-label` to all action buttons

## Environment Variables

Add to `.env.production`:
```
VITE_API_BASE=https://your-api-domain.com/api
```

Or let it default to `/api` for same-origin requests.

## Testing Checklist

- [ ] Run app and verify no console errors
- [ ] Test network error recovery (throttle network, wait for retries)
- [ ] Test 30-second timeout (slow API endpoint)
- [ ] Test error boundary (intentionally trigger error in dev)
- [ ] Run accessibility audit (axe DevTools, WAVE)
- [ ] Test with screen reader (NVDA, JAWS, VoiceOver)
- [ ] Verify bundle chunks split correctly (`npm run build && ls -la dist/assets/`)
- [ ] Test with `VITE_API_BASE` set to different domain

## Production Deployment

1. Build with optimizations: `npm run build`
2. Verify chunk splitting in `dist/assets/`
3. Set `VITE_API_BASE` environment variable if using different domain
4. Enable HTTP/2 server-push for vendor chunks
5. Set cache headers for vendor/charts chunks (long-lived)
6. Monitor error boundary catches via logging service
