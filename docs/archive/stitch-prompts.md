# God's Eye — Stitch Design Prompts (Apple + Claude Style)

Design type for each: **poster** (landscape, 1920x1080) or **presentation** slide.

**Global style direction across ALL screens:**

Apple dark mode meets Claude's warm intelligence. Background: #1C1C1E (Apple dark) with subtle warm undertone. Cards use frosted glass effect — semi-transparent white (#FFFFFF at 6-8% opacity) with soft blur backdrop, 16px rounded corners. Primary accent: Claude's warm terracotta/coral (#D97757). Secondary accent: soft amber (#E5A96C). Success green: #34C759 (Apple green). Danger red: #FF453A (Apple red). Text: #F5F5F7 (Apple white) for headers, #A1A1A6 (Apple secondary gray) for body text. Font: SF Pro Display for headers, SF Pro Text for body — clean, spacious, generous letter-spacing. Lots of breathing room between elements. No harsh borders — use subtle shadows and glassmorphism instead. Think: if Apple made a Bloomberg Terminal, and Claude designed the color palette.

---

## SCREEN 1: Main Dashboard

```
Design a premium dark-themed financial dashboard called "God's Eye" in Apple's design language. Resolution 1920x1080. Background #1C1C1E.

TOP BAR: Clean, minimal. Left: "God's Eye" in SF Pro Display medium weight, white #F5F5F7, with a small warm coral (#D97757) circle icon resembling an abstract eye (simple, geometric — just two concentric arcs). Center: "NIFTY 50" label in gray #A1A1A6, then "22,487.35" in large white text, then a small red (#FF453A) pill badge "▼ 1.2%". Next to it, "SENSEX 73,892" in smaller gray text. Right side: "India VIX 14.2" in white, a small green (#34C759) dot with "Live" label, and "09:45 IST" in gray.

LEFT PANEL (28% width) — frosted glass card with rounded corners:
Header: "Scenario" in small gray uppercase tracking-wide text.
Below, clean minimal list of market inputs with labels in gray and values in white, generous line spacing:
  Nifty Spot — 22,487
  India VIX — 14.2
  FII Flow (5d) — -₹8,400 Cr (in Apple red #FF453A)
  DII Flow (5d) — +₹6,200 Cr (in Apple green #34C759)
  USD/INR — 83.72
  PCR — 0.68

Below the inputs, a row of 4 small pill-shaped buttons with frosted glass backgrounds and thin borders: "RBI Cut", "FII Exit", "Budget", "Expiry". Subtle warm coral (#D97757) text.

At the bottom: a clean rounded button with warm coral (#D97757) background and white text "Run Simulation". Apple-style — full-width within the panel, 48px height, 12px rounded corners.

CENTER PANEL (44% width) — the hero section:
Header: "Market Pressure" in small gray uppercase text.

Below, 6 agent rows. Each row is a frosted glass mini-card with:
- Agent name on the left in white (e.g., "FII")
- A horizontal pressure bar in the center: left half represents SELL (Apple red gradient), right half represents BUY (Apple green gradient). A thin white center line. The bar fill shows the agent's direction and conviction.
  - FII: bar extends 78% to the LEFT (sell side) in red gradient
  - DII: bar extends 70% to the RIGHT (buy side) in green gradient
  - Retail F&O: bar extends 55% LEFT in red
  - Algo/Quant: bar extends 40% LEFT in red, more muted
  - Promoter: bar extends 45% RIGHT in green, subtle
  - RBI/Policy: bar barely extends either way, centered, gray
- Conviction percentage on the right in white

Below the pressure bars, a large centered aggregate card:
- "BEARISH" in large SF Pro Display semibold, Apple red (#FF453A)
- Below: a thin semicircular gauge arc (like Apple Watch activity ring style) showing 65% filled in red. "65%" in the center of the arc.
- Below the gauge: "Score: -0.32" in red, and "Quant-LLM: 72%" in warm coral

RIGHT PANEL (28% width) — frosted glass card:
Header: "Insights" in small gray uppercase text.
3 stacked insight cards with very subtle separators (thin #FFFFFF at 5% opacity lines):

Card 1: Small coral dot + "FII" label. Text in #A1A1A6: "DXY above 105 triggers rebalancing. Continued outflows expected over 2-4 weeks."
Card 2: Small green dot + "DII" label. Text: "SIP flows at ₹21K Cr/mo provide structural floor. Deploying into Banks."
Card 3: Small red dot + "Retail" label. Text: "PCR at 0.68 signals excessive bullishness. Expiry in 2 days."

BOTTOM BAR: Very subtle, just text in gray #A1A1A6: "Last run 2m ago" left, "Accuracy 64% ↑" right. No heavy visual treatment.
```

---

## SCREEN 2: Scenario Input (Modal)

```
Design a premium dark modal overlay for a financial app in Apple's design language. Resolution 1920x1080. Background: the dashboard dimmed at 40% opacity behind a centered modal.

MODAL: 880x680px, background #2C2C2E (Apple dark elevated), 20px rounded corners, subtle shadow. No harsh borders.

HEADER: "Configure Scenario" in SF Pro Display medium, white. A small circular X button on the right in gray, Apple style (circle with X inside).

SECTION 1 — "Market Data" label in gray uppercase small text, with a very thin separator line below.

Two columns of inputs. Each input is Apple-style: label in small gray text above, value in a dark rounded input field (#3A3A3C background, 12px rounded corners, white text inside). Generous padding and spacing.

Left column:
  Nifty Spot — 22,487
  India VIX — 14.2
  Gift Nifty — +0.3%
  Advance/Decline — 0.8

Right column:
  USD/INR — 83.72
  DXY Index — 105.2
  Brent Crude — $82.4
  US 10Y Yield — 4.35%

SECTION 2 — "Flow Data" label in gray.
Left:
  FII Net (Today) — -₹3,200 Cr (red text)
  FII 5-Day — -₹8,400 Cr (red)
  FII Futures OI Δ — -12%
Right:
  DII Net (Today) — +₹2,100 Cr (green text)
  DII 5-Day — +₹6,200 Cr (green)
  SIP Inflow — ₹21,000 Cr

SECTION 3 — "Options" label.
Row of 3 inputs:
  PCR — 0.68 | Max Pain — 22,200 | Days to Expiry — 2

SECTION 4 — "Context" label.
A large textarea with rounded corners, dark background, placeholder text in gray: "Add news, events, or context..." About 3 lines tall.

BOTTOM of modal: Left side has a subtle text link "Load Preset ▾" in coral. Right side has two buttons — "Cancel" in gray outlined Apple style, and "Run Simulation" in solid warm coral (#D97757) with white text. Both with Apple-style rounded rectangle shape (12px radius, 44px height).
```

---

## SCREEN 3: Agent Detail View

```
Design a premium dark-themed agent detail page in Apple's design language for a financial simulation app. Resolution 1920x1080. Background #1C1C1E.

TOP: A subtle back chevron "‹ Dashboard" in gray text on the left. Center: "FII Agent" in large white SF Pro Display. Right: a rounded pill badge with red background (#FF453A at 20% opacity) and red text "SELL · 78%".

MAIN LAYOUT — two columns with generous spacing:

LEFT COLUMN (58%):

Card 1 — "Timeframe Analysis" (frosted glass, rounded):
Three equal-width sub-cards side by side:
- "Intraday": a small red down arrow icon, "SELL 65%" in red below it, then small gray text "Gap-down opening expected"
- "Weekly": a small red down arrow, "SELL 78%" in red, "DXY trend continues"
- "Monthly": a small gray dash icon, "HOLD 55%" in gray, "Macro still supportive"
Clean, minimal — like Apple Watch complication cards.

Card 2 — "Reasoning by Round" (frosted glass):
Three sections separated by very thin lines:
"Round 1 · Independent" — white text: "SELL at 80%. DXY above 105, MSCI rebalancing approaching, net F&O position deeply short."
"Round 2 · Reaction" — white text: "Adjusted to 72%. DII absorption capacity provides floor, but insufficient to absorb outflow volume."
"Round 3 · Final" — white text with coral accent: "SELL at 78%. Retail panic signals reinforce thesis."

Card 3 — "Triggers" — a row of small pill tags:
"DXY > 105" (red pill), "MSCI Rebalance" (red pill), "Z-score: -2.3" (amber pill), "USD/INR 84" (amber pill)

RIGHT COLUMN (38%):

Card 4 — "Quantitative Inputs" (frosted glass):
A clean, spacious table with no heavy borders — just alternating subtle row shading:
  Signal | Value | Percentile
  FII 5d Z-score | -2.3 | 4th (red)
  USD/INR Trend | +1.8% | 82nd (amber)
  DXY | 105.2 | 87th (amber)
  MSCI Weight | 18.2% | —
  F&O Position | -₹14.2K Cr | 8th (red)

Card 5 — "30-Day Accuracy" (frosted glass):
A clean line chart, Apple Health style — thin coral line on dark background, showing accuracy fluctuating 55-75% over 30 days. A dashed gray line at 65% labeled "avg". Below: "19/30 correct · Best: SELL calls (78%)" in gray text.

Card 6 — "Interactions" (frosted glass):
Two rows:
"↑ Amplifies" with small red arrow: "Retail panic if Nifty < 22,000"
"↓ Dampened by" with small green arrow: "DII SIP floor at ₹21K Cr/mo"
```

---

## SCREEN 4: Simulation History

```
Design a premium dark-themed history page in Apple's design language for a financial simulation app. Resolution 1920x1080. Background #1C1C1E.

TOP: "History" in large white SF Pro Display on the left. Right: a frosted glass segmented control (Apple style) with "7D | 30D | 90D | All" — "30D" is selected with coral highlight.

MAIN — a clean table in a frosted glass card with generous rounded corners. Apple-style table: no heavy grid lines, just very subtle row separators. Headers in small gray uppercase text.

Columns: Date | Scenario | Call | Confidence | 1-Day | 1-Week | Result

8 rows with generous row height (56px):
Mar 29 | Manual | BEAR ▼ (red) | 65% | ▼ 0.8% (red) | pending (gray) | ● (green dot)
Mar 28 | Expiry Week | BEAR ▼ | 72% | ▼ 1.2% | ▼ 2.1% | ● (green)
Mar 27 | Manual | BULL ▲ (green) | 58% | ▲ 0.3% (green) | ▼ 0.5% (red) | ◐ (half, amber)
Mar 26 | RBI Cut | BULL ▲ | 81% | ▲ 1.5% | ▲ 2.2% | ● (green)
Mar 25 | FII Exodus | BEAR ▼ | 74% | ▼ 1.8% | ▼ 3.1% | ● (green)
Mar 24 | Manual | BULL ▲ | 52% | ▼ 0.4% (red) | ▼ 0.9% | ✕ (red)
Mar 21 | Budget | BULL ▲ | 69% | ▲ 0.9% | ▲ 1.7% | ● (green)
Mar 20 | Manual | BEAR ▼ | 61% | ▼ 0.2% | ▲ 0.5% (green) | ◐ (amber)

BOTTOM — 3 metric cards side by side, frosted glass, Apple style:

Card 1: Large "64%" in coral, "Accuracy" in gray below, small "↑ 3% vs prior month" in green.

Card 2: "Calibration" in gray header. A small clean dot plot (predicted confidence on x-axis vs actual accuracy on y-axis) with a diagonal reference line. Dots in coral. Text below: "Error: 11%"

Card 3: "Agent Ranking" in gray header. 6 rows:
RBI — 73% with thin green bar
FII — 68% with green bar
DII — 65% with green bar
Algo — 63% with amber bar
Retail — 58% with amber bar
Promoter — 55% with amber bar
```

---

## SCREEN 5: Paper Trading Mode

```
Design a premium dark-themed paper trading page in Apple's design language. Resolution 1920x1080. Background #1C1C1E.

TOP BANNER: A frosted glass banner with warm amber (#E5A96C at 15% opacity) background, spanning full width. Icon: a small circular progress ring (like Apple Watch) showing 70% complete. Text: "Paper Trading · 14 of 20 sessions complete" in amber text. Subtle, elegant — not a harsh warning banner.

LEFT HALF (48%):

Card 1 — "Today's Prediction" — large frosted glass card:
Small gray text "Generated 8:45 AM IST · Market opens in 0:30"
Large "BEARISH" text in Apple red (#FF453A), SF Pro Display semibold
Below: "-0.32" score and "65% confidence" with a thin arc gauge (Apple ring style)
Below the gauge: 6 small circular agent indicators in a row, each a small circle with the agent initial inside:
F (red), D (green), R (red), A (red), P (green), RBI (gray)
Small text below each: S, B, S, S, B, H
Bottom of card: "Quant-LLM Agreement: 72%" in coral text

Card 2 — "Accuracy Trend" — frosted glass card:
Apple Health-style line chart — clean coral line showing cumulative accuracy over 14 sessions. Y-axis 40-80%. A dashed gray line at 57% labeled "Pass". The accuracy line sits at 64%, above the threshold. Clean, minimal axes — no heavy gridlines.

RIGHT HALF (48%):

Card 3 — "Graduation Checklist" — frosted glass card:
6 rows, each with Apple-style checkmark circles:
✅ (green filled circle) "1-Day Accuracy ≥ 57%" — "64%" in green right-aligned
✅ "1-Week Accuracy ≥ 60%" — "62%" in green
✅ "Calibration Error < 15%" — "11%" in green
✅ "Agreement Accuracy ≥ 70%" — "73%" in green
⚠️ (amber circle) "No Catastrophic Miss" — "1 borderline" in amber
✅ "Consistency ≥ 75%" — "81%" in green

Clean, spacious rows — like Apple Settings checkmarks.

Card 4 — "Recent Sessions" — frosted glass card:
5 clean rows, Apple list style:
"Mar 29 · BEAR 65% → ▼ 0.8%" with green dot
"Mar 28 · BEAR 72% → ▼ 1.2%" with green dot
"Mar 27 · BULL 58% → ▲ 0.3%" with green dot
"Mar 26 · BULL 81% → ▲ 1.5%" with green dot
"Mar 25 · BEAR 74% → ▼ 1.8%" with green dot

BOTTOM: Two buttons, Apple style:
Left: "Reset" in gray text (no background, just text button)
Right: "Graduate to Live" — rounded button, currently disabled (gray background, gray text) with small lock icon. Tooltip-style text below: "1 criterion remaining"
```

---

## SCREEN 6: Settings

```
Design a premium dark-themed settings page in Apple's design language. Resolution 1920x1080. Background #1C1C1E.

LEFT SIDEBAR (220px): Apple Settings style — a frosted glass sidebar with menu items. Each item has a small icon and label:
🎛 Agent Weights (active — highlighted with coral background at 15% opacity, coral text)
🔑 API Keys
📊 Data Sources
📝 Prompts
🔔 Alerts

MAIN CONTENT — "Agent Weights":

Header: "Agent Weights" in large white SF Pro Display. Subtitle in gray: "Configure how much each agent influences the final score."

6 agent rows in a frosted glass card, Apple style with generous spacing:
Each row: agent name and icon on left, a clean slider in the center (Apple-style with coral (#D97757) fill and white thumb), value on right.

FII — ━━━━━━━━━━○━━━━ — 0.30
DII — ━━━━━━━━○━━━━━━ — 0.25
Retail F&O — ━━━━━━○━━━━━━━━ — 0.15
Algo/Quant — ━━━━○━━━━━━━━━━ — 0.10 (small lock icon, since it's the quant agent)
Promoter — ━━━━○━━━━━━━━━━ — 0.10
RBI/Policy — ━━━━○━━━━━━━━━━ — 0.10

Below: "Total: 1.00" with a small green checkmark.

Toggle row (Apple style — rounded toggle): "Auto-tune from accuracy data" — toggle ON (coral color). Gray subtext: "Monthly adjustment based on rolling 30-day performance."

SECTION 2 — "Simulation" header in white:
3 rows, Apple Settings style:
"Samples per Agent" — right-aligned "3" with chevron
"Temperature" — a clean slider at 0.3
"Interaction Rounds" — right-aligned "3" with chevron

SECTION 3 — "Quant / LLM Balance":
A slider with "Quant" label on left, "LLM" on right. Thumb at 45/55 position. Below: Apple-style toggle row: "Flag high uncertainty on >30% disagreement" — ON.

BOTTOM: "Reset Defaults" in gray text on left, "Save" button in coral on right.
```

---

## SCREEN 7: Login / Welcome

```
Design a premium dark welcome screen in Apple's design language blended with Claude's warm aesthetic. Resolution 1920x1080. Background: a subtle gradient from #1C1C1E to #2C2C2E with a very faint warm glow in the center (#D97757 at 3% opacity, large blur radius — like a warm light behind frosted glass).

CENTER — vertically and horizontally centered, with generous whitespace:

A minimal geometric eye icon — two thin concentric arcs in warm coral (#D97757), with a small filled coral circle as the pupil. Clean, Apple-quality iconography. About 64x40px.

Below the icon (20px gap): "God's Eye" in large SF Pro Display light weight, white #F5F5F7, generous letter-spacing (tracked out slightly).

Below (8px gap): "Multi-Agent Indian Market Intelligence" in SF Pro Text, gray #A1A1A6, smaller size.

Below (40px gap): A subtle visualization — 6 small circles arranged in a loose hexagonal pattern, connected by very thin gray lines (#FFFFFF at 8% opacity). Each circle is labeled in tiny text: FII, DII, Retail, Algo, Promoter, RBI. The FII and Retail circles have a faint red glow, DII and Promoter have faint green glow, RBI is neutral gray, Algo is coral. Very subtle — suggests the multi-agent network.

Below the visualization (40px gap):
An Apple-style input field — rounded rectangle, #3A3A3C background, 48px height, full 380px width. Placeholder text in gray: "Claude API Key". Small key icon on the left inside the input.

Below (16px gap): A rounded button, full 380px width, 48px height, warm coral (#D97757) background, white text "Get Started". Apple's rounded rectangle style.

Below (12px gap): Very small gray text "Stored locally · Never transmitted" with a small lock icon.

VERY BOTTOM (bottom margin 32px): "v1.0 · Built with Claude" in tiny gray text, centered.
```
