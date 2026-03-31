export default function BacktestSummary({ summary }) {
  if (!summary) return null

  const pnlPositive = summary.total_pnl_points >= 0
  const accuracyGood = summary.win_rate_pct >= 50

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
          <div key={s.label} className="bg-surface-2 rounded-lg p-3">
            <p className="text-[10px] font-mono text-onSurfaceDim mb-1">{s.label}</p>
            <p className={`text-lg font-bold font-mono ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>
      <p className="text-[10px] font-mono text-onSurfaceDim mt-3">
        {summary.from_date} → {summary.to_date}
      </p>
    </div>
  )
}
