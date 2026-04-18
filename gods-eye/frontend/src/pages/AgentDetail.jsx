import React, { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { AGENTS } from '../constants/agents'

export default function AgentDetail() {
  const [selectedAgentId, setSelectedAgentId] = useState('FII')
  const [agent, setAgent] = useState(null)
  const [accuracy, setAccuracy] = useState(null)
  const [failurePatterns, setFailurePatterns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const selectedAgent = AGENTS.find(a => a.id === selectedAgentId)

  useEffect(() => {
    const fetchAgentData = async () => {
      setLoading(true)
      setError(null)
      try {
        const [agentData, accuracyData, patternsData] = await Promise.all([
          apiClient.getAgent(selectedAgentId),
          apiClient.getAgentAccuracy(selectedAgentId, 90),
          apiClient.getFailurePatterns(selectedAgentId),
        ])
        setAgent(agentData)
        setAccuracy(accuracyData)
        setFailurePatterns(patternsData?.patterns || patternsData || [])
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchAgentData()
  }, [selectedAgentId])

  const directionData = accuracy?.directionBreakdown || []
  const accentColor = selectedAgent?.color || '#CC152B'

  return (
    <div className="flex h-full bg-surface-1 p-4 gap-4">
      {/* Left Panel — Agent List */}
      <div className="w-[220px] flex-shrink-0 flex flex-col gap-1 overflow-y-auto pr-1">
        <h2 className="font-mono text-xs uppercase tracking-widest text-onSurfaceMuted px-3 pb-3">
          Agents
        </h2>
        {AGENTS.map(a => {
          const isSelected = selectedAgentId === a.id
          return (
            <button
              key={a.id}
              onClick={() => setSelectedAgentId(a.id)}
              className={`w-full text-left rounded-xl px-3 py-2.5 transition-all duration-200 border ${
                isSelected
                  ? 'bg-white shadow-sm'
                  : 'border-transparent hover:bg-white/60'
              }`}
              style={{
                borderColor: isSelected ? `${a.color}30` : 'transparent',
                boxShadow: isSelected ? `inset 3px 0 0 ${a.color}` : 'none',
              }}
            >
              <div className="flex items-center gap-2.5">
                <span
                  className="font-mono text-[10px] font-bold w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{
                    backgroundColor: isSelected ? a.color : `${a.color}10`,
                    color: isSelected ? '#fff' : a.color,
                  }}
                >
                  {a.shortLabel}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-onSurface truncate">
                    {a.displayName}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span
                      className="font-mono text-[10px] font-bold"
                      style={{ color: a.color }}
                    >
                      {(a.weight * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Right Panel — Agent Detail */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="bg-bear-dim border border-bear/20 rounded-xl p-4 mb-4 text-bear text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center h-full">
            <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING AGENT DATA...</span>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Agent Header Card */}
            <div className="terminal-card p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center font-mono font-bold text-sm flex-shrink-0 text-white"
                    style={{ backgroundColor: accentColor }}
                  >
                    {selectedAgent?.shortLabel}
                  </div>
                  <div>
                    <h1 className="text-xl font-bold text-onSurface leading-tight">
                      {agent?.name || selectedAgent?.displayName}
                    </h1>
                    <p className="text-onSurfaceMuted text-sm leading-relaxed mt-1.5 max-w-2xl">
                      {agent?.description || 'Agent description not available'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-5 flex-shrink-0">
                  <div className="text-right">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-onSurfaceMuted block">
                      Weight
                    </span>
                    <span className="font-mono font-bold text-lg" style={{ color: accentColor }}>
                      {(selectedAgent?.weight * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-px h-8 bg-gray-200" />
                  <div className="text-right">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-onSurfaceMuted block">
                      Type
                    </span>
                    <span className="font-mono font-bold text-lg" style={{ color: accentColor }}>
                      {agent?.type || 'HYBRID'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Stat Cards — 2x2 Grid */}
            <div className="grid grid-cols-2 gap-4">
              <StatCard
                label="Overall Accuracy"
                value={accuracy?.overall?.toFixed(1) || '0.0'}
                unit="%"
                trend={accuracy?.trend}
                accentColor={accentColor}
              />
              <StatCard
                label="Directional Accuracy"
                value={accuracy?.directional?.toFixed(1) || '0.0'}
                unit="%"
                trend={accuracy?.directionalTrend}
                accentColor={accentColor}
              />
              <StatCard
                label="Conviction Calibration"
                value={accuracy?.convictionCalibration?.toFixed(1) || '0.0'}
                unit="%"
                trend={accuracy?.calibrationTrend}
                accentColor={accentColor}
              />
              <StatCard
                label="Avg Execution Time"
                value={accuracy?.avgExecutionTime?.toFixed(0) || '0'}
                unit="ms"
                accentColor={accentColor}
              />
            </div>

            {/* Direction Breakdown + Failure Patterns */}
            <div className="grid grid-cols-2 gap-4">
              {/* Direction Breakdown */}
              <div className="terminal-card p-5">
                <h3 className="font-mono font-bold text-xs uppercase tracking-widest text-primary mb-5">
                  Direction Breakdown
                </h3>
                <div className="space-y-4">
                  {['BUY', 'SELL', 'HOLD'].map((dir) => {
                    const dirData = directionData.find(d => d.direction === dir)
                    const percentage = dirData?.count || 0
                    const accuracy_pct = dirData?.accuracy || 0
                    const barColor =
                      dir === 'BUY' ? '#059669' : dir === 'SELL' ? '#DC2626' : '#D97706'

                    return (
                      <div key={dir}>
                        <div className="flex items-center justify-between mb-2">
                          <span
                            className="font-mono text-xs font-bold uppercase tracking-widest"
                            style={{ color: barColor }}
                          >
                            {dir}
                          </span>
                          <span className="text-onSurfaceMuted text-xs">
                            {percentage} calls · {accuracy_pct.toFixed(0)}% accurate
                          </span>
                        </div>
                        <div className="relative h-2 bg-surface-3 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${Math.min(percentage, 100)}%`,
                              backgroundColor: barColor,
                            }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Failure Patterns */}
              <div className="terminal-card p-5">
                <h3 className="font-mono font-bold text-xs uppercase tracking-widest text-primary mb-5">
                  Failure Patterns
                </h3>
                {failurePatterns.length === 0 ? (
                  <p className="text-onSurfaceMuted text-sm">No significant failure patterns detected</p>
                ) : (
                  <div className="space-y-3">
                    {failurePatterns.map((pattern, idx) => {
                      const severityColors = {
                        critical: '#DC2626',
                        high: '#EF4444',
                        medium: '#D97706',
                        low: '#059669',
                      }
                      const color = severityColors[pattern.severity] || '#D97706'

                      return (
                        <div
                          key={idx}
                          className="flex items-start gap-3 p-3 rounded-xl border border-gray-100"
                          style={{ backgroundColor: `${color}05` }}
                        >
                          <div
                            className="w-2 h-2 rounded-full mt-2 flex-shrink-0"
                            style={{ backgroundColor: color }}
                          />
                          <div className="flex-1">
                            <p className="text-onSurface text-sm font-medium">{pattern.pattern}</p>
                            <p className="text-onSurfaceMuted text-xs mt-1">{pattern.description}</p>
                          </div>
                          <span
                            className="font-mono text-xs font-bold uppercase tracking-wider flex-shrink-0"
                            style={{ color }}
                          >
                            {pattern.occurrences}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Agent Config */}
            <div className="terminal-card p-5">
              <h3 className="font-mono font-bold text-xs uppercase tracking-widest text-primary mb-4">
                Configuration
              </h3>
              <pre className="text-onSurface text-xs font-mono bg-surface-1 p-4 rounded-xl overflow-auto max-h-96 border border-gray-100">
                {JSON.stringify(
                  {
                    id: agent?.id,
                    displayName: agent?.displayName,
                    type: agent?.type,
                    weight: selectedAgent?.weight,
                    description: agent?.description,
                    parameters: agent?.parameters,
                  },
                  null,
                  2
                )}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, unit, trend, accentColor }) {
  return (
    <div className="terminal-card p-4 flex flex-col">
      <span className="font-mono text-xs uppercase tracking-widest text-onSurfaceMuted mb-3">
        {label}
      </span>
      <div className="flex items-baseline gap-1 mb-2">
        <span
          className="font-mono font-bold text-3xl tabular-nums"
          style={{ color: accentColor }}
        >
          {value}
        </span>
        <span className="text-onSurfaceMuted font-mono text-sm">{unit}</span>
      </div>
      {trend && (
        <div className="flex items-center gap-1">
          {trend > 0 ? (
            <>
              <span className="text-bull text-sm">▲</span>
              <span className="text-xs text-bull font-mono">+{trend.toFixed(1)}%</span>
            </>
          ) : trend < 0 ? (
            <>
              <span className="text-bear text-sm">▼</span>
              <span className="text-xs text-bear font-mono">{trend.toFixed(1)}%</span>
            </>
          ) : null}
        </div>
      )}
    </div>
  )
}
