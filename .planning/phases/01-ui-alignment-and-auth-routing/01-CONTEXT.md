# Phase 1: UI Alignment and Auth Routing - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Every UI surface reflects the plan spec exactly — correct agent names (FII, DII, Retail F&O, Algo/Quant, Promoter, RBI), plan-spec weights (0.30/0.25/0.15/0.10/0.10/0.10), plan's 6 graduation criteria with exact thresholds, in-scope sidebar items only, and a functional Welcome page accessible to unauthenticated users.

</domain>

<decisions>
## Implementation Decisions

### Agent Naming Standardization
- All screens must use exactly: FII, DII, Retail F&O, Algo/Quant, Promoter, RBI
- Welcome screen hexagon nodes: fix labels from SEC/SENT/VOL/MAC to correct agent names
- Paper Trading agent circles: fix sublabels from FED/DATA/RETAIL/ALGO/POLI/SENTI to S/B/S/S/B/H
- Settings page: fix agent names from FII Intelligence/DII Sentiment/Global Macro/Editorial Signal/Technical Cluster/Alternative Data to correct names
- Dashboard is the only screen already correct — use as reference

### Agent Weights
- Use plan spec: FII 0.30, DII 0.25, Retail F&O 0.15, Algo/Quant 0.10, Promoter 0.10, RBI 0.10
- Settings page already has correct defaults in React code — verify Stitch HTML alignment

### Graduation Criteria
- Replace Stitch's 5 criteria with plan's 6 exact criteria:
  1. Directional accuracy (1-day) >= 57% over 20 sessions
  2. Directional accuracy (1-week) >= 60% over 4 weeks
  3. Calibration error < 15%
  4. Quant-LLM agreement accuracy >= 70% when both agree
  5. No catastrophic miss (didn't miss >3% move with high-confidence wrong call)
  6. Internal consistency (LLM agents agree with themselves >= 75% across 3 samples)

### Sidebar Scope
- Remove: Portfolio, Execute Trade, Markets nav items
- Remove: "Terminal V2.4.0 High-Frequency" branding
- Remove: "Secure Node: 0x21...FF" from dashboard footer
- Remove: User profile / tier system (John Doe, Pro Tier)
- Keep: Dashboard, Agents, History, Paper Trading, Settings

### Quant/LLM Balance
- Default slider to 45/55 (plan spec), not 30/70 (Stitch)
- Flag trigger: >30% disagreement between quant and LLM (not confidence < 85%)

### Paper Trading Format
- Use date-based session format: "Mar 29 · BEAR 65% → ▼ 0.8%"
- Not session IDs like "SESSION_014_ALPHA"

### Scenario Modal Fields
- Add missing: FII Net (Today), FII Futures OI Δ, DII Net (Today)
- Keep existing: FII 5-Day, DII 5-Day, SIP Inflow

### Auth Routing
- Add /welcome route to App.jsx
- AuthGate redirects unauthenticated users to /welcome
- Welcome.jsx already built — just needs routing

### Claude's Discretion
- Exact visual styling decisions (CSS tweaks, spacing adjustments)
- Whether to modify Stitch HTML files or only React components (recommend: React only, Stitch is reference)
- Component refactoring approach (inline fixes vs extract shared constants)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AgentDetail.jsx` has AGENT_DESCS object with agent metadata — centralize for reuse
- `Settings.jsx` has agentLabels, agentColors — should share with other components
- `SimulationStream.jsx` has AGENT_ORDER — should be shared constant
- `GraduationChecklist.jsx` — reusable component, needs criteria update
- `utils/colors.js` — centralized color definitions

### Established Patterns
- Tailwind CSS for all styling
- React Router 6 for navigation
- Custom hooks (useSimulation, useStreamingSimulation) for state management
- API client at src/api/client.js with retry logic

### Integration Points
- App.jsx routes — add /welcome
- AuthGate.jsx — modify redirect behavior
- Layout.jsx / Sidebar.jsx — sidebar nav items
- TopNav.jsx — top navigation cleanup

</code_context>

<specifics>
## Specific Ideas

- Source of truth for agent definitions: create a shared constants file (e.g., src/constants/agents.js) with names, labels, colors, weights
- The comparison doc (stitch-vs-plan-comparison.md) has all 32 differences catalogued — use as checklist
- Plan document (gods-eye-plan.md) has exact specifications for all screens

</specifics>

<deferred>
## Deferred Ideas

- Stitch HTML files (gods-eye-ui/) are reference mockups, not production code — fixing React components is sufficient
- Dark mode consistency is Phase 3 (FE-07)
- Loading/empty/error states are Phase 3 (FE-01, FE-02, FE-03)

</deferred>
