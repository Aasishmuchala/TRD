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

const formatPercent = (value, decimals = 2) => {
  if (value === null || value === undefined) return '0%'
  const num = parseFloat(value)
  return isNaN(num) ? '0%' : `${num.toFixed(decimals)}%`
}

const getDirectionColor = (direction) => {
  if (direction === 'BUY') return 'text-bull'
  if (direction === 'SELL') return 'text-bear'
  return 'text-neutral'
}

const getDirectionBgColor = (direction) => {
  if (direction === 'BUY') return 'bg-bull/10'
  if (direction === 'SELL') return 'bg-bear/10'
  return 'bg-neutral/10'
}

const StatCard = ({ label, value, icon, accent, trend, trendValue }) => (
  <div className="terminal-card p-4 relative overflow-hidden group">
    <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

    <div className="relative z-10 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono uppercase tracking-wider text-onSurfaceMuted">{label}</span>
        {icon && (
          <span className="material-symbols-outlined text-lg text-primary/60 group-hover:text-primary transition-colors">
            {icon}
          </span>
        )}
      </div>

      <div className="flex-1">
        <div className={`text-3xl font-bold tracking-tight ${accent || 'text-primary'}`}>
          {value}
        </div>
      </div>

      {trend && trendValue !== null && (
        <div className={`text-xs mt-2 flex items-center gap-1 ${
          parseFloat(trendValue) >= 0 ? 'text-bull' : 'text-bear'
        }`}>
          <span className="material-symbols-outlined text-sm">
            {parseFloat(trendValue) >= 0 ? 'trending_up' : 'trending_down'}
          </span>
          <span>{Math.abs(parseFloat(trendValue)).toFixed(1)}%</span>
        </div>
      )}
    </div>
  </div>
)

// ─── Trading Mode Toggle ──────────────────────────────────────────────────────

const TradingModeToggle = ({ mode, onModeChange, dhanEnabled }) => {
  const [switching, setSwitching] = useState(false)

  const handleToggle = async (newMode) => {
    if (newMode === mode || switching) return
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

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => handleToggle('paper')}
        disabled={switching}
        className={`px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider transition-all ${
          mode === 'paper'
            ? 'bg-primary/20 text-primary border border-primary/40 shadow-glow-sm'
            : 'bg-surface-1 text-onSurfaceDim border border-surface-2 hover:border-primary/30'
        }`}
      >
        Paper
      </button>
      <button
        onClick={() => handleToggle('live')}
        disabled={switching}
        className={`px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider transition-all ${
          mode === 'live'
            ? 'bg-bear/20 text-bear border border-bear/40 shadow-glow-sm'
            : 'bg-surface-1 text-onSurfaceDim border border-surface-2 hover:border-bear/30'
        }`}
      >
        Live
      </button>
      {mode === 'live' && (
        <span className="flex items-center gap-1 text-xs text-bear">
          <span className="w-2 h-2 bg-bear rounded-full animate-pulse" />
          REAL MONEY
        </span>
      )}
    </div>
  )
}

// ─── P&L Breakdown Panel ──────────────────────────────────────────────────────

const PnLBreakdown = ({ summary, pnlData, isLoading }) => {
  if (isLoading) {
    return (
      <div className="terminal-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <span className="material-symbols-outlined text-lg text-primary">analytics</span>
          <h3 className="font-mono text-sm uppercase tracking-wider text-primary-glow">P&L Breakdown</h3>
        </div>
        <div className="flex items-center justify-center py-8">
          <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
          <span className="text-xs text-onSurfaceDim ml-2">Loading P&L...</span>
        </div>
      </div>
    )
  }

  // Validate that daily_pnl[0] is actually today before showing as "Today" P&L
  const todayDate = new Date().toISOString().slice(0, 10)
  const latestEntry = pnlData?.daily_pnl?.[0]
  const todayPnl = (latestEntry?.date === todayDate) ? (latestEntry?.pnl || 0) : 0
  const weeklyPnl = (pnlData?.daily_pnl || []).slice(0, 5).reduce((sum, d) => sum + (d.pnl || 0), 0)
  const totalPnl = summary?.total_pnl_inr || 0
  const winRate = summary?.win_rate_pct || 0
  const totalTrades = summary?.total_trades || 0
  const capital = summary?.capital || 0
  const totalReturn = summary?.total_return_pct || 0
  const maxDrawdown = summary?.max_drawdown_pct || 0
  const profitFactor = summary?.profit_factor || 0
  const avgWin = summary?.avg_win_inr || 0
  const avgLoss = summary?.avg_loss_inr || 0

  const PnLRow = ({ label, value, isPercent = false, highlight = false }) => (
    <div className={`flex justify-between items-center py-1.5 ${highlight ? 'border-t border-primary/20 pt-2 mt-1' : ''}`}>
      <span className="text-xs text-onSurfaceMuted">{label}</span>
      <span className={`text-sm font-mono font-semibold ${
        isPercent
          ? (parseFloat(value) >= 0 ? 'text-bull' : 'text-bear')
          : (typeof value === 'string' ? 'text-onSurface' : (value >= 0 ? 'text-bull' : 'text-bear'))
      }`}>
        {isPercent ? formatPercent(value) : (typeof value === 'string' ? value : formatINR(value))}
      </span>
    </div>
  )

  return (
    <div className="terminal-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-lg text-primary">analytics</span>
        <h3 className="font-mono text-sm uppercase tracking-wider text-primary-glow">P&L Breakdown</h3>
      </div>

      <div className="space-y-0.5">
        <PnLRow label="Today" value={todayPnl} />
        <PnLRow label="This Week (5d)" value={weeklyPnl} />
        <PnLRow label="Cumulative" value={totalPnl} highlight />
        <PnLRow label="Total Return" value={totalReturn} isPercent />
        <PnLRow label="Capital" value={capital} />

        <div className="border-t border-surface-2 my-2" />

        <PnLRow label="Win Rate" value={winRate} isPercent />
        <PnLRow label="Total Trades" value={String(totalTrades)} />
        <PnLRow label="Avg Win" value={avgWin} />
        <PnLRow label="Avg Loss" value={avgLoss} />
        <PnLRow label="Profit Factor" value={profitFactor ? profitFactor.toFixed(2) + 'x' : '—'} />
        <PnLRow label="Max Drawdown" value={maxDrawdown} isPercent />
      </div>
    </div>
  )
}

// ─── Daily P&L Chart ──────────────────────────────────────────────────────────

const DailyPnLChart = ({ pnlData, isLoading }) => {
  const dailyPnl = pnlData?.daily_pnl || []

  // Show last 14 days max
  const displayData = dailyPnl.slice(0, 14).reverse()

  if (isLoading || displayData.length === 0) {
    return (
      <div className="terminal-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <span className="material-symbols-outlined text-lg text-primary">bar_chart</span>
          <h3 className="font-mono text-sm uppercase tracking-wider text-primary-glow">Daily P&L</h3>
        </div>
        <div className="flex items-center justify-center py-12 text-onSurfaceDim text-xs">
          {isLoading ? 'Loading...' : 'No daily P&L data yet'}
        </div>
      </div>
    )
  }

  const maxVal = Math.max(...displayData.map(d => Math.abs(d.pnl || 0)), 1)
  const barWidth = 100 / displayData.length

  return (
    <div className="terminal-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-lg text-primary">bar_chart</span>
        <h3 className="font-mono text-sm uppercase tracking-wider text-primary-glow">Daily P&L</h3>
      </div>

      <div className="relative h-36 bg-surface-0/30 rounded px-2 pt-2 pb-6">
        {/* Zero line */}
        <div className="absolute left-2 right-2 top-1/2 border-t border-dashed border-primary/20" />

        <div className="flex items-end justify-around h-full relative">
          {displayData.map((day, idx) => {
            const pnl = day.pnl || 0
            const height = (Math.abs(pnl) / maxVal) * 45 // max 45% of container
            const isPositive = pnl >= 0

            return (
              <div
                key={day.date || idx}
                className="flex flex-col items-center relative"
                style={{ width: `${barWidth}%` }}
                title={`${day.date}: ${formatINR(pnl)}`}
              >
                <div className="relative w-full flex justify-center" style={{ height: '100%' }}>
                  <div
                    className={`w-3/4 max-w-[24px] rounded-sm transition-all ${
                      isPositive ? 'bg-bull/60' : 'bg-bear/60'
                    }`}
                    style={{
                      height: `${Math.max(height, 2)}%`,
                      position: 'absolute',
                      bottom: isPositive ? '50%' : 'auto',
                      top: isPositive ? 'auto' : '50%',
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>

        {/* Date labels */}
        <div className="absolute bottom-0 left-2 right-2 flex justify-between">
          <span className="text-[9px] text-onSurfaceDim">
            {displayData[0]?.date?.slice(5) || ''}
          </span>
          <span className="text-[9px] text-onSurfaceDim">
            {displayData[displayData.length - 1]?.date?.slice(5) || ''}
          </span>
        </div>
      </div>
    </div>
  )
}

// ─── Equity Curve (cumulative) ────────────────────────────────────────────────

const EquityCurveChart = ({ pnlData, isLoading }) => {
  const dailyPnl = pnlData?.daily_pnl || []
  const displayData = dailyPnl.slice().reverse()

  if (isLoading || displayData.length === 0) {
    return (
      <div className="terminal-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <span className="material-symbols-outlined text-lg text-primary">show_chart</span>
          <h3 className="font-mono text-sm uppercase tracking-wider text-primary-glow">Equity Curve</h3>
        </div>
        <div className="flex items-center justify-center py-12 text-onSurfaceDim text-xs">
          {isLoading ? 'Loading equity curve...' : 'No trade data yet'}
        </div>
      </div>
    )
  }

  const cumulativeData = displayData.map(d => d.cumulative || 0)
  const maxPnL = Math.max(...cumulativeData, 0) || 1
  const minPnL = Math.min(...cumulativeData, 0) || 0
  const range = maxPnL - minPnL || 1

  return (
    <div className="terminal-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-lg text-primary">show_chart</span>
        <h3 className="font-mono text-sm uppercase tracking-wider text-primary-glow">Equity Curve</h3>
      </div>

      <div className="relative h-32 bg-surface-0/30 rounded p-4">
        <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <line x1="0" y1="50" x2="100" y2="50" stroke="rgba(168, 154, 255, 0.1)" strokeWidth="0.5" />

          {cumulativeData.length > 1 && (
            <>
              <path
                d={`M 0 ${100 - ((cumulativeData[0] - minPnL) / range) * 100} ${cumulativeData
                  .map((val, i) => `L ${(i / (cumulativeData.length - 1)) * 100} ${100 - ((val - minPnL) / range) * 100}`)
                  .join(' ')} L 100 100 L 0 100 Z`}
                fill="rgba(168, 154, 255, 0.15)"
              />
              <polyline
                points={cumulativeData
                  .map((val, i) => `${(i / (cumulativeData.length - 1)) * 100},${100 - ((val - minPnL) / range) * 100}`)
                  .join(' ')}
                fill="none"
                stroke="#A89AFF"
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
            </>
          )}
        </svg>

        <div className="absolute bottom-2 left-2 right-2 flex justify-between text-xs text-onSurfaceDim pointer-events-none">
          <span>{formatINR(minPnL)}</span>
          <span>{formatINR(maxPnL)}</span>
        </div>
      </div>
    </div>
  )
}

// ─── Signal Intel ─────────────────────────────────────────────────────────────

const SignalIntelSection = ({ result, events, isLoading }) => {
  const getLatestSignals = () => {
    if (!result || !result.agents_output) return []

    // agents_output can be a dict (keyed by agent name) or an array — normalize to array
    const agentsArr = Array.isArray(result.agents_output)
      ? result.agents_output
      : Object.values(result.agents_output)

    return agentsArr
      .filter(r => r.reasoning)
      .slice(0, 3)
      .map(r => ({
        agent: r.agent_name,
        reasoning: r.reasoning.substring(0, 120) + (r.reasoning.length > 120 ? '...' : ''),
        confidence: r.conviction || 0
      }))
  }

  const signals = getLatestSignals()

  return (
    <div className="terminal-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-lg text-primary">smart_toy</span>
        <h3 className="font-mono text-sm uppercase tracking-wider text-primary-glow">Signal Intel</h3>
      </div>

      <div className="space-y-3">
        {isLoading ? (
          <div className="flex items-center gap-2 py-8 justify-center">
            <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
            <span className="text-xs text-onSurfaceDim">Analyzing agents...</span>
          </div>
        ) : signals.length === 0 ? (
          <div className="text-xs text-onSurfaceDim py-6 text-center">
            Run a simulation to see agent insights
          </div>
        ) : (
          signals.map((signal) => (
            <div key={signal.agent} className="p-3 bg-surface-0/50 rounded border border-primary/20 hover:border-primary/40 transition-colors">
              <div className="flex items-start justify-between gap-2 mb-1">
                <span className="text-xs font-mono text-primary-glow">{signal.agent}</span>
                <span className="text-xs text-onSurfaceDim">{formatPercent(signal.confidence)}</span>
              </div>
              <p className="text-xs text-onSurface leading-relaxed">{signal.reasoning}</p>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ─── Trade History Table ──────────────────────────────────────────────────────

const TradesTable = ({ trades, tradingMode, isLoading }) => {
  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString)
      return date.toLocaleString('en-IN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return dateString
    }
  }

  const getStatusBadge = (status) => {
    const styles = {
      OPEN: 'bg-primary/20 text-primary',
      STOPPED: 'bg-bear/20 text-bear',
      TARGET_HIT: 'bg-bull/20 text-bull',
      CLOSED_EOD: 'bg-neutral/20 text-neutral',
      ORDER_FAILED: 'bg-bear/30 text-bear',
      CANCELLED: 'bg-surface-2 text-onSurfaceDim',
    }
    return styles[status] || 'bg-surface-2 text-onSurfaceDim'
  }

  return (
    <div className="terminal-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-lg text-primary">trending_up</span>
          <h3 className="font-mono text-sm uppercase tracking-wider text-primary-glow">
            Trade History
          </h3>
        </div>
        <span className={`text-xs font-mono px-2 py-0.5 rounded ${
          tradingMode === 'live' ? 'bg-bear/10 text-bear' : 'bg-primary/10 text-primary'
        }`}>
          {tradingMode?.toUpperCase()}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-primary/20">
              <th className="text-left py-2 px-2 text-onSurfaceDim font-mono uppercase tracking-wider">Time</th>
              <th className="text-left py-2 px-2 text-onSurfaceDim font-mono uppercase tracking-wider">Dir</th>
              <th className="text-left py-2 px-2 text-onSurfaceDim font-mono uppercase tracking-wider">Type</th>
              <th className="text-right py-2 px-2 text-onSurfaceDim font-mono uppercase tracking-wider">Entry</th>
              <th className="text-right py-2 px-2 text-onSurfaceDim font-mono uppercase tracking-wider">Exit</th>
              <th className="text-right py-2 px-2 text-onSurfaceDim font-mono uppercase tracking-wider">P&L</th>
              <th className="text-left py-2 px-2 text-onSurfaceDim font-mono uppercase tracking-wider">Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="text-center py-6 text-onSurfaceDim">
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                    <span>Loading trades...</span>
                  </div>
                </td>
              </tr>
            ) : trades.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-6 text-onSurfaceDim">
                  No trades recorded yet
                </td>
              </tr>
            ) : (
              trades.map((trade) => {
                const pnl = parseFloat(trade.net_pnl) || 0
                const pnlColor = pnl > 0 ? 'text-bull' : pnl < 0 ? 'text-bear' : 'text-onSurfaceDim'
                const dirColor = trade.direction?.includes('BUY') ? 'text-bull' : trade.direction?.includes('SELL') ? 'text-bear' : 'text-neutral'

                return (
                  <tr key={trade.trade_id} className="border-b border-surface-2 hover:bg-surface-1/50 transition-colors">
                    <td className="py-2 px-2 text-onSurfaceMuted">{formatDate(trade.timestamp)}</td>
                    <td className={`py-2 px-2 font-mono font-semibold ${dirColor}`}>
                      {trade.direction}
                    </td>
                    <td className="py-2 px-2 text-onSurface">
                      {trade.option_type} {trade.lots}L
                    </td>
                    <td className="py-2 px-2 text-right text-onSurface font-mono">
                      {trade.entry_premium?.toFixed(1)}
                    </td>
                    <td className="py-2 px-2 text-right text-onSurface font-mono">
                      {trade.exit_premium ? trade.exit_premium.toFixed(1) : '—'}
                    </td>
                    <td className={`py-2 px-2 text-right font-mono font-semibold ${pnlColor}`}>
                      {trade.status === 'OPEN' ? '—' : formatINR(pnl)}
                    </td>
                    <td className="py-2 px-2">
                      <span className={`inline-block px-2 py-0.5 rounded text-[10px] uppercase tracking-wide ${getStatusBadge(trade.status)}`}>
                        {trade.status}
                      </span>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const { simulate, result, events, currentRound, completedAgents, aggregation, streamStatus, isLoading, error, reset } = useStreamingSimulation()

  // Trading mode state
  const [tradingMode, setTradingMode] = useState('paper')
  const [dhanEnabled, setDhanEnabled] = useState(false)

  // Unified trading data
  const [tradingSummary, setTradingSummary] = useState(null)
  const [tradingPnl, setTradingPnl] = useState(null)
  const [tradingTrades, setTradingTrades] = useState([])
  const [tradesLoading, setTradesLoading] = useState(false)

  // Fetch trading mode on mount
  useEffect(() => {
    apiClient.getTradingMode()
      .then(data => {
        setTradingMode(data.mode || 'paper')
        setDhanEnabled(data.dhan_orders_enabled || false)
      })
      .catch(() => {})
  }, [])

  // Handle mode change
  const handleModeChange = useCallback(async (newMode) => {
    try {
      const needsConfirm = newMode === 'live'
      await apiClient.setTradingMode(newMode, needsConfirm)
      setTradingMode(newMode)
    } catch (err) {
      alert(`Failed to switch mode: ${err.message}`)
    }
  }, [])

  // Fetch trading data (unified endpoint — respects active mode)
  const fetchTradingData = useCallback(async () => {
    // Skip fetch if tab is hidden to avoid wasting API calls
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

  // Poll trading data every 10s, and re-fetch on mode change
  // fetchTradingData is stable (no deps), so tradingMode change is the only re-trigger
  useEffect(() => {
    fetchTradingData()
    const interval = setInterval(fetchTradingData, 10000)
    return () => clearInterval(interval)
  }, [fetchTradingData, tradingMode])

  const getDirectionStats = () => {
    if (!aggregation) {
      return {
        direction: 'HOLD',
        conviction: 0,
        consensusScore: 0,
      }
    }

    return {
      direction: aggregation.final_direction || 'HOLD',
      conviction: aggregation.conviction_percent || 0,
      consensusScore: aggregation.consensus_score || 0,
    }
  }

  const directionStats = getDirectionStats()
  // FE-L4: completedAgents is an object, not an array — .length would be undefined
  const activeSignalCount = Object.keys(completedAgents).length
  // Validate that daily_pnl[0] is actually today before showing as "Today" P&L
  const todayStr = new Date().toISOString().slice(0, 10)
  const latestPnlEntry = tradingPnl?.daily_pnl?.[0]
  const todayPnl = (latestPnlEntry?.date === todayStr) ? (latestPnlEntry?.pnl || 0) : 0

  return (
    <div className="min-h-screen bg-surface-0 pt-6 pb-12">
      <div className="max-w-7xl mx-auto px-6">
        {/* Header with Trading Mode Toggle */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-primary-glow mb-1 tracking-tight">God's Eye</h1>
            <p className="text-sm text-onSurfaceDim font-mono">Multi-Agent Market Intelligence</p>
          </div>
          <TradingModeToggle
            mode={tradingMode}
            onModeChange={handleModeChange}
            dhanEnabled={dhanEnabled}
          />
        </div>

        {/* Error display */}
        {error && (
          <div className="mb-6 p-4 bg-bear/10 border border-bear/20 rounded text-bear text-sm">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined">error</span>
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Top Stats Row - 4 columns */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Market Sentiment"
            value={directionStats.direction}
            icon="psychology"
            accent={getDirectionColor(directionStats.direction)}
            trend={true}
            trendValue={directionStats.conviction}
          />
          <StatCard
            label="Consensus Score"
            value={formatPercent(directionStats.consensusScore)}
            icon="verified_user"
            accent="text-primary"
          />
          <StatCard
            label="Active Signals"
            value={activeSignalCount}
            icon="bolt"
            accent="text-neutral-bright"
          />
          <StatCard
            label="P&L Today"
            value={formatINR(todayPnl)}
            icon="account_balance_wallet"
            accent={todayPnl >= 0 ? 'text-bull' : 'text-bear'}
            trend={true}
            trendValue={tradingSummary?.total_return_pct || 0}
          />
        </div>

        {/* Main Grid Layout - 12 cols */}
        <div className="grid grid-cols-12 gap-4 mb-6">
          {/* Left Column - Scenario Panel (3 cols) */}
          <div className="col-span-3">
            <ScenarioPanel result={result} />
          </div>

          {/* Center Column - Agent Pressures + Insights (6 cols) */}
          <div className="col-span-6 space-y-4">
            <PressurePanel result={result} aggregation={aggregation} />
            <InsightsPanel result={result} aggregation={aggregation} />
          </div>

          {/* Right Column - P&L Breakdown + Signal Intel + Accuracy + Feedback (3 cols) */}
          <div className="col-span-3 space-y-4">
            <PnLBreakdown
              summary={tradingSummary}
              pnlData={tradingPnl}
              isLoading={tradesLoading}
            />
            <SignalIntelSection result={result} events={events} isLoading={isLoading} />
            <AccuracyPanel result={result} />
            <FeedbackPanel result={result} onFeedbackSubmit={fetchTradingData} />
          </div>
        </div>

        {/* Bottom Row - Trades Table (7 cols) + Charts (5 cols) */}
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-7">
            <TradesTable
              trades={tradingTrades}
              tradingMode={tradingMode}
              isLoading={tradesLoading}
            />
          </div>
          <div className="col-span-5 space-y-4">
            <DailyPnLChart pnlData={tradingPnl} isLoading={tradesLoading} />
            <EquityCurveChart pnlData={tradingPnl} isLoading={tradesLoading} />
          </div>
        </div>

        {/* Simulation Status Indicator */}
        {isLoading && (
          <div className="fixed bottom-6 right-6 terminal-card p-4 flex items-center gap-3">
            <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
            <div>
              <div className="text-xs font-mono text-primary-glow">Simulation Running</div>
              <div className="text-xs text-onSurfaceDim">
                Round {currentRound} • {Object.keys(completedAgents).length} agents active
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
