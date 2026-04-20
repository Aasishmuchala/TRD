import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { agents as agentColors, agentLabels } from '../utils/colors'

export default function FeedbackPanel({ refreshKey }) {
  const [weights, setWeights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setFetchError(null)
    apiClient.getFeedbackWeights(90)
      .then(data => { if (!cancelled) setWeights(data) })
      .catch(err => { if (!cancelled) setFetchError(err?.message || 'Failed to load feedback weights') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [refreshKey])

  if (loading) {
    return (
      <div className="terminal-card-lg p-5">
        <div className="section-header">Feedback Engine</div>
        <div className="flex items-center justify-center h-32" role="status" aria-live="polite">
          <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING...</span>
        </div>
      </div>
    )
  }

  if (fetchError && !weights) {
    return (
      <div className="terminal-card-lg p-5">
        <div className="section-header">Feedback Engine</div>
        <div className="flex flex-col items-center justify-center gap-2 h-32 px-4">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6 text-amber-500" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <span className="text-[10px] font-mono text-onSurfaceDim text-center">Feedback weights unavailable</span>
          <span className="text-[9px] font-mono text-onSurfaceDim text-center opacity-70">{fetchError}</span>
        </div>
      </div>
    )
  }

  const isActive = weights?.feedback_active
  const agentData = weights?.agents ? Object.entries(weights.agents) : []
  const minPredictions = weights?.min_predictions_required || 30

  return (
    <div className="terminal-card-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="section-header mb-0">Feedback Engine</div>
        <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-mono font-bold ${
          isActive
            ? 'bg-primary/10 text-primary border border-primary/20'
            : 'bg-surface-2 text-onSurfaceDim border border-gray-100'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-primary animate-pulse' : 'bg-onSurfaceDim'}`} />
          {isActive ? 'ACTIVE' : 'WARMING UP'}
        </div>
      </div>

      {!isActive && (
        <div className="mb-4 px-3 py-2 bg-surface-1 rounded-lg border border-gray-100 text-[10px] font-mono text-onSurfaceDim">
          Requires {minPredictions}+ predictions with recorded outcomes to activate self-tuning.
        </div>
      )}

      {/* Weight comparison table */}
      <div className="space-y-2.5">
        {agentData.map(([key, agent]) => {
          const color = agentColors[key] || '#8B95A5'
          const changePct = agent.change_pct || 0
          const isUp = changePct > 0
          const isDown = changePct < 0
          const baseW = (agent.base_weight * 100).toFixed(1)
          const tunedW = (agent.tuned_weight * 100).toFixed(1)

          return (
            <div key={key} className="flex items-center gap-3 group">
              {/* Agent identity */}
              <div className="flex items-center gap-2 w-20 flex-shrink-0">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-[11px] text-onSurfaceMuted font-medium truncate">
                  {agentLabels[key]?.split(' ')[0] || key}
                </span>
              </div>

              {/* Base → Tuned visual */}
              <div className="flex-1 flex items-center gap-2">
                <span className="text-[10px] font-mono text-onSurfaceDim w-10 text-right">{baseW}%</span>

                {/* Arrow */}
                <div className="flex items-center gap-1">
                  <div className="w-6 h-px bg-surface-2" />
                  <svg viewBox="0 0 8 8" className="w-2 h-2 text-onSurfaceDim">
                    <path d="M0 4h6M4 1l3 3-3 3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>

                <span className={`text-[10px] font-mono font-bold w-10 ${
                  isUp ? 'text-bull' : isDown ? 'text-bear' : 'text-onSurfaceMuted'
                }`}>
                  {tunedW}%
                </span>
              </div>

              {/* Change badge */}
              <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                isUp
                  ? 'bg-bull/10 text-bull border border-bull/20'
                  : isDown
                  ? 'bg-bear/10 text-bear border border-bear/20'
                  : 'bg-surface-2 text-onSurfaceDim border border-gray-100'
              }`}>
                {isUp ? '+' : ''}{changePct.toFixed(1)}%
              </span>
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="mt-4 pt-3 divider flex items-center justify-between text-[10px] font-mono text-onSurfaceDim">
        <span>Base weight</span>
        <span>Accuracy-tuned weight</span>
      </div>
    </div>
  )
}
