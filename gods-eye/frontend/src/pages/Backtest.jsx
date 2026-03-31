import { useState } from 'react'
import Layout from '../components/Layout'
import { apiClient } from '../api/client'

export default function Backtest() {
  // Form state
  const [instrument, setInstrument] = useState('NIFTY')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [mockMode, setMockMode] = useState(true)

  // Async state
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)   // BacktestRunResponse shape
  const [error, setError] = useState(null)

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

        {/* Results area — child panels injected by Plans 02 and 03 */}
        {result && (
          <div className="space-y-5">
            {/* Plans 02 and 03 will add BacktestSummary, StatsPanel, AgentAccuracyTable, EquityCurve, DayDetailModal here */}
            <div className="terminal-card p-4">
              <p className="text-[10px] font-mono text-onSurfaceDim">
                Run complete — {result.summary.day_count} days processed
              </p>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
