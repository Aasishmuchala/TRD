import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

/**
 * AccuracyChart — renders conviction trend from simulation history.
 * Props:
 *   history: Array of simulation history items (from /api/history)
 */
export default function AccuracyChart({ history = [] }) {
  // Build chart data from real history — show conviction trend per sim
  const chartData = history
    .slice()
    .reverse() // oldest first
    .map((sim, idx) => {
      const agg = sim.aggregator_result || {}
      const ts = sim.timestamp ? new Date(sim.timestamp) : null
      return {
        label: ts
          ? ts.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
          : `#${idx + 1}`,
        conviction: typeof agg.final_conviction === 'number'
          ? Math.round(agg.final_conviction)
          : 50,
      }
    })
    .slice(-15) // last 15 data points

  if (chartData.length === 0) {
    return (
      <div className="w-full h-48 flex items-center justify-center">
        <span className="text-[10px] font-mono text-onSurfaceDim">NO DATA YET</span>
      </div>
    )
  }

  return (
    <div className="w-full h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
          <XAxis
            dataKey="label"
            stroke="#5A6070"
            style={{ fontSize: '9px', fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            stroke="#5A6070"
            style={{ fontSize: '9px', fontFamily: 'JetBrains Mono' }}
            domain={[0, 100]}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(14,14,19,0.95)',
              border: '1px solid rgba(0,212,224,0.2)',
              borderRadius: '8px',
              fontSize: '11px',
              fontFamily: 'JetBrains Mono',
            }}
            labelStyle={{ color: '#8B95A5' }}
            formatter={(value) => [`${value}%`, 'Conviction']}
          />
          <Line
            type="monotone"
            dataKey="conviction"
            stroke="#00D4E0"
            strokeWidth={2}
            dot={{ fill: '#00D4E0', r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: '#00F0FF' }}
            isAnimationActive={true}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
