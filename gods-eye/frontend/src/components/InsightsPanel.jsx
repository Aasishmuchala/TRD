function SkeletonBlock({ h = 'h-20' }) {
  return (
    <div className={`bg-surface-2 rounded-lg p-4 border border-[rgba(255,255,255,0.04)] ${h}`}>
      <div className="w-16 h-2 bg-surface-3 rounded animate-pulse mb-3" />
      <div className="w-24 h-4 bg-surface-3 rounded animate-pulse" />
    </div>
  )
}

function InsightsSkeleton() {
  return (
    <div className="flex-1 flex flex-col gap-4">
      <SkeletonBlock h="h-[72px]" />
      <div className="bg-surface-2 rounded-lg p-4 border border-[rgba(255,255,255,0.04)]">
        <div className="w-16 h-2 bg-surface-3 rounded animate-pulse mb-3" />
        <div className="flex items-center justify-between">
          <div className="w-20 h-3 bg-surface-3 rounded animate-pulse" />
          <div className="w-12 h-3 bg-surface-3 rounded animate-pulse" />
        </div>
        <div className="mt-2 flex gap-1">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-1 flex-1 rounded-full bg-surface-3 animate-pulse" />
          ))}
        </div>
      </div>
      <SkeletonBlock h="h-[56px]" />
      <SkeletonBlock h="h-[72px]" />
      <div className="mt-auto">
        <div className="w-16 h-2 bg-surface-3 rounded animate-pulse mb-2" />
        <div className="flex gap-1.5">
          <div className="w-16 h-5 bg-surface-3 rounded animate-pulse" />
          <div className="w-20 h-5 bg-surface-3 rounded animate-pulse" />
          <div className="w-14 h-5 bg-surface-3 rounded animate-pulse" />
        </div>
      </div>
    </div>
  )
}

export default function InsightsPanel({ result = null, isLoading = false }) {
  const hasData = result && result.agents_output && result.aggregator_result

  const getInsights = () => {
    if (!hasData) return null

    const agg = result.aggregator_result
    const agents = result.agents_output

    // Strongest agent
    let strongest = { key: '', conviction: 0, direction: '' }
    for (const [key, agent] of Object.entries(agents)) {
      if (agent.conviction > strongest.conviction) {
        strongest = { key, conviction: agent.conviction, direction: agent.direction, name: agent.agent_name }
      }
    }

    // Alignment count
    const finalDir = agg.final_direction
    const aligned = Object.values(agents).filter(a => {
      if (finalDir === 'BUY' || finalDir === 'STRONG_BUY') return a.direction === 'BUY' || a.direction === 'STRONG_BUY'
      if (finalDir === 'SELL' || finalDir === 'STRONG_SELL') return a.direction === 'SELL' || a.direction === 'STRONG_SELL'
      return a.direction === 'HOLD'
    }).length

    // Top triggers from strongest agent
    const triggers = strongest.key && agents[strongest.key]?.key_triggers
      ? agents[strongest.key].key_triggers.slice(0, 3)
      : []

    return { agg, strongest, aligned, triggers }
  }

  const data = getInsights()
  const dirColor = (dir) => {
    if (!dir) return '#FFC107'
    if (dir.includes('BUY')) return '#00E676'
    if (dir.includes('SELL')) return '#FF1744'
    return '#FFC107'
  }

  return (
    <div className="terminal-card-lg p-5 flex flex-col h-full">
      <div className="section-header">Signal Intel</div>

      {isLoading ? (
        <InsightsSkeleton />
      ) : hasData && data ? (
        <div className="flex-1 flex flex-col gap-4">
          {/* Final Signal */}
          <div className="bg-surface-2 rounded-lg p-4 border border-[rgba(255,255,255,0.04)]">
            <span className="text-[10px] font-mono text-onSurfaceDim uppercase">Final Signal</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span
                className="text-2xl font-bold font-mono"
                style={{ color: dirColor(data.agg.final_direction), textShadow: `0 0 12px ${dirColor(data.agg.final_direction)}30` }}
              >
                {data.agg.final_direction}
              </span>
              <span className="text-sm font-mono text-onSurfaceMuted">
                @ {data.agg.final_conviction?.toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Consensus */}
          <div className="bg-surface-2 rounded-lg p-4 border border-[rgba(255,255,255,0.04)]">
            <span className="text-[10px] font-mono text-onSurfaceDim uppercase">Consensus</span>
            <div className="flex items-center justify-between mt-2">
              <span className={`text-xs font-mono font-bold ${
                data.agg.conflict_level === 'HIGH_AGREEMENT' ? 'text-bull' :
                data.agg.conflict_level === 'TUG_OF_WAR' ? 'text-bear' : 'text-neutral'
              }`}>
                {data.agg.conflict_level?.replace(/_/g, ' ')}
              </span>
              <span className="text-xs font-mono text-onSurfaceMuted">
                {data.aligned}/6 aligned
              </span>
            </div>
            <div className="mt-2 flex gap-1">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className={`h-1 flex-1 rounded-full ${i < data.aligned ? 'bg-primary' : 'bg-surface-3'}`}
                />
              ))}
            </div>
          </div>

          {/* Key Driver */}
          <div className="bg-surface-2 rounded-lg p-4 border border-[rgba(255,255,255,0.04)]">
            <span className="text-[10px] font-mono text-onSurfaceDim uppercase">Key Driver</span>
            <div className="flex items-center justify-between mt-1">
              <span className="text-sm font-semibold text-onSurface">{data.strongest.name || data.strongest.key}</span>
              <span className="font-mono text-xs" style={{ color: dirColor(data.strongest.direction) }}>
                {data.strongest.conviction?.toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Quant vs LLM */}
          <div className="bg-surface-2 rounded-lg p-4 border border-[rgba(255,255,255,0.04)]">
            <span className="text-[10px] font-mono text-onSurfaceDim uppercase">Quant / LLM Split</span>
            <div className="flex items-center gap-4 mt-2">
              <div className="flex-1">
                <span className="text-[10px] text-onSurfaceDim">Quant</span>
                <p className="text-xs font-mono" style={{ color: dirColor(data.agg.quant_consensus) }}>
                  {data.agg.quant_consensus || '---'}
                </p>
              </div>
              <div className="w-px h-6 bg-surface-3" />
              <div className="flex-1">
                <span className="text-[10px] text-onSurfaceDim">LLM</span>
                <p className="text-xs font-mono" style={{ color: dirColor(data.agg.llm_consensus) }}>
                  {data.agg.llm_consensus || '---'}
                </p>
              </div>
            </div>
          </div>

          {/* Top Triggers */}
          {data.triggers.length > 0 && (
            <div className="mt-auto">
              <span className="text-[10px] font-mono text-onSurfaceDim uppercase">Top Triggers</span>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {data.triggers.map((t, i) => (
                  <span key={i} className="tag-primary text-[10px]">{t}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-onSurfaceDim">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8 opacity-30">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
          <span className="text-xs font-mono">RUN A SIMULATION</span>
          <span className="text-[10px] font-mono text-onSurfaceDim">Select scenario + click run</span>
        </div>
      )}

      {/* Meta */}
      {hasData && (
        <div className="mt-4 pt-3 divider flex items-center justify-between text-[10px] font-mono text-onSurfaceDim">
          <span>{result.execution_time_ms?.toFixed(0)}ms</span>
          <span>{result.model_used || 'mock'}</span>
        </div>
      )}
    </div>
  )
}
