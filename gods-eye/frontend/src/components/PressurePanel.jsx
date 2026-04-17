// TODO (FE-M2): Consider wrapping PressurePanel with React.memo once component is stable
import AgentPressureBar from './AgentPressureBar'
import DirectionGauge from './DirectionGauge'
import { agentLabels } from '../utils/colors'
import { AGENT_ORDER } from '../constants/agents'

// FE-L5: Use canonical AGENT_ORDER from constants instead of hardcoded list
const AGENTS = AGENT_ORDER

function mapDirection(dir) {
  if (!dir) return 'neutral'
  if (dir === 'STRONG_BUY' || dir === 'BUY') return 'bullish'
  if (dir === 'STRONG_SELL' || dir === 'SELL') return 'bearish'
  return 'neutral'
}

function SkeletonBar() {
  return (
    <div className="flex items-center gap-3">
      <div className="w-14 h-3 bg-surface-3 rounded animate-pulse" />
      <div className="flex-1 h-2 bg-surface-3 rounded-full animate-pulse" />
      <div className="w-8 h-3 bg-surface-3 rounded animate-pulse" />
    </div>
  )
}

function SkeletonGauge() {
  return (
    <div className="flex flex-col items-center gap-3">
      <div className="w-28 h-28 bg-surface-3 rounded-full animate-pulse" />
      <div className="w-20 h-3 bg-surface-3 rounded animate-pulse" />
      <div className="flex items-center gap-3 mt-1">
        <div className="w-16 h-2 bg-surface-3 rounded animate-pulse" />
        <div className="w-16 h-1 bg-surface-3 rounded-full animate-pulse" />
      </div>
    </div>
  )
}

export default function PressurePanel({ result = null, isLoading = false }) {
  let agentData = {}
  let agg = {}
  let quantLLMAgreement = 0

  if (result && result.agents_output) {
    for (const [key, agent] of Object.entries(result.agents_output)) {
      agentData[key] = {
        pressure: (agent.conviction || 50) / 100,
        direction: mapDirection(agent.direction),
        conviction: agent.conviction || 50,
      }
    }
    const aggResult = result.aggregator_result || {}
    agg = {
      direction: mapDirection(aggResult.final_direction),
      magnitude: (aggResult.final_conviction || 50) / 100,
      confidence: (aggResult.final_conviction || 50) / 100,
    }
    quantLLMAgreement = aggResult.agreement_boost
      ? Math.min(1, 0.5 + aggResult.agreement_boost)
      : (aggResult.consensus_score ? Math.abs(aggResult.consensus_score) / 100 : 0)
  }

  const hasData = result && result.agents_output

  return (
    <div className="terminal-card-lg p-5 flex flex-col h-full">
      <div className="section-header">Agent Pressure Map</div>

      {/* Agent Bars */}
      <div className="space-y-3 mb-6">
        {isLoading ? (
          AGENTS.map((_, i) => <SkeletonBar key={i} />)
        ) : (
          AGENTS.map((agent) => (
            <AgentPressureBar
              key={agent}
              agentKey={agent}
              label={agentLabels[agent] || agent}
              pressure={agentData[agent]?.pressure || 0.5}
              direction={agentData[agent]?.direction || 'neutral'}
              conviction={agentData[agent]?.conviction || 50}
            />
          ))
        )}
      </div>

      {/* Divider */}
      <div className="divider mb-4" />

      {/* Direction Gauge */}
      <div className="flex-1 flex flex-col items-center justify-center">
        {isLoading ? (
          <SkeletonGauge />
        ) : hasData ? (
          <>
            <DirectionGauge
              direction={agg.direction}
              magnitude={agg.magnitude}
              confidence={agg.confidence}
            />
            {/* Quant-LLM Agreement */}
            <div className="flex items-center gap-3 mt-2">
              <span className="text-[10px] text-onSurfaceDim font-mono uppercase">Q/L Agreement</span>
              <div className="w-16 h-1 bg-surface-3 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${quantLLMAgreement * 100}%` }}
                />
              </div>
              <span className="text-[10px] font-mono text-primary tabular-nums">
                {Math.round(quantLLMAgreement * 100)}%
              </span>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 text-onSurfaceDim">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8 opacity-30">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
            </svg>
            <span className="text-xs font-mono">AWAITING SIMULATION</span>
          </div>
        )}
      </div>

      {/* Feedback indicator */}
      {result?.feedback_active && (
        <div className="mt-3 flex items-center gap-2 px-3 py-1.5 bg-primary/5 border border-primary/15 rounded-lg">
          <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" />
          <span className="text-[10px] font-mono text-primary">FEEDBACK ENGINE ACTIVE</span>
        </div>
      )}
    </div>
  )
}
