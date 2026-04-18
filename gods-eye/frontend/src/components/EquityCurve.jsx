import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

/**
 * EquityCurve — renders cumulative P&L over a backtest period.
 * Props:
 *   days: Array<{ date, cumulative_pnl_points, pnl_points, predicted_direction, direction_correct }>
 *   onDayClick: (day) => void  — called when user clicks a data point (optional)
 */
export default function EquityCurve({ days = [], onDayClick }) {
  if (days.length === 0) {
    return (
      <div className="terminal-card p-4">
        <h2 className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider mb-3">
          Equity Curve — Cumulative P&L (pts)
        </h2>
        <div className="w-full h-[200px] flex items-center justify-center">
          <span className="text-[10px] font-mono text-onSurfaceDim">NO DATA YET</span>
        </div>
      </div>
    )
  }

  const chartData = days.map((d) => ({
    date: d.date.slice(5), // "MM-DD" compact label
    cumPnl: d.cumulative_pnl_points,
    rawDay: d,
  }))

  // Dynamic line color based on final cumulative P&L
  const lastCumPnl = chartData[chartData.length - 1]?.cumPnl ?? 0
  const lineColor = lastCumPnl > 0 ? '#059669' : lastCumPnl < 0 ? '#DC2626' : '#CC152B'

  const handleChartClick = (data) => {
    if (data?.activePayload?.[0]?.payload?.rawDay) {
      onDayClick?.(data.activePayload[0].payload.rawDay)
    }
  }

  // Custom dot: color each dot based on that day's pnl_points
  const renderDot = (props) => {
    const { cx, cy, payload } = props
    const pnl = payload?.rawDay?.pnl_points ?? 0
    const color = pnl > 0 ? '#059669' : pnl < 0 ? '#DC2626' : '#D97706'
    return <circle key={`dot-${payload.date}`} cx={cx} cy={cy} r={3} fill={color} strokeWidth={0} />
  }

  const renderActiveDot = (props) => {
    const { cx, cy, payload } = props
    const pnl = payload?.rawDay?.pnl_points ?? 0
    const color = pnl > 0 ? '#059669' : pnl < 0 ? '#DC2626' : '#D97706'
    return (
      <circle
        key={`active-dot-${payload.date}`}
        cx={cx}
        cy={cy}
        r={5}
        fill={color}
        strokeWidth={0}
        style={{ cursor: onDayClick ? 'pointer' : 'default' }}
      />
    )
  }

  return (
    <div className="terminal-card p-4">
      <h2 className="text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider mb-3">
        Equity Curve — Cumulative P&L (pts)
      </h2>
      <div className="w-full h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            onClick={handleChartClick}
            style={{ cursor: onDayClick ? 'pointer' : 'default' }}
          >
            <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              stroke="#9CA3AF"
              style={{ fontSize: '9px', fontFamily: "'Geist Mono', monospace" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#9CA3AF"
              style={{ fontSize: '9px', fontFamily: "'Geist Mono', monospace" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v > 0 ? '+' : ''}${v}`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #E5E7EB',
                borderRadius: '12px',
                fontSize: '11px',
                fontFamily: "'Geist Mono', monospace",
              }}
              labelStyle={{ color: '#6B7280' }}
              formatter={(value) => [`${value > 0 ? '+' : ''}${value} pts`, 'Cum. P&L']}
            />
            <ReferenceLine
              y={0}
              stroke="rgba(0,0,0,0.1)"
              strokeDasharray="3 3"
            />
            <Line
              type="monotone"
              dataKey="cumPnl"
              stroke={lineColor}
              strokeWidth={2}
              dot={renderDot}
              activeDot={renderActiveDot}
              isAnimationActive={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
