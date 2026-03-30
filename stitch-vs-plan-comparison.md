# God's Eye: Stitch UI vs Plan Specification — Full Comparison

## Summary

After comparing all 6 Stitch-generated HTML screens against the master plan (`gods-eye-plan.md`) and the original Stitch prompts (`stitch-prompts.md`), I've identified **32 differences** across 7 categories. Some are cosmetic, some are structural, and a few are critical misalignments that need decisions before we build.

---

## 1. AGENT NAMING — CRITICAL MISMATCH

This is the biggest issue. The plan defines 6 specific India-market agents, but Stitch used different names across different screens, and no screen is fully consistent with the plan.

### Plan Specification (Source of Truth)
| # | Agent Name | Short Label |
|---|-----------|-------------|
| 1 | FII (Foreign Institutional) | FII |
| 2 | DII (Domestic Institutional) | DII |
| 3 | Retail F&O Trader | Retail |
| 4 | Algo/HFT (Quant) | Algo |
| 5 | Promoter/Insider | Promoter |
| 6 | RBI/Policy | RBI |

### What Each Stitch Screen Shows

| Screen | Agent 1 | Agent 2 | Agent 3 | Agent 4 | Agent 5 | Agent 6 | Match? |
|--------|---------|---------|---------|---------|---------|---------|--------|
| **Welcome** (hexagon) | FII | DII | SEC | SENT | VOL | MAC | NO — 4/6 wrong |
| **Dashboard** (pressure bars) | FII | DII | Retail | Algo | Promoter | RBI | YES |
| **Agent Detail** | FII Agent | — | — | — | — | — | Partial (only shows FII) |
| **Paper Trading** (circles) | F (FED) | D (DATA) | R (RETAIL) | A (ALGO) | P (POLI) | RBI (SENTI) | NO — labels wrong |
| **Settings** (weights) | FII Intelligence | DII Sentiment | Global Macro | Editorial Signal | Technical Cluster | Alternative Data | NO — 4/6 wrong |

**Decision needed:** The Dashboard is the only screen that matches the plan. All other screens need agent names corrected to: FII, DII, Retail F&O, Algo/Quant, Promoter, RBI.

---

## 2. AGENT WEIGHTS — MISMATCH

### Plan Specification
| Agent | Weight |
|-------|--------|
| FII | 0.30 |
| DII | 0.25 |
| Retail F&O | 0.15 |
| Algo/Quant | 0.10 |
| Promoter | 0.10 |
| RBI/Policy | 0.10 |
| **Total** | **1.00** |

### Stitch Settings Page
| Agent (wrong name) | Weight |
|--------------------|--------|
| FII Intelligence | 0.35 |
| DII Sentiment | 0.25 |
| Global Macro | 0.15 |
| Editorial Signal | 0.10 |
| Technical Cluster | 0.10 |
| Alternative Data | 0.05 |
| **Total** | **1.00** |

**Differences:**
- FII weight: Plan says 0.30, Stitch says 0.35
- Smallest weight: Plan says 0.10 (three agents), Stitch says 0.05 (Alternative Data)
- Agent names are completely different (as noted above)

**Decision needed:** Use plan weights (0.30/0.25/0.15/0.10/0.10/0.10) with correct agent names.

---

## 3. NAVIGATION & LAYOUT — STRUCTURAL DIFFERENCE

### Plan Specification
- Dashboard is a standalone 3-panel layout (Scenario 28% | Pressure 44% | Insights 28%)
- No persistent sidebar mentioned anywhere in the plan
- Navigation between screens is implied but not specified

### Stitch Implementation
- **Welcome screen:** No sidebar, no top nav — clean centered layout (MATCHES plan intent)
- **Dashboard:** Has a top nav bar with NIFTY 50/SENSEX/BANK NIFTY tabs, notification and settings icons. No sidebar. (MOSTLY matches — top nav is a reasonable addition)
- **Scenario Modal:** Overlays on dimmed dashboard (MATCHES plan)
- **Agent Detail, Paper Trading, Settings:** All have a persistent left sidebar (264px) with:
  - "Terminal" branding with "V2.4.0 High-Frequency" version label
  - Nav items: Intelligence, Portfolio, Markets, Agents, History
  - "Execute Trade" CTA button
  - Help and Sign Out links

**Issues with the sidebar:**
1. "Terminal" branding and "V2.4.0 High-Frequency" — not in plan, implies a trading terminal rather than a simulation tool
2. "Portfolio" nav item — plan explicitly says "NOT In Scope: Portfolio management features"
3. "Execute Trade" button — plan explicitly says "NOT In Scope: Live order execution"
4. "Markets" nav item — not specified in plan

**Decision needed:** Remove sidebar elements that conflict with plan scope (Portfolio, Execute Trade, Markets). Either simplify to: Dashboard, Agents, History, Paper Trading, Settings — or remove the sidebar entirely and use the top nav for page switching.

---

## 4. MISSING SCREEN — SIMULATION HISTORY

### Plan Prompt (Screen 4)
The stitch prompts included a detailed Simulation History screen with:
- Time filter segmented control (7D | 30D | 90D | All)
- Table with columns: Date, Scenario, Call, Confidence, 1-Day, 1-Week, Result
- 8 sample rows with green/amber/red result indicators
- Bottom metric cards: Accuracy (64%), Calibration dot plot, Agent Ranking

### Stitch Output
**This screen was never generated.** Only 6 of 7 screens were produced.

**Decision needed:** This screen needs to be built from the prompt specification. It's essential for the self-learning feedback loop.

---

## 5. GRADUATION CRITERIA — PAPER TRADING PAGE

### Plan Specification (6 criteria)
| # | Criterion | Threshold |
|---|-----------|-----------|
| 1 | Directional accuracy (1-day) | ≥ 57% over 20 sessions |
| 2 | Directional accuracy (1-week) | ≥ 60% over 4 weeks |
| 3 | Calibration error | < 15% |
| 4 | Quant-LLM agreement accuracy | ≥ 70% when both agree |
| 5 | No catastrophic miss | Didn't miss >3% move with high-confidence wrong call |
| 6 | Internal consistency | LLM agents agree with themselves ≥ 75% across 3 samples |

### Stitch Paper Trading Page (5 criteria)
| # | Criterion | Threshold | Value Shown |
|---|-----------|-----------|-------------|
| 1 | 1-Day Forecast Accuracy | > 60% | 68.4% ✅ |
| 2 | Calibration Error | < 0.15 | 0.09 ✅ |
| 3 | Consistency Score | Min. 20 Sessions | 14/20 ◐ |
| 4 | Risk Management Compliance | — | PENDING |
| 5 | Max Drawdown Verification | — | PENDING |

**Differences:**
- Plan has 6 criteria, Stitch shows 5
- 1-Day threshold: Plan says ≥57%, Stitch says >60%
- Missing from Stitch: 1-Week accuracy (≥60%), Quant-LLM agreement (≥70%), No catastrophic miss
- Added in Stitch (not in plan): Risk Management Compliance, Max Drawdown Verification
- Consistency: Plan says "≥75% across 3 samples" (LLM internal), Stitch says "Min 20 sessions" (different metric)

**Decision needed:** Use plan's 6 criteria with exact thresholds. The Stitch additions (Risk Management, Max Drawdown) could be added as nice-to-haves.

---

## 6. QUANT/LLM BALANCE — SETTINGS PAGE

### Plan Specification
- Quant weight: 0.45 (fixed)
- LLM weight: 0.55 (adjustable based on accuracy)
- Flag conflicts when agreement < 0.3
- Stitch prompt said: slider at "45/55 position"

### Stitch Settings Page
- Slider at value="70" (70% toward LLM side)
- Label says "High LLM balance prioritizes narrative nuance"
- Flag threshold described as "confidence < 85%" (not in plan — plan says ">30% disagreement")

**Differences:**
- Balance: Plan says 45/55 Quant/LLM, Stitch shows 30/70
- Flag trigger: Plan says ">30% disagreement between quant and LLM", Stitch says "confidence < 85%"

**Decision needed:** Use plan's 45/55 default. Flag trigger should be based on quant-LLM disagreement, not raw confidence.

---

## 7. DATA & CONTENT MISMATCHES (Per Screen)

### 7a. Welcome Screen
| Element | Plan/Prompt | Stitch | Issue |
|---------|------------|--------|-------|
| Hexagon node labels | FII, DII, Retail, Algo, Promoter, RBI | FII, DII, SEC, SENT, VOL, MAC | Wrong agent names |
| Node colors | FII+Retail=red glow, DII+Promoter=green, RBI=gray, Algo=coral | FII=green, DII=coral, SEC=gray, SENT=red, VOL=gray, MAC=green | Colors don't match agent sentiment mapping |
| Subtitle | "Multi-Agent Indian Market Intelligence" | Same | ✅ Matches |

### 7b. Main Dashboard
| Element | Plan/Prompt | Stitch | Issue |
|---------|------------|--------|-------|
| Nifty price | 22,487.35 | 22,487.35 ▼1.2% | ✅ Matches |
| Agent pressure bars | FII 78% SELL, DII 70% BUY, Retail 55% SELL, Algo 40% SELL, Promoter 45% BUY, RBI centered | FII 75%, DII 60%, Retail 45%, Algo 82%, Promoter 20%, RBI Neutral | Values differ but structure matches |
| Aggregate badge | "BEARISH" in red with 65% gauge | "BEARISH" with -0.32 score | ✅ Close enough |
| Bottom bar | "Last run 2m ago" + "Accuracy 64% ↑" | Same + added "Secure Node: 0x21...FF" | Extra element not in plan |
| Top nav | Not specified in plan | NIFTY 50, SENSEX tabs + notifications | Reasonable addition |

### 7c. Scenario Input Modal
| Element | Plan/Prompt | Stitch | Issue |
|---------|------------|--------|-------|
| Flow Data fields | 6 fields (FII Net Today, FII 5-Day, FII Futures OI Δ, DII Net Today, DII 5-Day, SIP Inflow) | 3 fields (FII Net/5-Day, DII Net/5-Day, SIP Inflow) | Missing: FII daily, FII Futures OI change, DII daily |
| Flow Data layout | 2 columns of 3 | 1 row of 3 | Different layout |
| Data values | Specific values from prompt | Different values | Minor — sample data |

### 7d. Agent Detail View
| Element | Plan/Prompt | Stitch | Issue |
|---------|------------|--------|-------|
| Timeframe analysis | Text-based (Intraday SELL 65%, Weekly SELL 78%, Monthly HOLD 55%) | Ring gauges (Intraday 72%, Weekly 64%, Monthly 48%) | Different format + values |
| Round 3 display | "White text with coral accent" | Inverted white card with dark text | Stylistic — OK |
| Active triggers | "DXY>105" (red), "MSCI Rebalance" (red), "Z-score:-2.3" (amber), "USD/INR 84" (amber) | Same triggers but different visual treatment | ✅ Close |
| 30-Day Accuracy | "19/30 correct · Best: SELL calls (78%)" | "74.2%" with line chart | Different metric presentation |
| Interactions | "Retail panic if Nifty < 22,000" / "DII SIP floor" | "Amplifies: Yield Agent" / "Dampened By: Retail Pulse" | Wrong agent names in interactions |
| Navigation | "‹ Dashboard" back link | Full sidebar + "‹ Dashboard FII Agent" header | Structural difference |

### 7e. Paper Trading Page
| Element | Plan/Prompt | Stitch | Issue |
|---------|------------|--------|-------|
| Progress ring | 70% (14/20) | Same | ✅ Matches |
| Agent circles | F(red), D(green), R(red), A(red), P(green), RBI(gray) with S/B/S/S/B/H labels | F(FED), D(DATA), R(RETAIL), A(ALGO), P(POLI), RBI(SENTI) | Wrong agent sublabels |
| Accuracy chart threshold | "Pass" at 57% | "Threshold (57%)" | ✅ Matches |
| Recent sessions format | "Mar 29 · BEAR 65% → ▼ 0.8%" with dots | "SESSION_014_ALPHA" with +1.24% and timestamps | Completely different format |
| Quant-LLM Agreement | Shown: "72%" in coral | Not shown | Missing metric |
| Status badges | Not specified | "EVALUATION PHASE" + "Time Left: 06:42:11" | Added (reasonable) |

### 7f. Settings Page
| Element | Plan/Prompt | Stitch | Issue |
|---------|------------|--------|-------|
| Sidebar structure | 5 items: Agent Weights, API Keys, Data Sources, Prompts, Alerts | 5 items under "Preferences" + 5 main nav items + user profile | Extended sidebar |
| User profile | Not in plan | "John Doe, Pro Tier" with avatar | Added — plan says "NOT In Scope: Multi-user / SaaS features" |
| Save/Cancel buttons | "Reset Defaults" + "Save" | "Reset to Default Configuration" + "Discard Changes" + "Save Changes" | Extra button (Discard) |

---

## 8. FEATURES ADDED IN STITCH (Not in Plan)

These elements appear in Stitch designs but were not specified anywhere in the plan:

1. **"Execute Trade" button** — in sidebar of Agent Detail, Paper Trading, Settings
2. **"Portfolio" nav item** — in sidebar
3. **"Markets" nav item** — in sidebar
4. **"Secure Node: 0x21...FF"** — in dashboard footer (implies blockchain/crypto)
5. **"Terminal V2.4.0 High-Frequency"** — branding suggests a trading terminal
6. **User profile (John Doe, Pro Tier)** — implies multi-user/tiers
7. **Session naming (SESSION_014_ALPHA)** — custom naming convention for paper trades
8. **"Time Left" countdown timer** — in paper trading banner
9. **BANK NIFTY tab** — in top nav (only NIFTY 50 and SENSEX mentioned in prompt)

**Recommendation:** Remove items 1-6 (conflict with plan scope). Items 7-9 are reasonable additions to keep.

---

## 9. DECISION SUMMARY

Here's what needs your call before we build:

| # | Decision | Recommendation |
|---|----------|---------------|
| 1 | Agent names across all screens | Standardize to plan: FII, DII, Retail F&O, Algo/Quant, Promoter, RBI |
| 2 | Agent weights | Use plan: 0.30, 0.25, 0.15, 0.10, 0.10, 0.10 |
| 3 | Sidebar nav (Agent Detail, Paper Trading, Settings) | Simplify — remove Portfolio, Execute Trade, Markets |
| 4 | Missing History screen | Build from prompt specification |
| 5 | Graduation criteria | Use plan's 6 criteria with exact thresholds |
| 6 | Quant/LLM balance default | Use plan's 45/55 split |
| 7 | Paper trading session format | Use date-based format from prompt ("Mar 29 · BEAR 65%") not session IDs |
| 8 | Flow Data fields in Scenario Modal | Add missing fields (FII daily, FII Futures OI Δ, DII daily) |
| 9 | User profile / tier system | Remove (not in scope for Phase 1) |
| 10 | "Secure Node" hash | Remove (not relevant to simulation system) |

---

## 10. WHAT STITCH GOT RIGHT

To be fair, Stitch nailed several things:

- **Design system execution** — the glassmorphism, warm coral palette, surface hierarchy, and "no-line rule" are beautifully implemented across all screens
- **Dashboard 3-panel layout** — matches plan perfectly
- **Scenario modal** — clean, well-structured, 4-section layout as specified
- **Agent detail view structure** — timeframe analysis, reasoning by round, triggers, quantitative inputs, accuracy chart, interactions — all present
- **Paper trading progress ring** — matches prompt exactly
- **Overall aesthetic** — the "Apple dark mode + Claude warm" vibe is consistent and premium
- **Typography and spacing** — SF Pro Display/Inter with generous whitespace throughout
- **Color tokens** — primary (#FFB59E → #D97757), tertiary (#5EDAC7), error (#FFB4AB) all consistent with DESIGN.md
