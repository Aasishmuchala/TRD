import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../api/client'

function ISTClock() {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const istTime = time.toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })

  const isMarketHours = (() => {
    const ist = new Date(time.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
    const h = ist.getHours()
    const m = ist.getMinutes()
    const mins = h * 60 + m
    const day = ist.getDay()
    return day >= 1 && day <= 5 && mins >= 555 && mins <= 930
  })()

  return (
    <div className="flex items-center gap-2.5">
      <span className="font-mono text-onSurface text-[11px]">{istTime}</span>
      <span className="text-[10px] text-onSurfaceDim">IST</span>
      <span className={`w-1.5 h-1.5 rounded-full ${isMarketHours ? 'bg-bull animate-pulse' : 'bg-onSurfaceDim'}`} />
      <span className={`text-[10px] font-mono uppercase tracking-wide ${isMarketHours ? 'text-bull' : 'text-onSurfaceDim'}`}>
        {isMarketHours ? 'OPEN' : 'CLOSED'}
      </span>
    </div>
  )
}

export default function TopBar({ onCommandPalette }) {
  const [data, setData] = useState(null)
  const [options, setOptions] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const live = await apiClient.getMarketLive()
      setData(live)
      apiClient.getMarketOptions().then(setOptions).catch(() => null)
    } catch {
      // Backend down — data stays null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [fetchData])

  const formatNum = (n, decimals = 0) => {
    if (n == null) return '--'
    return Number(n).toLocaleString('en-IN', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  const formatFlow = (n) => {
    if (n == null) return '--'
    const abs = Math.abs(n)
    const prefix = n >= 0 ? '+' : '-'
    if (abs >= 1000) return `${prefix}₹${(abs / 1000).toFixed(1)}K Cr`
    return `${prefix}₹${abs.toFixed(0)} Cr`
  }

  const pctClass = (positive) => positive ? 'text-bull' : 'text-bear'

  const Divider = () => <span className="text-gray-200">│</span>

  return (
    <div className="h-12 bg-white border-b border-gray-100 px-4 flex items-center justify-between flex-shrink-0">

      {/* Left: Market data */}
      <div className="flex items-center gap-4 text-[10px] font-mono min-w-0 overflow-hidden">

        {loading ? (
          <span className="text-onSurfaceDim animate-pulse">CONNECTING...</span>
        ) : !data ? (
          <>
            <span className="text-bear">FEED OFFLINE</span>
            <button onClick={fetchData} className="text-primary hover:text-primary-glow px-1.5 py-0.5 border border-primary/20 rounded text-[9px]">
              RETRY
            </button>
          </>
        ) : (
          <>
            {/* Live indicator */}
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${
                (data.data_source === 'nse_live' || data.data_source === 'dhan_live')
                  ? 'bg-bull animate-pulse' : 'bg-neutral'
              }`} />
              <span className="text-onSurfaceDim uppercase tracking-wider">
                {(data.data_source === 'nse_live' || data.data_source === 'dhan_live') ? 'LIVE' : 'CACHED'}
              </span>
            </div>

            <Divider />

            {/* Nifty */}
            <div className="flex items-center gap-1.5">
              <span className="text-onSurfaceMuted">NIFTY</span>
              <span className="text-onSurface font-bold">{formatNum(data.nifty_spot, 1)}</span>
              <span className={pctClass(data.nifty_change >= 0)}>
                {data.nifty_change >= 0 ? '▲' : '▼'}{formatNum(Math.abs(data.nifty_change_pct), 2)}%
              </span>
            </div>

            <Divider />

            {/* Bank Nifty */}
            <div className="flex items-center gap-1.5">
              <span className="text-onSurfaceMuted">BANK</span>
              <span className="text-onSurface font-bold">
                {data.bank_nifty_spot ? formatNum(data.bank_nifty_spot, 1) : '--'}
              </span>
              {data.bank_nifty_spot > 0 && (
                <span className={pctClass((data.bank_nifty_change ?? 0) >= 0)}>
                  {(data.bank_nifty_change ?? 0) >= 0 ? '▲' : '▼'}{formatNum(Math.abs(data.bank_nifty_change_pct ?? 0), 2)}%
                </span>
              )}
            </div>

            <Divider />

            {/* VIX */}
            <div className="flex items-center gap-1.5">
              <span className="text-onSurfaceMuted">VIX</span>
              <span className={`font-bold ${data.india_vix > 20 ? 'text-bear' : data.india_vix > 14 ? 'text-neutral' : 'text-bull'}`}>
                {formatNum(data.india_vix, 2)}
              </span>
            </div>

            <Divider />

            {/* FII / DII */}
            <div className="flex items-center gap-1.5">
              <span className="text-onSurfaceMuted">FII</span>
              <span className={pctClass(data.fii_net_today >= 0)}>{formatFlow(data.fii_net_today)}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-onSurfaceMuted">DII</span>
              <span className={pctClass(data.dii_net_today >= 0)}>{formatFlow(data.dii_net_today)}</span>
            </div>

            {/* PCR */}
            {options && (
              <>
                <Divider />
                <div className="flex items-center gap-1.5">
                  <span className="text-onSurfaceMuted">PCR</span>
                  <span className={`font-bold ${
                    options.pcr > 1.2 ? 'text-bull' :
                    options.pcr < 0.8 ? 'text-bear' : 'text-neutral'
                  }`}>
                    {formatNum(options.pcr, 3)}
                  </span>
                </div>
              </>
            )}

            {/* A/D */}
            <div className="flex items-center gap-1.5">
              <span className="text-onSurfaceMuted">A/D</span>
              <span className={pctClass(data.advance_decline_ratio >= 1)}>
                {formatNum(data.advance_decline_ratio, 2)}
              </span>
            </div>
          </>
        )}
      </div>

      {/* Right: Clock + Status + Command Palette */}
      <div className="flex items-center gap-4 flex-shrink-0">
        <ISTClock />

        <span className="text-gray-200">│</span>

        {/* Command palette trigger */}
        <button
          onClick={onCommandPalette}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-2 hover:bg-surface-3 border border-gray-200 hover:border-gray-300 transition-all duration-200 text-onSurfaceMuted hover:text-onSurface"
          title="Command Palette (⌘K)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <span className="text-[10px] font-mono">⌘K</span>
        </button>
      </div>
    </div>
  )
}
