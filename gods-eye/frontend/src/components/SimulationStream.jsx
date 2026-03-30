import { agents as agentColors, agentLabels } from '../utils/colors'

const DIRECTION_COLORS = {
  STRONG_BUY: '#00FF88',
  BUY: '#00E676',
  HOLD: '#FFC107',
  SELL: '#FF1744',
  STRONG_SELL: '#FF3D71',
}

const ROUND_LABELS = {
  1: 'Independent Analysis',
  2: 'Reacting to Others',
  3: 'Finding Equilibrium',
}

const AGENT_ORDER = ['ALGO', 'FII', 'DII', 'RETAIL_FNO', 'PROMOTER', 'RBI']

/**
 * SimulationStream — real-time visualization of agent simulation.
 *
 * Shows a live feed of agents completing each round, with direction
 * badges, conviction bars, and reasoning text appearing as they stream in.
 */
export default function SimulationStream({
  events,
  currentRound,
  completedAgents,
  aggregation,
  streamStatus,
}) {
  if (streamStatus === 'idle') return null

  const isStreaming = streamStatus === 'streaming' || streamStatus === 'connecting'

  return (
    <div className="terminal-card-lg p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isStreaming && (
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          )}
          <div>
            <span className="section-header mb-0">
              {streamStatus === 'connecting' ? 'CONNECTING...' :
               streamStatus === 'streaming' ? 'SIMULATION LIVE' :
               streamStatus === 'done' ? 'SIMULATION COMPLETE' :
               'SIMULATION ERROR'}
            </span>
            {streamStatus === 'streaming' && currentRound > 0 && (
              <div className="text-[10px] font-mono text-onSurfaceDim mt-0.5">
                Round {currentRound} of 3 — {ROUND_LABELS[currentRound]}
              </div>
            )}
          </div>
        </div>
        {currentRound > 0 && (
          <div className="flex items-center gap-2">
            {[1, 2, 3].map((r) => (
              <div
                key={r}
                className={`w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-mono font-bold border transition-all ${
                  r < currentRound
                    ? 'bg-primary/15 border-primary/30 text-primary'
                    : r === currentRound && isStreaming
                    ? 'bg-primary/10 border-primary/40 text-primary animate-pulse'
                    : 'bg-surface-2 border-[rgba(255,255,255,0.06)] text-onSurfaceDim'
                }`}
              >
                {r}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Round sections */}
      {[1, 2, 3].map((roundNum) => {
        const roundStarted = events.some(
          (e) => e.type === 'round_start' && e.round === roundNum
        )
        const roundSkipped = events.some(
          (e) => e.type === 'round_skipped' && e.round === roundNum
        )
        if (!roundStarted && !roundSkipped) return null

        if (roundSkipped) {
          return (
            <div key={roundNum} className="px-3 py-2 bg-surface-2/50 rounded-lg border border-[rgba(255,255,255,0.04)]">
              <span className="text-[10px] font-mono text-onSurfaceDim">
                ROUND 3 SKIPPED — Consensus reached in Round 2
              </span>
            </div>
          )
        }

        const roundAgents = events.filter(
          (e) => e.type === 'agent_result' && e.round === roundNum
        )
        const isCurrentRound = currentRound === roundNum && isStreaming

        return (
          <div key={roundNum} className="space-y-2">
            {/* Round header */}
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono font-bold text-primary tracking-wider">
                ROUND {roundNum}
              </span>
              <span className="text-[10px] font-mono text-onSurfaceDim">
                {ROUND_LABELS[roundNum]}
              </span>
              {isCurrentRound && (
                <div className="w-3 h-3 border border-primary/40 border-t-primary rounded-full animate-spin" />
              )}
            </div>

            {/* Agent cards */}
            <div className="grid grid-cols-3 gap-2">
              {AGENT_ORDER.map((agentName) => {
                const agentResult = roundAgents.find((e) => e.agent_name === agentName)
                const color = agentColors[agentName] || '#00D4E0'
                const label = agentLabels[agentName] || agentName
                const isPending = isCurrentRound && !agentResult

                if (isPending) {
                  return (
                    <div
                      key={agentName}
                      className="px-3 py-2.5 rounded-lg bg-surface-2/50 border border-[rgba(255,255,255,0.04)] animate-pulse"
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color, opacity: 0.4 }} />
                        <span className="text-[10px] font-mono text-onSurfaceDim">{label}</span>
                      </div>
                      <div className="mt-1.5 h-2 bg-surface-3 rounded-full w-2/3" />
                    </div>
                  )
                }

                if (!agentResult) return null

                const dirColor = DIRECTION_COLORS[agentResult.direction] || '#FFC107'

                return (
                  <div
                    key={agentName}
                    className="px-3 py-2.5 rounded-lg bg-surface-2 border transition-all duration-300"
                    style={{ borderColor: `${color}20` }}
                  >
                    {/* Agent name + direction */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
                        <span className="text-[10px] font-mono font-bold" style={{ color }}>
                          {label}
                        </span>
                      </div>
                      <span
                        className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded"
                        style={{
                          color: dirColor,
                          backgroundColor: `${dirColor}12`,
                          border: `1px solid ${dirColor}30`,
                        }}
                      >
                        {agentResult.direction}
                      </span>
                    </div>

                    {/* Conviction bar */}
                    <div className="mt-1.5 flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${agentResult.conviction}%`,
                            backgroundColor: dirColor,
                            opacity: 0.7,
                          }}
                        />
                      </div>
                      <span className="text-[9px] font-mono text-onSurfaceMuted w-8 text-right">
                        {agentResult.conviction.toFixed(0)}%
                      </span>
                    </div>

                    {/* Direction change indicator (Round 2+) */}
                    {agentResult.direction_changed && (
                      <div className="mt-1 text-[8px] font-mono text-neutral-bright">
                        Changed from {agentResult.previous_direction}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}

      {/* Aggregation result */}
      {aggregation && (
        <div
          className="px-4 py-3 rounded-lg border"
          style={{
            backgroundColor: `${DIRECTION_COLORS[aggregation.final_direction]}08`,
            borderColor: `${DIRECTION_COLORS[aggregation.final_direction]}25`,
          }}
        >
          <div className="flex items-center justify-between">
            <div>
              <span className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">
                Final Signal
              </span>
              <div className="flex items-center gap-3 mt-1">
                <span
                  className="text-lg font-bold font-mono"
                  style={{ color: DIRECTION_COLORS[aggregation.final_direction] }}
                >
                  {aggregation.final_direction}
                </span>
                <span className="text-sm font-mono text-onSurface">
                  {aggregation.final_conviction.toFixed(1)}%
                </span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-mono text-onSurfaceDim">Consensus</div>
              <div className="text-xs font-mono font-bold text-onSurface mt-0.5">
                {aggregation.conflict_level.replace(/_/g, ' ')}
              </div>
              {aggregation.quant_llm_agreement != null && (
                <div className="text-[10px] font-mono text-primary mt-0.5">
                  Q/L Agreement: {(aggregation.quant_llm_agreement * 100).toFixed(0)}%
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Execution time */}
      {streamStatus === 'done' && (
        <div className="text-[10px] font-mono text-onSurfaceDim text-center">
          {events.find((e) => e.type === 'simulation_end')?.execution_time_ms.toFixed(0)}ms
          {' • '}{events.find((e) => e.type === 'simulation_end')?.total_rounds} rounds
          {' • '}{events.find((e) => e.type === 'simulation_end')?.model_used}
        </div>
      )}
    </div>
  )
}
