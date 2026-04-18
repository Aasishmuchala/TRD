export default function DirectionGauge({ direction = 'neutral', magnitude = 0.5, confidence = 0.65 }) {
  const isBull = direction === 'bullish'
  const isBear = direction === 'bearish'
  const color = isBull ? '#059669' : isBear ? '#DC2626' : '#D97706'
  const label = isBull ? 'BULLISH' : isBear ? 'BEARISH' : 'NEUTRAL'
  const pct = Math.round(magnitude * 100)

  // Semicircle gauge params
  const radius = 38
  const cx = 50
  const cy = 50
  const circumference = Math.PI * radius
  const offset = circumference - (magnitude * circumference)

  return (
    <div className="flex flex-col items-center gap-3 py-4">
      {/* Gauge */}
      <div className="relative w-28 h-16">
        <svg className="w-full h-full" viewBox="0 0 100 55">
          {/* Background arc */}
          <path
            d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
            fill="none"
            stroke="rgba(0,0,0,0.06)"
            strokeWidth="5"
            strokeLinecap="round"
          />
          {/* Active arc */}
          <path
            d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
            fill="none"
            stroke={color}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{
              transition: 'stroke-dashoffset 0.8s ease-out, stroke 0.3s ease',
            }}
          />
          {/* Needle dot */}
          <circle
            cx={cx + radius * Math.cos(Math.PI - magnitude * Math.PI)}
            cy={cy - radius * Math.sin(magnitude * Math.PI)}
            r="3"
            fill={color}
          />
        </svg>

        {/* Center value */}
        <div className="absolute bottom-0 left-0 right-0 flex flex-col items-center">
          <span className="text-xl font-bold font-mono tabular-nums" style={{ color }}>
            {pct}%
          </span>
        </div>
      </div>

      {/* Label */}
      <div className="text-center">
        <p
          className="text-xs font-bold font-mono tracking-widest"
          style={{ color }}
        >
          {label}
        </p>
        <p className="text-[10px] text-onSurfaceDim mt-1 font-mono">
          CONF {Math.round(confidence * 100)}%
        </p>
      </div>
    </div>
  )
}
