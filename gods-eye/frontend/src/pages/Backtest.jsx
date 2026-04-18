import { useState } from 'react'
import { apiClient } from '../api/client'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { AGENT_COLORS, AGENTS } from '../constants/agents'

export default function Backtest() {
  const [instrument, setInstrument] = useState('NIFTY')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [mockMode, setMockMode] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [results, setResults] = useState(null)
  const [selectedDay, setSelectedDay] = useState(null)

  const handleRun = async (e) => {
    e.preventDefault()
    if (!startDate || !endDate) return
    setLoading(true)
    setError(null)
    setResults(null)
    try {
      const data = await apiClient.runBacktest({
        instrument,
        start_date: startDate,
        end_date: endDate,
        mock_mode: mockMode,
      })
      setResults(data)
    } catch (err) {
      setError(err.message || 'Backtest failed')
    } finally {
      setLoading(false)
    }
  }

  const getStatTrend = (current, previous) => {
    if (!previous) return null
    return (current - previous) / Math.abs(previous) * 100
  }

  const formatPercent = (value) => {
    if (!value) return '0%'
    return `${(value * 100).toFixed(2)}%`
  }

  const formatCurrency = (value) => {
    if (!value) return '₹0'
    return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
  }

  // Light-theme signal colors
  const sigColor = (dir) => dir === 'BUY' || dir === 'UP' ? '#059669' : dir === 'SELL' || dir === 'DN' ? '#DC2626' : '#D97706'

  return (
    <>
      <div className="p-4 h-full overflow-hidden flex flex-col">
        {/* Page header */}
        <div className="mb-3 flex-shrink-0">
          <h1 className="text-xl font-bold text-onSurface">Backtest Engine</h1>
          <p className="text-[10px] font-mono text-onSurfaceDim mt-0.5">
            Validate agent performance against historical market data
          </p>
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-12 gap-4 flex-1 min-h-0">
          {/* Left column: Controls + Stats */}
          <div className="col-span-4 flex flex-col gap-3 overflow-y-auto pr-1">
            <form onSubmit={handleRun} className="terminal-card p-4 flex-shrink-0">
              <div className="flex flex-col gap-3 mb-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">Instrument</label>
                  <select
                    value={instrument}
                    onChange={(e) => setInstrument(e.target.value)}
                    className="bg-surface-1 text-onSurface border border-gray-200 rounded-xl px-3 py-1.5 text-xs font-mono focus:outline-none focus:border-primary"
                  >
                    <option value="NIFTY">NIFTY</option>
                    <option value="BANKNIFTY">BANKNIFTY</option>
                    <option value="FINNIFTY">FINNIFTY</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    required
                    className="bg-surface-1 text-onSurface border border-gray-200 rounded-xl px-3 py-1.5 text-xs font-mono focus:outline-none focus:border-primary"
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    required
                    className="bg-surface-1 text-onSurface border border-gray-200 rounded-xl px-3 py-1.5 text-xs font-mono focus:outline-none focus:border-primary"
                  />
                </div>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={mockMode}
                    onChange={(e) => setMockMode(e.target.checked)}
                    className="w-4 h-4 rounded accent-primary"
                  />
                  <span className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">Mock Data</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={loading || !startDate || !endDate}
                className="w-full px-4 py-2 rounded-xl text-xs font-mono font-bold bg-primary text-white hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-300"
              >
                {loading ? 'RUNNING BACKTEST...' : 'RUN BACKTEST'}
              </button>
            </form>

            <p className="text-[10px] font-mono text-onSurfaceDim flex-shrink-0">
              Backtest may take 1-10 minutes depending on date range. Results include day-by-day performance and per-agent accuracy metrics.
            </p>

            {!loading && results && (
              <div className="flex flex-col gap-3">
                <StatCard label="Total Return" value={formatPercent(results.total_return)} unit="" trend={getStatTrend(results.total_return, results.prev_total_return)} accentColor="#059669" />
                <StatCard label="Win Rate" value={formatPercent(results.win_rate)} unit="" trend={getStatTrend(results.win_rate, results.prev_win_rate)} accentColor="#CC152B" />
                <StatCard label="Sharpe Ratio" value={(results.sharpe_ratio || 0).toFixed(2)} unit="" trend={getStatTrend(results.sharpe_ratio, results.prev_sharpe_ratio)} accentColor="#2563EB" />
                <StatCard label="Max Drawdown" value={formatPercent(Math.abs(results.max_drawdown))} unit="" trend={getStatTrend(results.max_drawdown, results.prev_max_drawdown)} accentColor="#DC2626" />
              </div>
            )}

            {!loading && results && results.agent_accuracy && Object.keys(results.agent_accuracy).length > 0 && (
              <div className="terminal-card p-4 flex-shrink-0">
                <h3 className="text-xs font-mono font-bold text-onSurface mb-3 uppercase tracking-wider">Per-Agent Accuracy</h3>
                <div className="flex flex-col gap-2">
                  {AGENTS.map((agent) => {
                    const acc = results.agent_accuracy[agent.id]
                    return (
                      <div
                        key={agent.id}
                        className="terminal-card p-3 border-l-2"
                        style={{ borderColor: agent.color }}
                      >
                        <p className="text-[10px] font-mono font-bold text-onSurface mb-1">{agent.shortLabel}</p>
                        <p className="text-lg font-mono font-bold" style={{ color: agent.color }}>
                          {acc ? formatPercent(acc) : '-'}
                        </p>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Right column: Charts + Table */}
          <div className="col-span-8 flex flex-col gap-3 overflow-y-auto pl-1">
            {error && (
              <div className="terminal-card border-l-2 border-bear p-3 flex-shrink-0">
                <p className="text-[10px] font-mono text-bear">Error: {error}</p>
              </div>
            )}

            {loading && (
              <div className="terminal-card p-6 flex justify-center flex-shrink-0">
                <span className="text-xs font-mono text-primary animate-pulse">BACKTEST IN PROGRESS...</span>
              </div>
            )}

            {!loading && !results && !error && (
              <div className="terminal-card p-8 flex flex-col items-center gap-2 flex-1 justify-center">
                <p className="text-xs font-mono text-onSurfaceDim">Select date range and run backtest</p>
                <p className="text-[10px] font-mono text-onSurfaceDim opacity-60">
                  Agent predictions vs actual market movement will be displayed here
                </p>
              </div>
            )}

            {!loading && results && (
              <>
                {results.equity_curve && results.equity_curve.length > 0 && (
                  <div className="terminal-card p-4 flex-shrink-0">
                    <h3 className="text-xs font-mono font-bold text-onSurface mb-3 uppercase tracking-wider">Equity Curve</h3>
                    <ResponsiveContainer width="100%" height={280}>
                      <LineChart data={results.equity_curve}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                        <XAxis dataKey="date" stroke="#9CA3AF" tick={{ fontSize: 10, fill: '#6B7280' }} />
                        <YAxis stroke="#9CA3AF" tick={{ fontSize: 10, fill: '#6B7280' }} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#fff',
                            border: '1px solid #E5E7EB',
                            borderRadius: '12px',
                            boxShadow: '0 7px 29px rgba(0,0,0,0.08)',
                          }}
                          labelStyle={{ color: '#1A1A1A' }}
                          formatter={(value) => `₹${value.toLocaleString()}`}
                        />
                        <Line type="monotone" dataKey="equity" stroke="#059669" strokeWidth={2} dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {results.day_results && results.day_results.length > 0 && (
                  <div className="terminal-card overflow-x-auto flex-shrink-0">
                    <h3 className="text-xs font-mono font-bold text-onSurface px-4 pt-4 uppercase tracking-wider">
                      Day-by-Day Results
                    </h3>
                    <table className="w-full text-[10px] font-mono">
                      <thead>
                        <tr className="border-b border-gray-100">
                          <th className="px-4 py-2 text-left text-onSurfaceMuted uppercase tracking-wider font-bold">Date</th>
                          <th className="px-4 py-2 text-right text-onSurfaceMuted uppercase tracking-wider font-bold">Open</th>
                          <th className="px-4 py-2 text-right text-onSurfaceMuted uppercase tracking-wider font-bold">Close</th>
                          <th className="px-4 py-2 text-right text-onSurfaceMuted uppercase tracking-wider font-bold">Return</th>
                          <th className="px-4 py-2 text-center text-onSurfaceMuted uppercase tracking-wider font-bold">Prediction</th>
                          <th className="px-4 py-2 text-center text-onSurfaceMuted uppercase tracking-wider font-bold">Actual</th>
                          <th className="px-4 py-2 text-center text-onSurfaceMuted uppercase tracking-wider font-bold">Match</th>
                          <th className="px-4 py-2 text-center text-onSurfaceMuted uppercase tracking-wider font-bold">Detail</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.day_results.map((day) => {
                          const isMatch = (day.prediction === 'BUY' && day.actual_direction === 'UP') ||
                            (day.prediction === 'SELL' && day.actual_direction === 'DN') ||
                            (day.prediction === 'HOLD' && day.actual_direction === 'FLAT')
                          return (
                            <tr key={day.date} className="border-b border-gray-50 hover:bg-surface-1">
                              <td className="px-4 py-3 text-onSurface">{day.date}</td>
                              <td className="px-4 py-3 text-right text-onSurface tabular-nums">
                                {day.open_price ? day.open_price.toFixed(0) : '-'}
                              </td>
                              <td className="px-4 py-3 text-right text-onSurface tabular-nums">
                                {day.close_price ? day.close_price.toFixed(0) : '-'}
                              </td>
                              <td className="px-4 py-3 text-right tabular-nums" style={{ color: sigColor(day.daily_return > 0 ? 'BUY' : 'SELL') }}>
                                {formatPercent(day.daily_return)}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span
                                  className="px-2 py-1 rounded-pill text-[9px] font-bold"
                                  style={{
                                    backgroundColor: `${sigColor(day.prediction)}08`,
                                    color: sigColor(day.prediction),
                                    border: `1px solid ${sigColor(day.prediction)}20`,
                                  }}
                                >
                                  {day.prediction || '-'}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span
                                  className="px-2 py-1 rounded-pill text-[9px] font-bold"
                                  style={{
                                    backgroundColor: `${sigColor(day.actual_direction)}08`,
                                    color: sigColor(day.actual_direction),
                                    border: `1px solid ${sigColor(day.actual_direction)}20`,
                                  }}
                                >
                                  {day.actual_direction || '-'}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span style={{ color: isMatch ? '#059669' : '#DC2626' }} className="font-bold">
                                  {isMatch ? '✓' : '✗'}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <button
                                  onClick={() => setSelectedDay(day)}
                                  className="text-[9px] font-bold px-2.5 py-1 rounded-pill bg-primary/5 text-primary hover:bg-primary/10 border border-primary/15 transition-all"
                                >
                                  VIEW
                                </button>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Day detail modal */}
        {selectedDay && (
          <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-2xl border border-gray-200 shadow-elevated p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <h2 className="text-lg font-bold text-onSurface mb-4 font-mono uppercase">Day Detail: {selectedDay.date}</h2>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <p className="text-[10px] font-mono text-onSurfaceMuted uppercase tracking-wider mb-1">Open Price</p>
                  <p className="text-xl font-mono font-bold text-onSurface">{selectedDay.open_price?.toFixed(0) || '-'}</p>
                </div>
                <div>
                  <p className="text-[10px] font-mono text-onSurfaceMuted uppercase tracking-wider mb-1">Close Price</p>
                  <p className="text-xl font-mono font-bold text-onSurface">{selectedDay.close_price?.toFixed(0) || '-'}</p>
                </div>
                <div>
                  <p className="text-[10px] font-mono text-onSurfaceMuted uppercase tracking-wider mb-1">Daily Return</p>
                  <p className="text-xl font-mono font-bold" style={{ color: sigColor(selectedDay.daily_return > 0 ? 'BUY' : 'SELL') }}>
                    {formatPercent(selectedDay.daily_return)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-mono text-onSurfaceMuted uppercase tracking-wider mb-1">Prediction</p>
                  <p className="text-lg font-mono font-bold text-primary">{selectedDay.prediction || '-'}</p>
                </div>
              </div>

              {selectedDay.agent_contributions && (
                <div>
                  <p className="text-[10px] font-mono text-onSurfaceMuted uppercase tracking-wider mb-3">Agent Contributions</p>
                  <div className="space-y-2">
                    {Object.entries(selectedDay.agent_contributions).map(([agentId, contribution]) => {
                      const agent = AGENTS.find((a) => a.id === agentId)
                      return (
                        <div key={agentId} className="flex items-center justify-between">
                          <span className="text-[10px] font-mono text-onSurface">{agent?.shortLabel || agentId}</span>
                          <div className="flex items-center gap-2 flex-1 mx-3">
                            <div className="flex-1 h-1 bg-surface-3 rounded overflow-hidden">
                              <div
                                className="h-full"
                                style={{
                                  width: `${Math.abs(contribution) * 100}%`,
                                  backgroundColor: contribution > 0 ? agent?.color : '#DC2626',
                                }}
                              />
                            </div>
                          </div>
                          <span className="text-[10px] font-mono text-onSurface tabular-nums w-12 text-right">
                            {formatPercent(Math.abs(contribution))}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              <button
                onClick={() => setSelectedDay(null)}
                className="mt-6 w-full btn-secondary font-mono text-xs"
              >
                CLOSE
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

function StatCard({ label, value, unit, trend, accentColor }) {
  return (
    <div className="terminal-card p-4 flex flex-col">
      <span className="font-mono text-xs uppercase tracking-widest text-onSurfaceMuted mb-3">{label}</span>
      <div className="flex items-baseline gap-1 mb-2">
        <span className="font-mono font-bold text-3xl tabular-nums" style={{ color: accentColor }}>
          {value}
        </span>
        <span className="text-onSurfaceMuted font-mono text-sm">{unit}</span>
      </div>
      {trend && (
        <div className="flex items-center gap-1">
          {trend > 0 ? (
            <>
              <span className="text-bull text-sm">▲</span>
              <span className="text-xs text-bull font-mono">+{Math.abs(trend).toFixed(1)}%</span>
            </>
          ) : (
            <>
              <span className="text-bear text-sm">▼</span>
              <span className="text-xs text-bear font-mono">-{Math.abs(trend).toFixed(1)}%</span>
            </>
          )}
        </div>
      )}
    </div>
  )
}
