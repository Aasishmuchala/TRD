export default function BacktestSummary({ summary }) {
  if (!summary) return null

  const pnlPositive = summary.total_pnl_points >= 0
  const accuracyGood = summary.win_rate_pct >= 50
  const sharpeGood = (summary.sharpe_ratio || 0) >= 1.0

  const stats = [
    {
      label: 'Direction Accuracy',
      value: `${summary.win_rate_pct.toFixed(1)}%`,
      color: accuracyGood ? 'text-bull' : 'text-bear',
    },
    {
      label: 'Days Analyzed',
      value: summary.day_count,
      color: 'text-primary',
    },
    {
      label: 'Total P&L',
      value: `${pnlPositive ? '+' : ''}${summary.total_pnl_points.toFixed(0)} pts`,
      color: pnlPositive ? 'text-bull' : 'text-bear',
    },
    {
      label: 'Instrument',
      value: summary.instrument,
      color: 'text-onSurface',
    },
  ]

  // Stop loss stats (Profitability Roadmap v2)
  const stopPct = summary.total_trades > 0
    ? ((summary.total_stops_hit || 0) / summary.total_trades * 100).toFixed(1)
    : '0.0'

  // Phase 3 extended metrics (only show if available)
  const hasExtended = summary.hit_rate_pct !== undefined
  const extendedStats = hasExtended ? [
    {
      label: 'Hit Rate',
      value: `${(summary.hit_rate_pct || 0).toFixed(1)}%`,
      color: (summary.hit_rate_pct || 0) >= 50 ? 'text-bull' : 'text-bear',
    },
    {
      label: 'Avg P&L / Trade',
      value: `${(summary.avg_pnl_per_trade || 0) >= 0 ? '+' : ''}${(summary.avg_pnl_per_trade || 0).toFixed(1)} pts`,
      color: (summary.avg_pnl_per_trade || 0) >= 0 ? 'text-bull' : 'text-bear',
    },
    {
      label: 'Max Drawdown',
      value: `${(summary.max_drawdown_pct || 0).toFixed(1)}%`,
      color: (summary.max_drawdown_pct || 0) <= 20 ? 'text-neutral' : 'text-bear',
    },
    {
      label: 'Sharpe Ratio',
      value: (summary.sharpe_ratio || 0).toFixed(2),
      color: sharpeGood ? 'text-bull' : (summary.sharpe_ratio || 0) >= 0 ? 'text-neutral' : 'text-bear',
    },
    {
      label: 'Total Trades',
      value: summary.total_trades || 0,
      color: 'text-primary',
    },
  ] : []

  return (
    <div className="terminal-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-mono text-onSurfaceDim uppercase tracking-wider">Summary</h2>
        {summary.mock_mode && (
          <span className="text-[9px] font-mono text-neutral bg-neutral/10 border border-neutral/20 px-2 py-0.5 rounded">
            MOCK MODE
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-surface-1 rounded-lg p-3">
            <p className="text-[10px] font-mono text-onSurfaceDim mb-1">{s.label}</p>
            <p className={`text-lg font-bold font-mono ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Phase 3 extended metrics */}
      {extendedStats.length > 0 && (
        <>
          <div className="mt-4 mb-2">
            <h3 className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">Performance Metrics</h3>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {extendedStats.map((s) => (
              <div key={s.label} className="bg-surface-1 rounded-lg p-3">
                <p className="text-[10px] font-mono text-onSurfaceDim mb-1">{s.label}</p>
                <p className={`text-lg font-bold font-mono ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Stop Loss Stats */}
      {summary.stop_loss_enabled && (
        <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-4 flex-wrap">
          <span className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">Stop Loss</span>
          <span className="text-[11px] font-mono text-bear font-bold">
            {summary.total_stops_hit || 0} stops hit
          </span>
          <span className="text-[11px] font-mono text-onSurfaceDim">
            ({stopPct}% of trades)
          </span>
          <span className="text-[9px] font-mono bg-bear/10 text-bear border border-bear/20 px-2 py-0.5 rounded">
            ATR×1.5 or 1.5% rule
          </span>
        </div>
      )}

      <p className="text-[10px] font-mono text-onSurfaceDim mt-3">
        {summary.from_date} → {summary.to_date}
      </p>
    </div>
  )
}
