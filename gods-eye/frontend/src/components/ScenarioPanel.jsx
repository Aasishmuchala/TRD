import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import CustomScenarioForm from './CustomScenarioForm'

const SCENARIO_ICONS = {
  rbi_rate_cut: 'RBI',
  fii_exodus: 'FII',
  budget_bull: 'BDG',
  budget_bear: 'BDG',
  expiry_carnage: 'EXP',
  global_contagion: 'GLB',
  adani_shock: 'ADN',
  election_day: 'ELC',
}

const DIRECTION_STYLES = {
  STRONG_BUY: { color: '#059669', bg: 'rgba(5,150,105,0.08)', border: 'rgba(5,150,105,0.2)' },
  BUY: { color: '#059669', bg: 'rgba(5,150,105,0.06)', border: 'rgba(5,150,105,0.15)' },
  HOLD: { color: '#D97706', bg: 'rgba(217,119,6,0.06)', border: 'rgba(217,119,6,0.15)' },
  SELL: { color: '#DC2626', bg: 'rgba(220,38,38,0.06)', border: 'rgba(220,38,38,0.15)' },
  STRONG_SELL: { color: '#DC2626', bg: 'rgba(220,38,38,0.08)', border: 'rgba(220,38,38,0.2)' },
}

const fallbackScenarios = [
  { scenario_id: 'rbi_rate_cut', name: 'RBI Rate Cut', description: 'Monetary easing scenario', expected_direction: 'STRONG_BUY' },
  { scenario_id: 'fii_exodus', name: 'FII Mass Exodus', description: 'Foreign fund outflow', expected_direction: 'STRONG_SELL' },
  { scenario_id: 'budget_bull', name: 'Budget Bull', description: 'Fiscal stimulus', expected_direction: 'STRONG_BUY' },
  { scenario_id: 'expiry_carnage', name: 'Expiry Carnage', description: 'Derivatives expiration', expected_direction: 'SELL' },
]

export default function ScenarioPanel({ onSimulate, isLoading }) {
  const [scenarios, setScenarios] = useState(fallbackScenarios)
  const [selected, setSelected] = useState(null)
  const [liveAvailable, setLiveAvailable] = useState(false)
  const [marketOpen, setMarketOpen] = useState(null)
  const [dataError, setDataError] = useState(null)
  const [showCustom, setShowCustom] = useState(false)

  useEffect(() => {
    apiClient.getPresets()
      .then((presets) => { if (presets?.length) setScenarios(presets) })
      .catch(() => null)

    // Check if live market data is reachable, retry every 15s if not
    const checkLive = () => {
      apiClient.getMarketLive()
        .then((data) => {
          setMarketOpen(data?.market_open ?? false)
          if (data?.nifty_spot > 0 && data?.data_source !== 'error') {
            setLiveAvailable(true)
            setDataError(null)
          } else {
            setLiveAvailable(false)
            setDataError(data?.data_error || (data?.market_open ? 'Live data unavailable' : null))
          }
        })
        .catch(() => { setLiveAvailable(false); setMarketOpen(null); setDataError('Backend unreachable') })
    }
    checkLive()
    const interval = setInterval(checkLive, 15000)
    return () => clearInterval(interval)
  }, [])

  const handleSimulate = () => {
    if (!selected) return
    onSimulate({
      scenario_id: selected.scenario_id,
      name: selected.name,
      description: selected.description,
    })
  }

  const handleSimulateLive = () => {
    onSimulate({
      source: 'live',
      name: 'Live Market',
      description: 'Simulating against real-time NSE data',
    })
  }

  if (showCustom) {
    return (
      <CustomScenarioForm
        onSimulate={onSimulate}
        isLoading={isLoading}
        onClose={() => setShowCustom(false)}
      />
    )
  }

  return (
    <div className="terminal-card-lg p-5 flex flex-col h-full">
      <div className="flex items-center justify-between">
        <div className="section-header mb-0">Scenario Select</div>
        <button
          onClick={() => setShowCustom(true)}
          className="text-[9px] font-mono text-primary border border-primary/20 bg-primary/5 px-2 py-1 rounded hover:bg-primary/10 transition-colors"
        >
          CUSTOM
        </button>
      </div>
      <div className="h-3" />

      {/* Selected info */}
      {selected && (
        <div className="mb-4 px-3 py-2.5 bg-surface-1 rounded-lg border border-primary/15">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-onSurfaceDim uppercase">Active</span>
            <span
              className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded"
              style={{
                color: DIRECTION_STYLES[selected.expected_direction]?.color || '#D97706',
                backgroundColor: DIRECTION_STYLES[selected.expected_direction]?.bg || 'rgba(217,119,6,0.06)',
                border: `1px solid ${DIRECTION_STYLES[selected.expected_direction]?.border || 'rgba(217,119,6,0.15)'}`,
              }}
            >
              {selected.expected_direction}
            </span>
          </div>
          <p className="text-sm font-semibold text-onSurface mt-1">{selected.name}</p>
          <p className="text-[11px] text-onSurfaceMuted mt-0.5">{selected.description}</p>
        </div>
      )}

      {/* Live Market Button */}
      <button
        onClick={handleSimulateLive}
        disabled={isLoading || (!liveAvailable && !marketOpen)}
        aria-label="Simulate live market with real-time NSE data"
        className={`w-full mb-3 px-3 py-3 rounded-lg text-left transition-all duration-150 border ${
          liveAvailable
            ? 'border-bull/25 bg-bull/5 hover:bg-bull/10'
            : marketOpen
              ? 'border-amber-500/25 bg-amber-500/5 hover:bg-amber-500/10'
              : 'border-gray-100 bg-surface-1 opacity-50'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-md flex items-center justify-center text-[10px] font-mono font-bold flex-shrink-0 bg-bull/10 text-bull border border-bull/20">
            <span className={`w-2 h-2 rounded-full ${liveAvailable ? 'bg-bull animate-pulse' : marketOpen ? 'bg-neutral-muted animate-pulse' : 'bg-onSurfaceDim'}`} aria-hidden="true" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-onSurface">Simulate Live Market</p>
            <p className="text-[10px] text-onSurfaceDim" aria-live="polite">
              {liveAvailable
                ? 'Real-time Dhan data available'
                : marketOpen === null
                  ? 'Checking market data...'
                  : marketOpen
                    ? `Market open — ${dataError || 'data feed connecting...'}`
                    : 'Market closed — use presets below'}
            </p>
          </div>
          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-bull bg-bull/10 border border-bull/20" aria-label="Live market data mode">
            LIVE
          </span>
        </div>
      </button>

      {/* Preset Divider */}
      <div className="flex items-center gap-2 mb-2">
        <span className="flex-1 h-px bg-gray-200" />
        <span className="text-[9px] font-mono text-onSurfaceDim tracking-widest">OR PRESET</span>
        <span className="flex-1 h-px bg-gray-200" />
      </div>

      {/* Scenario Grid */}
      <div className="flex-1 overflow-y-auto space-y-1.5 mb-4 pr-0.5">
        {scenarios.map((s) => {
          const isActive = selected?.scenario_id === s.scenario_id
          const style = DIRECTION_STYLES[s.expected_direction] || DIRECTION_STYLES.HOLD
          return (
            <button
              key={s.scenario_id}
              onClick={() => setSelected(s)}
              className={`w-full text-left px-3 py-2.5 rounded-lg transition-all duration-150 border ${
                isActive
                  ? 'bg-surface-1 border-primary/20'
                  : 'bg-transparent border-transparent hover:bg-surface-1 hover:border-gray-100'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-md flex items-center justify-center text-[10px] font-mono font-bold flex-shrink-0"
                  style={{
                    color: style.color,
                    backgroundColor: style.bg,
                    border: `1px solid ${style.border}`,
                  }}
                >
                  {SCENARIO_ICONS[s.scenario_id] || '---'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-onSurface truncate">{s.name}</p>
                  <p className="text-[10px] text-onSurfaceDim truncate">{s.description}</p>
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Run Button */}
      <button
        onClick={handleSimulate}
        disabled={isLoading || !selected}
        aria-label={isLoading ? 'Simulation in progress' : 'Run the selected scenario simulation'}
        className="w-full btn-primary disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2 h-10"
      >
        {isLoading ? (
          <span className="flex items-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <span className="font-mono text-xs">SIMULATING...</span>
          </span>
        ) : (
          <span className="font-mono text-xs tracking-wider">RUN SIMULATION</span>
        )}
      </button>
    </div>
  )
}
