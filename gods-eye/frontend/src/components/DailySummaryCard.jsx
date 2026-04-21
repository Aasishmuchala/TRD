import React, { useEffect, useState, useRef } from 'react'
import { apiClient } from '../api/client'

// The backend job runs at 16:00 IST. Poll after that window so the card
// shows the freshly-generated recap without hammering the API during
// market hours.
const POLL_INTERVAL_MS = 60_000

const formatINR = (value) => {
  if (value === null || value === undefined) return '—'
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.abs(num))
  return num < 0 ? `-${formatted}` : formatted
}

const formatPct = (value, decimals = 2) => {
  if (value === null || value === undefined) return '—'
  const num = parseFloat(value)
  if (isNaN(num)) return '—'
  const sign = num > 0 ? '+' : ''
  return `${sign}${num.toFixed(decimals)}%`
}

const colorForPnl = (value) => {
  if (value === null || value === undefined || value === 0) return 'text-onSurfaceDim'
  return value > 0 ? 'text-bull' : 'text-bear'
}

/**
 * Daily trading recap card. Rendered on the dashboard; reads the row the
 * scheduler persists at 16:00 IST. Falls back gracefully:
 *   - No row yet (pre-16:00 or fresh DB)  → informational empty state
 *   - Fetch error                         → silent (no console noise)
 *   - Trading holiday                     → shows the holiday label
 */
export default function DailySummaryCard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const pollRef = useRef(null)

  const fetchSummary = async () => {
    try {
      const data = await apiClient.getDailySummary()
      setSummary(data)
      setError(null)
    } catch (err) {
      // 404 pre-generation is the common case — treat as empty, not error.
      if (err?.message?.toLowerCase?.().includes('no summary') ||
          err?.message?.toLowerCase?.().includes('not yet')) {
        setSummary(null)
        setError(null)
      } else {
        setError(err.message || 'Failed to load daily summary')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSummary()
    pollRef.current = setInterval(fetchSummary, POLL_INTERVAL_MS)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  if (loading && !summary) {
    return (
      <div className="terminal-card p-4">
        <div className="mb-3">
          <h2 className="text-xs font-mono text-onSurfaceDim uppercase tracking-wider">
            Daily Recap
          </h2>
        </div>
        <div className="h-24 animate-pulse bg-surface-1 rounded-lg" />
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="terminal-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-mono text-onSurfaceDim uppercase tracking-wider">
            Daily Recap
          </h2>
          <span className="text-[10px] font-mono text-onSurfaceDim">generated 16:00 IST</span>
        </div>
        <div className="bg-surface-1 rounded-lg p-4 text-center">
          <p className="text-xs font-mono text-onSurfaceDim">
            {error ? 'Unable to load recap' : 'No recap yet — runs daily at 16:00 IST'}
          </p>
        </div>
      </div>
    )
  }

  const {
    date_ist,
    is_trading_day,
    nifty_open,
    nifty_close,
    nifty_move_pct,
    actual_direction,
    predictions_count,
    majority_direction,
    avg_conviction,
    trades_opened,
    trades_closed,
    wins,
    losses,
    win_rate,
    net_pnl,
    top_agent,
  } = summary

  const moveColor = colorForPnl(nifty_move_pct)
  const pnlColor = colorForPnl(net_pnl)

  return (
    <div className="terminal-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-mono text-onSurfaceDim uppercase tracking-wider">
          Daily Recap — {date_ist}
        </h2>
        <span className="text-[10px] font-mono text-onSurfaceDim">
          {is_trading_day ? '16:00 IST' : 'non-trading day'}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="bg-surface-1 rounded-lg p-3">
          <p className="text-[10px] font-mono text-onSurfaceDim mb-1">NIFTY MOVE</p>
          <p className={`text-lg font-mono font-semibold ${moveColor}`}>
            {formatPct(nifty_move_pct)}
          </p>
          <p className="text-[10px] font-mono text-onSurfaceDim mt-1">
            {nifty_open ? `${nifty_open.toFixed(0)} → ${nifty_close?.toFixed(0)}` : '—'}
          </p>
        </div>

        <div className="bg-surface-1 rounded-lg p-3">
          <p className="text-[10px] font-mono text-onSurfaceDim mb-1">NET P&amp;L</p>
          <p className={`text-lg font-mono font-semibold ${pnlColor}`}>
            {formatINR(net_pnl)}
          </p>
          <p className="text-[10px] font-mono text-onSurfaceDim mt-1">
            {trades_opened ? `${trades_closed}/${trades_opened} closed` : 'no trades'}
          </p>
        </div>

        <div className="bg-surface-1 rounded-lg p-3">
          <p className="text-[10px] font-mono text-onSurfaceDim mb-1">WIN RATE</p>
          <p className="text-lg font-mono font-semibold">
            {win_rate !== null && win_rate !== undefined ? `${win_rate.toFixed(0)}%` : '—'}
          </p>
          <p className="text-[10px] font-mono text-onSurfaceDim mt-1">
            {trades_closed > 0 ? `${wins}W / ${losses}L` : '—'}
          </p>
        </div>

        <div className="bg-surface-1 rounded-lg p-3">
          <p className="text-[10px] font-mono text-onSurfaceDim mb-1">CONSENSUS</p>
          <p className="text-lg font-mono font-semibold">
            {majority_direction || '—'}
          </p>
          <p className="text-[10px] font-mono text-onSurfaceDim mt-1">
            {predictions_count > 0
              ? `${predictions_count} sims · ${avg_conviction ? avg_conviction.toFixed(0) : '—'}% conv`
              : 'no sims'}
          </p>
        </div>
      </div>

      {(actual_direction || top_agent) && (
        <div className="mt-3 pt-3 border-t border-onSurfaceDim/10 flex items-center justify-between text-[11px] font-mono text-onSurfaceDim">
          {actual_direction && (
            <span>
              actual:{' '}
              <span className="text-onSurface font-semibold">{actual_direction}</span>
            </span>
          )}
          {top_agent && (
            <span>
              top agent:{' '}
              <span className="text-onSurface font-semibold">{top_agent}</span>
            </span>
          )}
        </div>
      )}
    </div>
  )
}
