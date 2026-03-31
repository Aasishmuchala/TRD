const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(url, options = {}, retries = 3, timeoutMs = 30000) {
  // Attach auth header from localStorage if available
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
      // Retry on network errors but not on client errors
      if (attempt < retries && !err.message.includes('4')) {
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
  }),

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

  // Health
  getHealth: () => request(`${API_BASE}/health`),

  // Backtest (10min timeout, no retries — LLM calls are slow)
  runBacktest: (data) => request(`${API_BASE}/backtest/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, 0, 600000),
  getBacktestResult: (runId) => request(`${API_BASE}/backtest/results/${runId}`),

  // Fast Backtest — Rules-Only (quant engine, ~1yr in <10s)
  runQuantBacktest: (data) => request(`${API_BASE}/backtest/quant-run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, 0, 60000),

  // Fast Backtest — Hybrid (rules + agents, ~1mo in <5min)
  runHybridBacktest: (data) => request(`${API_BASE}/backtest/hybrid-run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }, 0, 600000),
}
