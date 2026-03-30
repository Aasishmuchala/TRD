import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import { apiClient } from '../api/client'

export default function Settings() {
  const [agentWeights, setAgentWeights] = useState({
    FII: 0.30,
    DII: 0.25,
    RETAIL_FNO: 0.15,
    ALGO: 0.10,
    PROMOTER: 0.10,
    RBI: 0.10,
  })
  const [simParams, setSimParams] = useState({
    samples_per_agent: 3,
    interaction_rounds: 3,
    temperature: 0.3,
  })
  const [mockMode, setMockMode] = useState(false)
  const [model, setModel] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

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
      } catch (err) {
        console.error('Failed to load settings:', err)
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
    setAgentWeights({ FII: 0.30, DII: 0.25, RETAIL_FNO: 0.15, ALGO: 0.10, PROMOTER: 0.10, RBI: 0.10 })
    setSimParams({ samples_per_agent: 3, interaction_rounds: 3, temperature: 0.3 })
    setSaved(false)
  }

  const agentLabels = {
    FII: 'FII Flows Analyst',
    DII: 'DII Strategy Desk',
    RETAIL_FNO: 'Retail F&O Desk',
    ALGO: 'Algo Trading Engine',
    PROMOTER: 'Promoter Desk',
    RBI: 'RBI Policy Desk',
  }

  const agentColors = {
    FII: '#FF6B6B',
    DII: '#00E676',
    RETAIL_FNO: '#FFD740',
    ALGO: '#00D4E0',
    PROMOTER: '#BB86FC',
    RBI: '#448AFF',
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
              {Object.entries(agentWeights).map(([agent, weight]) => (
                <div key={agent}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: agentColors[agent] || '#8B95A5' }}
                      />
                      <span className="text-[11px] font-mono text-onSurface">
                        {agentLabels[agent] || agent}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono font-bold" style={{ color: agentColors[agent] }}>
                      {(weight * 100).toFixed(0)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="0.5"
                    step="0.01"
                    value={weight}
                    onChange={(e) => handleWeightChange(agent, e.target.value)}
                    className="w-full h-1 bg-surface-3 rounded-full appearance-none cursor-pointer accent-primary"
                  />
                </div>
              ))}
            </div>
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
