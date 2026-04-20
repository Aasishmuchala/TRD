import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { agents as agentColors, agentLabels } from '../utils/colors'
import { AGENT_ORDER } from '../constants/agents'

// FE-L5: Use canonical AGENT_ORDER from constants instead of hardcoded list
const AGENT_KEYS = AGENT_ORDER

export default function AccuracyPanel({ refreshKey }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)

  useEffect(() => {
    let cancelled = false
    const fetchAll = async () => {
      setLoading(true)
      setFetchError(null)
      try {
        const results = await Promise.all(
          AGENT_KEYS.map(async (key) => {
            try {
              const acc = await apiClient.getAgentAccuracy(key, 90)
              return { key, ...acc }
            } catch (err) {
              // Per-agent fallback so one 404 doesn't break the whole panel
              return {
                key,
                accuracy_percent: 0,
                total_predictions: 0,
                correct: 0,
                calibration_score: 0,
                recent_streak: 0,
                strongest_context: 'unknown',
                _error: err?.message || 'fetch failed',
              }
            }
          })
        )
        if (!cancelled) setData(results)
      } catch (err) {
        if (!cancelled) {
          setFetchError(err?.message || 'Failed to load accuracy data')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchAll()
    return () => { cancelled = true }
  }, [refreshKey])

  if (loading) {
    return (
      <div className="terminal-card-lg p-5">
        <div className="section-header">Agent Accuracy</div>
        <div className="flex items-center justify-center h-40">
          <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING...</span>
        </div>
      </div>
    )
  }

  const totalPredictions = data?.reduce((sum, a) => sum + a.total_predictions, 0) || 0
  const partialErrors = data?.filter(a => a._error).length || 0

  return (
    <div className="terminal-card-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="section-header mb-0">Agent Accuracy</div>
        <div className="flex items-center gap-2">
          {partialErrors > 0 && (
            <span
              title={`${partialErrors} agent accuracy endpoint(s) returned an error — showing zeros for those.`}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono bg-amber-50 text-amber-800 border border-amber-300"
            >
              <span className="w-1 h-1 rounded-full bg-amber-500" aria-hidden="true" />
              {partialErrors} unavailable
            </span>
          )}
          <span className="text-[10px] font-mono text-onSurfaceDim">
            {totalPredictions} total predictions
          </span>
        </div>
      </div>

      {fetchError && (
        <div className="mb-3 px-3 py-2 bg-bear-dim rounded-lg border border-bear/20 text-[10px] font-mono text-bear">
          {fetchError}
        </div>
      )}

      {totalPredictions === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 gap-2">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-6 h-6 text-onSurfaceDim opacity-30">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
          <span className="text-xs font-mono text-onSurfaceDim">NO ACCURACY DATA YET</span>
          <span className="text-[10px] font-mono text-onSurfaceDim">Run simulations + record outcomes to build history</span>
        </div>
      ) : (
        <div className="space-y-3">
          {data.map((agent) => {
            const color = agentColors[agent.key] || '#9CA3AF'
            const pct = agent.accuracy_percent || 0
            const total = agent.total_predictions || 0
            const correct = agent.correct || 0

            return (
              <div key={agent.key} className="group">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                    <span className="text-xs font-medium text-onSurfaceMuted group-hover:text-onSurface transition-colors">
                      {agentLabels[agent.key] || agent.key}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] font-mono text-onSurfaceDim">
                      {correct}/{total}
                    </span>
                    <span className="text-xs font-mono font-bold tabular-nums" style={{ color: pct >= 60 ? '#059669' : pct >= 45 ? '#D97706' : '#DC2626' }}>
                      {pct.toFixed(1)}%
                    </span>
                  </div>
                </div>
                {/* Accuracy bar */}
                <div className="h-1 bg-surface-2 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700 ease-out"
                    style={{
                      width: `${Math.min(100, pct)}%`,
                      backgroundColor: pct >= 60 ? '#059669' : pct >= 45 ? '#D97706' : '#DC2626',
                    }}
                  />
                </div>

                {/* Extra stats on hover */}
                {total > 0 && (
                  <div className="flex items-center gap-4 mt-1.5 text-[10px] font-mono text-onSurfaceDim">
                    {agent.calibration_score > 0 && (
                      <span>CAL: {(agent.calibration_score * 100).toFixed(0)}%</span>
                    )}
                    {agent.recent_streak !== 0 && (
                      <span className={agent.recent_streak > 0 ? 'text-bull' : 'text-bear'}>
                        STREAK: {agent.recent_streak > 0 ? '+' : ''}{agent.recent_streak}
                      </span>
                    )}
                    {agent.strongest_context && agent.strongest_context !== 'unknown' && (
                      <span>BEST: {agent.strongest_context}</span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
