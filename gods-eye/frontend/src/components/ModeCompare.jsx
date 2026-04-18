export default function ModeCompare({ quantResult, hybridResult }) {
  if (!quantResult && !hybridResult) return null

  // Helper: format value with sign
  const fmt = (v, decimals = 1, suffix = '') =>
    v == null ? 'N/A' : `${Number(v).toFixed(decimals)}${suffix}`

  // Extract summary metrics from a result object (quant or hybrid response shape)
  const metrics = (r) => r ? {
    win_rate_pct: r.win_rate_pct,
    total_pnl_points: r.total_pnl_points,
    sharpe_ratio: r.sharpe_ratio,
    max_drawdown_pct: r.max_drawdown_pct,
    win_loss_ratio: r.win_loss_ratio,
    tradeable_days: r.tradeable_days,
    elapsed_seconds: r.elapsed_seconds,
  } : null

  const qm = metrics(quantResult)
  const hm = metrics(hybridResult)

  const rows = [
    { label: 'Win Rate', key: 'win_rate_pct', fmt: (v) => fmt(v, 1, '%'), better: 'higher' },
    { label: 'Total P&L (pts)', key: 'total_pnl_points', fmt: (v) => fmt(v, 0), better: 'higher' },
    { label: 'Sharpe Ratio', key: 'sharpe_ratio', fmt: (v) => fmt(v, 2), better: 'higher' },
    { label: 'Max Drawdown', key: 'max_drawdown_pct', fmt: (v) => v == null ? 'N/A' : `${Number(v).toFixed(1)}%`, better: 'higher' },
    { label: 'Win/Loss Ratio', key: 'win_loss_ratio', fmt: (v) => fmt(v, 2), better: 'higher' },
    { label: 'Tradeable Days', key: 'tradeable_days', fmt: (v) => fmt(v, 0), better: 'higher' },
    { label: 'Elapsed', key: 'elapsed_seconds', fmt: (v) => v == null ? 'N/A' : `${Number(v).toFixed(1)}s`, better: 'lower' },
  ]

  // Delta color: green if hybrid is better, red if worse, neutral if same or N/A
  const deltaColor = (key, better) => {
    if (!qm || !hm) return 'text-onSurfaceDim'
    const qv = qm[key], hv = hm[key]
    if (qv == null || hv == null) return 'text-onSurfaceDim'
    const diff = hv - qv
    if (diff === 0) return 'text-onSurfaceDim'
    const hybridIsBetter = better === 'higher' ? diff > 0 : diff < 0
    return hybridIsBetter ? 'text-bull' : 'text-bear'
  }

  const fmtDelta = (key, fmtFn, better) => {
    if (!qm || !hm) return '—'
    const qv = qm[key], hv = hm[key]
    if (qv == null || hv == null) return '—'
    const diff = hv - qv
    const sign = diff >= 0 ? '+' : ''
    // Use raw diff formatted similarly to the value
    if (key === 'win_rate_pct') return `${sign}${diff.toFixed(1)}%`
    if (key === 'total_pnl_points') return `${sign}${diff.toFixed(0)}`
    if (key === 'elapsed_seconds') return `${sign}${diff.toFixed(1)}s`
    return `${sign}${diff.toFixed(2)}`
  }

  return (
    <div className="terminal-card p-4">
      <div className="mb-3">
        <h2 className="text-xs font-mono text-onSurfaceDim uppercase tracking-wider">
          Mode Comparison
        </h2>
        {qm && hm && (
          <p className="text-[10px] font-mono text-onSurfaceDim mt-0.5">
            Delta = Hybrid minus Rules-Only
          </p>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[10px] font-mono">
          <thead>
            <tr className="text-onSurfaceDim border-b border-gray-100">
              <th className="text-left py-2 pr-4">Metric</th>
              <th className="text-right py-2 pr-4 text-primary">Rules Only</th>
              <th className="text-right py-2 pr-4 text-primary">Hybrid</th>
              {qm && hm && <th className="text-right py-2">Delta</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ label, key, fmt: fmtFn, better }) => (
              <tr key={key} className="border-b border-gray-50">
                <td className="py-2 pr-4 text-onSurfaceDim">{label}</td>
                <td className="py-2 pr-4 text-right text-onSurface font-bold">
                  {qm ? fmtFn(qm[key]) : '—'}
                </td>
                <td className="py-2 pr-4 text-right text-onSurface font-bold">
                  {hm ? fmtFn(hm[key]) : '—'}
                </td>
                {qm && hm && (
                  <td className={`py-2 text-right font-bold ${deltaColor(key, better)}`}>
                    {fmtDelta(key, fmtFn, better)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
