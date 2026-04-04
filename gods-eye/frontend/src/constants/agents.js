/**
 * Canonical agent definitions — single source of truth for all agent data.
 * Plan spec: FII 0.30, DII 0.25, Retail F&O 0.15, Algo 0.10, Promoter 0.10, RBI 0.10
 * Use these exports in all components. Do NOT hardcode agent names, weights, or colors elsewhere.
 */

export const AGENTS = [
  { id: 'FII',        displayName: 'FII Flows Analyst',   shortLabel: 'FII', color: '#FF6B6B', weight: 0.30 },
  { id: 'DII',        displayName: 'DII Strategy Desk',   shortLabel: 'DII', color: '#00E676', weight: 0.25 },
  { id: 'RETAIL_FNO', displayName: 'Retail F&O Desk',     shortLabel: 'RET', color: '#FFD740', weight: 0.15 },
  { id: 'ALGO',       displayName: 'Algo Trading Engine', shortLabel: 'ALG', color: '#00D4E0', weight: 0.10 },
  { id: 'PROMOTER',   displayName: 'Promoter Desk',       shortLabel: 'PRM', color: '#BB86FC', weight: 0.10 },
  { id: 'RBI',        displayName: 'RBI Policy Desk',     shortLabel: 'RBI', color: '#448AFF', weight: 0.10 },
]

export const AGENT_ORDER = AGENTS.map(a => a.id)

export const AGENT_COLORS = Object.fromEntries(AGENTS.map(a => [a.id, a.color]))

export const AGENT_WEIGHTS = Object.fromEntries(AGENTS.map(a => [a.id, a.weight]))

export const AGENT_DISPLAY_NAMES = Object.fromEntries(AGENTS.map(a => [a.id, a.displayName]))

export const AGENT_SHORT_LABELS = Object.fromEntries(AGENTS.map(a => [a.id, a.shortLabel]))

/** Backward-compat label map matching the keys used by AgentAccuracyTable */
export const AGENT_LABELS = Object.fromEntries(AGENTS.map(a => [a.id, a.shortLabel === 'RET' ? 'Retail F&O' : a.shortLabel === 'ALG' ? 'Algo/Quant' : a.shortLabel === 'PRM' ? 'Promoter' : a.id]))
