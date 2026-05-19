import { useState, useEffect } from 'react'
// Layout provided by App.jsx
import { apiClient } from '../api/client'
import { AGENT_ORDER, AGENT_DISPLAY_NAMES, AGENT_COLORS, AGENT_WEIGHTS } from '../constants/agents'

export default function Settings() {
  const [agentWeights, setAgentWeights] = useState({ ...AGENT_WEIGHTS })
  const [simParams, setSimParams] = useState({
    samples_per_agent: 3,
    interaction_rounds: 3,
    temperature: 0.3,
  })
  const [quantLlmBalance, setQuantLlmBalance] = useState(45)
  const [mockMode, setMockMode] = useState(false)
  const [model, setModel] = useState('')
  // LLM provider state
  const [providers, setProviders] = useState([])
  const [llmProvider, setLlmProvider] = useState('')
  const [llmApiKey, setLlmApiKey] = useState('')           // user input (write-only)
  const [llmApiKeyMasked, setLlmApiKeyMasked] = useState('') // server preview
  const [llmApiKeySet, setLlmApiKeySet] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [fetchError, setFetchError] = useState(null)

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await apiClient.getSettings()
        if (data.agent_weights) setAgentWeights(data.agent_weights)
        if (data.samples_per_agent) setSimParams(prev => ({ ...prev, samples_per_agent: data.samples_per_agent }))
        if (data.interaction_rounds) setSimParams(prev => ({ ...prev, interaction_rounds: data.interaction_rounds }))
        if (data.temperature != null) setSimParams(prev => ({ ...prev, temperature: data.temperature }))
        if (data.mock_mode != null) setMockMode(data.mock_mode)
        if (data.model) setModel(data.model)
        if (data.quant_llm_balance != null) setQuantLlmBalance(Math.round(data.quant_llm_balance * 100))
        if (data.providers) setProviders(data.providers)
        if (data.llm_provider) setLlmProvider(data.llm_provider)
        if (data.llm_api_key_masked) setLlmApiKeyMasked(data.llm_api_key_masked)
        if (data.llm_api_key_set != null) setLlmApiKeySet(data.llm_api_key_set)
      } catch (err) {
        setFetchError(err.message || 'Failed to load settings')
      } finally {
        setLoading(false)
      }
    }
    fetchSettings()
  }, [])

  const currentProvider = providers.find(p => p.id === llmProvider) || {}
  const modelOptions = currentProvider.available_models && currentProvider.available_models.length
    ? currentProvider.available_models
    : (currentProvider.default_model ? [currentProvider.default_model] : [])

  const handleProviderChange = (pid) => {
    setLlmProvider(pid)
    const p = providers.find(x => x.id === pid)
    if (p && p.default_model) setModel(p.default_model)
    setTestResult(null)
    setSaved(false)
  }

  const handleTestKey = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      // Save first so the backend tests the current form values (provider/model/key)
      await apiClient.updateSettings({
        llm_provider: llmProvider || undefined,
        model: model || undefined,
        ...(llmApiKey ? { llm_api_key: llmApiKey } : {}),
        mock_mode: false,
      })
      // Re-fetch to refresh masked key / mock_mode state
      const fresh = await apiClient.getSettings()
      if (fresh.llm_api_key_masked) setLlmApiKeyMasked(fresh.llm_api_key_masked)
      if (fresh.llm_api_key_set != null) setLlmApiKeySet(fresh.llm_api_key_set)
      if (fresh.mock_mode != null) setMockMode(fresh.mock_mode)
      setLlmApiKey('') // clear input — server now holds it

      const res = await apiClient.testLlmConnection()
      setTestResult(res)
    } catch (err) {
      setTestResult({ ok: false, error: err.message || 'Test failed' })
    } finally {
      setTesting(false)
    }
  }

  const handleWeightChange = (agent, value) => {
    setAgentWeights(prev => ({ ...prev, [agent]: parseFloat(value) }))
    setSaved(false)
  }

  const handleSimParamChange = (param, value) => {
    setSimParams(prev => ({
      ...prev,
      [param]: param === 'temperature' ? parseFloat(value) : parseInt(value),
    }))
    setSaved(false)
  }

  const totalWeight = Object.values(agentWeights).reduce((a, b) => a + b, 0)
  const weightsValid = totalWeight >= 0.99 && totalWeight <= 1.01

  const handleSave = async () => {
    setSaving(true)
    try {
      await apiClient.updateSettings({
        agent_weights: agentWeights,
        samples_per_agent: simParams.samples_per_agent,
        interaction_rounds: simParams.interaction_rounds,
        temperature: simParams.temperature,
        quant_llm_balance: quantLlmBalance / 100,
        llm_provider: llmProvider || undefined,
        model: model || undefined,
        ...(llmApiKey ? { llm_api_key: llmApiKey } : {}),
      })
      // Refresh masked-key preview if a new key was sent
      if (llmApiKey) {
        try {
          const fresh = await apiClient.getSettings()
          if (fresh.llm_api_key_masked) setLlmApiKeyMasked(fresh.llm_api_key_masked)
          if (fresh.llm_api_key_set != null) setLlmApiKeySet(fresh.llm_api_key_set)
          if (fresh.mock_mode != null) setMockMode(fresh.mock_mode)
        } catch { /* non-fatal */ }
        setLlmApiKey('')
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      console.error('Failed to save:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setAgentWeights({ ...AGENT_WEIGHTS })
    setSimParams({ samples_per_agent: 3, interaction_rounds: 3, temperature: 0.3 })
    setQuantLlmBalance(45)
    setSaved(false)
  }

  if (loading) {
    return (
      <>
        <div className="flex items-center justify-center h-full">
          <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING SETTINGS...</span>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="p-4 h-full overflow-y-auto">
        <div className="max-w-3xl">
          {fetchError && (
            <div className="terminal-card p-3 border-l-2 border-bear mb-4">
              <p className="text-xs font-mono text-bear">
                Settings unavailable: {fetchError}. Showing defaults — changes may not persist.
              </p>
            </div>
          )}
          <h1 className="text-xl font-bold text-onSurface mb-1">Settings</h1>
          <p className="text-[10px] font-mono text-onSurfaceDim mb-5">
            MODEL: {model} | MODE: {mockMode ? 'MOCK' : 'LIVE'} | PROVIDER: {llmProvider || '—'}
          </p>

          {/* LLM Provider */}
          <div className="terminal-card p-4 mb-4">
            <div className="flex items-center justify-between mb-4">
              <div className="section-header">LLM Provider</div>
              <span className={`text-[10px] font-mono ${mockMode ? 'text-bear' : llmApiKeySet ? 'text-bull' : 'text-onSurfaceDim'}`}>
                {mockMode ? 'MOCK MODE' : llmApiKeySet ? 'KEY: ' + (llmApiKeyMasked || 'set') : 'NO KEY'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-[10px] font-mono text-onSurfaceDim uppercase mb-1.5">
                  Provider
                </label>
                <select
                  value={llmProvider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="input-field font-mono text-sm w-full"
                >
                  {providers.length === 0 && <option value="">Loading…</option>}
                  {providers.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
                {currentProvider.inference_base && (
                  <p className="text-[9px] font-mono text-onSurfaceDim mt-1 truncate" title={currentProvider.inference_base}>
                    {currentProvider.inference_base}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-[10px] font-mono text-onSurfaceDim uppercase mb-1.5">
                  Model
                </label>
                {modelOptions.length > 0 ? (
                  <select
                    value={model}
                    onChange={(e) => { setModel(e.target.value); setSaved(false) }}
                    className="input-field font-mono text-sm w-full"
                  >
                    {!modelOptions.includes(model) && model && <option value={model}>{model} (custom)</option>}
                    {modelOptions.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={model}
                    onChange={(e) => { setModel(e.target.value); setSaved(false) }}
                    placeholder="claude-opus-4-6"
                    className="input-field font-mono text-sm w-full"
                  />
                )}
                <p className="text-[9px] font-mono text-onSurfaceDim mt-1">
                  {currentProvider.default_model ? `default: ${currentProvider.default_model}` : '\u00a0'}
                </p>
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-mono text-onSurfaceDim uppercase mb-1.5">
                API Key {llmApiKeySet && <span className="text-onSurfaceDim normal-case">(currently: {llmApiKeyMasked})</span>}
              </label>
              <div className="flex gap-2">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={llmApiKey}
                  onChange={(e) => { setLlmApiKey(e.target.value); setSaved(false); setTestResult(null) }}
                  placeholder={currentProvider.key_prefix ? `${currentProvider.key_prefix}...` : (llmApiKeySet ? 'Leave blank to keep current key' : 'Paste your API key')}
                  className="input-field font-mono text-sm flex-1"
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  type="button"
                  onClick={() => setShowKey(s => !s)}
                  className="btn-secondary font-mono text-[10px] tracking-wider px-3"
                >
                  {showKey ? 'HIDE' : 'SHOW'}
                </button>
                <button
                  type="button"
                  onClick={handleTestKey}
                  disabled={testing || (!llmApiKey && !llmApiKeySet)}
                  className="btn-secondary font-mono text-[10px] tracking-wider px-3 disabled:opacity-40"
                >
                  {testing ? 'TESTING…' : 'TEST'}
                </button>
              </div>
              <p className="text-[9px] font-mono text-onSurfaceDim mt-1">
                Stored in backend/.env on save. Never echoed back to the browser.
              </p>

              {testResult && (
                <div className={`mt-3 p-2 border-l-2 ${testResult.ok ? 'border-bull bg-bull/5' : 'border-bear bg-bear/5'}`}>
                  <p className={`text-[10px] font-mono ${testResult.ok ? 'text-bull' : 'text-bear'}`}>
                    {testResult.ok
                      ? `✓ CONNECTED — ${testResult.provider} · ${testResult.model}`
                      : `✗ ${testResult.error || 'Test failed'}`}
                  </p>
                  {testResult.ok && testResult.base_url && (
                    <p className="text-[9px] font-mono text-onSurfaceDim mt-0.5">{testResult.base_url}</p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-gray-100 my-5" />

          {/* Agent Weights */}
          <div className="terminal-card p-4 mb-4">
            <div className="flex items-center justify-between mb-4">
              <div className="section-header">Agent Weights</div>
              <span className={`text-[10px] font-mono ${weightsValid ? 'text-bull' : 'text-bear'}`}>
                Total: {(totalWeight * 100).toFixed(0)}%
              </span>
            </div>

            <div className="space-y-3">
              {AGENT_ORDER.map((agentId) => {
                const weight = agentWeights[agentId] ?? 0
                return (
                  <div key={agentId}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: AGENT_COLORS[agentId] || '#9CA3AF' }}
                        />
                        <span className="text-[11px] font-mono text-onSurface">
                          {AGENT_DISPLAY_NAMES[agentId] || agentId}
                        </span>
                      </div>
                      <span className="text-[11px] font-mono font-bold" style={{ color: AGENT_COLORS[agentId] }}>
                        {(weight * 100).toFixed(0)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="0.5"
                      step="0.01"
                      value={weight}
                      onChange={(e) => handleWeightChange(agentId, e.target.value)}
                      className="w-full h-1 bg-surface-2 rounded-full appearance-none cursor-pointer accent-primary"
                    />
                  </div>
                )
              })}
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-gray-100 my-5" />

          {/* Quant / LLM Balance */}
          <div className="terminal-card p-4 mb-4">
            <div className="section-header mb-4">Quant / LLM Balance</div>
            <div className="mb-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono text-onSurfaceDim uppercase">Balance</span>
                <span className="text-[10px] font-mono text-onSurface">
                  Quant {quantLlmBalance}% / LLM {100 - quantLlmBalance}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={quantLlmBalance}
                onChange={(e) => { setQuantLlmBalance(parseInt(e.target.value)); setSaved(false) }}
                className="w-full h-1 bg-surface-2 rounded-full appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between mt-1">
                <span className="text-[9px] font-mono text-onSurfaceDim">Pure Quant</span>
                <span className="text-[9px] font-mono text-onSurfaceDim">Pure LLM</span>
              </div>
            </div>
            <p className="text-[9px] font-mono text-onSurfaceDim mt-2">
              Flag conflicts when quant-LLM disagreement exceeds 30%
            </p>
          </div>

          {/* Divider */}
          <div className="border-t border-gray-100 my-5" />

          {/* Simulation Parameters */}
          <div className="terminal-card p-4 mb-4">
            <div className="section-header mb-4">Simulation Parameters</div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-[10px] font-mono text-onSurfaceDim uppercase mb-1.5">
                  Samples / Agent
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={simParams.samples_per_agent}
                  onChange={(e) => handleSimParamChange('samples_per_agent', e.target.value)}
                  className="input-field font-mono text-sm w-full"
                />
                <p className="text-[9px] text-onSurfaceDim mt-1">Higher = slower but more robust</p>
              </div>

              <div>
                <label className="block text-[10px] font-mono text-onSurfaceDim uppercase mb-1.5">
                  Interaction Rounds
                </label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={simParams.interaction_rounds}
                  onChange={(e) => handleSimParamChange('interaction_rounds', e.target.value)}
                  className="input-field font-mono text-sm w-full"
                />
                <p className="text-[9px] text-onSurfaceDim mt-1">Agent reaction rounds</p>
              </div>

              <div>
                <label className="block text-[10px] font-mono text-onSurfaceDim uppercase mb-1.5">
                  Temperature: {simParams.temperature.toFixed(2)}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={simParams.temperature}
                  onChange={(e) => handleSimParamChange('temperature', e.target.value)}
                  className="w-full h-1 bg-surface-2 rounded-full appearance-none cursor-pointer accent-primary mt-2"
                />
                <p className="text-[9px] text-onSurfaceDim mt-1">Low = deterministic, High = creative</p>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={handleSave}
              disabled={saving || !weightsValid}
              className={`flex-1 font-mono text-xs tracking-wider py-2.5 rounded-pill transition-all ${
                saved
                  ? 'bg-bull/20 text-bull border border-bull/30'
                  : 'btn-primary'
              } disabled:opacity-50`}
            >
              {saving ? 'SAVING...' : saved ? 'SAVED' : 'SAVE SETTINGS'}
            </button>
            <button onClick={handleReset} className="flex-1 btn-secondary font-mono text-xs tracking-wider">
              RESET DEFAULTS
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
