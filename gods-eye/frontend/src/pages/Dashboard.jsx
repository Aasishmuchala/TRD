import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useStreamingSimulation } from '../hooks/useStreamingSimulation'
import { apiClient } from '../api/client'
import { AGENTS } from '../constants/agents'
import ScenarioPanel from '../components/ScenarioPanel'
import PressurePanel from '../components/PressurePanel'
import InsightsPanel from '../components/InsightsPanel'
import AccuracyPanel from '../components/AccuracyPanel'
import FeedbackPanel from '../components/FeedbackPanel'
import DailySummaryCard from '../components/DailySummaryCard'

const formatINR = (value) => {
  if (value === null || value === undefined) return '₹0'
  const num = parseFloat(value)
  if (isNaN(num)) return '₹0'
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Math.abs(num))
  return num < 0 ? `-${formatted}` : formatted
}

const formatPercent = (value, decimals = 1) => {
  if (value === null || value === undefined) return '0%'
  const num = parseFloat(value)
  return isNaN(num) ? '0%' : `${num.toFixed(decimals)}%`
}

// ─── Inline Toast / Notification (no external dep) ─────────────────────────────

const Toast = ({ notification, onClose }) => {
  useEffect(() => {
    if (!notification) return
    const t = setTimeout(onClose, notification.ttl ?? 5000)
    return () => clearTimeout(t)
  }, [notification, onClose])

  if (!notification) return null

  const variantClass = {
    error: 'bg-bear-dim border-bear/30 text-bear',
    success: 'bg-bull-dim border-bull/30 text-bull',
    info: 'bg-primary/10 border-primary/30 text-primary',
    warn: 'bg-amber-50 border-amber-300 text-amber-900',
  }[notification.variant] || 'bg-surface-2 border-gray-200 text-onSurface'

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl border shadow-card text-sm font-medium max-w-sm ${variantClass}`}
    >
      <div className="flex items-start gap-3">
        <span className="flex-1 leading-snug">{notification.message}</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Dismiss notification"
          className="text-lg leading-none opacity-60 hover:opacity-100 transition-opacity"
        >
          ×
        </button>
      </div>
    </div>
  )
}

// ─── Data Source Badge ─────────────────────────────────────────────────────────

const DataSourceBadge = ({ source }) => {
  if (!source) return null
  const s = String(source).toLowerCase()
  const isFallback = s.includes('fallback') || s === 'mock' || s === 'error' || s === 'unknown'
  const isLive = s === 'live' || s === 'dhan' || s === 'nse'

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-pill text-[10px] font-mono uppercase tracking-wider border ${
        isFallback
          ? 'bg-amber-50 text-amber-800 border-amber-300'
          : isLive
            ? 'bg-bull-dim text-bull border-bull/20'
            : 'bg-surface-2 text-onSurfaceMuted border-gray-200'
      }`}
      title={isFallback ? 'Live market feed unavailable — using cached scenario defaults' : `Data source: ${source}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          isFallback ? 'bg-amber-500' : isLive ? 'bg-bull animate-pulse' : 'bg-onSurfaceDim'
        }`}
        aria-hidden="true"
      />
      {isFallback ? `${source} data` : `${source} feed`}
    </span>
  )
}

// ─── Hero Banner ───────────────────────────────────────────────────────────────

const HeroBanner = ({
  direction,
  conviction,
  consensusScore,
  todayPnl,
  tradingMode,
  onModeChange,
  dhanEnabled,
  isSimulating,
  onAbort,
  onNotify,
  dataSource,
}) => {
  const [switching, setSwitching] = useState(false)
  const [confirmingLive, setConfirmingLive] = useState(false)

  const handleToggle = async (newMode) => {
    if (newMode === tradingMode || switching) return
    if (newMode === 'live') {
      if (!dhanEnabled) {
        onNotify?.({
          variant: 'warn',
          message: 'Cannot switch to live: DHAN_ORDERS_ENABLED is not set on the server.',
        })
        return
      }
      setConfirmingLive(true)
      return
    }
    setSwitching(true)
    try {
      await onModeChange(newMode)
      onNotify?.({ variant: 'success', message: 'Switched to paper trading.' })
    } catch (err) {
      onNotify?.({ variant: 'error', message: err?.message || 'Failed to switch mode.' })
    } finally {
      setSwitching(false)
    }
  }

  const confirmLive = async () => {
    setConfirmingLive(false)
    setSwitching(true)
    try {
      await onModeChange('live')
      onNotify?.({ variant: 'warn', message: 'Live trading enabled — real orders will be placed via Dhan.' })
    } catch (err) {
      onNotify?.({ variant: 'error', message: err?.message || 'Failed to enable live trading.' })
    } finally {
      setSwitching(false)
    }
  }

  const dirColor = direction === 'BUY' ? 'text-bull' : direction === 'SELL' ? 'text-bear' : 'text-neutral'
  const dirBg = direction === 'BUY' ? 'bg-bull-dim' : direction === 'SELL' ? 'bg-bear-dim' : 'bg-neutral-dim'
  const dirArrow = direction === 'BUY' ? '▲' : direction === 'SELL' ? '▼' : '─'
  const pnlColor = todayPnl >= 0 ? 'text-bull' : 'text-bear'

  return (
    <div className={`terminal-card p-5 ${dirBg} relative`}>
      {confirmingLive && (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="live-confirm-title"
          className="absolute inset-0 z-10 flex items-center justify-center bg-white/80 backdrop-blur-sm rounded-xl"
        >
          <div className="bg-white border border-bear/40 rounded-xl p-4 shadow-card max-w-sm">
            <h3 id="live-confirm-title" className="text-sm font-bold text-bear mb-1">Switch to LIVE trading?</h3>
            <p className="text-xs text-onSurfaceMuted mb-3">
              This will place REAL orders with real money via Dhan. Make sure you understand the risk.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmingLive(false)}
                className="px-3 py-1.5 rounded-pill text-xs font-mono border border-gray-200 hover:bg-surface-2"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmLive}
                className="px-3 py-1.5 rounded-pill text-xs font-mono bg-bear text-white hover:bg-bear/90"
              >
                Enable Live
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        {/* Left: Direction + Conviction */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <span className={`text-3xl font-bold ${dirColor}`} aria-hidden="true">{dirArrow}</span>
            <div>
              <div className={`text-2xl font-bold tracking-tight ${dirColor}`}>{direction}</div>
              <div className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-widest">CONSENSUS</div>
            </div>
          </div>

          <div className="h-10 w-px bg-gray-200" />

          <div className="text-center">
            <div className="text-xl font-bold font-mono text-onSurface">{formatPercent(conviction)}</div>
            <div className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-widest">CONVICTION</div>
          </div>

          <div className="h-10 w-px bg-gray-200" />

          <div className="text-center">
            <div className="text-xl font-bold font-mono text-primary">{formatPercent(consensusScore)}</div>
            <div className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-widest">ALIGNMENT</div>
          </div>

          {isSimulating && (
            <>
              <div className="h-10 w-px bg-gray-200" />
              <div className="flex items-center gap-2" role="status" aria-live="polite">
                <div className="w-2 h-2 bg-primary rounded-full animate-pulse" aria-hidden="true" />
                <span className="text-xs font-mono text-primary">SIMULATING...</span>
                {onAbort && (
                  <button
                    type="button"
                    onClick={onAbort}
                    aria-label="Abort running simulation"
                    className="ml-1 px-2 py-0.5 rounded-pill text-[10px] font-mono uppercase border border-primary/30 text-primary hover:bg-primary/10"
                  >
                    Abort
                  </button>
                )}
              </div>
            </>
          )}

          {!isSimulating && dataSource && (
            <>
              <div className="h-10 w-px bg-gray-200" />
              <DataSourceBadge source={dataSource} />
            </>
          )}
        </div>

        {/* Right: P&L + Mode */}
        <div className="flex items-center gap-5">
          <div className="text-right">
            <div className={`text-xl font-bold font-mono ${pnlColor}`}>{formatINR(todayPnl)}</div>
            <div className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-widest">TODAY P&L</div>
          </div>

          <div className="h-10 w-px bg-gray-200" />

          {/* Mode toggle */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => handleToggle('paper')}
              disabled={switching}
              className={`px-3 py-1.5 rounded-pill text-[10px] font-mono uppercase tracking-wider transition-all ${
                tradingMode === 'paper'
                  ? 'bg-primary/10 text-primary border border-primary/30'
                  : 'bg-surface-2 text-onSurfaceDim border border-gray-200 hover:border-primary/30'
              }`}
            >
              Paper
            </button>
            <button
              onClick={() => handleToggle('live')}
              disabled={switching}
              className={`px-3 py-1.5 rounded-pill text-[10px] font-mono uppercase tracking-wider transition-all ${
                tradingMode === 'live'
                  ? 'bg-bear-dim text-bear border border-bear/30'
                  : 'bg-surface-2 text-onSurfaceDim border border-gray-200 hover:border-bear/30'
              }`}
            >
              Live
            </button>
            {tradingMode === 'live' && (
              <span className="w-2 h-2 bg-bear rounded-full animate-pulse" title="Real money mode" />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Compact Agent Grid ─────────────────────────────────────────────────────────

const AgentGrid = ({ completedAgents, result }) => {
  const agentsOutput = result?.agents_output
  const agentsArr = agentsOutput
    ? (Array.isArray(agentsOutput) ? agentsOutput : Object.values(agentsOutput))
    : []

  const agentMap = {}
  agentsArr.forEach(a => { agentMap[a.agent_name] = a })

  return (
    <div className="grid grid-cols-4 gap-2">
      {AGENTS.map(agent => {
        const data = agentMap[agent.id] || completedAgents[agent.id]
        const dir = data?.direction || data?.final_direction || '—'
        const conv = data?.conviction || data?.conviction_percent || 0
        const dirColor = dir === 'BUY' ? 'text-bull' : dir === 'SELL' ? 'text-bear' : 'text-onSurfaceDim'
        const dirArrow = dir === 'BUY' ? '▲' : dir === 'SELL' ? '▼' : '─'
        const isActive = !!data

        return (
          <div
            key={agent.id}
            className={`rounded-xl border p-2.5 transition-all ${
              isActive
                ? 'bg-white border-gray-200 shadow-sm'
                : 'bg-surface-1 border-gray-100'
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: agent.color }} />
                <span className="text-[10px] font-mono text-onSurfaceMuted uppercase tracking-wider">{agent.shortLabel}</span>
              </div>
              <span className="text-[10px] font-mono text-onSurfaceDim">{(agent.weight * 100).toFixed(0)}%w</span>
            </div>
            <div className="flex items-center justify-between">
              <span className={`text-sm font-bold ${dirColor}`}>{dirArrow} {dir}</span>
              <span className="text-xs font-mono text-onSurfaceMuted">{isActive ? formatPercent(conv) : '—'}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ─── Quick Scenario Buttons ────────────────────────────────────────────────────

const QuickScenarios = ({ onSelect, disabled = false }) => {
  const scenarios = [
    { id: 'rbi_rate_cut', label: 'RBI', icon: '🏦' },
    { id: 'expiry_carnage', label: 'Expiry', icon: '⏰' },
    { id: 'budget_bull', label: 'Budget', icon: '📊' },
    { id: 'fii_exodus', label: 'FII Exit', icon: '⚡' },
    { id: 'global_contagion', label: 'Global', icon: '🌍' },
    { id: 'election_day', label: 'Election', icon: '🗳' },
  ]

  return (
    <div className="flex flex-wrap gap-1.5">
      {scenarios.map(s => (
        <button
          key={s.id}
          type="button"
          onClick={() => onSelect(s.id)}
          disabled={disabled}
          aria-label={`Run ${s.label} scenario`}
          className="px-3 py-1.5 rounded-pill bg-surface-2 hover:bg-surface-3 border border-gray-200 hover:border-primary/20 text-xs font-medium text-onSurfaceMuted hover:text-onSurface transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-surface-2 disabled:hover:border-gray-200"
        >
          <span className="mr-1" aria-hidden="true">{s.icon}</span>{s.label}
        </button>
      ))}
    </div>
  )
}

// ─── P&L Summary Strip ──────────────────────────────────────────────────────────

const PnLStat = ({ label, value, color }) => (
  <div className="text-center">
    <div className={`text-sm font-bold font-mono ${color || 'text-onSurface'}`}>{value}</div>
    <div className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-widest">{label}</div>
  </div>
)

const PnLStripSkeleton = () => (
  <div className="terminal-card px-4 py-3" aria-hidden="true">
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-6">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="text-center">
            <div className="w-16 h-4 bg-surface-2 rounded animate-pulse mb-1" />
            <div className="w-10 h-2 bg-surface-2 rounded animate-pulse mx-auto" />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-6">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="text-center">
            <div className="w-12 h-4 bg-surface-2 rounded animate-pulse mb-1" />
            <div className="w-10 h-2 bg-surface-2 rounded animate-pulse mx-auto" />
          </div>
        ))}
      </div>
    </div>
  </div>
)

const PnLStrip = ({ summary, pnlData, isLoading, hasFetched }) => {
  // Show skeleton only on first load, not on background refetches
  if (isLoading && !hasFetched) return <PnLStripSkeleton />

  // Empty state when no trading activity yet
  if (!summary || summary.total_trades === 0) {
    return (
      <div className="terminal-card px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-onSurfaceDim text-xs">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4 opacity-60" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625z" />
            </svg>
            <span className="font-mono">No trading activity yet — run a simulation + record outcome to start tracking P&L.</span>
          </div>
          <div className="flex items-center gap-6 opacity-40">
            <PnLStat label="Trades" value="0" />
          </div>
        </div>
      </div>
    )
  }

  const todayDate = new Date().toISOString().slice(0, 10)
  const latestEntry = pnlData?.daily_pnl?.[0]
  const todayPnl = (latestEntry?.date === todayDate) ? (latestEntry?.pnl || 0) : 0
  const weeklyPnl = (pnlData?.daily_pnl || []).slice(0, 5).reduce((sum, d) => sum + (d.pnl || 0), 0)
  const totalPnl = summary?.total_pnl_inr || 0
  const winRate = summary?.win_rate_pct || 0
  const trades = summary?.total_trades || 0
  const maxDD = summary?.max_drawdown_pct || 0

  return (
    <div className="terminal-card px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <PnLStat label="Today" value={formatINR(todayPnl)} color={todayPnl >= 0 ? 'text-bull' : 'text-bear'} />
          <PnLStat label="Week" value={formatINR(weeklyPnl)} color={weeklyPnl >= 0 ? 'text-bull' : 'text-bear'} />
          <PnLStat label="Total" value={formatINR(totalPnl)} color={totalPnl >= 0 ? 'text-bull' : 'text-bear'} />
        </div>
        <div className="flex items-center gap-6">
          <PnLStat label="Win Rate" value={formatPercent(winRate)} color={winRate >= 50 ? 'text-bull' : 'text-bear'} />
          <PnLStat label="Trades" value={String(trades)} />
          <PnLStat label="Max DD" value={formatPercent(maxDD)} color="text-bear" />
        </div>
      </div>
    </div>
  )
}

// ─── Signal Intel ───────────────────────────────────────────────────────────────

const SignalIntelSection = ({ result, isLoading }) => {
  const [expandedAgent, setExpandedAgent] = useState(null)

  const getTopSignals = () => {
    if (!result || !result.agents_output) return []
    const agentsArr = Array.isArray(result.agents_output)
      ? result.agents_output
      : Object.values(result.agents_output)
    // Sort by conviction desc, then take top 3
    return agentsArr
      .filter(r => r && r.reasoning)
      .map(r => ({
        agent: r.agent_name,
        reasoning: r.reasoning,
        confidence: r.conviction || 0,
        direction: r.direction || 'HOLD',
      }))
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 3)
  }

  const signals = getTopSignals()

  return (
    <div className="terminal-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[10px] font-mono uppercase tracking-widest text-onSurfaceMuted">Top Signals</h3>
        {signals.length > 0 && (
          <span className="text-[9px] font-mono text-onSurfaceDim">by conviction</span>
        )}
      </div>
      <div className="space-y-2">
        {isLoading ? (
          <div className="flex items-center gap-2 py-4 justify-center" role="status" aria-live="polite">
            <div className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" aria-hidden="true" />
            <span className="text-[11px] text-onSurfaceDim">Analyzing agent reasoning...</span>
          </div>
        ) : signals.length === 0 ? (
          <div className="flex flex-col items-center gap-1 py-4 text-onSurfaceDim">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5 opacity-40" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
            <span className="text-[11px]">Run a simulation to see agent insights</span>
          </div>
        ) : (
          signals.map((signal) => {
            const isExpanded = expandedAgent === signal.agent
            const truncated = signal.reasoning.length > 100
            const preview = truncated ? signal.reasoning.substring(0, 100) + '...' : signal.reasoning
            const dirColor = signal.direction?.includes('BUY') ? 'text-bull' : signal.direction?.includes('SELL') ? 'text-bear' : 'text-neutral'
            return (
              <div key={signal.agent} className="p-2.5 bg-surface-1 rounded-xl border border-gray-100">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-mono text-primary font-medium">{signal.agent}</span>
                    <span className={`text-[9px] font-mono ${dirColor}`}>{signal.direction}</span>
                  </div>
                  <span className="text-[10px] text-onSurfaceDim tabular-nums">{formatPercent(signal.confidence)}</span>
                </div>
                <p className="text-[11px] text-onSurfaceMuted leading-relaxed">
                  {isExpanded ? signal.reasoning : preview}
                </p>
                {truncated && (
                  <button
                    type="button"
                    onClick={() => setExpandedAgent(isExpanded ? null : signal.agent)}
                    aria-expanded={isExpanded}
                    aria-label={isExpanded ? `Collapse ${signal.agent} reasoning` : `Show full ${signal.agent} reasoning`}
                    className="mt-1 text-[10px] font-mono text-primary hover:underline"
                  >
                    {isExpanded ? '− less' : '+ more'}
                  </button>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

// ─── Main Dashboard ─────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { simulate, result, events, currentRound, completedAgents, aggregation, streamStatus, isLoading, error, reset } = useStreamingSimulation()

  const [tradingMode, setTradingMode] = useState('paper')
  const [dhanEnabled, setDhanEnabled] = useState(false)
  const [tradingSummary, setTradingSummary] = useState(null)
  const [tradingPnl, setTradingPnl] = useState(null)
  const [tradingTrades, setTradingTrades] = useState([])
  const [tradesLoading, setTradesLoading] = useState(false)
  const [hasFetchedTrading, setHasFetchedTrading] = useState(false)
  const [notification, setNotification] = useState(null)
  const prevStreamStatus = useRef(streamStatus)

  useEffect(() => {
    apiClient.getTradingMode()
      .then(data => {
        setTradingMode(data.mode || 'paper')
        setDhanEnabled(data.dhan_orders_enabled || false)
      })
      .catch((err) => {
        setNotification({
          variant: 'warn',
          message: `Trading mode unavailable — using paper fallback. (${err?.message || 'network error'})`,
        })
      })
  }, [])

  const handleModeChange = useCallback(async (newMode) => {
    const needsConfirm = newMode === 'live'
    await apiClient.setTradingMode(newMode, needsConfirm)
    setTradingMode(newMode)
  }, [])

  const fetchTradingData = useCallback(async () => {
    if (document.hidden) return
    setTradesLoading(true)
    try {
      const [summaryRes, pnlRes, tradesRes] = await Promise.all([
        apiClient.getTradingSummary(30),
        apiClient.getTradingPnl(30),
        apiClient.getTradingTrades({ limit: 15 }),
      ])
      setTradingSummary(summaryRes)
      setTradingPnl(pnlRes)
      setTradingTrades(tradesRes.trades || [])
      setHasFetchedTrading(true)
    } catch (err) {
      console.error('Failed to fetch trading data:', err)
      if (!hasFetchedTrading) {
        setNotification({
          variant: 'warn',
          message: 'Trading data unavailable — P&L strip will show once backend is reachable.',
        })
      }
    } finally {
      setTradesLoading(false)
    }
  }, [hasFetchedTrading])

  useEffect(() => {
    fetchTradingData()
    const interval = setInterval(fetchTradingData, 10000)
    return () => clearInterval(interval)
  }, [fetchTradingData, tradingMode])

  // Refresh trading data when a simulation completes
  useEffect(() => {
    if (prevStreamStatus.current !== 'done' && streamStatus === 'done') {
      fetchTradingData()
    }
    prevStreamStatus.current = streamStatus
  }, [streamStatus, fetchTradingData])

  // Surface streaming errors via toast once
  useEffect(() => {
    if (error) {
      setNotification({ variant: 'error', message: String(error), ttl: 7000 })
    }
  }, [error])

  const handleAbort = useCallback(() => {
    reset()
    setNotification({ variant: 'info', message: 'Simulation aborted.' })
  }, [reset])

  const handleRunScenario = useCallback((id) => {
    if (isLoading) return
    simulate({ scenario_id: id })
  }, [isLoading, simulate])

  const directionStats = (() => {
    if (!aggregation) return { direction: 'HOLD', conviction: 0, consensusScore: 0 }
    return {
      direction: aggregation.final_direction || 'HOLD',
      conviction: aggregation.conviction_percent || 0,
      consensusScore: aggregation.consensus_score || 0,
    }
  })()

  const todayStr = new Date().toISOString().slice(0, 10)
  const latestPnlEntry = tradingPnl?.daily_pnl?.[0]
  const todayPnl = (latestPnlEntry?.date === todayStr) ? (latestPnlEntry?.pnl || 0) : 0

  const totalAgents = AGENTS.length
  const simulationKey = result?.simulation_id || result?.run_id || streamStatus

  return (
    <div className="h-full bg-surface-1 p-4 overflow-auto">
      <Toast notification={notification} onClose={() => setNotification(null)} />

      <div className="max-w-[1600px] mx-auto space-y-3">

        <HeroBanner
          direction={directionStats.direction}
          conviction={directionStats.conviction}
          consensusScore={directionStats.consensusScore}
          todayPnl={todayPnl}
          tradingMode={tradingMode}
          onModeChange={handleModeChange}
          dhanEnabled={dhanEnabled}
          isSimulating={isLoading}
          onAbort={handleAbort}
          onNotify={setNotification}
          dataSource={result?.data_source || result?.market_data_source}
        />

        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-8">
            <AgentGrid completedAgents={completedAgents} result={result} />
          </div>

          <div className="col-span-4 flex flex-col gap-3">
            <button
              type="button"
              onClick={() => handleRunScenario('rbi_rate_cut')}
              disabled={isLoading}
              aria-busy={isLoading}
              aria-label={isLoading ? 'Simulation running' : 'Run default RBI rate cut simulation'}
              className={`w-full py-3 rounded-xl font-semibold text-sm transition-all duration-300 ${
                isLoading
                  ? 'bg-primary/10 text-primary cursor-wait'
                  : 'bg-primary text-white hover:bg-secondary hover:shadow-card active:scale-[0.98]'
              }`}
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-2 h-2 bg-primary rounded-full animate-pulse" aria-hidden="true" />
                  Round {currentRound || 1} · {Object.keys(completedAgents).length}/{totalAgents} Agents
                </span>
              ) : (
                '▶ RUN SIMULATION'
              )}
            </button>
            <div className="terminal-card p-3">
              <div className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-widest mb-2">Quick Scenario</div>
              <QuickScenarios onSelect={handleRunScenario} disabled={isLoading} />
            </div>
          </div>
        </div>

        <PnLStrip
          summary={tradingSummary}
          pnlData={tradingPnl}
          isLoading={tradesLoading}
          hasFetched={hasFetchedTrading}
        />

        <DailySummaryCard />

        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-5">
            <PressurePanel result={result} isLoading={isLoading} />
          </div>
          <div className="col-span-4">
            <SignalIntelSection result={result} isLoading={isLoading} />
          </div>
          <div className="col-span-3">
            <InsightsPanel result={result} isLoading={isLoading} />
          </div>
        </div>

        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-5">
            <ScenarioPanel onSimulate={simulate} isLoading={isLoading} />
          </div>
          <div className="col-span-4">
            <AccuracyPanel refreshKey={simulationKey} />
          </div>
          <div className="col-span-3">
            <FeedbackPanel refreshKey={simulationKey} />
          </div>
        </div>
      </div>
    </div>
  )
}
