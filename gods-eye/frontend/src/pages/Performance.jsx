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
      <div className="p-4 h-full overflow-y-auto flex flex-col">
        <div className="mb-3 flex-shrink-0">
          <h1 className="text-xl font-bold text-onSurface">Performance Comparison</h1>
          <p className="text-[10px] font-mono text-onSurfaceDim mt-0.5">
            Rules-Only vs Hybrid — same date range, side by side
          </p>
        </div>

        <form onSubmit={handleRun} className="terminal-card p-4 mb-3 flex-shrink-0">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">Instrument</label>
              <div className="flex gap-1.5">
                {['NIFTY', 'BANKNIFTY'].map((inst) => (
                  <button
                    key={inst}
                    type="button"
                    onClick={() => setInstrument(inst)}
                    className={`px-3 py-1.5 rounded-pill text-[10px] font-mono font-bold border transition-all ${
                      instrument === inst
                        ? 'bg-primary/10 text-primary border-primary/30'
                        : 'bg-surface-2 text-onSurfaceDim border-gray-200 hover:border-primary/30 hover:text-onSurface'
                    }`}
                  >
                    {inst}
                  </button>
                ))}
              </div>
            </div>

            <div className="hidden sm:block w-px h-8 bg-gray-200" />

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">From</label>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                required
                className="text-onSurface bg-surface-1 border border-gray-200 rounded-xl px-3 py-1.5 text-xs font-mono focus:outline-none focus:border-primary"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">To</label>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                required
                className="text-onSurface bg-surface-1 border border-gray-200 rounded-xl px-3 py-1.5 text-xs font-mono focus:outline-none focus:border-primary"
              />
            </div>

            <div className="hidden sm:block w-px h-8 bg-gray-200" />

            <button
              type="submit"
              disabled={isRunning || !fromDate || !toDate}
              className="px-5 py-1.5 rounded-pill text-xs font-mono font-bold bg-primary text-white hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-300"
            >
              {isRunning ? 'RUNNING...' : 'RUN COMPARISON'}
            </button>
          </div>
        </form>

        <p className="text-[10px] font-mono text-onSurfaceDim mb-4 flex-shrink-0">
          Note: Hybrid mode makes LLM calls per day — 1-month range may take up to 5 minutes.
        </p>

        {(quantLoading || hybridLoading) && (
          <div className="flex flex-wrap gap-3 mb-4 flex-shrink-0">
            {quantLoading && (
              <div className="terminal-card px-3 py-1.5">
                <span className="text-[10px] font-mono text-primary animate-pulse">RULES ONLY: RUNNING...</span>
              </div>
            )}
            {hybridLoading && (
              <div className="terminal-card px-3 py-1.5">
                <span className="text-[10px] font-mono text-purple-600 animate-pulse">HYBRID: RUNNING...</span>
              </div>
            )}
          </div>
        )}

        {(quantError || hybridError) && (
          <div className="flex flex-col gap-2 mb-4 flex-shrink-0">
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

        {hasNeitherResult && (
          <div className="terminal-card p-8 flex flex-col items-center gap-2 flex-1 justify-center">
            <p className="text-xs font-mono text-onSurfaceDim">Set date range and run comparison</p>
            <p className="text-[10px] font-mono text-onSurfaceDim opacity-60">
              Both modes will run concurrently for the selected period
            </p>
          </div>
        )}

        {hasAnyResult && (
          <div className="space-y-4 flex-1 min-h-0">
            <ModeCompare quantResult={quantResult} hybridResult={hybridResult} />
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
