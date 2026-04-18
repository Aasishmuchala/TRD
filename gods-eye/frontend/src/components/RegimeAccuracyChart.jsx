import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { AGENT_COLORS } from '../constants/agents'

const REGIME_LABELS = {
  low_vix: 'Low VIX (<15)',
  normal_vix: 'Normal (15-20)',
  elevated_vix: 'Elevated (20-30)',
  high_vix: 'High VIX (>30)',
}

export default function RegimeAccuracyChart({ regimeAccuracy }) {
  if (!regimeAccuracy || Object.keys(regimeAccuracy).length === 0) return null

  // Check if there's any data at all
  const hasData = Object.values(regimeAccuracy).some(
    (agents) => agents && Object.keys(agents).length > 0
  )
  if (!hasData) return null

  // Collect all agent names across all regimes
  const allAgents = new Set()
  Object.values(regimeAccuracy).forEach((agents) => {
    if (agents) Object.keys(agents).forEach((a) => allAgents.add(a))
  })

  // Build chart data: one row per regime
  const chartData = Object.entries(REGIME_LABELS).map(([key, label]) => {
    const agents = regimeAccuracy[key] || {}
    const row = { regime: label }
    allAgents.forEach((agent) => {
      row[agent] = agents[agent] !== undefined ? Math.round(agents[agent] * 100) : null
    })
    return row
  })

  // Only show regimes that have data
  const filteredData = chartData.filter((row) =>
    [...allAgents].some((a) => row[a] !== null && row[a] !== undefined)
  )

  if (filteredData.length === 0) return null

  return (
    <div className="terminal-card p-4">
      <div className="section-header mb-3">Agent Accuracy by VIX Regime</div>
      <p className="text-[10px] font-mono text-onSurfaceDim mb-4">
        Per-agent direction accuracy (%) grouped by India VIX level at time of prediction
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={filteredData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis
            dataKey="regime"
            tick={{ fontSize: 10, fontFamily: 'monospace', fill: 'rgba(0,0,0,0.4)' }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 10, fontFamily: 'monospace', fill: 'rgba(0,0,0,0.4)' }}
            label={{
              value: 'Accuracy %',
              angle: -90,
              position: 'insideLeft',
              style: { fontSize: 10, fontFamily: 'monospace', fill: 'rgba(0,0,0,0.3)' },
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #E5E7EB',
              borderRadius: '12px',
              fontSize: '10px',
              fontFamily: 'monospace',
            }}
            formatter={(value) => (value !== null ? `${value}%` : 'N/A')}
          />
          <Legend
            wrapperStyle={{ fontSize: '10px', fontFamily: 'monospace' }}
          />
          {[...allAgents].map((agent) => (
            <Bar
              key={agent}
              dataKey={agent}
              fill={AGENT_COLORS[agent] || '#6b7280'}
              fillOpacity={0.8}
              radius={[2, 2, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
