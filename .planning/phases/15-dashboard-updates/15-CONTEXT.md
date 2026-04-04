# Phase 15: Dashboard Updates - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (frontend phase)

<domain>
## Phase Boundary

Signal page shows real-time quant score + agent consensus + validator reasoning. Trade history distinguishes quant-driven vs agent-confirmed signals. Performance comparison view shows rules-only vs hybrid accuracy/P&L.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- DASH-07: New Signal page at /signal — shows 4 sections: quant breakdown, agent consensus, validator verdict, recommended trade with risk params
- DASH-08: SimulationHistory extended with signal_type tag column (quant/hybrid/agent)
- DASH-09: Performance page or tab showing rules-only vs hybrid comparison (ModeCompare from Phase 14 can be reused)

Frontend: React + Tailwind + Recharts. Existing patterns.
New route: /signal
Sidebar: add Signal nav item.

</decisions>

<code_context>
## Existing Code Insights

### Reusable
- src/components/ModeCompare.jsx — side-by-side comparison (Phase 14)
- src/api/client.js — has all backtest methods
- API: POST /api/signal/hybrid/{instrument}/{date} — returns full hybrid signal
- API: GET /api/signal/quant/{instrument}/{date} — returns quant score

### New API client methods needed
- getHybridSignal(instrument, date) — calls POST /api/signal/hybrid/{instrument}/{date}
- getQuantSignal(instrument, date) — calls GET /api/signal/quant/{instrument}/{date}

</code_context>

<specifics>
No specific requirements beyond success criteria.
</specifics>

<deferred>
None.
</deferred>
