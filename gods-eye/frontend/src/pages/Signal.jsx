import { useState } from 'react'
import { apiClient } from '../api/client'
import { AGENT_DISPLAY_NAMES } from '../constants/agents'

const TODAY = new Date().toISOString().slice(0, 10)

function DirectionTag({ direction }) {
  const cls =
    direction === 'BUY'
      ? 'text-bull bg-bull/10 border border-bull/20'
      : direction === 'SELL'
      ? 'text-bear bg-bear/10 border border-bear/20'
      : 'text-neutral-bright bg-neutral/10 border border-neutral/20'
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${cls}`}>
      {direction}
    </span>
  )
}

function ProgressBar({ value, max = 100, height = 'h-1.5', colorClass = 'bg-primary' }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div className={`w-full rounded-full bg-primary/20 ${height}`}>
      <div
        className={`${height} rounded-full ${colorClass} transition-all`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function SectionTitle({ children }) {
  return (
    <h2 className="text-[10px] font-mono font-bold text-onSurfaceDim uppercase tracking-widest mb-3">
      {children}
    </h2>
  )
}

// Section 1 — Quant Score Breakdown
function QuantSection({ quant }) {
  const factors = quant.factors ? Object.entries(quant.factors) : []
  return (
    <div className="terminal-card p-4">
      <div className="flex items-center gap-3 mb-4">
        <SectionTitle>Quant Score</SectionTitle>
        <span className="text-2xl font-mono font-bold text-onSurface ml-auto">
          {quant.total_score}
          <span className="text-xs text-onSurfaceDim font-normal">/100</span>
        </span>
        <DirectionTag direction={quant.direction} />
      </div>

      {/* Score progress bar */}
      <ProgressBar value={quant.total_score} max={100} height="h-2" />

      {/* Factor table */}
      {factors.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-[10px] font-mono">
            <thead>
              <tr className="text-onSurfaceDim border-b border-[rgba(255,255,255,0.06)]">
                <th className="text-left py-1.5 pr-4">Factor</th>
                <th className="text-center py-1.5 pr-4">Threshold Hit</th>
                <th className="text-center py-1.5 pr-4">Side</th>
                <th className="text-right py-1.5">Points</th>
              </tr>
            </thead>
            <tbody>
              {factors.map(([key, val]) => (
                <tr key={key} className="border-b border-[rgba(255,255,255,0.03)]">
                  <td className="py-1.5 pr-4 text-onSurface capitalize">{key.replace(/_/g, ' ')}</td>
                  <td className="py-1.5 pr-4 text-center">
                    {val.threshold_hit ? (
                      <span className="text-bull font-bold">✓</span>
                    ) : (
                      <span className="text-onSurfaceDim">—</span>
                    )}
                  </td>
                  <td className={`py-1.5 pr-4 text-center uppercase font-bold ${
                    val.side === 'buy' ? 'text-bull' : val.side === 'sell' ? 'text-bear' : 'text-onSurfaceDim'
                  }`}>
                    {val.side ?? '—'}
                  </td>
                  <td className={`py-1.5 text-right font-bold ${
                    val.points_awarded > 0 ? 'text-primary' : 'text-onSurfaceDim'
                  }`}>
                    {val.points_awarded > 0 ? `+${val.points_awarded}` : val.points_awarded}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// Section 2 — Agent Consensus
function AgentSection({ agents }) {
  if (!agents || agents.length === 0) return null
  return (
    <div className="terminal-card p-4">
      <SectionTitle>Agent Consensus</SectionTitle>
      <div className="space-y-3">
        {agents.map((agent) => {
          const label = AGENT_DISPLAY_NAMES[agent.agent_id] || agent.agent_id.replace(/_/g, ' ')
          return (
            <div key={agent.agent_id} className="space-y-1">
              <div className="flex items-center justify-between gap-3">
                <span className="text-[11px] font-mono text-onSurface font-medium">{label}</span>
                <div className="flex items-center gap-2">
                  <DirectionTag direction={agent.direction} />
                  <span className="text-[10px] font-mono text-onSurfaceDim">
                    {agent.conviction?.toFixed(0)}%
                  </span>
                </div>
              </div>
              <ProgressBar
                value={agent.conviction ?? 0}
                max={100}
                height="h-1"
                colorClass={
                  agent.direction === 'BUY'
                    ? 'bg-bull'
                    : agent.direction === 'SELL'
                    ? 'bg-bear'
                    : 'bg-neutral'
                }
              />
              {agent.rationale && (
                <p
                  className="text-[10px] text-onSurfaceDim italic truncate"
                  title={agent.rationale}
                >
                  {agent.rationale}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Section 3 — Validator Verdict
function ValidatorSection({ verdict, reasoning }) {
  const verdictStyle =
    verdict === 'confirm'
      ? 'text-bull bg-bull/10 border-bull/20'
      : verdict === 'skip'
      ? 'text-bear bg-bear/10 border-bear/20'
      : 'text-neutral-bright bg-neutral/10 border-neutral/20'

  return (
    <div className="terminal-card p-4">
      <SectionTitle>Validator Verdict</SectionTitle>
      <div className="flex items-center gap-3 mb-3">
        <span className={`px-3 py-1 rounded border text-xs font-mono font-bold uppercase ${verdictStyle}`}>
          {verdict}
        </span>
      </div>
      {reasoning && (
        <p className="text-[11px] text-onSurfaceDim italic leading-relaxed">{reasoning}</p>
      )}
    </div>
  )
}

// Section 4 — Recommended Trade
function TradeSection({ signal }) {
  const { risk_params, tradeable, tier, instrument_hint, direction } = signal
  const isSkip = !tradeable || tier === 'skip'

  const rows = [
    { label: 'Instrument', value: instrument_hint ?? '—' },
    { label: 'Tier', value: tier ? tier.toUpperCase() : '—' },
    { label: 'Position Size', value: risk_params?.position_size_lots != null ? `${risk_params.position_size_lots} lots` : '—' },
    {
      label: 'Stop Loss',
      value: risk_params?.stop_level != null
        ? `${risk_params.stop_level} (${risk_params.stop_loss_pts} pts)`
        : '—',
    },
    {
      label: 'Target',
      value: risk_params?.target_level != null
        ? `${risk_params.target_level} (${risk_params.target_pts} pts)`
        : '—',
    },
    { label: 'VIX Used', value: risk_params?.vix_used != null ? risk_params.vix_used.toFixed(2) : '—' },
  ]

  return (
    <div className="terminal-card p-4 relative overflow-hidden">
      <div className="flex items-center gap-3 mb-4">
        <SectionTitle>Recommended Trade</SectionTitle>
        <span
          className={`ml-auto px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
            tradeable
              ? 'text-bull bg-bull/10 border-bull/20'
              : 'text-bear bg-bear/10 border-bear/20'
          }`}
        >
          {tradeable ? 'TRADEABLE' : 'SKIP'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {rows.map(({ label, value }) => (
          <div key={label} className="flex flex-col gap-0.5">
            <span className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-wider">{label}</span>
            <span className="text-xs font-mono text-onSurface font-medium">{value}</span>
          </div>
        ))}
      </div>

      {/* Skip overlay */}
      {isSkip && (
        <div className="absolute inset-0 bg-surface-1/70 flex items-center justify-center rounded">
          <span className="text-[11px] font-mono text-onSurfaceDim font-bold uppercase tracking-widest">
            Signal tier is SKIP — no trade recommended
          </span>
        </div>
      )}
    </div>
  )
}

export default function Signal() {
  const [instrument, setInstrument] = useState('NIFTY')
  const [date, setDate] = useState(TODAY)
  const [loading, setLoading] = useState(false)
  const [signal, setSignal] = useState(null)
  const [error, setError] = useState(null)

  const handleRun = async (e) => {
    e.preventDefault()
    if (!date) return
    setLoading(true)
    setError(null)
    setSignal(null)
    try {
      const data = await apiClient.getHybridSignal(instrument, date)
      setSignal(data)
    } catch (err) {
      setError(err.message || 'Signal computation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
      <div className="p-5 h-[calc(100vh-2.5rem)] overflow-y-auto">
        {/* Page header */}
        <div className="mb-5">
          <h1 className="text-xl font-bold text-onSurface">Signal</h1>
          <p className="text-[10px] font-mono text-onSurfaceDim mt-0.5">
            Real-time hybrid signal — quant + agents + validator
          </p>
        </div>

        {/* Control bar */}
        <form onSubmit={handleRun} className="terminal-card p-4 mb-5">
          <div className="flex flex-wrap items-end gap-3">
            {/* Instrument toggle */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">
                Instrument
              </label>
              <div className="flex gap-1">
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

            {/* Date input */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">
                Date
              </label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
                className="bg-surface-2 border border-[rgba(255,255,255,0.08)] rounded-lg px-3 py-2 text-xs font-mono text-onSurface focus:outline-none focus:border-primary/50"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !date}
              className="px-4 py-2 rounded-lg text-xs font-mono font-bold bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {loading ? 'COMPUTING...' : 'RUN SIGNAL'}
            </button>
          </div>
        </form>

        {/* Loading state */}
        {loading && (
          <div className="terminal-card p-8 mb-5 flex flex-col items-center gap-3">
            <span className="text-xs font-mono text-primary animate-pulse">
              COMPUTING HYBRID SIGNAL...
            </span>
            <span className="text-[10px] font-mono text-onSurfaceDim">
              Running quant engine, agent consensus, and validator. Please wait.
            </span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="terminal-card border-l-2 border-bear p-4 mb-5">
            <p className="text-xs font-mono text-bear font-bold mb-1">SIGNAL FAILED</p>
            <p className="text-[11px] text-onSurfaceMuted">{error}</p>
          </div>
        )}

        {/* Empty state — before first fetch */}
        {!loading && !error && !signal && (
          <div className="terminal-card p-12 flex items-center justify-center">
            <p className="text-[11px] font-mono text-onSurfaceDim">
              Select instrument and date, then run signal
            </p>
          </div>
        )}

        {/* Results — 4 sections */}
        {signal && !loading && (
          <div className="flex flex-col gap-4">
            <QuantSection quant={signal.quant_breakdown} />
            <AgentSection agents={signal.agent_breakdown} />
            <ValidatorSection
              verdict={signal.validator_verdict}
              reasoning={signal.validator_reasoning}
            />
            <TradeSection signal={signal} />
          </div>
        )}
      </div>
  )
}
