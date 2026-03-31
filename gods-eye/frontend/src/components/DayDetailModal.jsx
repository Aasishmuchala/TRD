import { dirColor, dirLabel } from '../utils/format'

/**
 * DayDetailModal — full drill-down overlay for a single backtest day.
 * Props:
 *   day: backtest day object | null
 *   onClose: () => void
 */

const AGENT_LABELS = {
  FII: 'FII',
  DII: 'DII',
  RETAIL_FNO: 'Retail F&O',
  ALGO_QUANT: 'Algo/Quant',
  PROMOTER: 'Promoter',
  RBI: 'RBI',
}

function TierBadge({ tier }) {
  if (!tier) return null
  const styles = {
    strong: 'text-bull bg-bull/10 border-bull/20',
    moderate: 'text-primary bg-primary/10 border-primary/20',
    skip: 'text-onSurfaceDim bg-surface-2 border-[rgba(255,255,255,0.08)]',
  }
  const cls = styles[tier] ?? styles.skip
  return (
    <span className={`text-[9px] font-mono font-bold uppercase px-2 py-0.5 rounded border ${cls}`}>
      {tier}
    </span>
  )
}

export default function DayDetailModal({ day, onClose }) {
  if (!day) return null

  const {
    date,
    next_date,
    nifty_close,
    nifty_next_close,
    actual_move_pct,
    predicted_direction,
    predicted_conviction,
    direction_correct,
    pnl_points,
    cumulative_pnl_points,
    per_agent_directions,
    signal_score,
  } = day

  const predColor = dirColor(predicted_direction)
  const predLabel = dirLabel(predicted_direction)

  const actualSign = actual_move_pct >= 0 ? '+' : ''
  const actualColor = actual_move_pct >= 0 ? '#00E676' : '#FF1744'

  const pnlSign = pnl_points >= 0 ? '+' : ''
  const pnlColor = pnl_points >= 0 ? '#00E676' : '#FF1744'

  const cumSign = cumulative_pnl_points >= 0 ? '+' : ''
  const cumColor = cumulative_pnl_points >= 0 ? '#00E676' : '#FF1744'

  const agentEntries = per_agent_directions
    ? Object.entries(per_agent_directions).filter(([key]) => key in AGENT_LABELS)
    : []

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="bg-surface-1 rounded-2xl border border-[rgba(255,255,255,0.08)] p-5 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm font-mono font-bold text-onSurface">{date}</p>
            {next_date && (
              <p className="text-[10px] font-mono text-onSurfaceDim">
                next trading day: {next_date}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-onSurfaceDim hover:text-onSurface text-lg leading-none transition-colors px-1"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {/* Prediction vs Actual */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-surface-2 rounded-lg p-3">
            <p className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-wider mb-2">
              Predicted
            </p>
            <p className="text-sm font-mono font-bold mb-1" style={{ color: predColor }}>
              {predLabel}
            </p>
            <p className="text-[10px] font-mono text-onSurfaceDim">
              Conviction:{' '}
              <span className="text-onSurface font-bold">
                {typeof predicted_conviction === 'number'
                  ? `${predicted_conviction.toFixed(0)}%`
                  : 'N/A'}
              </span>
            </p>
          </div>

          <div className="bg-surface-2 rounded-lg p-3">
            <p className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-wider mb-2">
              Actual
            </p>
            <p
              className="text-sm font-mono font-bold mb-1"
              style={{ color: actualColor }}
            >
              {actualSign}{typeof actual_move_pct === 'number' ? actual_move_pct.toFixed(2) : '—'}%
            </p>
            {direction_correct === null ? (
              <span className="text-[9px] font-mono font-bold text-neutral">HELD</span>
            ) : direction_correct ? (
              <span className="text-[9px] font-mono font-bold text-bull">CORRECT</span>
            ) : (
              <span className="text-[9px] font-mono font-bold text-bear">INCORRECT</span>
            )}
          </div>
        </div>

        {/* P&L row */}
        <div className="bg-surface-2 rounded-lg p-3 mb-4 flex items-center justify-between">
          <div>
            <p className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-wider mb-1">
              Day P&amp;L
            </p>
            <p className="text-base font-mono font-bold" style={{ color: pnlColor }}>
              {pnlSign}{typeof pnl_points === 'number' ? pnl_points.toFixed(0) : '—'} pts
            </p>
          </div>
          <div className="text-right">
            <p className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-wider mb-1">
              Cumulative P&amp;L
            </p>
            <p className="text-base font-mono font-bold" style={{ color: cumColor }}>
              {cumSign}{typeof cumulative_pnl_points === 'number' ? cumulative_pnl_points.toFixed(0) : '—'} pts
            </p>
          </div>
        </div>

        {/* Agent Directions */}
        {agentEntries.length > 0 && (
          <div className="mb-4">
            <p className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-wider mb-2">
              Agent Directions
            </p>
            <div className="grid grid-cols-3 gap-2">
              {agentEntries.map(([key, dir]) => (
                <div key={key} className="bg-surface-2 rounded-lg p-2">
                  <p className="text-[9px] font-mono text-onSurfaceDim mb-1">
                    {AGENT_LABELS[key] ?? key}
                  </p>
                  <p
                    className="text-[10px] font-mono font-bold"
                    style={{ color: dirColor(dir) }}
                  >
                    {dirLabel(dir)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Signal Score */}
        {signal_score && (
          <div className="mb-4">
            <p className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-wider mb-2">
              Signal Score
            </p>
            <div className="bg-surface-2 rounded-lg p-3">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl font-bold font-mono text-onSurface">
                  {signal_score.score}
                </span>
                <TierBadge tier={signal_score.tier} />
                {signal_score.direction && (
                  <span
                    className="text-[10px] font-mono font-bold"
                    style={{ color: dirColor(signal_score.direction) }}
                  >
                    {dirLabel(signal_score.direction)}
                  </span>
                )}
              </div>
              {signal_score.suggested_instrument && (
                <p className="text-[10px] font-mono text-onSurfaceDim mb-2">
                  Instrument:{' '}
                  <span className="text-onSurface">{signal_score.suggested_instrument}</span>
                </p>
              )}
              {signal_score.contributing_factors?.length > 0 && (
                <ul className="space-y-0.5">
                  {signal_score.contributing_factors.map((factor, i) => (
                    <li key={i} className="text-[10px] font-mono text-onSurfaceMuted flex gap-1.5">
                      <span className="text-onSurfaceDim">•</span>
                      {factor}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Nifty prices */}
        {typeof nifty_close === 'number' && typeof nifty_next_close === 'number' && (
          <div className="border-t border-[rgba(255,255,255,0.06)] pt-3">
            <p className="text-[9px] font-mono text-onSurfaceDim uppercase tracking-wider mb-1">
              Nifty Close
            </p>
            <p className="text-[11px] font-mono text-onSurfaceMuted">
              {nifty_close.toLocaleString()} → {nifty_next_close.toLocaleString()}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
