/**
 * God's Eye — Algon.iq-Inspired Light Design System
 *
 * Clean whites, #CC152B red accent, Geist Sans typography.
 * Professional, corporate, generous whitespace.
 */

export const colors = {
  // Core surfaces — white/cream
  surface: {
    base: '#FFFFFF',
    1: '#FAFAFA',
    2: '#F5F5F5',
    3: '#EEEEEE',
    4: '#E0E0E0',
  },

  // Primary accent — Algon red
  primary: {
    glow: '#E8192F',
    DEFAULT: '#CC152B',
    muted: '#A81123',
    dim: '#7A0C19',
  },

  // Signal colors — trading standard (light-theme adjusted)
  bull: {
    bright: '#16A34A',
    DEFAULT: '#059669',
    muted: '#047857',
    dim: '#ECFDF5',
  },
  bear: {
    bright: '#EF4444',
    DEFAULT: '#DC2626',
    muted: '#B91C1C',
    dim: '#FEF2F2',
  },
  neutral: {
    bright: '#F59E0B',
    DEFAULT: '#D97706',
    muted: '#B45309',
    dim: '#FFFBEB',
  },

  // Text hierarchy (dark on light)
  text: {
    primary: '#1A1A1A',
    secondary: '#6B7280',
    muted: '#9CA3AF',
    data: '#374151',
  },

  // Borders
  border: {
    DEFAULT: 'rgba(0,0,0,0.06)',
    hover: 'rgba(0,0,0,0.12)',
    active: 'rgba(204,21,43,0.3)',
  },
}

// Agent identity colors — adjusted for light background contrast
export const agents = {
  FII:        '#DC2626',
  DII:        '#059669',
  RETAIL_FNO: '#D97706',
  ALGO:       '#CC152B',
  PROMOTER:   '#7C3AED',
  RBI:        '#2563EB',
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
  bullish: '#059669',
  bearish: '#DC2626',
  neutral: '#D97706',
}
