import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

export default function PaperTrading() {
  const [trades, setTrades] = useState([])
  const [pnl, setPnl] = useState(null)
  const [openTrades, setOpenTrades] = useState([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)
  const [liveSpot, setLiveSpot] = useState(null)

  // Estimate current option premium from spot move (delta ≈ 0.5 for ATM)
  const estimatePremium = (trade, currentSpot) => {
    if (!currentSpot || !trade.entry_spot || !trade.entry_premium) return null
    const spotDelta = currentSpot - trade.entry_spot
    const direction = trade.option_type === 'CE' ? 1 : -1
    const delta = 0.5  // ATM approximation
    const estimated = trade.entry_premium + (spotDelta * direction * delta)
    return Math.max(estimated, 0) // Premium can't go below 0
  }

  const getUnrealizedPnl = (trade, currentSpot) => {
    const currentPremium = estimatePremium(trade, currentSpot)
    if (currentPremium == null) return null
    const qty = (trade.lots || 1) * (trade.lot_size || 25)
    return (currentPremium - trade.entry_premium) * qty
  }

  const fetchData = async () => {
    try {
      const [tradesData, summaryData, marketData] = await Promise.all([
        apiClient.getPaperTrades({ limit: 50 }),
        apiClient.getPaperSummary().catch(() => null),
        apiClient.getMarketLive().catch(() => null),
      ])
      const allTrades = tradesData.trades || tradesData || []
      setTrades(allTrades)
      if (summaryData) setPnl(summaryData)
      setOpenTrades(allTrades.filter(t => t.status === 'OPEN'))
      if (marketData?.nifty_spot) setLiveSpot(marketData.nifty_spot)
    } catch (err) {
      setFetchError(err.message || 'Failed to load paper trades')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 15000) // Refresh every 15s for live P&L
    return () => clearInterval(interval)
  }, [])

  const dirColor = (dir) => {
    if (!dir) return '#FFC107'
    if (dir.includes('BUY')) return '#00E676'
    if (dir.includes('SELL')) return '#FF1744'
    return '#FFC107'
  }

  const statusColor = (status) => {
    switch (status) {
      case 'OPEN': return '#A89AFF'
      case 'TARGET_HIT': return '#00E676'
      case 'STOPPED': return '#FF1744'
      case 'CLOSED_EOD': return '#FFC107'
      default: return '#928F9F'
    }
  }

  const statusLabel = (status) => {
    switch (status) {
      case 'OPEN': return 'OPEN'
      case 'TARGET_HIT': return 'TARGET'
      case 'STOPPED': return 'SL HIT'
      case 'CLOSED_EOD': return 'EOD'
      default: return status
    }
  }
  const formatINR = (n) => {
    if (n == null) return '--'
    const prefix = n >= 0 ? '+' : ''
    return `${prefix}₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
  }

  if (loading) {
    return (
        <div className="flex items-center justify-center h-[calc(100vh-2.5rem)]">
          <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING PAPER TRADING...</span>
        </div>
    )
  }

  const totalTrades = pnl?.total_trades || 0
  const winRate = pnl?.win_rate_pct || 0
  const realizedPnl = pnl?.total_pnl_inr || 0
  const capital = pnl?.capital || 20000

  // Calculate total unrealized P&L across open positions
  const unrealizedPnl = openTrades.reduce((sum, t) => {
    const pnl = getUnrealizedPnl(t, liveSpot)
    return sum + (pnl || 0)
  }, 0)
  const totalPnl = realizedPnl + unrealizedPnl

  return (
      <div className="p-5 h-[calc(100vh-2.5rem)] overflow-y-auto">
        {fetchError && (
          <div className="terminal-card p-3 border-l-2 border-bear mb-4">
            <p className="text-xs font-mono text-bear">
              {fetchError}
            </p>
          </div>
        )}
        {/* ── P&L Summary Cards ─────────────────────────────────────── */}
        <div className="grid grid-cols-6 gap-3 mb-5">
          <div className="terminal-card p-4 text-center">
            <span className="text-[10px] font-mono text-onSurfaceDim block">CAPITAL</span>
            <span className="text-lg font-bold font-mono text-onSurface">₹{capital.toLocaleString('en-IN')}</span>
          </div>
          <div className="terminal-card p-4 text-center">
            <span className="text-[10px] font-mono text-onSurfaceDim block">NET P&L</span>
            <span className={`text-lg font-bold font-mono ${totalPnl >= 0 ? 'text-bull' : 'text-bear'}`}>
              {formatINR(totalPnl)}
            </span>
            {unrealizedPnl !== 0 && (
              <span className={`text-[9px] font-mono block ${unrealizedPnl >= 0 ? 'text-bull/70' : 'text-bear/70'}`}>
                Unrealized: {formatINR(unrealizedPnl)}
              </span>
            )}
            {liveSpot && (
              <span className="text-[9px] font-mono text-onSurfaceDim block">
                Spot: {liveSpot.toLocaleString('en-IN', { maximumFractionDigits: 1 })}
              </span>
            )}
          </div>
          <div className="terminal-card p-4 text-center">
            <span className="text-[10px] font-mono text-onSurfaceDim block">TRADES</span>
            <span className="text-lg font-bold font-mono text-onSurface">{totalTrades}</span>
            <span className="text-[10px] font-mono text-onSurfaceDim block">
              {pnl?.open_trades || 0} open
            </span>
          </div>
          <div className="terminal-card p-4 text-center">
            <span className="text-[10px] font-mono text-onSurfaceDim block">WIN RATE</span>
            <span className={`text-lg font-bold font-mono ${winRate >= 50 ? 'text-bull' : 'text-bear'}`}>
              {winRate.toFixed(1)}%
            </span>
            <span className="text-[10px] font-mono text-onSurfaceDim block">
              {pnl?.wins || 0}W / {pnl?.losses || 0}L
            </span>
          </div>          <div className="terminal-card p-4 text-center">
            <span className="text-[10px] font-mono text-onSurfaceDim block">MAX DD</span>
            <span className="text-lg font-bold font-mono text-bear">
              {pnl?.max_drawdown_pct ? `-${pnl.max_drawdown_pct}%` : '--'}
            </span>
            <span className="text-[10px] font-mono text-onSurfaceDim block">
              {pnl?.max_drawdown_inr ? `₹${Math.abs(pnl.max_drawdown_inr).toLocaleString('en-IN')}` : ''}
            </span>
          </div>
          <div className="terminal-card p-4 text-center">
            <span className="text-[10px] font-mono text-onSurfaceDim block">PROFIT FACTOR</span>
            <span className={`text-lg font-bold font-mono ${(pnl?.profit_factor || 0) >= 1 ? 'text-bull' : 'text-bear'}`}>
              {pnl?.profit_factor?.toFixed(2) || '--'}
            </span>
            <span className="text-[10px] font-mono text-onSurfaceDim block">
              SL:{pnl?.stopped_count || 0} TGT:{pnl?.target_hit_count || 0} EOD:{pnl?.eod_close_count || 0}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4">
          {/* ── Open Positions ──────────────────────────────────────── */}
          <div className="col-span-4">
            <div className="terminal-card p-4">
              <div className="section-header mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                Open Positions
              </div>
              {openTrades.length > 0 ? openTrades.map(trade => (                <div key={trade.trade_id} className="p-3 bg-surface-2 rounded-lg mb-2">
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className="text-xs font-mono font-bold px-2 py-0.5 rounded"
                      style={{ backgroundColor: `${dirColor(trade.direction)}15`, color: dirColor(trade.direction) }}
                    >
                      {trade.direction} {trade.option_type}
                    </span>
                    <span className="text-[10px] font-mono text-onSurfaceDim">{trade.lots}×{trade.lot_size}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[10px] font-mono">
                    <div>
                      <span className="text-onSurfaceDim">Entry</span>
                      <p className="text-onSurface">₹{trade.entry_premium?.toFixed(1)}</p>
                      <p className="text-onSurfaceDim">@{trade.entry_spot?.toFixed(0)}</p>
                    </div>
                    <div>
                      <span className="text-bear">Stop</span>
                      <p className="text-bear">{trade.stop_nifty?.toFixed(0)}</p>
                    </div>
                    <div>
                      <span className="text-bull">Target</span>
                      <p className="text-bull">{trade.target_nifty?.toFixed(0)}</p>
                    </div>
                  </div>
                  {/* Live P&L estimation */}
                  {liveSpot && (() => {
                    const curPrem = estimatePremium(trade, liveSpot)
                    const uPnl = getUnrealizedPnl(trade, liveSpot)
                    return curPrem != null ? (
                      <div className="mt-2 pt-2 border-t border-[rgba(255,255,255,0.06)] flex items-center justify-between text-[10px] font-mono">
                        <div>
                          <span className="text-onSurfaceDim">Current: </span>
                          <span className="text-primary font-bold">₹{curPrem.toFixed(1)}</span>
                          <span className="text-onSurfaceDim ml-1">@{liveSpot.toFixed(0)}</span>
                        </div>
                        <span className={`font-bold ${uPnl >= 0 ? 'text-bull' : 'text-bear'}`}>
                          {formatINR(uPnl)}
                        </span>
                      </div>
                    ) : null
                  })()}
                  <div className="mt-2 text-[9px] font-mono text-onSurfaceDim">
                    Cost: ₹{trade.entry_cost?.toLocaleString('en-IN')} · Conv: {trade.conviction?.toFixed(0)}%
                  </div>
                </div>              )) : (
                <div className="flex flex-col items-center justify-center py-8 gap-2 text-onSurfaceDim">
                  <span className="text-xs font-mono">NO OPEN POSITIONS</span>
                  <span className="text-[10px] font-mono">Trades open on BUY/SELL signals</span>
                </div>
              )}
            </div>

            {/* Daily P&L */}
            {pnl?.daily_pnl?.length > 0 && (
              <div className="terminal-card p-4 mt-4">
                <div className="section-header mb-3">Daily P&L</div>
                <div className="space-y-1.5">
                  {pnl.daily_pnl.slice(-10).reverse().map((day) => (
                    <div key={day.date} className="flex items-center justify-between text-[10px] font-mono">
                      <span className="text-onSurfaceDim">{day.date}</span>
                      <span className="text-onSurfaceDim">{day.trades}t · {day.wins}w</span>
                      <span className={day.pnl >= 0 ? 'text-bull' : 'text-bear'}>
                        {formatINR(day.pnl)}
                      </span>
                      <span className={day.cumulative >= 0 ? 'text-bull/60' : 'text-bear/60'}>
                        {formatINR(day.cumulative)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          {/* ── Trade History Table ─────────────────────────────────── */}
          <div className="col-span-8 terminal-card p-4">
            <div className="section-header mb-3">Trade History</div>
            {trades.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-[10px] font-mono">
                  <thead>
                    <tr className="text-onSurfaceDim border-b border-[rgba(255,255,255,0.06)]">
                      <th className="text-left py-2 px-2">TIME</th>
                      <th className="text-left py-2 px-2">SIGNAL</th>
                      <th className="text-left py-2 px-2">TYPE</th>
                      <th className="text-right py-2 px-2">ENTRY</th>
                      <th className="text-right py-2 px-2">EXIT</th>
                      <th className="text-right py-2 px-2">NIFTY</th>
                      <th className="text-center py-2 px-2">STATUS</th>
                      <th className="text-right py-2 px-2">P&L</th>
                      <th className="text-right py-2 px-2">RETURN</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((trade) => {
                      const ts = trade.timestamp ? new Date(trade.timestamp) : null
                      const dateStr = ts
                        ? ts.toLocaleString('en-IN', {
                            month: 'short', day: 'numeric',
                            hour: '2-digit', minute: '2-digit',
                            timeZone: 'Asia/Kolkata',
                          })
                        : '--'
                      return (
                        <tr
                          key={trade.trade_id}
                          className="border-b border-[rgba(255,255,255,0.03)] hover:bg-surface-2/50"
                        >
                          <td className="py-2 px-2 text-onSurfaceDim">{dateStr}</td>
                          <td className="py-2 px-2">
                            <span style={{ color: dirColor(trade.direction) }}>
                              {trade.direction}
                            </span>
                            <span className="text-onSurfaceDim ml-1">{trade.conviction?.toFixed(0)}%</span>
                          </td>
                          <td className="py-2 px-2 text-onSurface">
                            {trade.option_type} {trade.lots}×{trade.lot_size}
                          </td>
                          <td className="py-2 px-2 text-right text-onSurface">
                            ₹{trade.entry_premium?.toFixed(1)}
                          </td>
                          <td className="py-2 px-2 text-right text-onSurface">
                            {trade.exit_premium != null ? `₹${trade.exit_premium.toFixed(1)}` : '--'}
                          </td>
                          <td className="py-2 px-2 text-right text-onSurfaceDim">
                            {trade.entry_spot?.toFixed(0)}
                            {trade.exit_spot != null && (
                              <span className="text-onSurfaceDim"> → {trade.exit_spot.toFixed(0)}</span>
                            )}
                          </td>
                          <td className="py-2 px-2 text-center">
                            <span                              className="px-1.5 py-0.5 rounded text-[9px] font-bold"
                              style={{
                                backgroundColor: `${statusColor(trade.status)}15`,
                                color: statusColor(trade.status),
                              }}
                            >
                              {statusLabel(trade.status)}
                            </span>
                          </td>
                          <td className={`py-2 px-2 text-right font-bold ${
                            trade.net_pnl != null
                              ? trade.net_pnl >= 0 ? 'text-bull' : 'text-bear'
                              : 'text-onSurfaceDim'
                          }`}>
                            {trade.net_pnl != null ? formatINR(trade.net_pnl) : '--'}
                          </td>
                          <td className={`py-2 px-2 text-right ${
                            trade.return_pct != null
                              ? trade.return_pct >= 0 ? 'text-bull' : 'text-bear'
                              : 'text-onSurfaceDim'
                          }`}>
                            {trade.return_pct != null ? `${trade.return_pct > 0 ? '+' : ''}${trade.return_pct}%` : '--'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>            ) : (
              <div className="flex flex-col items-center justify-center py-12 gap-2 text-onSurfaceDim">
                <span className="text-xs font-mono">NO TRADES YET</span>
                <span className="text-[10px] font-mono text-center max-w-sm">
                  Trades are automatically placed when the scheduler generates BUY or SELL signals
                  with conviction above 55%. HOLD signals are skipped.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
  )
}
