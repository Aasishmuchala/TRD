/**
 * God's Eye — Trading Terminal Design System
 *
 * Bloomberg/TradingView-inspired dark theme with neon accents.
 * Dense data, monospace numbers, command-center feel.
 */

export const colors = {
  // Core surfaces — pure blacks with slight blue undertone
  surface: {
    base: '#0A0A0F',     // Near-black canvas
    1: '#0F1117',         // Card background
    2: '#161922',         // Elevated surface
    3: '#1C1F2B',         // Input/hover state
    4: '#242836',         // Active state
  },

  // Neon accent — electric cyan (primary action)
  primary: {
    glow: '#00F0FF',      // Brightest — scanlines, active borders
    DEFAULT: '#00D4E0',   // CTAs, active states
    muted: '#00A8B3',     // Secondary emphasis
    dim: '#007A82',       // Subtle indicators
  },

  // Signal colors — trading standard
  bull: {
    bright: '#00FF88',    // Neon green — strong buy
    DEFAULT: '#00E676',   // Buy signal
    muted: '#00C853',     // Confirmed bullish
    dim: '#1B5E20',       // Background hint
  },
  bear: {
    bright: '#FF3D71',    // Neon red — strong sell
    DEFAULT: '#FF1744',   // Sell signal
    muted: '#D50000',     // Confirmed bearish
    dim: '#4A1525',       // Background hint
  },
  neutral: {
    bright: '#FFD740',    // Amber — hold/caution
    DEFAULT: '#FFC107',   // Warning
    muted: '#FF8F00',     // Active neutral
    dim: '#3E2723',       // Background hint
  },

  // Text hierarchy
  text: {
    primary: '#E8ECF1',   // Primary text
    secondary: '#8B95A5', // Labels, descriptions
    muted: '#505A6B',     // Inactive, tertiary
    data: '#C5CDD8',      // Data values (monospace)
  },

  // Borders
  border: {
    DEFAULT: 'rgba(255,255,255,0.06)',
    hover: 'rgba(255,255,255,0.12)',
    active: 'rgba(0,212,224,0.3)',
  },
}

// Agent identity colors — each agent gets a unique neon identity
export const agents = {
  FII:        '#FF6B6B',  // Coral red — foreign pressure
  DII:        '#00E676',  // Neon green — domestic stability
  RETAIL_FNO: '#FFD740',  // Amber — retail volatility
  ALGO:       '#00D4E0',  // Cyan — machine precision
  PROMOTER:   '#BB86FC',  // Purple — insider knowledge
  RBI:        '#448AFF',  // Blue — policy authority
}

export const agentLabels = {
  FII: 'FII Flows',
  DII: 'DII Strategy',
  RETAIL_FNO: 'Retail F&O',
  ALGO: 'Algo Engine',
  PROMOTER: 'Promoter Desk',
  RBI: 'RBI Policy',
}

export const sentiment = {
  bullish: '#00E676',
  bearish: '#FF1744',
  neutral: '#FFC107',
}
