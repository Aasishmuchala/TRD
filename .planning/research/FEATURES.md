# Feature Research

**Domain:** Multi-Agent Indian Market Intelligence & Simulation Tool (MVP → Production)
**Researched:** 2026-03-30
**Confidence:** MEDIUM — Indian trading tool ecosystem well-documented; specific multi-agent simulation product analogues are sparse

---

## Context: What Already Exists

The prototype already ships: 6 AI agents (FII, DII, Retail F&O, Algo/Quant, Promoter, RBI), 3-round simulation, weighted consensus, live NSE data, accuracy feedback, auto-learning, paper trading, simulation history, and a full React dashboard. This research answers: **what separates "working prototype" from "shippable product" for a derivatives trader on Dalal Street?**

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that, if missing, make the product feel unfinished or untrustworthy. Indian derivatives traders have high standards set by Sensibull, Zerodha Kite, StockEdge, and Trendlyne. Missing any of these will cause users to dismiss the tool on first impression.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Consistent agent naming everywhere | Traders orient around "FII", "DII", "RBI" — inconsistent names break trust and create confusion | LOW | Plan names (FII, DII, Retail F&O, Algo/Quant, Promoter, RBI) must match in UI, API responses, history records, and export labels. Currently diverges between Stitch HTML and React components. |
| Working auth flow (login → dashboard) | No trader will use a tool that drops them on a broken welcome screen | LOW | Welcome.jsx exists but is not routed. Wiring this is purely routing work, not new code. |
| Error states for failed simulations | When LLM or NSE data calls fail, the UI must explain what happened and offer a recovery path | LOW | "Something went wrong" blank screens are unacceptable. Toast notifications + inline error states required. |
| Empty states for first-time use | New users with no simulation history need guided entry, not blank tables | LOW | Empty history, empty accuracy charts — all need instructional empty states that nudge toward first simulation. |
| Loading indicators during simulation | 3-round LLM simulation takes 10-30 seconds. Without visible progress, users assume it is broken | LOW | Streaming via WebSocket already exists; UI must show per-round progress, not just a spinner. |
| Readable confidence scores with interpretation | Numbers alone (0.73) mean nothing. Indian traders expect a label: "Moderately Bullish", "High Conviction", "Mixed Signals" | LOW | Map numeric consensus to human-readable labels. Sensibull and StockEdge both do this — it is expected. |
| Dark mode (or dark-first UI) | All serious Indian trading tools (Zerodha Kite, Sensibull, TradingView) are dark-first. Light mode in a trading tool signals "not built for traders" | MEDIUM | Tailwind supports dark mode. Needs systematic theme pass, not just background color. |
| Mobile-responsive layout | Indian traders are mobile-first. Over 70% of retail market activity comes from mobile. A desktop-only tool has a narrow addressable audience | MEDIUM | Not for order execution — for pre-market review on the go. Dashboard and simulation history need to be readable at 375px. Agent detail pages can be desktop-only in v1. |
| Simulation history export (CSV/JSON) | Any tool that produces data must let you take your data out. This is a basic trust signal. | LOW | Already in Active requirements. CSV export of history with date, scenario, agent calls, consensus, and outcome. |
| Accurate NSE market data with visible freshness | Traders will not trust signals based on stale data. Timestamp and last-refresh indicator is mandatory | LOW | Data staleness label ("Live", "15-min delay", "Mock data") must be visible on dashboard at all times. |
| Session persistence (survive page refresh) | Losing a running simulation or filled scenario form on accidental refresh destroys trust | LOW | Last scenario inputs and active simulation state should survive a page reload via localStorage or sessionStorage. |
| Basic keyboard navigation | Power users navigate by keyboard. Options traders are fast and do not want to context-switch to mouse for every interaction | LOW | Tab order, Enter to run simulation, Escape to cancel — baseline accessibility that also speeds up expert workflows. |

### Differentiators (Competitive Advantage)

Features that align with the Core Value: "accurate, explainable multi-agent market direction calls that a derivatives trader on Dalal Street would actually use to think through scenarios before market open." These are what make God's Eye worth using instead of a generic AI chatbot or static FII/DII dashboard.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Live market ticker integrated in dashboard | Grounds the simulation in real market context. Trader can see Nifty, Bank Nifty, India VIX while interpreting simulation results — removing the need to alt-tab to NSE | MEDIUM | Already in Active requirements. Use NSE's free public data endpoint. Ticker strip at top of dashboard: Nifty50, Bank Nifty, India VIX, SGX Nifty. |
| Skill injection visibly affecting agent behavior | The auto-learning loop means agents improve over time. If users can see "RBI agent learned: rate hike signals → bearish" and verify it changes outputs, the product becomes self-improving and sticky | MEDIUM | Requires Learning/Skills management UI (already in Active requirements). Display learned skills per agent on the Agent Detail page. |
| Agent disagreement surfacing | When agents diverge sharply (FII bearish, DII bullish), that tension is signal. Most tools just show a consensus number. God's Eye can surface "FII and Promoter agents disagree — here is why" | LOW | Already computable from simulation output. Needs UI treatment: disagreement indicator, expandable explanation. |
| Accuracy-weighted consensus explanation | Showing not just what the consensus is, but which agents drove it and why those agents earned their weights through past accuracy, builds explainability no competitor offers | LOW | "This Bullish call was driven by FII (30% weight, 68% accurate) and DII (25%, 71% accurate)" — visible attribution. |
| Pre-market scenario templates | Derivatives traders run the same mental scenarios every morning: Budget day, RBI MPC, FII sell-off, expiry day. Pre-filled templates reduce friction from 2 minutes to 10 seconds | LOW | 6-8 canned scenario templates covering India-specific events: RBI MPC, FII sell-off, Budget/Union Budget, Earnings season, Global risk-off, Weekly expiry (Thursday), SGX gap scenario |
| India VIX–aware simulation framing | India VIX is the primary fear gauge for Nifty options traders. When VIX > 18, trader posture changes completely. Agents should factor this, and the UI should call it out | LOW | Add India VIX as a fetched live data point. Annotate simulation output with "VIX elevated — confidence bands widen" when VIX > 18. |
| Outcome recording with annotation | Most intelligence tools give you a call but have no loop. God's Eye can close the loop: run simulation, record actual market outcome, annotate what went right/wrong, improve accuracy | MEDIUM | Already partially exists (outcome recording in history). Adding free-text annotation field and summary statistics ("FII agent has been right 7 of last 10 times when calling bullish in expiry week") makes this a true learning journal |
| Simulation result share (image/link) | Indian trading communities on WhatsApp groups and Telegram channels share market views constantly. A one-click "Share this simulation as image" turns every output into organic distribution | MEDIUM | Generate an OG-image-style card: scenario, consensus direction, confidence, top agent call. PNG download or URL-based share. |
| CSV/JSON export for quant overlay | Serious traders want to pull simulation history into Excel or Python and overlay against actual price moves. Export is table stakes, but structured export with all agent scores — not just consensus — is a differentiator | LOW | Export each simulation with full per-agent call, confidence, weight, and outcome if recorded. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like natural additions but would harm the product or violate its core scope.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Live order execution / broker integration | "If you know direction, just one-click trade" is the logical next ask | SEBI regulations require brokerage registration. Legal liability if a bad call causes loss. Scope explosion. The product's value is intelligence, not execution. | Keep paper trading. Let users copy a trade manually using God's Eye as their pre-trade intelligence input. Never connect to a broker API. |
| Portfolio P&L tracking | Traders want to see their positions alongside simulation calls | This requires persistent user accounts, position data, and reconciliation — a separate product. Sidebar already has scope creep with "Portfolio" links from Stitch. | Remove portfolio from sidebar. Defer entirely. Paper trading graduation tracker covers the need for progress measurement. |
| Real-time streaming price feeds with charting | "Show me a Nifty chart" is natural | TradingView, Zerodha Kite already do this perfectly. Duplicating charting against a free NSE feed is low quality and high effort. Traders will have charting open in another window. | Integrate a lightweight ticker strip and link out to TradingView or NSE for actual charting. Do not build charts. |
| Social / community features (sharing calls, leaderboards) | Traders love comparing calls in Discord/Telegram | Multi-user social features require auth infrastructure, moderation, and scale planning that is premature. The tool is explicitly single-user per PROJECT.md. | Post-MVP: share individual simulation cards as images. No user accounts or community features in v1. |
| Backtesting against historical data | "Show me how accurate this would have been in 2023" | Historical data licensing from NSE is expensive and complex. Multi-year backtesting requires a data warehouse. PROJECT.md explicitly defers this to Phase 2. | The accuracy feedback engine auto-tunes weights based on actual outcomes you record. That is a lightweight forward-testing loop, which is enough for v1. |
| Push notifications / alerts ("notify me when market opens") | Users want to be reminded to run pre-market simulation | Requires a background service, push notification infra (FCM/APNs), and a persistent backend — engineering overhead disproportionate to single-user tool value | In v1: let the user bookmark the page and run it manually. In v2: a simple email digest via a cron job is safer than native push. |
| WhatsApp/Telegram bot integration | Large Indian trader community uses WhatsApp groups | Bot infra, rate limiting, multi-user sessions, SEBI communication guidelines for financial advice via messaging apps — all add complexity with no core value contribution in v1 | The share-as-image feature (differentiator above) lets users copy results into WhatsApp manually without a bot. |
| AI chatbot on the dashboard ("ask the agents a question") | Feels like a natural LLM extension | This blurs the product's identity. The simulation is structured (3-round debate, weighted consensus) and that structure is what makes it trustworthy and explainable. A freeform chatbot undermines the discipline. | The structured scenario input form IS the interface for querying the agents. Protect the structured simulation paradigm. |
| Multiple user accounts / team access | "My fund uses this, let multiple analysts share it" | SaaS multi-tenancy is a full product rewrite: auth, billing, data isolation. PROJECT.md explicitly rules this out for v1. | Single-user local deployment is fine for v1. The deployment target (Vercel + Railway) supports per-user self-hosting if needed. |

---

## Feature Dependencies

```
[Auth Flow (Welcome.jsx routed)]
    └──required by──> [Session Persistence]
    └──required by──> [Simulation History Export]

[Agent Naming Consistency]
    └──required by──> [All UI features — history, export, agent detail]

[Live NSE Ticker Integration]
    └──enables──> [India VIX-Aware Simulation Framing]
    └──enables──> [Data Freshness Label]

[Skill Injection (backend)]
    └──required by──> [Learning/Skills Management UI]
    └──enables──> [Agent Disagreement Surfacing (richer context)]

[Outcome Recording (existing)]
    └──enhanced by──> [Outcome Annotation Field]
    └──enables──> [Accuracy Statistics per Agent per Scenario Type]

[Simulation History (existing)]
    └──enhanced by──> [CSV/JSON Export]
    └──enhanced by──> [Simulation Result Share Card]

[Loading Indicators during Simulation]
    └──required by──> [Pre-Market Scenario Templates (UX: fast template load must show progress)]

[Error States]
    └──required by──> [All live-data features — ticker, simulation, NSE fetch]

[Empty States]
    └──required by──> [First-time user experience — history, accuracy chart, paper trading]
```

### Dependency Notes

- **Agent naming consistency is a prerequisite for everything:** Export labels, history display, agent detail pages, and skill attribution all break if names are inconsistent. This must be resolved before any other UI work.
- **Auth flow gates session persistence:** Until Welcome.jsx is routed and auth works end-to-end, session persistence is untestable in a realistic flow.
- **Live ticker gates India VIX awareness:** The India VIX annotation is zero effort once the ticker fetch exists — it is just a threshold check on the fetched VIX value.
- **Skill injection (backend) gates Skills UI:** The wire-up is already in Active requirements. UI should not be built until injection is verified working.
- **Outcome annotation enhances but does not require outcome recording:** Recording already exists; annotation is an additive field.

---

## MVP Definition

The prototype is ~90% functionally complete. "MVP to production" means polish, reliability, and the three things traders will judge in the first 5 minutes.

### Launch With (v1) — Production-Ready Milestone

- [ ] **Agent naming consistency** — Every surface uses plan-specified names. No "Market Maker" vs "Algo/Quant" variance.
- [ ] **Auth flow end-to-end** — Welcome.jsx routed, login works, lands on dashboard.
- [ ] **Error states for simulation and data fetch failures** — Clear messages, retry actions, no blank screens.
- [ ] **Empty states for history and accuracy charts** — Instructional UI that nudges toward first simulation.
- [ ] **Loading indicators showing per-round simulation progress** — WebSocket stream drives visible step indicators (Round 1 of 3 in progress...).
- [ ] **Data freshness label** — Always-visible indicator of whether NSE data is live, delayed, or mock.
- [ ] **Readable consensus labels** — "Strongly Bullish / High Conviction" mapped from numeric score.
- [ ] **Simulation history CSV export** — Full per-simulation record with agent calls, consensus, outcome.
- [ ] **Skill injection wired** — Auto-learned skills reach agent prompts. Learning/Skills UI shows what was learned.
- [ ] **Live NSE ticker strip** — Nifty, Bank Nifty, India VIX on dashboard header.
- [ ] **Sidebar scope cleanup** — Remove Portfolio, Execute Trade, Markets links from Stitch HTML that conflict with out-of-scope features.
- [ ] **Mobile-responsive dashboard and history** — Readable at 375px. Agent detail can stay desktop-only.
- [ ] **Dark mode (or verified dark-first)** — Consistent dark UI across all pages. No jarring light-mode components.
- [ ] **Frontend deployment on Vercel, backend on Railway/Render** — Publicly accessible URL, not localhost.

### Add After Validation (v1.x)

- [ ] **Pre-market scenario templates** — Add after confirming which scenarios users actually run first.
- [ ] **Agent disagreement surfacing** — Add once accuracy feedback shows which agents diverge most usefully.
- [ ] **India VIX–aware simulation framing** — Add with VIX threshold annotation once ticker is live and stable.
- [ ] **Outcome annotation field** — Add once users have recorded several outcomes and request richer notes.
- [ ] **Simulation result share card (image/PNG)** — Add once simulation quality is validated and sharing becomes natural.
- [ ] **Session persistence (last scenario inputs)** — Add once auth flow is stable and users report losing inputs.

### Future Consideration (v2+)

- [ ] **Structured CSV export with full agent scores per simulation** — Defer until users demonstrate quant overlay use case.
- [ ] **Backtesting against historical NSE data** — PROJECT.md explicitly defers. Data licensing required.
- [ ] **Email digest / cron-based reminders** — Defer until engagement data shows users forgetting to run pre-market sims.
- [ ] **Mobile app (PWA or native)** — Defer; web-responsive covers mobile use case for v1.
- [ ] **Multi-user / team access** — Explicit out-of-scope per PROJECT.md. Revisit only if product-market fit established.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Agent naming consistency | HIGH | LOW | P1 |
| Auth flow end-to-end | HIGH | LOW | P1 |
| Error states (simulation + data fetch) | HIGH | LOW | P1 |
| Loading indicators (per-round progress) | HIGH | LOW | P1 |
| Data freshness label | HIGH | LOW | P1 |
| Consensus readable labels | HIGH | LOW | P1 |
| Dark mode / dark-first UI | HIGH | MEDIUM | P1 |
| Mobile-responsive dashboard | HIGH | MEDIUM | P1 |
| History CSV export | MEDIUM | LOW | P1 |
| Sidebar scope cleanup (remove out-of-scope links) | HIGH | LOW | P1 |
| Skill injection wired + Skills UI | HIGH | MEDIUM | P1 |
| Live NSE ticker strip | HIGH | LOW | P1 |
| Frontend + backend deployment | HIGH | MEDIUM | P1 |
| Empty states (history, accuracy) | MEDIUM | LOW | P1 |
| Pre-market scenario templates | HIGH | LOW | P2 |
| Agent disagreement surfacing | HIGH | LOW | P2 |
| India VIX–aware framing | MEDIUM | LOW | P2 |
| Outcome annotation field | MEDIUM | LOW | P2 |
| Simulation result share card | MEDIUM | MEDIUM | P2 |
| Session persistence | MEDIUM | LOW | P2 |
| Full per-agent export (structured CSV) | LOW | LOW | P3 |
| Backtesting | HIGH | HIGH | P3 (deferred) |
| Email digest reminders | LOW | MEDIUM | P3 |
| Multi-user / SaaS | LOW | HIGH | P3 (out of scope v1) |

**Priority key:**
- P1: Must have for launch — product feels broken or untrustworthy without it
- P2: Should have — adds significant value, low risk, add when P1 complete
- P3: Nice to have or explicitly deferred

---

## Competitor Feature Analysis

| Feature | Sensibull | StockEdge | Trendlyne | God's Eye Approach |
|---------|-----------|-----------|-----------|-------------------|
| FII/DII activity tracking | Yes (detailed, 4-tab breakdown) | Yes (basic) | Yes (alerts) | Built-in as first-class agent — not a data page but a simulated actor |
| Market direction call | No (tools, not calls) | Market Mood Index (sentiment gauge) | DVM score (quantitative) | Direct: "Bullish / Bearish / Sideways" with confidence % and agent attribution |
| Explainability | None — shows data, user interprets | None — MMI is a black box score | None — DVM score is opaque | Core differentiator: 3-round debate transcript, per-agent rationale, weight attribution |
| Scenario input ("what if RBI hikes?") | No | No | No | Core feature — structured scenario form drives the simulation |
| Accuracy feedback / self-improvement | No | No | No | Unique: auto-tunes agent weights based on outcome recording |
| Options-specific intelligence | Yes (core product) | Partial (F&O scans) | Partial | Not options-specific — broader market direction intelligence |
| Live data integration | Yes (broker-integrated) | Yes (NSE/BSE) | Yes (NSE/BSE) | NSE data via public endpoint with freshness label |
| Paper trading | Yes (virtual portfolio) | No | No | Yes (with graduation tracker) |
| Export | Limited (no CSV) | Limited | Limited | CSV/JSON export (in Active requirements) |
| Dark mode | Yes | Yes | Yes | Must have — currently unverified |
| Mobile | Yes (native app) | Yes (native app) | Yes | Responsive web — v1 |

---

## Sources

- Sensibull feature documentation: https://sensibull.com / https://web.sensibull.com/fii-dii-data/fno
- Sensibull review and feature breakdown: https://www.strike.money/reviews/sensibull
- StockEdge, Tickertape, Trendlyne comparison: https://help.trendlyne.com/support/solutions/articles/84000396310-trendlyne-vs-stockedge-vs-tickertape-vs-screener-in
- AI tools for Indian stock market 2025: https://thefingain.com/free-ai-tools-for-stock-analysis-india/
- Best Indian trading platforms 2025: https://www.strike.money/options/best-option-trading-platforms-apps-india
- NSE FII/DII data: https://www.nseindia.com/reports/fii-dii
- Empty states UX best practices: https://raw.studio/blog/empty-states-error-states-onboarding-the-hidden-ux-moments-users-notice/
- Dark mode UX for trading tools: https://www.tradesviz.com/blog/darkmode/
- Production web app deployment checklist: https://vercel.com/docs/production-checklist
- Indian stock market alert tools: https://www.pocketful.in/blog/best-stock-alert-apps-in-india/

---
*Feature research for: Multi-Agent Indian Market Intelligence System (God's Eye)*
*Researched: 2026-03-30*
*Confidence: MEDIUM — Indian trading ecosystem well-studied; multi-agent simulation product analogues limited*
