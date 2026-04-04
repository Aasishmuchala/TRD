import { useState } from 'react'
import Layout from '../components/Layout'
import { apiClient } from '../api/client'
import BacktestSummary from '../components/BacktestSummary'
import StatsPanel from '../components/StatsPanel'
import AgentAccuracyTable from '../components/AgentAccuracyTable'
import EquityCurve from '../components/EquityCurve'
import DayDetailModal from '../components/DayDetailModal'
import RegimeAccuracyChart from '../components/RegimeAccuracyChart'

export default function Backtest() {
  // Form state
  const [instrument, setInstrument] = useState('NIFTY')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [mockMode, setMockMode] = useState(true)

  // Async state
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [selectedDay, setSelectedDay] = useState(null)

  const handleRun = async (e) => {
    e.preventDefault()
    if (!fromDate || !toDate) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await apiClient.runBacktest({
        instrument,
        from_date: fromDate,
        to_date: toDate,
        mock_mode: mockMode,
      })
      setResult(data)
    } catch (err) {
      setError(err.message || 'Backtest failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="p-5 h-[calc(100vh-2.5rem)] overflow-y-auto">
        {/* Page header */}
        <div className="mb-5">
          <h1 className="text-xl font-bold text-onSurface">Backtest</h1>
          <p className="text-[10px] font-mono text-onSurfaceDim mt-0.5">
            Replay historical market days through the agent simulation
          </p>
        </div>

        {/* Run form */}
        <form onSubmit={handleRun} className="terminal-card p-4 mb-5">
          <div className="flex flex-wrap items-end gap-3">
            {/* Instrument */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">Instrument</label>
              <select
                value={instrument}
                onChange={(e) => setInstrument(e.target.value)}
                className="bg-surface-2 border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs font-mono text-onSurface focus:outline-none focus:border-primary/50"
              >
                <option value="NIFTY">NIFTY</option>
                <option value="BANKNIFTY">BANKNIFTY</option>
              </select>
            </div>

            {/* From date */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">From</label>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                required
                className="bg-surface-2 border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs font-mono text-onSurface focus:outline-none focus:border-primary/50"
              />
            </div>

            {/* To date */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">To</label>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                required
                className="bg-surface-2 border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs font-mono text-onSurface focus:outline-none focus:border-primary/50"
              />
            </div>

            {/* Mock mode toggle */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">Mode</label>
              <button
                type="button"
                onClick={() => setMockMode((m) => !m)}
                className={`px-3 py-2 rounded-lg text-[10px] font-mono font-bold border transition-all ${
                  mockMode
                    ? 'bg-neutral/10 text-neutral border-neutral/30'
                    : 'bg-primary/10 text-primary border-primary/30'
                }`}
              >
                {mockMode ? 'MOCK' : 'LIVE LLM'}
              </button>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !fromDate || !toDate}
              className="px-4 py-2 rounded-lg text-xs font-mono font-bold bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {loading ? 'RUNNING...' : 'RUN BACKTEST'}
            </button>
          </div>
        </form>

        {/* Progress indicator */}
        {loading && (
          <div className="terminal-card p-8 mb-5 flex flex-col items-center gap-3">
            <span className="text-xs font-mono text-primary animate-pulse">RUNNING BACKTEST...</span>
            <span className="text-[10px] font-mono text-onSurfaceDim">
              Replaying each trading day through the agent simulation. This may take a moment.
            </span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="terminal-card border-l-2 border-bear p-4 mb-5">
            <p className="text-xs font-mono text-bear font-bold mb-1">BACKTEST FAILED</p>
            <p className="text-[11px] text-onSurfaceMuted">{error}</p>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-5">
            {/* Summary + Stats */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <BacktestSummary summary={result.summary} mockMode={mockMode} />
              <StatsPanel days={result.days || []} />
            </div>

            {/* Agent Accuracy Table */}
            <AgentAccuracyTable perAgentAccuracy={result.summary?.per_agent_accuracy || {}} />

            {/* Phase 3: Regime Accuracy Chart */}
            <RegimeAccuracyChart regimeAccuracy={result.summary?.regime_accuracy} />

            {/* Equity Curve */}
            <EquityCurve days={result.days || []} onDayClick={(day) => setSelectedDay(day)} />

            {/* Day-by-Day Results Table */}
            {result.days && result.days.length > 0 && (
              <div className="terminal-card p-4">
                <div className="section-header mb-3">Day-by-Day Results</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[10px] font-mono">
                    <thead>
                      <tr className="text-onSurfaceDim border-b border-[rgba(255,255,255,0.06)]">
                        <th className="text-left py-2 pr-3">Date</th>
                        <th className="text-left py-2 pr-3">Predicted</th>
                        <th className="text-right py-2 pr-3">Conviction</th>
                        <th className="text-right py-2 pr-3">Actual Move</th>
                        <th className="text-center py-2 pr-3">Correct</th>
                        <th className="text-right py-2">P&L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.days.map((day) => (
                        <tr
                          key={day.date}
                          onClick={() => setSelectedDay(day)}
                          className="border-b border-[rgba(255,255,255,0.03)] cursor-pointer hover:bg-surface-2 transition-colors"
                        >
                          <td className="py-2 pr-3 text-onSurfaceMuted">{day.date}</td>
                          <td className={`py-2 pr-3 font-bold ${
                            day.predicted_direction?.includes('BUY') ? 'text-bull' :
                            day.predicted_direction?.includes('SELL') ? 'text-bear' : 'text-neutral-bright'
                          }`}>{day.predicted_direction}</td>
                          <td className="py-2 pr-3 text-right text-onSurfaceMuted">{day.predicted_conviction?.toFixed(0)}%</td>
                          <td className={`py-2 pr-3 text-right font-bold ${
                            day.actual_move_pct > 0.1 ? 'text-bull' :
                            day.actual_move_pct < -0.1 ? 'text-bear' : 'text-onSurfaceDim'
                          }`}>{day.actual_move_pct?.toFixed(2)}%</td>
                          <td className="py-2 pr-3 text-center">
                            {day.is_correct === true ? '✓' : day.is_correct === false ? '✗' : '—'}
                          </td>
                          <td className={`py-2 text-right font-bold ${
                            day.pnl_points > 0 ? 'text-bull' : day.pnl_points < 0 ? 'text-bear' : 'text-onSurfaceDim'
                          }`}>{day.pnl_points?.toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Day Detail Modal */}
        <DayDetailModal day={selectedDay} onClose={() => setSelectedDay(null)} />
      </div>
    </Layout>
  )
}
