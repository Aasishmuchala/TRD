import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import { apiClient } from '../api/client'
import { agents as agentColors } from '../utils/colors'
import { dirColor } from '../utils/format'

export default function PaperTrading() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [latestSim, setLatestSim] = useState(null)
  const [fetchError, setFetchError] = useState(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await apiClient.getHistory({ limit: 20 })
        const items = data.items || []
        setHistory(items)
        if (items.length > 0) setLatestSim(items[0])
      } catch (err) {
        setFetchError(err.message || 'Failed to load history')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const totalSims = history.length
  const minRequired = 20

  // Graduation criteria — plan spec thresholds
  const criteria = [
    {
      metric: 'Directional Accuracy (1-day)',
      target: '>= 57% over 20 sessions',
      current: (() => {
        const withAccuracy = history.filter(h => h.outcome_accuracy_1d != null)
        if (withAccuracy.length < 5) return 'N/A'
        const avg = withAccuracy.reduce((s, h) => s + h.outcome_accuracy_1d, 0) / withAccuracy.length
        return `${(avg * 100).toFixed(1)}%`
      })(),
      passed: (() => {
        const withAccuracy = history.filter(h => h.outcome_accuracy_1d != null)
        if (withAccuracy.length < 20) return false
        const avg = withAccuracy.reduce((s, h) => s + h.outcome_accuracy_1d, 0) / withAccuracy.length
        return avg >= 0.57
      })(),
    },
    {
      metric: 'Directional Accuracy (1-week)',
      target: '>= 60% over 4 weeks',
      current: (() => {
        const withAccuracy = history.filter(h => h.outcome_accuracy_1w != null)
        if (withAccuracy.length < 4) return 'N/A'
        const avg = withAccuracy.reduce((s, h) => s + h.outcome_accuracy_1w, 0) / withAccuracy.length
        return `${(avg * 100).toFixed(1)}%`
      })(),
      passed: (() => {
        const withAccuracy = history.filter(h => h.outcome_accuracy_1w != null)
        if (withAccuracy.length < 4) return false
        const avg = withAccuracy.reduce((s, h) => s + h.outcome_accuracy_1w, 0) / withAccuracy.length
        return avg >= 0.60
      })(),
    },
    {
      metric: 'Calibration Error',
      target: '< 15%',
      current: (() => {
        const withCalib = history.filter(h => h.calibration_error != null)
        if (withCalib.length === 0) return 'N/A'
        const avg = withCalib.reduce((s, h) => s + h.calibration_error, 0) / withCalib.length
        return `${(avg * 100).toFixed(1)}%`
      })(),
      passed: (() => {
        const withCalib = history.filter(h => h.calibration_error != null)
        if (withCalib.length === 0) return false
        const avg = withCalib.reduce((s, h) => s + h.calibration_error, 0) / withCalib.length
        return avg < 0.15
      })(),
    },
    {
      metric: 'Quant-LLM Agreement',
      target: '>= 70% when both agree',
      current: (() => {
        const withAgreement = history.filter(h => h.aggregator_result?.quant_llm_agreement != null)
        if (withAgreement.length === 0) return 'N/A'
        const avg = withAgreement.reduce((s, h) => s + h.aggregator_result.quant_llm_agreement, 0) / withAgreement.length
        return `${(avg * 100).toFixed(1)}%`
      })(),
      passed: (() => {
        const withAgreement = history.filter(h => h.aggregator_result?.quant_llm_agreement != null)
        if (withAgreement.length === 0) return false
        const avg = withAgreement.reduce((s, h) => s + h.aggregator_result.quant_llm_agreement, 0) / withAgreement.length
        return avg >= 0.70
      })(),
    },
    {
      metric: 'No Catastrophic Miss',
      target: 'No >3% move missed with high-confidence wrong call',
      current: history.some(h => h.catastrophic_miss) ? 'FAIL' : history.length > 0 ? 'PASS' : 'N/A',
      passed: history.length > 0 && !history.some(h => h.catastrophic_miss),
    },
    {
      metric: 'Internal Consistency',
      target: '>= 75% across 3 samples',
      current: (() => {
        const withConsistency = history.filter(h => h.internal_consistency != null)
        if (withConsistency.length === 0) return 'N/A'
        const avg = withConsistency.reduce((s, h) => s + h.internal_consistency, 0) / withConsistency.length
        return `${(avg * 100).toFixed(1)}%`
      })(),
      passed: (() => {
        const withConsistency = history.filter(h => h.internal_consistency != null)
        if (withConsistency.length === 0) return false
        const avg = withConsistency.reduce((s, h) => s + h.internal_consistency, 0) / withConsistency.length
        return avg >= 0.75
      })(),
    },
  ]

  const passedCount = criteria.filter(c => c.passed).length

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-[calc(100vh-2.5rem)]">
          <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING PAPER TRADING...</span>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-5 h-[calc(100vh-2.5rem)] overflow-y-auto">
        {fetchError && !loading && (
          <div className="terminal-card p-3 border-l-2 border-bear mb-4">
            <p className="text-xs font-mono text-bear">
              Could not load history: {fetchError}. Check that the backend is running.
            </p>
          </div>
        )}
        {!loading && !fetchError && history.length === 0 && (
          <div className="terminal-card p-5 flex flex-col items-center justify-center gap-2 mb-4">
            <span className="text-xs font-mono text-onSurfaceDim">NO SIMULATION HISTORY</span>
            <span className="text-[10px] font-mono text-onSurfaceDim">
              Run simulations from the Dashboard to start building your Paper Trading record.
            </span>
          </div>
        )}
        {/* Progress Header */}
        <div className="terminal-card p-5 mb-5">
          <div className="flex items-center gap-5">
            {/* Progress Ring */}
            <div className="relative w-20 h-20 flex-shrink-0">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
                <circle
                  cx="50" cy="50" r="42" fill="none"
                  stroke="#00D4E0" strokeWidth="6"
                  strokeDasharray={`${(totalSims / minRequired) * 264} 264`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-lg font-bold font-mono text-primary">{totalSims}</span>
                <span className="text-[9px] font-mono text-onSurfaceDim">/ {minRequired}</span>
              </div>
            </div>

            <div className="flex-1">
              <h1 className="text-xl font-bold text-onSurface">Paper Trading</h1>
              <p className="text-[10px] font-mono text-primary uppercase tracking-widest mt-0.5">
                {totalSims >= minRequired ? 'READY FOR GRADUATION' : 'EVALUATION PHASE'}
              </p>
              <p className="text-[10px] font-mono text-onSurfaceDim mt-1">
                Run {Math.max(0, minRequired - totalSims)} more simulation{minRequired - totalSims !== 1 ? 's' : ''} to complete evaluation
              </p>
            </div>

            <div className="text-right">
              <span className="text-3xl font-bold font-mono text-primary">{passedCount}/{criteria.length}</span>
              <p className="text-[10px] font-mono text-onSurfaceDim">criteria met</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4">
          {/* Latest Prediction */}
          <div className="col-span-4 terminal-card p-4">
            <div className="section-header mb-3">Latest Prediction</div>
            {latestSim ? (() => {
              const agg = latestSim.aggregator_result || {}
              const dir = agg.final_direction || agg.direction || 'HOLD'
              const conv = agg.final_conviction || agg.conviction || 0
              const agree = agg.quant_llm_agreement

              return (
                <div className="space-y-4">
                  <div className="text-center py-3">
                    <span
                      className="text-2xl font-bold font-mono"
                      style={{ color: dirColor(dir) }}
                    >
                      {dir.replace('_', ' ')}
                    </span>
                    <p className="text-[10px] font-mono text-onSurfaceDim mt-1">
                      {latestSim.market_input?.context || 'custom'}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-surface-2 rounded-lg p-3 text-center">
                      <span className="text-[10px] font-mono text-onSurfaceDim">Conviction</span>
                      <p className="text-lg font-mono font-bold text-primary mt-1">
                        {typeof conv === 'number' ? conv.toFixed(0) : '--'}%
                      </p>
                    </div>
                    <div className="bg-surface-2 rounded-lg p-3 text-center">
                      <span className="text-[10px] font-mono text-onSurfaceDim">Q/L Agree</span>
                      <p className="text-lg font-mono font-bold text-onSurface mt-1">
                        {agree != null ? `${(agree * 100).toFixed(0)}%` : '--'}
                      </p>
                    </div>
                  </div>

                  {/* Agent breakdown from latest sim */}
                  {latestSim.agents_output && (
                    <div className="space-y-2">
                      {Object.entries(latestSim.agents_output).map(([key, agent]) => {
                        const aKey = key.toUpperCase()
                        const color = agentColors[aKey] || '#8B95A5'
                        return (
                          <div key={key} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                              <span className="text-[10px] font-mono text-onSurfaceMuted">{agent.agent_name || key}</span>
                            </div>
                            <span
                              className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
                              style={{ backgroundColor: `${dirColor(agent.direction)}15`, color: dirColor(agent.direction) }}
                            >
                              {agent.direction}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })() : (
              <div className="flex flex-col items-center justify-center py-8 gap-2 text-onSurfaceDim">
                <span className="text-xs font-mono">NO SIMULATIONS YET</span>
                <span className="text-[10px] font-mono">Run from Dashboard</span>
              </div>
            )}
          </div>

          {/* Graduation Checklist */}
          <div className="col-span-4 terminal-card p-4">
            <div className="section-header mb-3">Graduation Checklist</div>
            <div className="space-y-2">
              {criteria.map((item) => (
                <div
                  key={item.metric}
                  className={`flex items-center gap-2.5 p-2.5 rounded-lg ${
                    item.passed ? 'bg-bull/5 border border-bull/10' : 'bg-surface-2'
                  }`}
                >
                  <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 ${
                    item.passed ? 'bg-bull' : 'border border-[rgba(255,255,255,0.15)]'
                  }`}>
                    {item.passed && <span className="text-[8px] text-black font-bold">OK</span>}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-mono text-onSurface">{item.metric}</p>
                    <p className="text-[9px] font-mono text-onSurfaceDim">{item.target}</p>
                  </div>
                  <span className={`text-[11px] font-mono ${item.passed ? 'text-bull' : 'text-onSurfaceMuted'}`}>
                    {typeof item.current === 'number'
                      ? item.metric.includes('Time') ? `${item.current}ms` : item.current
                      : item.current}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Sessions */}
          <div className="col-span-4 terminal-card p-4">
            <div className="section-header mb-3">Recent Sessions</div>
            {history.length > 0 ? (
              <div className="space-y-2">
                {history.slice(0, 8).map((sim, idx) => {
                  const agg = sim.aggregator_result || {}
                  const dir = agg.final_direction || agg.direction || 'HOLD'
                  const conv = agg.final_conviction || agg.conviction || 0
                  const ts = sim.timestamp ? new Date(sim.timestamp) : null
                  const dateStr = ts
                    ? ts.toLocaleString('en-IN', { month: 'short', day: 'numeric', timeZone: 'Asia/Kolkata' })
                    : '--'

                  return (
                    <div key={sim.simulation_id || idx} className="p-2 bg-surface-2 rounded-lg">
                      <p className="text-[10px] font-mono text-onSurface">
                        {dateStr} · {dir.replace('_', ' ')} {typeof conv === 'number' ? conv.toFixed(0) : '--'}%
                      </p>
                      <p className="text-[9px] font-mono text-onSurfaceDim">{sim.market_input?.context || 'custom'}</p>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 gap-2 text-onSurfaceDim">
                <span className="text-xs font-mono">NO DATA</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}
