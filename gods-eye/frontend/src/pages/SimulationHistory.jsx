import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../api/client'

const dirColor = (dir) => {
  if (!dir) return '#D97706'
  if (dir.includes('BUY')) return '#059669'
  if (dir.includes('SELL')) return '#DC2626'
  return '#D97706'
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
    <div className="p-4 h-full overflow-y-auto relative">
      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-5 right-5 z-50 px-4 py-2.5 rounded-xl text-xs font-mono shadow-card border transition-all ${
          toast.type === 'success' ? 'bg-bull-dim text-bull border-bull/20' :
          toast.type === 'error' ? 'bg-bear-dim text-bear border-bear/20' :
          'bg-primary/5 text-primary border-primary/20'
        }`}>
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-baseline gap-3 min-w-0">
          <h1 className="text-xl font-bold text-onSurface whitespace-nowrap">Simulation History</h1>
          <span className="text-[10px] font-mono text-onSurfaceDim whitespace-nowrap">
            {totalSims} simulation{totalSims !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="flex items-center gap-1 p-0.5 bg-surface-2 rounded-xl">
          {['7D', '30D', '90D', 'All'].map((filter) => (
            <button
              key={filter}
              onClick={() => setTimeFilter(filter)}
              className={`px-3 py-1.5 rounded-lg text-[10px] font-mono transition-all ${
                timeFilter === filter
                  ? 'bg-white text-primary border border-primary/20 shadow-sm'
                  : 'text-onSurfaceDim hover:text-onSurface border border-transparent'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>

        <div className="flex items-center justify-end min-w-[100px]">
          {history.length > 0 && (
            <button
              onClick={handleExport}
              className="btn-secondary font-mono text-[10px] tracking-wider px-3 py-1.5"
            >
              EXPORT CSV
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="terminal-card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING HISTORY...</span>
          </div>
        ) : history.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <span className="text-xs font-mono text-onSurfaceDim">NO SIMULATIONS YET</span>
            <span className="text-[10px] font-mono text-onSurfaceDim">Run a simulation from the Dashboard</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-gray-100">
                <tr>
                  <th className="text-left px-4 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Time</th>
                  <th className="text-left px-4 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Scenario</th>
                  <th className="text-left px-4 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Nifty</th>
                  <th className="text-center px-4 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Signal</th>
                  <th className="text-center px-4 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Conv.</th>
                  <th className="text-center px-4 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Time</th>
                  <th className="text-center px-4 py-3 text-[10px] font-mono text-onSurfaceDim uppercase">Record Outcome</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {history.map((item, idx) => {
                  const agg = item.aggregator_result || {}
                  const dir = agg.final_direction || agg.direction || 'HOLD'
                  const conv = agg.final_conviction || agg.conviction || 0
                  const ts = item.timestamp ? new Date(item.timestamp) : null
                  const simId = item.simulation_id
                  const isRecording = recordingId === simId

                  return (
                    <tr key={simId || idx} className="hover:bg-surface-1 transition-colors">
                      <td className="px-4 py-3 font-mono text-onSurfaceMuted text-[10px]">
                        {ts ? ts.toLocaleString('en-IN', { hour12: false, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '--'}
                      </td>
                      <td className="px-4 py-3 text-onSurface text-[11px]">
                        {item.market_input?.context || 'custom'}
                      </td>
                      <td className="px-4 py-3 font-mono text-onSurface text-[11px]">
                        {item.market_input?.nifty_spot?.toLocaleString() || '--'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className="px-2 py-0.5 rounded-pill text-[10px] font-mono font-bold"
                          style={{
                            backgroundColor: `${dirColor(dir)}08`,
                            color: dirColor(dir),
                            border: `1px solid ${dirColor(dir)}20`,
                          }}
                        >
                          {dirLabel(dir)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center font-mono font-bold text-[11px]" style={{ color: dirColor(dir) }}>
                        {typeof conv === 'number' ? conv.toFixed(0) : '--'}%
                      </td>
                      <td className="px-4 py-3 text-center font-mono text-onSurfaceDim text-[10px]">
                        {item.execution_time_ms ? `${(item.execution_time_ms / 1000).toFixed(1)}s` : '--'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {isRecording ? (
                          <span className="text-[10px] font-mono text-primary animate-pulse">SAVING...</span>
                        ) : (
                          <div className="flex items-center justify-center gap-1">
                            <button
                              onClick={() => handleRecordOutcome(simId, 'BUY')}
                              className="px-2 py-1 rounded-pill text-[10px] font-mono font-bold bg-bull-dim text-bull border border-bull/20 hover:bg-bull/10 transition-colors"
                              title="Market went UP"
                            >
                              UP
                            </button>
                            <button
                              onClick={() => handleRecordOutcome(simId, 'HOLD')}
                              className="px-2 py-1 rounded-pill text-[10px] font-mono font-bold bg-neutral-dim text-neutral border border-neutral/20 hover:bg-neutral/10 transition-colors"
                              title="Market was FLAT"
                            >
                              FLAT
                            </button>
                            <button
                              onClick={() => handleRecordOutcome(simId, 'SELL')}
                              className="px-2 py-1 rounded-pill text-[10px] font-mono font-bold bg-bear-dim text-bear border border-bear/20 hover:bg-bear/10 transition-colors"
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
      <p className="text-[9px] font-mono text-onSurfaceDim mt-4 text-center">
        Record actual market outcomes to train the accuracy feedback engine. After 30+ outcomes, agent weights auto-tune.
      </p>
    </div>
  )
}
