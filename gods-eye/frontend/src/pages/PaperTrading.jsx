import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import { apiClient } from '../api/client'
import { agents as agentColors } from '../utils/colors'

export default function PaperTrading() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [latestSim, setLatestSim] = useState(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await apiClient.getHistory({ limit: 20 })
        const items = data.items || []
        setHistory(items)
        if (items.length > 0) setLatestSim(items[0])
      } catch (err) {
        console.error('Failed to fetch:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const totalSims = history.length
  const minRequired = 20

  // Graduation criteria based on real data
  const criteria = [
    {
      metric: 'Simulations Run',
      target: `>= ${minRequired}`,
      current: totalSims,
      passed: totalSims >= minRequired,
    },
    {
      metric: 'Unique Scenarios',
      target: '>= 5',
      current: new Set(history.map(h => h.market_input?.context).filter(Boolean)).size,
      passed: new Set(history.map(h => h.market_input?.context).filter(Boolean)).size >= 5,
    },
    {
      metric: 'Feedback Engine Active',
      target: 'Active',
      current: history.some(h => h.feedback_active) ? 'Yes' : 'No',
      passed: history.some(h => h.feedback_active),
    },
    {
      metric: 'Avg Execution Time',
      target: '< 30s',
      current: history.length > 0
        ? Math.round(history.reduce((sum, h) => sum + (h.execution_time_ms || 0), 0) / history.length)
        : 0,
      passed: history.length > 0 &&
        (history.reduce((sum, h) => sum + (h.execution_time_ms || 0), 0) / history.length) < 30000,
    },
  ]

  const passedCount = criteria.filter(c => c.passed).length

  const dirColor = (dir) => {
    if (!dir) return '#FFC107'
    if (dir.includes('BUY')) return '#00E676'
    if (dir.includes('SELL')) return '#FF1744'
    return '#FFC107'
  }

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
              {criteria.map((item, idx) => (
                <div
                  key={idx}
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

                  return (
                    <div key={sim.simulation_id || idx} className="flex items-center justify-between p-2 bg-surface-2 rounded-lg">
                      <div>
                        <p className="text-[10px] font-mono text-onSurface">
                          {ts ? ts.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false }) : '--'}
                        </p>
                        <p className="text-[9px] font-mono text-onSurfaceDim">{sim.market_input?.context || 'custom'}</p>
                      </div>
                      <div className="text-right">
                        <span
                          className="text-[10px] font-mono font-bold"
                          style={{ color: dirColor(dir) }}
                        >
                          {dir.replace('_', ' ')}
                        </span>
                        <p className="text-[9px] font-mono text-onSurfaceDim">{typeof conv === 'number' ? conv.toFixed(0) : '--'}%</p>
                      </div>
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
