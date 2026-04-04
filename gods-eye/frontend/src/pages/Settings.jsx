import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
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
      } catch (err) {
        setFetchError(err.message || 'Failed to load settings')
      } finally {
        setLoading(false)
      }
    }
    fetchSettings()
  }, [])

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
      })
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
      <Layout>
        <div className="flex items-center justify-center h-[calc(100vh-2.5rem)]">
          <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING SETTINGS...</span>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-5 h-[calc(100vh-2.5rem)] overflow-y-auto">
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
            MODEL: {model} | MODE: {mockMode ? 'MOCK' : 'LIVE'}
          </p>

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
                          style={{ backgroundColor: AGENT_COLORS[agentId] || '#8B95A5' }}
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
                      className="w-full h-1 bg-surface-3 rounded-full appearance-none cursor-pointer accent-primary"
                    />
                  </div>
                )
              })}
            </div>
          </div>

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
                className="w-full h-1 bg-surface-3 rounded-full appearance-none cursor-pointer accent-primary"
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
                  className="w-full h-1 bg-surface-3 rounded-full appearance-none cursor-pointer accent-primary mt-2"
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
              className={`flex-1 font-mono text-xs tracking-wider py-2.5 rounded-lg transition-all ${
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
    </Layout>
  )
}
