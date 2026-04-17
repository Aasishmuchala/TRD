import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../api/client'

const dirColor = (dir) => {
  if (!dir) return '#FFC107'
  if (dir.includes('BUY')) return '#00E676'
  if (dir.includes('SELL')) return '#FF1744'
  return '#FFC107'
}

const dirLabel = (dir) => {
  if (!dir) return 'NEUTRAL'
  if (dir.includes('STRONG_BUY')) return 'STRONG BUY'
  if (dir.includes('BUY')) return 'BULLISH'
  if (dir.includes('STRONG_SELL')) return 'STRONG SELL'
  if (dir.includes('SELL')) return 'BEARISH'
  return 'NEUTRAL'
}

export default function SimulationHistory() {
  const [timeFilter, setTimeFilter] = useState('30D')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [recordingId, setRecordingId] = useState(null)
  const [toast, setToast] = useState(null)

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    try {
      const limitMap = { '7D': 10, '30D': 20, '90D': 50, 'All': 100 }
      const data = await apiClient.getHistory({ limit: limitMap[timeFilter] || 20, offset: 0 })
      setHistory(data.items || [])
    } catch (err) {
      showToast('Failed to fetch history', 'error')
      setHistory([])
    } finally {
      setLoading(false)
    }
  }, [timeFilter])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  const showToast = (message, type = 'info') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleRecordOutcome = async (simId, direction) => {
    setRecordingId(simId)
    try {
      await apiClient.recordOutcome(simId, direction)
      showToast(`Outcome recorded: ${direction}`, 'success')
      // Refresh to update stats
      await fetchHistory()
    } catch (err) {
      showToast(`Failed to record: ${err.message}`, 'error')
    } finally {
      setRecordingId(null)
    }
  }

  const handleExport = () => {
    if (history.length === 0) return

    const dateStr = new Date().toISOString().slice(0, 10)
    const filename = `gods-eye-history-${dateStr}.csv`

    const headers = ['simulation_id', 'timestamp', 'scenario', 'nifty_spot', 'direction', 'conviction_pct', 'execution_time_ms']

    const rows = history.map((item) => {
      const agg = item.aggregator_result || {}
      const dir = agg.final_direction || agg.direction || 'HOLD'
      const conv = agg.final_conviction ?? agg.conviction ?? 0
      const ts = item.timestamp || ''
      return [
        item.simulation_id || '',
        ts,
        item.market_input?.context || 'custom',
        item.market_input?.nifty_spot?.toString() || '',
        dir,
        typeof conv === 'number' ? conv.toFixed(1) : '',
        item.execution_time_ms?.toFixed(0) || '',
      ].map((v) => {
          // FE-M10: Prefix formula-injection characters to prevent CSV injection in Excel/Sheets
          let s = String(v).replace(/"/g, '""')
          if (/^[=+\-@\t\r]/.test(s)) s = "'" + s
          return `"${s}"`
        }).join(',')
    })

    const csv = [headers.join(','), ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  const totalSims = history.length

  return (
      <div className="p-5 h-[calc(100vh-2.5rem)] overflow-y-auto relative">
        {/* Toast */}
        {toast && (
          <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg text-xs font-mono shadow-lg border transition-all ${
            toast.type === 'success' ? 'bg-bull/10 text-bull border-bull/20' :
            toast.type === 'error' ? 'bg-bear/10 text-bear border-bear/20' :
            'bg-primary/10 text-primary border-primary/20'
          }`}>
            {toast.message}
          </div>
        )}

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-xl font-bold text-onSurface">Simulation History</h1>
            <p className="text-[10px] font-mono text-onSurfaceDim mt-0.5">
              {totalSims} simulation{totalSims !== 1 ? 's' : ''} recorded
            </p>
          </div>

          {history.length > 0 && (
            <button
              onClick={handleExport}
              className="btn-secondary font-mono text-[10px] tracking-wider px-3 py-1.5"
            >
              EXPORT CSV
            </button>
          )}

          <div className="flex items-center gap-1 p-0.5 bg-surface-2 rounded-lg">
            {['7D', '30D', '90D', 'All'].map((filter) => (
              <button
                key={filter}
                onClick={() => setTimeFilter(filter)}
                className={`px-3 py-1.5 rounded-md text-[10px] font-mono transition-all ${
                  timeFilter === filter
                    ? 'bg-primary/20 text-primary border border-primary/30'
                    : 'text-onSurfaceDim hover:text-onSurface'
                }`}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="terminal-card overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING HISTORY...</span>
            </div>
          ) : history.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2">
              <span className="text-xs font-mono text-onSurfaceDim">NO SIMULATIONS YET</span>
              <span className="text-[10px] font-mono text-onSurfaceDim">Run a simulation from the Dashboard</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="border-b border-[rgba(255,255,255,0.06)]">
                  <tr>
                    <th className="text-left px-3 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Time</th>
                    <th className="text-left px-3 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Scenario</th>
                    <th className="text-left px-3 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Nifty</th>
                    <th className="text-center px-3 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Signal</th>
                    <th className="text-center px-3 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Conv.</th>
                    <th className="text-center px-3 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Time</th>
                    <th className="text-center px-3 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Record Outcome</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[rgba(255,255,255,0.04)]">
                  {history.map((item, idx) => {
                    const agg = item.aggregator_result || {}
                    const dir = agg.final_direction || agg.direction || 'HOLD'
                    const conv = agg.final_conviction || agg.conviction || 0
                    const ts = item.timestamp ? new Date(item.timestamp) : null
                    const simId = item.simulation_id
                    const isRecording = recordingId === simId

                    return (
                      <tr key={simId || idx} className="hover:bg-surface-2/50 transition-colors">
                        <td className="px-3 py-2.5 font-mono text-onSurfaceMuted text-[10px]">
                          {ts ? ts.toLocaleString('en-IN', { hour12: false, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '--'}
                        </td>
                        <td className="px-3 py-2.5 text-onSurface text-[11px]">
                          {item.market_input?.context || 'custom'}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-onSurface text-[11px]">
                          {item.market_input?.nifty_spot?.toLocaleString() || '--'}
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span
                            className="px-2 py-0.5 rounded text-[10px] font-mono font-bold"
                            style={{
                              backgroundColor: `${dirColor(dir)}15`,
                              color: dirColor(dir),
                              border: `1px solid ${dirColor(dir)}30`,
                            }}
                          >
                            {dirLabel(dir)}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-center font-mono font-bold text-[11px]" style={{ color: dirColor(dir) }}>
                          {typeof conv === 'number' ? conv.toFixed(0) : '--'}%
                        </td>
                        <td className="px-3 py-2.5 text-center font-mono text-onSurfaceDim text-[10px]">
                          {item.execution_time_ms ? `${(item.execution_time_ms / 1000).toFixed(1)}s` : '--'}
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          {isRecording ? (
                            <span className="text-[10px] font-mono text-primary animate-pulse">SAVING...</span>
                          ) : (
                            <div className="flex items-center justify-center gap-1">
                              <button
                                onClick={() => handleRecordOutcome(simId, 'BUY')}
                                className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-bull/10 text-bull border border-bull/20 hover:bg-bull/20 transition-colors"
                                title="Market went UP"
                              >
                                UP
                              </button>
                              <button
                                onClick={() => handleRecordOutcome(simId, 'HOLD')}
                                className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-neutral/10 text-neutral border border-neutral/20 hover:bg-neutral/20 transition-colors"
                                title="Market was FLAT"
                              >
                                FLAT
                              </button>
                              <button
                                onClick={() => handleRecordOutcome(simId, 'SELL')}
                                className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-bear/10 text-bear border border-bear/20 hover:bg-bear/20 transition-colors"
                                title="Market went DOWN"
                              >
                                DN
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Help text */}
        <p className="text-[9px] font-mono text-onSurfaceDim mt-3 text-center">
          Record actual market outcomes to train the accuracy feedback engine. After 30+ outcomes, agent weights auto-tune.
        </p>
      </div>
  )
}
