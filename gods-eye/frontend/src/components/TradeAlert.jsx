/**
 * TradeAlert — surfaces a stock options trade when God's Eye fires a
 * high-conviction directional signal.
 *
 * Shows only when:
 *   - final_direction is not HOLD
 *   - consensus_score absolute value > 20
 *   - final_conviction >= 55
 *
 * Fetches top screened stock + option suggestion from the backend.
 */
import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../api/client'

const CONVICTION_FLOOR = 55
const SCORE_FLOOR = 20

function AlertBadge({ direction }) {
  const isBuy = direction === 'BUY' || direction === 'STRONG_BUY'
  const color = isBuy ? 'bg-bull' : 'bg-bear'
  const label = isBuy ? '▲ BUY SIGNAL' : '▼ SELL SIGNAL'
  return (
    <span className={`${color} text-white text-xs font-bold px-2 py-1 rounded-full uppercase tracking-wide`}>
      {label}
    </span>
  )
}

function Stat({ label, value, sub }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-onSurfaceMuted uppercase tracking-wide">{label}</span>
      <span className="text-sm font-semibold text-onSurface">{value}</span>
      {sub && <span className="text-xs text-onSurfaceDim">{sub}</span>}
    </div>
  )
}

export default function TradeAlert({ simulationResult, capital = 10000 }) {
  const [candidates, setCandidates] = useState(null)
  const [option, setOption] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedSymbol, setSelectedSymbol] = useState(null)

  const agg = simulationResult?.aggregator_result
  const direction = agg?.final_direction
  const conviction = agg?.final_conviction ?? 0
  const score = agg?.consensus_score ?? 0

  const isActive =
    direction &&
    direction !== 'HOLD' &&
    Math.abs(score) >= SCORE_FLOOR &&
    conviction >= CONVICTION_FLOOR

  const fetchScreener = useCallback(async () => {
    if (!isActive) return
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.screenStocks(direction, capital, 3)
      setCandidates(data.candidates || [])
      if (data.candidates?.length > 0) {
        setSelectedSymbol(data.candidates[0].symbol)
      }
    } catch (e) {
      setError('Screener unavailable — check backend')
    } finally {
      setLoading(false)
    }
  }, [isActive, direction, capital])

  const fetchOption = useCallback(async (symbol) => {
    if (!symbol || !direction) return
    setOption(null)
    try {
      const data = await apiClient.getOptionSuggestion(symbol, direction, capital)
      setOption(data)
    } catch (e) {
      // non-fatal, just don't show options block
    }
  }, [direction, capital])

  // Fetch screener when signal arrives
  useEffect(() => {
    setCandidates(null)
    setOption(null)
    setSelectedSymbol(null)
    fetchScreener()
  }, [fetchScreener])

  // Fetch option when stock is selected
  useEffect(() => {
    if (selectedSymbol) fetchOption(selectedSymbol)
  }, [selectedSymbol, fetchOption])

  if (!simulationResult) return null
  if (!isActive) return null

  const isBuy = direction === 'BUY' || direction === 'STRONG_BUY'
  const borderColor = isBuy ? 'border-bull' : 'border-bear'
  const glowColor = ''

  return (
    <div className={`rounded-xl border-2 ${borderColor} bg-white shadow-lg ${glowColor} p-4 space-y-4`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">⚡</span>
          <span className="text-onSurface font-bold text-sm">TRADE ALERT</span>
          <AlertBadge direction={direction} />
        </div>
        <div className="flex gap-4 text-right">
          <Stat label="Score" value={score > 0 ? `+${score.toFixed(0)}` : score.toFixed(0)} />
          <Stat label="Conviction" value={`${conviction.toFixed(0)}%`} />
        </div>
      </div>

      {/* Stock screener candidates */}
      {loading && (
        <div className="text-onSurfaceMuted text-xs animate-pulse">Scanning F&O universe…</div>
      )}
      {error && (
        <div className="text-bear text-xs">{error}</div>
      )}

      {candidates && candidates.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs text-onSurfaceMuted uppercase tracking-wide">Top Candidates</div>
          <div className="flex gap-2 flex-wrap">
            {candidates.map((c) => {
              const aligned = c.direction_aligned
              const active = c.symbol === selectedSymbol
              return (
                <button
                  key={c.symbol}
                  onClick={() => setSelectedSymbol(c.symbol)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                    ${active
                      ? isBuy ? 'bg-bull text-white' : 'bg-bear text-white'
                      : 'bg-surface-1 text-onSurfaceMuted hover:bg-surface-2'}
                    ${aligned ? 'ring-1 ring-primary/20' : 'opacity-60'}`}
                >
                  <span className="font-bold">{c.symbol}</span>
                  <span className="ml-1 opacity-75">{c.rs_5d_pct > 0 ? '+' : ''}{c.rs_5d_pct}%</span>
                </button>
              )
            })}
          </div>

          {/* Selected stock details */}
          {selectedSymbol && (() => {
            const c = candidates.find(x => x.symbol === selectedSymbol)
            if (!c) return null
            return (
              <div className="grid grid-cols-4 gap-3 bg-surface-1 rounded-lg p-3">
                <Stat label="RS 5d" value={`${c.rs_5d_pct > 0 ? '+' : ''}${c.rs_5d_pct}%`} />
                <Stat label="Volume" value={`${c.volume_ratio}×`} sub="vs 20d avg" />
                <Stat label="RSI" value={c.rsi} />
                <Stat label="Score" value={`${c.screener_score}/100`} />
              </div>
            )
          })()}
        </div>
      )}

      {candidates && candidates.length === 0 && (
        <div className="text-onSurfaceMuted text-xs">
          No affordable F&O stocks found for ₹{capital.toLocaleString()} capital.
        </div>
      )}

      {/* Option suggestion */}
      {option && (
        <div className="border border-gray-200 rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-onSurface font-bold text-sm">
              {option.symbol} {option.suggested_strike} {option.option_type}
            </span>
            <span className="text-xs text-onSurfaceMuted">Expires {option.expiry} ({option.days_to_expiry}d)</span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Stat
              label="Premium (est.)"
              value={`₹${option.premium}/share`}
              sub={`₹${option.lot_cost.toLocaleString()} total`}
            />
            <Stat
              label="Stop → Exit at"
              value={`₹${option.stop_loss_premium}`}
              sub={`Max loss ₹${option.max_loss_inr.toLocaleString()}`}
            />
            <Stat
              label="Target → Exit at"
              value={`₹${option.target_premium}`}
              sub={`Gain ₹${option.target_gain_inr.toLocaleString()}`}
            />
          </div>
          <div className="text-xs text-onSurfaceMuted pt-1 border-t border-gray-200">
            ⚠ {option.note}
          </div>
        </div>
      )}
    </div>
  )
}
