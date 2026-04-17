import { useState } from 'react'
import { apiClient } from '../api/client'
import ModeCompare from '../components/ModeCompare'

export default function Performance() {
  const [instrument, setInstrument] = useState('NIFTY')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [quantResult, setQuantResult] = useState(null)
  const [hybridResult, setHybridResult] = useState(null)
  const [quantLoading, setQuantLoading] = useState(false)
  const [hybridLoading, setHybridLoading] = useState(false)
  const [quantError, setQuantError] = useState(null)
  const [hybridError, setHybridError] = useState(null)

  const handleRun = async (e) => {
    e.preventDefault()
    if (!fromDate || !toDate) return
    setQuantLoading(true)
    setHybridLoading(true)
    setQuantError(null)
    setHybridError(null)
    setQuantResult(null)
    setHybridResult(null)

    const [quantSettled, hybridSettled] = await Promise.allSettled([
      apiClient.runQuantBacktest({ instrument, from_date: fromDate, to_date: toDate }),
      apiClient.runHybridBacktest({ instrument, from_date: fromDate, to_date: toDate }),
    ])

    setQuantLoading(false)
    setHybridLoading(false)

    if (quantSettled.status === 'fulfilled') setQuantResult(quantSettled.value)
    else setQuantError(quantSettled.reason?.message || 'Rules-only backtest failed')

    if (hybridSettled.status === 'fulfilled') setHybridResult(hybridSettled.value)
    else setHybridError(hybridSettled.reason?.message || 'Hybrid backtest failed')
  }

  const isRunning = quantLoading || hybridLoading
  const hasAnyResult = quantResult || hybridResult
  const hasNeitherResult = !hasAnyResult && !isRunning && !quantError && !hybridError

  return (
      <div className="p-5 h-[calc(100vh-2.5rem)] overflow-y-auto">
        {/* Page header */}
        <div className="mb-5">
          <h1 className="text-xl font-bold text-onSurface">Performance Comparison</h1>
          <p className="text-[10px] font-mono text-onSurfaceDim mt-0.5">
            Rules-Only vs Hybrid — same date range, side by side
          </p>
        </div>

        {/* Control bar */}
        <form onSubmit={handleRun} className="terminal-card p-4 mb-3">
          <div className="flex flex-wrap items-end gap-3">
            {/* Instrument selector */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">Instrument</label>
              <div className="flex gap-2">
                {['NIFTY', 'BANKNIFTY'].map((inst) => (
                  <button
                    key={inst}
                    type="button"
                    onClick={() => setInstrument(inst)}
                    className={`px-3 py-1.5 rounded-lg text-[10px] font-mono font-bold border transition-all ${
                      instrument === inst
                        ? 'bg-primary/20 text-primary border-primary/40'
                        : 'bg-surface-2 text-onSurfaceDim border-[rgba(255,255,255,0.08)] hover:border-primary/30'
                    }`}
                  >
                    {inst}
                  </button>
                ))}
              </div>
            </div>

            {/* From date */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">From</label>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                required
                className="text-onSurface bg-surface-2 border border-[rgba(255,255,255,0.08)] rounded px-2 py-1 text-xs font-mono focus:outline-none focus:border-primary/50"
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
                className="text-onSurface bg-surface-2 border border-[rgba(255,255,255,0.08)] rounded px-2 py-1 text-xs font-mono focus:outline-none focus:border-primary/50"
              />
            </div>

            {/* Run button */}
            <button
              type="submit"
              disabled={isRunning || !fromDate || !toDate}
              className="px-4 py-2 rounded-lg text-xs font-mono font-bold bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {isRunning ? 'RUNNING...' : 'RUN COMPARISON'}
            </button>
          </div>
        </form>

        {/* Hybrid timeout info banner */}
        <p className="text-[10px] font-mono text-onSurfaceDim mb-5">
          Note: Hybrid mode makes LLM calls per day — 1-month range may take up to 5 minutes.
        </p>

        {/* Status row — loading indicators per mode */}
        {(quantLoading || hybridLoading) && (
          <div className="flex flex-wrap gap-3 mb-4">
            {quantLoading && (
              <div className="terminal-card px-3 py-1.5">
                <span className="text-[10px] font-mono text-primary animate-pulse">RULES ONLY: RUNNING...</span>
              </div>
            )}
            {hybridLoading && (
              <div className="terminal-card px-3 py-1.5">
                <span className="text-[10px] font-mono text-[#a78bfa] animate-pulse">HYBRID: RUNNING...</span>
              </div>
            )}
          </div>
        )}

        {/* Error states — independent per mode */}
        {(quantError || hybridError) && (
          <div className="flex flex-col gap-2 mb-4">
            {quantError && (
              <div className="terminal-card border-l-2 border-bear p-3">
                <p className="text-[10px] font-mono text-bear">Rules-Only error: {quantError}</p>
              </div>
            )}
            {hybridError && (
              <div className="terminal-card border-l-2 border-bear p-3">
                <p className="text-[10px] font-mono text-bear">Hybrid error: {hybridError}</p>
              </div>
            )}
          </div>
        )}

        {/* Empty state */}
        {hasNeitherResult && (
          <div className="terminal-card p-8 flex flex-col items-center gap-2">
            <p className="text-xs font-mono text-onSurfaceDim">Set date range and run comparison</p>
            <p className="text-[10px] font-mono text-onSurfaceDim opacity-60">
              Both modes will run concurrently for the selected period
            </p>
          </div>
        )}

        {/* Results area */}
        {hasAnyResult && (
          <div className="space-y-4">
            <ModeCompare quantResult={quantResult} hybridResult={hybridResult} />

            {/* Timing note — shown when both results are present */}
            {quantResult && hybridResult && (
              <p className="text-[10px] font-mono text-onSurfaceDim">
                Rules-only: {quantResult.elapsed_seconds?.toFixed(1)}s | Hybrid: {hybridResult.elapsed_seconds?.toFixed(1)}s
              </p>
            )}
          </div>
        )}
      </div>
  )
}
