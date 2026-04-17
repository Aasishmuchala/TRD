// FE-H5: Validate API_BASE to prevent SSRF via malicious env var
const API_BASE = (() => {
  const base = import.meta.env.VITE_API_BASE || '/api'
  if (!base.startsWith('/') && !base.startsWith('http')) throw new Error('Invalid API_BASE')
  return base
})()

async function request(url, options = {}, retries = 3, timeoutMs = 30000) {
  // TODO (FE-C3): API key stored in localStorage persists across sessions. Moving to
  // sessionStorage would log users out on every tab — acceptable trade-off for single-user tool.
  // Revisit if multi-user auth is added.
  const apiKey = localStorage.getItem('godsEyeApiKey')
  if (apiKey) {
    options.headers = {
      ...options.headers,
      'Authorization': `Bearer ${apiKey}`,
    }
  }

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), timeoutMs)

    try {
      const response = await fetch(url, { ...options, signal: controller.signal })
      clearTimeout(timeout)

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }))
        // Don't retry on client errors (4xx)
        if (response.status >= 500 && attempt < retries) {
          await new Promise(r => setTimeout(r, 1000 * Math.pow(2, attempt)))
          continue
        }
        throw new Error(error.detail || 'Request failed')
      }
      return response.json()
    } catch (err) {
      clearTimeout(timeout)
      // Handle timeout errors
      if (err.name === 'AbortError') {
        if (attempt < retries) {
          await new Promise(r => setTimeout(r, 1000 * Math.pow(2, attempt)))
          continue
        }
        throw new Error('Request timed out')
      }
      // Retry on network errors (fetch failures throw TypeError)
      // FE-C2: Previous heuristic (!err.message.includes('4')) was too broad
      if (attempt < retries && err.name === 'TypeError') {
        await new Promise(r => setTimeout(r, 1000 * Math.pow(2, attempt)))
        continue
      }
      throw err
    }
  }
}

export const apiClient = {
  // Simulation
  simulate: (data) => request(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, 3, 120000),

  // Presets
  getPresets: () => request(`${API_BASE}/presets`),

  // History
  getHistory: (params = {}) => {
    const query = new URLSearchParams(params)
    return request(`${API_BASE}/history?${query}`)
  },

  // Agent info
  getAgent: (agentId) => request(`${API_BASE}/agent/${agentId}`),
  getAgentAccuracy: (agentId, days = 30) => request(`${API_BASE}/agent/${agentId}/accuracy?days=${days}`),

  // Feedback / Accuracy layer
  getFeedbackWeights: (days = 90) => request(`${API_BASE}/feedback/weights?days=${days}`),
  getFailurePatterns: (agentId) => request(`${API_BASE}/feedback/patterns/${agentId}`),

  // Settings
  getSettings: () => request(`${API_BASE}/settings`),
  updateSettings: (settings) => request(`${API_BASE}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  }),

  // Outcome recording
  recordOutcome: (simulationId, actualDirection, notes = '') =>
    request(`${API_BASE}/history/${simulationId}/outcome?actual_direction=${actualDirection}&notes=${encodeURIComponent(notes)}`, {
      method: 'POST',
    }),

  // Live Market Data
  getMarketLive: () => request(`${API_BASE}/market/live`),
  getMarketOptions: (symbol = 'NIFTY') => request(`${API_BASE}/market/options?symbol=${symbol}`),
  getMarketSectors: () => request(`${API_BASE}/market/sectors`),

  // Live Simulation (auto-populates from NSE data)
  simulateLive: () => request(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: 'live' }),
  }),

  // Auth (Codex-style device flow)
  startLogin: (provider = 'openai') => request(`${API_BASE}/auth/login?provider=${provider}`, {
    method: 'POST',
  }),
  pollAuth: (deviceCode, provider = 'openai') => request(`${API_BASE}/auth/poll?device_code=${deviceCode}&provider=${provider}`, {
    method: 'POST',
  }),
  getAuthStatus: () => request(`${API_BASE}/auth/status`),
  logout: () => request(`${API_BASE}/auth/logout`, { method: 'POST' }),

  // Learning / Skills
  getSkills: () => request(`${API_BASE}/learning/skills`),
  getAgentSkills: (agentId) => request(`${API_BASE}/learning/skills/${agentId}`),
  toggleLearning: (enabled) => request(`${API_BASE}/learning/toggle?enabled=${enabled}`, { method: 'POST' }),

  // Paper Trading
  getPaperSummary: () => request(`${API_BASE}/paper-trades/summary`),
  getPaperTrades: (params = {}) => {
    const query = new URLSearchParams(params)
    return request(`${API_BASE}/paper-trades?${query}`)
  },
  getOpenTrades: () => request(`${API_BASE}/paper-trades/open`),
  getTodayTrades: () => request(`${API_BASE}/paper-trades/today`),
  getPaperPnl: (days = 30) => request(`${API_BASE}/paper-trades/pnl?days=${days}`),
  getPaperTrade: (tradeId) => request(`${API_BASE}/paper-trades/${tradeId}`),
  closeAllTrades: () => request(`${API_BASE}/paper-trades/close-all`, { method: 'POST' }),

  // Market Screener
  screenStocks: () => request(`${API_BASE}/market/screener`),

  // Options Suggestion
  getOptionSuggestion: (data) => request(`${API_BASE}/options/suggestion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, 0, 60000),

  // Hybrid Signal (quant + agents + validator)
  getHybridSignal: (instrument, date) => request(`${API_BASE}/hybrid/signal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instrument, date }),
  }, 0, 60000),

  // Quant-only backtest
  runQuantBacktest: (data) => request(`${API_BASE}/backtest/quant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, 0, 600000),

  // Hybrid backtest (quant + LLM)
  runHybridBacktest: (data) => request(`${API_BASE}/backtest/hybrid`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, 0, 600000),

  // Health
  getHealth: () => request(`${API_BASE}/health`),

  // Backtest (10min timeout, no retries — LLM calls are slow)
  runBacktest: (data) => request(`${API_BASE}/backtest/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, 0, 600000),
  getBacktestResult: (runId) => request(`${API_BASE}/backtest/results/${runId}`),
}
