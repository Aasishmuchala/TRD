function computeStats(days) {
  if (!days || days.length === 0) {
    return { maxDrawdown: null, sharpeRatio: null, avgWin: null, avgLoss: null }
  }

  // max_drawdown: track running peak of cumulative_pnl_points
  let peak = -Infinity
  let maxDrawdown = 0
  for (const day of days) {
    const cum = day.cumulative_pnl_points
    if (cum > peak) peak = cum
    const drawdown = peak - cum
    if (drawdown > maxDrawdown) maxDrawdown = drawdown
  }

  // sharpe_ratio: only non-HOLD days (direction_correct !== null)
  const activeDays = days.filter((d) => d.direction_correct !== null)
  let sharpeRatio = null
  if (activeDays.length >= 2) {
    const pnls = activeDays.map((d) => d.pnl_points)
    const mean = pnls.reduce((a, b) => a + b, 0) / pnls.length
    const variance =
      pnls.reduce((acc, v) => acc + (v - mean) ** 2, 0) / (pnls.length - 1)
    const stddev = Math.sqrt(variance)
    sharpeRatio = stddev === 0 ? null : (mean / stddev) * Math.sqrt(252)
  }

  // avg_win: mean of pnl_points > 0
  const wins = days.filter((d) => d.pnl_points > 0).map((d) => d.pnl_points)
  const avgWin = wins.length > 0 ? wins.reduce((a, b) => a + b, 0) / wins.length : null

  // avg_loss: mean of pnl_points < 0 (absolute value)
  const losses = days.filter((d) => d.pnl_points < 0).map((d) => Math.abs(d.pnl_points))
  const avgLoss = losses.length > 0 ? losses.reduce((a, b) => a + b, 0) / losses.length : null

  return { maxDrawdown, sharpeRatio, avgWin, avgLoss }
}

export default function StatsPanel({ days }) {
  const { maxDrawdown, sharpeRatio, avgWin, avgLoss } = computeStats(days)

  const sharpeColor =
    sharpeRatio === null
      ? 'text-bear'
      : sharpeRatio > 0.5
      ? 'text-bull'
      : sharpeRatio >= 0
      ? 'text-neutral'
      : 'text-bear'

  const stats = [
    {
      label: 'DRAWDOWN',
      value: maxDrawdown === null ? 'N/A' : `${maxDrawdown.toFixed(0)} pts`,
      color: 'text-bear',
    },
    {
      label: 'SHARPE',
      value: sharpeRatio === null ? 'N/A' : sharpeRatio.toFixed(2),
      color: sharpeColor,
    },
    {
      label: 'AVG WIN',
      value: avgWin === null ? 'N/A' : `+${avgWin.toFixed(0)} pts`,
      color: 'text-bull',
    },
    {
      label: 'AVG LOSS',
      value: avgLoss === null ? 'N/A' : `-${avgLoss.toFixed(0)} pts`,
      color: 'text-bear',
    },
  ]

  return (
    <div className="terminal-card p-4">
      <div className="mb-3">
        <h2 className="text-xs font-mono text-onSurfaceDim uppercase tracking-wider">Statistics</h2>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="bg-surface-2 rounded-lg p-3">
            <p className="text-[10px] font-mono text-onSurfaceDim mb-1">{s.label}</p>
            <p className={`text-lg font-bold font-mono ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
