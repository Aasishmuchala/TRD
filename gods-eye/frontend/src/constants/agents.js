/**
 * Canonical agent definitions — single source of truth for all agent data.
 * Backend config.py weights: FII 0.27, DII 0.22, RETAIL_FNO 0.13, ALGO 0.17,
 * PROMOTER 0.05, RBI 0.05, STOCK_OPTIONS 0.04, NEWS_EVENT 0.07 (sum=1.00)
 * Use these exports in all components. Do NOT hardcode agent names, weights, or colors elsewhere.
 *
 * Colors adjusted for light (#FFFFFF) background contrast — WCAG AA compliant.
 */

export const AGENTS = [
  { id: 'FII',            displayName: 'FII Flows Analyst',       shortLabel: 'FII', color: '#DC2626', weight: 0.27 },
  { id: 'DII',            displayName: 'DII Strategy Desk',       shortLabel: 'DII', color: '#059669', weight: 0.22 },
  { id: 'RETAIL_FNO',     displayName: 'Retail F&O Desk',         shortLabel: 'RET', color: '#D97706', weight: 0.13 },
  { id: 'ALGO',           displayName: 'Algo Trading Engine',     shortLabel: 'ALG', color: '#CC152B', weight: 0.17 },
  { id: 'PROMOTER',       displayName: 'Promoter Desk',           shortLabel: 'PRM', color: '#7C3AED', weight: 0.05 },
  { id: 'RBI',            displayName: 'RBI Policy Desk',         shortLabel: 'RBI', color: '#2563EB', weight: 0.05 },
  { id: 'STOCK_OPTIONS',  displayName: 'Stock Options Desk',      shortLabel: 'OPT', color: '#EA580C', weight: 0.04 },
  { id: 'NEWS_EVENT',     displayName: 'News & Event Desk',       shortLabel: 'NWS', color: '#DB2777', weight: 0.07 },
]

export const AGENT_ORDER = AGENTS.map(a => a.id)

export const AGENT_COLORS = Object.fromEntries(AGENTS.map(a => [a.id, a.color]))

export const AGENT_WEIGHTS = Object.fromEntries(AGENTS.map(a => [a.id, a.weight]))

export const AGENT_DISPLAY_NAMES = Object.fromEntries(AGENTS.map(a => [a.id, a.displayName]))

export const AGENT_SHORT_LABELS = Object.fromEntries(AGENTS.map(a => [a.id, a.shortLabel]))

/** Backward-compat label map matching the keys used by AgentAccuracyTable */
export const AGENT_LABELS = Object.fromEntries(AGENTS.map(a => [a.id,
  a.shortLabel === 'RET' ? 'Retail F&O' :
  a.shortLabel === 'ALG' ? 'Algo/Quant' :
  a.shortLabel === 'PRM' ? 'Promoter' :
  a.shortLabel === 'OPT' ? 'Stock Options' :
  a.shortLabel === 'NWS' ? 'News/Event' :
  a.id
]))
