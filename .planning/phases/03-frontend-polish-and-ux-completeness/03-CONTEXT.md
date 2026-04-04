# Phase 3: Frontend Polish and UX Completeness - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning
**Mode:** Auto-generated (autonomous mode)

<domain>
## Phase Boundary

Every user-facing flow communicates its state (loading, empty, error) clearly, the live market ticker works, simulation history is exportable, the Learning/Skills page is accessible, and the dark mode theme is consistent across all screens.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion. Key requirements:
- FE-01: Loading states during API calls (spinners, skeleton screens)
- FE-02: Empty states when no data (meaningful messages, not blank)
- FE-03: Error states with actionable messages
- FE-04: Live market ticker in dashboard header (Nifty/Sensex/VIX from backend /api/market/live)
- FE-05: CSV/JSON export for simulation history
- FE-06: Learning/Skills management page (new route, uses /api/learning/skills endpoint)
- FE-07: Dark mode theme consistency (Apple dark + Claude warm palette per design system)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- src/api/client.js — has getMarketLive(), getSkills(), getAgentSkills() already
- src/components/MarketTicker.jsx — built but integration unclear
- src/constants/agents.js — canonical agent data (from Phase 1)
- Tailwind config has full dark theme palette defined

### Established Patterns
- React functional components with hooks
- Tailwind CSS utility classes
- API client with retry logic and error handling
- Toast notifications for user feedback

### Integration Points
- App.jsx — add /skills route
- Layout.jsx — integrate MarketTicker in header
- Sidebar.jsx — may need Skills nav item (or nest under existing)

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond ROADMAP success criteria.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
