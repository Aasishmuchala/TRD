import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../api/client'

/**
 * MarketTicker — persistent top bar showing live market data.
 *
 * Displays: Nifty 50, India VIX, FII/DII net, PCR, Advance/Decline.
 * Auto-refreshes every 60s. Falls back gracefully if backend/NSE unavailable.
 */
export default function MarketTicker() {
  const [data, setData] = useState(null)
  const [options, setOptions] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)

  const fetchData = useCallback(async () => {
    try {
      // Fetch live data first (critical), options separately (nice-to-have)
      const live = await apiClient.getMarketLive()
      setData(live)
      setLastUpdate(new Date())
      // Options is non-blocking
      apiClient.getMarketOptions().then(setOptions).catch(() => null)
    } catch {
      // Backend might be down — data stays null, but loading stops
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30s (also retries on failure)
    return () => clearInterval(interval)
  }, [fetchData])

  if (loading) {
    return (
      <div className="h-8 bg-white border-b border-gray-100 px-4 flex items-center">
        <span className="text-[10px] font-mono text-onSurfaceDim animate-pulse">
          CONNECTING TO MARKET FEED...
        </span>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="h-8 bg-white border-b border-gray-100 px-4 flex items-center justify-between">
        <span className="text-[10px] font-mono text-bear">
          MARKET FEED OFFLINE — retrying...
        </span>
        <button
          onClick={fetchData}
          className="text-[9px] font-mono text-primary hover:text-primary/80 px-2 py-0.5 border border-primary/20 rounded"
        >
          RETRY
        </button>
      </div>
    )
  }

  const niftyUp = data.nifty_change >= 0
  const bankNiftyUp = (data.bank_nifty_change ?? 0) >= 0
  const vixUp = data.vix_change >= 0
  const fiiPositive = data.fii_net_today >= 0
  const diiPositive = data.dii_net_today >= 0
  const isLive = data.data_source === 'nse_live' || data.data_source === 'dhan_live'

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

  const pctClass = (positive) =>
    positive ? 'text-bull' : 'text-bear'

  return (
    <div className="h-8 bg-white border-b border-gray-100 px-4 flex items-center justify-between">
      <div className="flex items-center gap-5 text-[10px] font-mono">

        {/* Source indicator */}
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-bull animate-pulse' : 'bg-[#D97706]'}`} />
          <span className="text-onSurfaceDim uppercase tracking-wider">
            {isLive ? 'LIVE' : 'CACHED'}
          </span>
        </div>

        {/* Divider */}
        <span className="text-gray-200">│</span>

        {/* Nifty 50 */}
        <div className="flex items-center gap-1.5">
          <span className="text-onSurfaceMuted">NIFTY</span>
          <span className="text-onSurface font-bold">{formatNum(data.nifty_spot, 1)}</span>
          <span className={pctClass(niftyUp)}>
            {niftyUp ? '▲' : '▼'} {formatNum(Math.abs(data.nifty_change), 1)} ({formatNum(Math.abs(data.nifty_change_pct), 2)}%)
          </span>
        </div>

        <span className="text-gray-200">│</span>

        {/* Bank Nifty */}
        <div className="flex items-center gap-1.5">
          <span className="text-onSurfaceMuted">BANK</span>
          <span className="text-onSurface font-bold">
            {data.bank_nifty_spot ? formatNum(data.bank_nifty_spot, 1) : '--'}
          </span>
          {data.bank_nifty_spot > 0 && (
            <span className={pctClass(bankNiftyUp)}>
              {bankNiftyUp ? '▲' : '▼'}{formatNum(Math.abs(data.bank_nifty_change_pct ?? 0), 2)}%
            </span>
          )}
        </div>

        <span className="text-gray-200">│</span>

        {/* VIX */}
        <div className="flex items-center gap-1.5">
          <span className="text-onSurfaceMuted">VIX</span>
          <span className={`font-bold ${data.india_vix > 20 ? 'text-bear' : data.india_vix > 14 ? 'text-neutral' : 'text-bull'}`}>
            {formatNum(data.india_vix, 2)}
          </span>
          <span className={pctClass(!vixUp)}>
            {vixUp ? '▲' : '▼'}{formatNum(Math.abs(data.vix_change_pct), 1)}%
          </span>
        </div>

        <span className="text-gray-200">│</span>

        {/* FII */}
        <div className="flex items-center gap-1.5">
          <span className="text-onSurfaceMuted">FII</span>
          <span className={pctClass(fiiPositive)}>
            {formatFlow(data.fii_net_today)}
          </span>
        </div>

        {/* DII */}
        <div className="flex items-center gap-1.5">
          <span className="text-onSurfaceMuted">DII</span>
          <span className={pctClass(diiPositive)}>
            {formatFlow(data.dii_net_today)}
          </span>
        </div>

        <span className="text-gray-200">│</span>

        {/* PCR */}
        {options && (
          <div className="flex items-center gap-1.5">
            <span className="text-onSurfaceMuted">PCR</span>
            <span className={`font-bold ${
              options.pcr > 1.2 ? 'text-bull' :
              options.pcr < 0.8 ? 'text-bear' : 'text-neutral'
            }`}>
              {formatNum(options.pcr, 3)}
            </span>
          </div>
        )}

        {/* A/D Ratio */}
        <div className="flex items-center gap-1.5">
          <span className="text-onSurfaceMuted">A/D</span>
          <span className={pctClass(data.advance_decline_ratio >= 1)}>
            {formatNum(data.advance_decline_ratio, 2)}
          </span>
        </div>
      </div>

      {/* Right side: last update */}
      <div className="text-[9px] font-mono text-onSurfaceDim">
        {lastUpdate && `Updated ${lastUpdate.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit' })} IST`}
      </div>
    </div>
  )
}
