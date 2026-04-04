import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import { apiClient } from '../api/client'
import { agents as agentColors, agentLabels } from '../utils/colors'

const AGENT_KEYS = ['fii', 'dii', 'retail_fno', 'algo', 'promoter', 'rbi']
const AGENT_DESCS = {
  fii: 'Foreign Institutional Investor managing Asia-Pacific allocations',
  dii: 'Large domestic mutual fund tracking SIP inflows and sector rotation',
  retail_fno: 'Retail derivatives trader focused on expiry-week gamma and momentum',
  algo: 'Pure quantitative engine analyzing technical signals deterministically',
  promoter: 'Company insider tracking pledged holdings and bulk deal patterns',
  rbi: 'Monetary policy committee focused on inflation control and forex stability',
}

const dirColor = (dir) => {
  if (!dir) return '#FFC107'
  if (dir.includes('BUY')) return '#00E676'
  if (dir.includes('SELL')) return '#FF1744'
  return '#FFC107'
}

function AgentCard({ agentKey, isActive, onClick }) {
  const key = agentKey.toUpperCase()
  const color = agentColors[key] || '#8B95A5'
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 rounded-lg transition-all duration-150 border ${
        isActive
          ? 'bg-surface-2 border-primary/20'
          : 'bg-transparent border-transparent hover:bg-surface-2'
      }`}
    >
      <div className="flex items-center gap-2.5">
        <div
          className="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-mono font-bold flex-shrink-0"
          style={{ backgroundColor: `${color}15`, border: `1px solid ${color}30`, color }}
        >
          {agentKey.slice(0, 2).toUpperCase()}
        </div>
        <div>
          <p className="text-xs font-semibold text-onSurface">{agentLabels[key] || key}</p>
          <p className="text-[10px] text-onSurfaceDim truncate max-w-[140px]">{AGENT_DESCS[agentKey]?.split(' ').slice(0, 4).join(' ')}...</p>
        </div>
      </div>
    </button>
  )
}

export default function AgentDetail() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selected, setSelected] = useState(searchParams.get('id') || 'fii')
  const [agentInfo, setAgentInfo] = useState(null)
  const [accuracy, setAccuracy] = useState(null)
  const [patterns, setPatterns] = useState(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)

  useEffect(() => {
    const fetchAgent = async () => {
      setFetchError(null)
      setLoading(true)
      try {
        const [info, acc, pat] = await Promise.all([
          apiClient.getAgent(selected),
          apiClient.getAgentAccuracy(selected, 90),
          apiClient.getFailurePatterns(selected),
        ])
        setAgentInfo(info)
        setAccuracy(acc)
        setPatterns(pat)
      } catch (err) {
        setFetchError(err.message || 'Failed to load agent data')
      } finally {
        setLoading(false)
      }
    }
    fetchAgent()
  }, [selected])

  const handleSelect = (key) => {
    setSelected(key)
    setSearchParams({ id: key })
  }

  const agentColor = agentColors[selected.toUpperCase()] || '#8B95A5'

  return (
    <Layout>
      <div className="flex h-[calc(100vh-2.5rem)]">
        {/* Agent Sidebar */}
        <div className="w-52 bg-surface-1 border-r border-[rgba(255,255,255,0.06)] p-3 space-y-1 overflow-y-auto flex-shrink-0">
          <span className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-widest px-3 block mb-2">Agents</span>
          {AGENT_KEYS.map((key) => (
            <AgentCard
              key={key}
              agentKey={key}
              isActive={selected === key}
              onClick={() => handleSelect(key)}
            />
          ))}
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING AGENT DATA...</span>
            </div>
          ) : fetchError ? (
            <div className="terminal-card p-3 border-l-2 border-bear">
              <p className="text-xs font-mono text-bear">
                Could not load agent data: {fetchError}
              </p>
            </div>
          ) : (
            <>
              {/* Header */}
              <div className="flex items-center gap-4 mb-2">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center text-lg font-mono font-bold"
                  style={{ backgroundColor: `${agentColor}15`, border: `1px solid ${agentColor}30`, color: agentColor }}
                >
                  {selected.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h1 className="text-xl font-bold text-onSurface">
                    {agentLabels[selected.toUpperCase()] || selected}
                  </h1>
                  <p className="text-xs text-onSurfaceMuted">{AGENT_DESCS[selected]}</p>
                </div>
                <div className="ml-auto flex items-center gap-3">
                  {agentInfo && (
                    <>
                      <span className="tag-primary">{agentInfo.type}</span>
                      <span className="tag-primary">{agentInfo.time_horizon}</span>
                      <span className="text-xs font-mono text-onSurfaceMuted">
                        W: {((agentInfo.weight || 0) * 100).toFixed(0)}%
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-12 gap-4">
                {/* Accuracy Overview */}
                <div className="col-span-4 terminal-card p-4">
                  <div className="section-header mb-3">Accuracy Stats</div>
                  {accuracy && accuracy.total_predictions > 0 ? (
                    <div className="space-y-4">
                      {/* Big accuracy number */}
                      <div className="text-center py-3">
                        <span
                          className="text-4xl font-bold font-mono tabular-nums"
                          style={{ color: accuracy.accuracy_percent >= 55 ? '#00E676' : accuracy.accuracy_percent >= 40 ? '#FFC107' : '#FF1744' }}
                        >
                          {accuracy.accuracy_percent?.toFixed(1)}%
                        </span>
                        <p className="text-[10px] font-mono text-onSurfaceDim mt-1">
                          {accuracy.correct}/{accuracy.total_predictions} correct
                        </p>
                      </div>

                      {/* Stats grid */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-surface-2 rounded-lg p-3">
                          <span className="text-[10px] font-mono text-onSurfaceDim">Conv. (correct)</span>
                          <p className="text-sm font-mono text-bull mt-1">
                            {accuracy.avg_conviction_when_correct?.toFixed(1)}%
                          </p>
                        </div>
                        <div className="bg-surface-2 rounded-lg p-3">
                          <span className="text-[10px] font-mono text-onSurfaceDim">Conv. (wrong)</span>
                          <p className="text-sm font-mono text-bear mt-1">
                            {accuracy.avg_conviction_when_wrong?.toFixed(1)}%
                          </p>
                        </div>
                        <div className="bg-surface-2 rounded-lg p-3">
                          <span className="text-[10px] font-mono text-onSurfaceDim">Calibration</span>
                          <p className="text-sm font-mono text-primary mt-1">
                            {(accuracy.calibration_score * 100)?.toFixed(0)}%
                          </p>
                        </div>
                        <div className="bg-surface-2 rounded-lg p-3">
                          <span className="text-[10px] font-mono text-onSurfaceDim">Streak</span>
                          <p className={`text-sm font-mono mt-1 ${accuracy.recent_streak > 0 ? 'text-bull' : accuracy.recent_streak < 0 ? 'text-bear' : 'text-onSurfaceMuted'}`}>
                            {accuracy.recent_streak > 0 ? '+' : ''}{accuracy.recent_streak}
                          </p>
                        </div>
                      </div>

                      {/* Strengths */}
                      {accuracy.strongest_context !== 'unknown' && (
                        <div className="text-[10px] font-mono text-onSurfaceDim mt-2 space-y-1">
                          <div className="flex justify-between">
                            <span>Best context:</span>
                            <span className="text-bull">{accuracy.strongest_context}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Worst context:</span>
                            <span className="text-bear">{accuracy.weakest_context}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-8 gap-2 text-onSurfaceDim">
                      <span className="text-xs font-mono">NO DATA YET</span>
                      <span className="text-[10px] font-mono">Run simulations to build accuracy history</span>
                    </div>
                  )}
                </div>

                {/* Direction Breakdown */}
                <div className="col-span-4 terminal-card p-4">
                  <div className="section-header mb-3">Direction Breakdown</div>
                  {accuracy?.direction_breakdown && Object.keys(accuracy.direction_breakdown).length > 0 ? (
                    <div className="space-y-3">
                      {Object.entries(accuracy.direction_breakdown).map(([dir, stats]) => (
                        <div key={dir} className="flex items-center gap-3">
                          <span
                            className="text-[10px] font-mono font-bold w-20 text-right"
                            style={{ color: dirColor(dir) }}
                          >
                            {dir}
                          </span>
                          <div className="flex-1 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${stats.accuracy || 0}%`,
                                backgroundColor: dirColor(dir),
                              }}
                            />
                          </div>
                          <span className="text-[10px] font-mono text-onSurfaceMuted w-12 text-right">
                            {stats.count || 0}x
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-8 gap-2 text-onSurfaceDim">
                      <span className="text-xs font-mono">AWAITING OUTCOMES</span>
                    </div>
                  )}
                </div>

                {/* Failure Patterns */}
                <div className="col-span-4 terminal-card p-4">
                  <div className="section-header mb-3">Failure Patterns</div>
                  {patterns?.patterns?.length > 0 ? (
                    <div className="space-y-3">
                      {patterns.patterns.map((p, i) => (
                        <div key={i} className="bg-surface-2 rounded-lg p-3 border border-bear/10">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="w-1.5 h-1.5 bg-bear rounded-full" />
                            <span className="text-[11px] font-mono font-bold text-bear">
                              {p.type?.replace(/_/g, ' ').toUpperCase()}
                            </span>
                          </div>
                          <p className="text-[10px] text-onSurfaceDim">
                            {p.sample_count} occurrences
                          </p>
                          {p.example_contexts?.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {p.example_contexts.slice(0, 3).map((ctx, j) => (
                                <span key={j} className="text-[9px] font-mono px-1.5 py-0.5 bg-surface-3 rounded text-onSurfaceDim">
                                  {ctx}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-8 gap-2 text-onSurfaceDim">
                      <span className="text-xs font-mono">NO PATTERNS DETECTED</span>
                      <span className="text-[10px] font-mono">Insufficient data for pattern analysis</span>
                    </div>
                  )}

                  {/* Prompt Hints */}
                  {patterns?.prompt_hints && (
                    <div className="mt-4 pt-3 divider">
                      <span className="text-[10px] font-mono text-onSurfaceDim uppercase">Active Prompt Hints</span>
                      <p className="text-[11px] text-primary font-mono mt-1 leading-relaxed">
                        {patterns.prompt_hints}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Agent Meta */}
              <div className="terminal-card p-4">
                <div className="section-header mb-3">Agent Configuration</div>
                <div className="grid grid-cols-6 gap-4">
                  {agentInfo && [
                    { label: 'Type', value: agentInfo.type },
                    { label: 'Persona', value: agentInfo.persona?.split(' ').slice(0, 6).join(' ') + '...' },
                    { label: 'Horizon', value: agentInfo.time_horizon },
                    { label: 'Weight', value: `${((agentInfo.weight || 0) * 100).toFixed(0)}%` },
                    { label: 'Risk', value: agentInfo.risk_appetite },
                    { label: 'ID', value: agentInfo.id },
                  ].map((item) => (
                    <div key={item.label} className="bg-surface-2 rounded-lg p-3">
                      <span className="text-[10px] font-mono text-onSurfaceDim uppercase">{item.label}</span>
                      <p className="text-xs font-mono text-onSurface mt-1 truncate">{item.value}</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </Layout>
  )
}
