# God's Eye Frontend - Quick Start Guide

## Prerequisites
- Node.js 16+ (LTS recommended)
- npm 8+

## Installation

```bash
cd /sessions/busy-friendly-rubin/mnt/TRD/gods-eye/frontend
npm install
```

## Development

Start the development server:
```bash
npm run dev
```

The app will open at `http://localhost:5173`

## First Run

1. You'll land on the **Welcome** page
2. Enter any valid API key (format: `sk-ant-...`)
3. Click "Get Started" to navigate to the Dashboard

The API key is stored locally in `localStorage` under `godsEyeApiKey`.

## API Proxy Configuration

By default, the app proxies requests to `http://localhost:8000/api`. If your backend runs elsewhere, update `vite.config.js`:

```javascript
proxy: {
  '/api': {
    target: 'http://your-backend:port',
    changeOrigin: true,
  }
}
```

## Mock Data

Components include mock data as fallbacks. They'll automatically use real API responses when available. This allows development without a running backend.

## Key Files to Know

| File | Purpose |
|------|---------|
| `src/App.jsx` | Router & private route wrapper |
| `src/pages/*` | Page components |
| `src/components/*` | Reusable UI components |
| `src/hooks/useSimulation.js` | Simulation API hook |
| `src/api/client.js` | API client methods |
| `src/utils/colors.js` | Design system tokens |
| `src/index.css` | Tailwind + custom styles |

## Component Tree

```
App (Router)
├── Welcome (public route)
└── Layout (private routes wrapper)
    ├── Sidebar
    ├── TopNav
    └── Page Content
        ├── Dashboard
        │   ├── ScenarioPanel
        │   ├── PressurePanel
        │   │   ├── AgentPressureBar (6x)
        │   │   └── DirectionGauge
        │   └── InsightsPanel
        ├── AgentDetail
        ├── SimulationHistory
        ├── PaperTrading
        │   ├── AccuracyChart
        │   └── GraduationChecklist
        └── Settings
```

## Tailwind Classes Reference

**Glass Cards:**
- `.glass-card` - Small card with blur & border
- `.glass-card-lg` - Large card variant

**Buttons:**
- `.btn-primary` - Primary action (coral gradient)
- `.btn-secondary` - Secondary action

**Inputs:**
- `.input-field` - Text input with focus styling

**Text:**
- `.stat-value` - Large stat display
- `.stat-label` - Stat label

**Utilities:**
- `gradient-primary` - Background gradient
- `gradient-primary-text` - Text gradient

## Build for Production

```bash
npm run build
```

Outputs to `dist/` directory. Deploy the contents.

## Troubleshooting

**Port 5173 already in use?**
```bash
npm run dev -- --port 5174
```

**API not connecting?**
Check `vite.config.js` proxy target matches your backend URL.

**Import errors?**
Run `npm install` again to ensure all dependencies are installed.

**Styling looks off?**
Clear browser cache (Cmd+Shift+R or Ctrl+Shift+F5).

## Project Stats

- **26 Component Files** (6 pages, 13 components, hooks, API)
- **~2000 Lines of Code** (fully functional)
- **Zero External UI Libraries** (pure Tailwind)
- **Charts via Recharts** (lightweight)
- **Design System Tokens** in Tailwind config

## Next Steps

1. Start dev server: `npm run dev`
2. Explore all pages via sidebar navigation
3. Try the "Run Simulation" flow on Dashboard
4. Check out Paper Trading graduation criteria
5. Customize agent weights in Settings

The entire design from the Stitch DESIGN.md is now interactive and ready to use!
