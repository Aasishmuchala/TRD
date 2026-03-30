# God's Eye Frontend

Complete React + Vite + Tailwind CSS implementation of the God's Eye multi-agent market intelligence system.

## Project Structure

```
frontend/
├── src/
│   ├── pages/               # Page components
│   │   ├── Welcome.jsx      # Authentication + onboarding
│   │   ├── Dashboard.jsx    # Main simulation interface
│   │   ├── AgentDetail.jsx  # Agent analysis
│   │   ├── SimulationHistory.jsx
│   │   ├── PaperTrading.jsx # Graduation tracking
│   │   └── Settings.jsx     # Configuration
│   ├── components/          # Reusable components
│   │   ├── Layout.jsx       # Sidebar + TopNav shell
│   │   ├── Sidebar.jsx
│   │   ├── TopNav.jsx
│   │   ├── ScenarioPanel.jsx
│   │   ├── PressurePanel.jsx
│   │   ├── InsightsPanel.jsx
│   │   ├── AgentPressureBar.jsx
│   │   ├── DirectionGauge.jsx
│   │   ├── GraduationChecklist.jsx
│   │   ├── AccuracyChart.jsx
│   │   └── ScenarioModal.jsx
│   ├── hooks/               # Custom React hooks
│   │   └── useSimulation.js
│   ├── api/                 # API client
│   │   └── client.js
│   ├── utils/               # Utilities
│   │   └── colors.js        # Design system tokens
│   ├── App.jsx              # Router setup
│   ├── main.jsx             # Entry point
│   └── index.css            # Tailwind + custom styles
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## Design System

**Colors:**
- Surface hierarchy: #131315 → #1B1B1D → #2A2A2C → #39393B
- Primary gradient: #FFB59E → #D97757 (coral)
- Success/Tertiary: #5EDAC7 (teal)
- Error: #FFB4AB (red)
- Text: #E4E2E4 (primary), #DBC1B9 (muted)

**Components:**
- Glass cards with backdrop-filter blur(20px)
- No 1px borders (use subtle shadows instead)
- Smooth transitions and animations
- Responsive Tailwind utilities

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start development server:**
   ```bash
   npm run dev
   ```
   Opens at `http://localhost:5173`

3. **Build for production:**
   ```bash
   npm run build
   ```

## API Integration

The app proxies `/api/*` requests to `http://localhost:8000/api`. Configure in `vite.config.js`.

Required endpoints:
- `POST /api/simulate` - Run simulation
- `GET /api/presets` - Fetch scenario presets
- `GET /api/history` - Simulation history
- `GET /api/agent/{id}` - Agent details
- `GET /api/settings` - User settings
- `POST /api/settings` - Update settings

## Authentication

API key is stored in `localStorage` under `godsEyeApiKey`. Private routes check for this key on mount.

## Pages

### Welcome
- Geometric eye SVG icon
- Agent network hexagon
- API key input
- Stores key in localStorage

### Dashboard
- 3-panel layout (28% | 44% | 28%)
- Live market data in TopNav
- Run simulation with modal confirmation
- Real-time pressure bars and direction gauge

### AgentDetail
- Agent analysis with timeframe rings
- Reasoning by round (R1-R3)
- Active triggers
- Quantitative inputs table
- 30-day accuracy chart

### SimulationHistory
- Time filters (7D, 30D, 90D, All)
- Historical simulation results
- Accuracy metrics
- Sortable table

### PaperTrading
- Progress ring (14/20)
- Today's prediction card
- 6 agent consensus
- Graduation checklist (6 criteria)
- Recent sessions
- Reset/Graduate buttons

### Settings
- Agent weight sliders (≥ 6 agents)
- Simulation parameters (samples, rounds, temperature)
- Quant/LLM balance slider
- Save/Reset buttons

## Components

### ScenarioPanel
- Market inputs list
- 4 preset scenario buttons
- "Run Simulation" CTA
- Loading state

### PressurePanel
- 6 agent pressure bars
- DirectionGauge (bullish/bearish/neutral)
- Quant-LLM confidence display

### InsightsPanel
- 3 key insight cards
- Status indicators (last run, accuracy, connected)

### DirectionGauge
- SVG arc gauge
- Dynamic coloring by sentiment
- Magnitude + confidence display

### AccuracyChart
- Recharts line chart
- 30-day data points
- Responsive container

## Development

- **React 18.3** with hooks
- **React Router 6.26** for navigation
- **Recharts 2.12** for visualizations
- **Tailwind CSS 3.4** for styling
- **Vite 5.4** for build tooling

## Customization

### Adding New Agents
Update `AGENTS` array in `PressurePanel.jsx` and add colors in `utils/colors.js`:
```javascript
export const agents = {
  YourAgent: '#COLOR_HEX',
}
```

### Styling
All custom styles are in `src/index.css` with Tailwind `@layer` components. Extend colors in `tailwind.config.js`.

### API Mocking
Components have mock data as fallback. Real API responses will override these defaults automatically.

## Notes

- Glass morphism effects use `backdrop-blur-xl` with subtle borders
- Animations are GPU-accelerated transitions
- Responsive design uses Tailwind grid system
- Icons are emoji for simplicity (can be replaced with SVGs)
- Chart colors match design system palette
