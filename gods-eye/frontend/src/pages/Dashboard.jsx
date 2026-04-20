import React, { useState, useEffect, useCallback } from 'react'
import { useStreamingSimulation } from '../hooks/useStreamingSimulation'
import { apiClient } from '../api/client'
import { AGENTS, AGENT_COLORS } from '../constants/agents'
import ScenarioPanel from '../components/ScenarioPanel'
import PressurePanel from '../components/PressurePanel'
import InsightsPanel from '../components/InsightsPanel'
import AccuracyPanel from '../components/AccuracyPanel'
import FeedbackPanel from '../components/FeedbackPanel'

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

// ─── Hero Banner ──────────────────────────────────────────────────────────────

const HeroBanner = ({ direction, conviction, consensusScore, todayPnl, tradingMode, onModeChange, dhanEnabled, isSimulating }) => {
  const [switching, setSwitching] = useState(false)

  const handleToggle = async (newMode) => {
    if (newMode === tradingMode || switching) return
    setSwitching(true)
    try {
      if (newMode === 'live') {
        if (!dhanEnabled) {
          alert('Cannot switch to live: DHAN_ORDERS_ENABLED is not set on the server.')
          return
        }
        const confirmed = window.confirm(
          'Switch to LIVE trading? This will place REAL orders with real money via Dhan.'
        )
        if (!confirmed) return
      }
      await onModeChange(newMode)
    } finally {
      setSwitching(false)
    }
  }

  const dirColor = direction === 'BUY' ? 'text-bull' : direction === 'SELL' ? 'text-bear' : 'text-neutral'
  const dirBg = direction === 'BUY' ? 'bg-bull-dim' : direction === 'SELL' ? 'bg-bear-dim' : 'bg-neutral-dim'
  const dirArrow = direction === 'BUY' ? '▲' : direction === 'SELL' ? '▼' : '─'
  const pnlColor = todayPnl >= 0 ? 'text-bull' : 'text-bear'

  return (
    <div className={`terminal-card p-5 ${dirBg}`}>
      <div className="flex items-center justify-between">
        {/* Left: Direction + Conviction */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <span className={`text-3xl font-bold ${dirColor}`}>{dirArrow}</span>
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
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                <span className="text-xs font-mono text-primary">SIMULATING...</span>
              </div>
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

const QuickScenarios = ({ onSelect }) => {
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
          onClick={() => onSelect(s.id)}
          aria-label={`Run ${s.label} scenario`}
          className="px-3 py-1.5 rounded-pill bg-surface-2 hover:bg-surface-3 border border-gray-200 hover:border-primary/20 text-xs font-medium text-onSurfaceMuted hover:text-onSurface transition-all duration-200"
        >
          <span className="mr-1" aria-hidden="true">{s.icon}</span>{s.label}
        </button>
      ))}
    </div>
  )
}

// ─── P&L Summary Strip ──────────────────────────────────────────────────────────

const PnLStrip = ({ summary, pnlData, isLoading }) => {
  if (isLoading || !summary) return null

  const todayDate = new Date().toISOString().slice(0, 10)
  const latestEntry = pnlData?.daily_pnl?.[0]
  const todayPnl = (latestEntry?.date === todayDate) ? (latestEntry?.pnl || 0) : 0
  const weeklyPnl = (pnlData?.daily_pnl || []).slice(0, 5).reduce((sum, d) => sum + (d.pnl || 0), 0)
  const totalPnl = summary?.total_pnl_inr || 0
  const winRate = summary?.win_rate_pct || 0
  const trades = summary?.total_trades || 0
  const maxDD = summary?.max_drawdown_pct || 0

  const Stat = ({ label, value, color }) => (
    <div className="text-center">
      <div className={`text-sm font-bold font-mono ${color || 'text-onSurface'}`}>{value}</div>
      <div className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-widest">{label}</div>
    </div>
  )

  return (
    <div className="terminal-card px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Stat label="Today" value={formatINR(todayPnl)} color={todayPnl >= 0 ? 'text-bull' : 'text-bear'} />
          <Stat label="Week" value={formatINR(weeklyPnl)} color={weeklyPnl >= 0 ? 'text-bull' : 'text-bear'} />
          <Stat label="Total" value={formatINR(totalPnl)} color={totalPnl >= 0 ? 'text-bull' : 'text-bear'} />
        </div>
        <div className="flex items-center gap-6">
          <Stat label="Win Rate" value={formatPercent(winRate)} color={winRate >= 50 ? 'text-bull' : 'text-bear'} />
          <Stat label="Trades" value={String(trades)} />
          <Stat label="Max DD" value={formatPercent(maxDD)} color="text-bear" />
        </div>
      </div>
    </div>
  )
}

// ─── Signal Intel ───────────────────────────────────────────────────────────────

const SignalIntelSection = ({ result, isLoading }) => {
  const getLatestSignals = () => {
    if (!result || !result.agents_output) return []
    const agentsArr = Array.isArray(result.agents_output)
      ? result.agents_output
      : Object.values(result.agents_output)
    return agentsArr
      .filter(r => r.reasoning)
      .slice(0, 3)
      .map(r => ({
        agent: r.agent_name,
        reasoning: r.reasoning.substring(0, 100) + (r.reasoning.length > 100 ? '...' : ''),
        confidence: r.conviction || 0
      }))
  }

  const signals = getLatestSignals()

  return (
    <div className="terminal-card p-4">
      <h3 className="text-[10px] font-mono uppercase tracking-widest text-onSurfaceMuted mb-3">Key Signals</h3>
      <div className="space-y-2">
        {isLoading ? (
          <div className="flex items-center gap-2 py-4 justify-center">
            <div className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" />
            <span className="text-[11px] text-onSurfaceDim">Analyzing...</span>
          </div>
        ) : signals.length === 0 ? (
          <div className="text-[11px] text-onSurfaceDim py-3 text-center">
            Run a simulation to see agent insights
          </div>
        ) : (
          signals.map((signal) => (
            <div key={signal.agent} className="p-2.5 bg-surface-1 rounded-xl border border-gray-100">
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[10px] font-mono text-primary font-medium">{signal.agent}</span>
                <span className="text-[10px] text-onSurfaceDim">{formatPercent(signal.confidence)}</span>
              </div>
              <p className="text-[11px] text-onSurfaceMuted leading-relaxed">{signal.reasoning}</p>
            </div>
          ))
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

  useEffect(() => {
    apiClient.getTradingMode()
      .then(data => {
        setTradingMode(data.mode || 'paper')
        setDhanEnabled(data.dhan_orders_enabled || false)
      })
      .catch(() => {})
  }, [])

  const handleModeChange = useCallback(async (newMode) => {
    try {
      const needsConfirm = newMode === 'live'
      await apiClient.setTradingMode(newMode, needsConfirm)
      setTradingMode(newMode)
    } catch (err) {
      alert(`Failed to switch mode: ${err.message}`)
    }
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
    } catch (err) {
      console.error('Failed to fetch trading data:', err)
    } finally {
      setTradesLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTradingData()
    const interval = setInterval(fetchTradingData, 10000)
    return () => clearInterval(interval)
  }, [fetchTradingData, tradingMode])

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

  return (
    <div className="h-full bg-surface-1 p-4 overflow-auto">
      <div className="max-w-[1600px] mx-auto space-y-3">

        {error && (
          <div className="p-3 bg-bear-dim border border-bear/20 rounded-xl text-bear text-sm flex items-center gap-2">
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 flex-shrink-0"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
            <span>{error}</span>
          </div>
        )}

        <HeroBanner
          direction={directionStats.direction}
          conviction={directionStats.conviction}
          consensusScore={directionStats.consensusScore}
          todayPnl={todayPnl}
          tradingMode={tradingMode}
          onModeChange={handleModeChange}
          dhanEnabled={dhanEnabled}
          isSimulating={isLoading}
        />

        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-8">
            <AgentGrid completedAgents={completedAgents} result={result} />
          </div>

          <div className="col-span-4 flex flex-col gap-3">
            <button
              onClick={() => simulate({ scenario_id: 'rbi_rate_cut' })}
              disabled={isLoading}
              className={`w-full py-3 rounded-xl font-semibold text-sm transition-all duration-300 ${
                isLoading
                  ? 'bg-primary/10 text-primary cursor-wait'
                  : 'bg-primary text-white hover:bg-secondary hover:shadow-card active:scale-[0.98]'
              }`}
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
                  Round {currentRound} · {Object.keys(completedAgents).length}/8 Agents
                </span>
              ) : (
                '▶ RUN SIMULATION'
              )}
            </button>
            <div className="terminal-card p-3">
              <div className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-widest mb-2">Quick Scenario</div>
              <QuickScenarios onSelect={(id) => simulate({ scenario_id: id })} />
            </div>
          </div>
        </div>

        <PnLStrip summary={tradingSummary} pnlData={tradingPnl} isLoading={tradesLoading} />

        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-5">
            <PressurePanel result={result} aggregation={aggregation} />
          </div>
          <div className="col-span-4">
            <SignalIntelSection result={result} isLoading={isLoading} />
          </div>
          <div className="col-span-3">
            <InsightsPanel result={result} aggregation={aggregation} />
          </div>
        </div>

        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-5">
            <ScenarioPanel result={result} />
          </div>
          <div className="col-span-4">
            <AccuracyPanel result={result} />
          </div>
          <div className="col-span-3">
            <FeedbackPanel result={result} onFeedbackSubmit={fetchTradingData} />
          </div>
        </div>
      </div>
    </div>
  )
}
