import { agents as agentColors } from '../utils/colors'

export default function AgentPressureBar({ agentKey, label, pressure = 0.5, direction = 'neutral', conviction = 50 }) {
  const color = agentColors[agentKey] || '#8B95A5'
  const pct = Math.max(0, Math.min(100, pressure * 100))
  const dirLabel = direction === 'bullish' ? 'BUY' : direction === 'bearish' ? 'SELL' : 'HOLD'
  const dirColor = direction === 'bullish' ? '#00E676' : direction === 'bearish' ? '#FF1744' : '#FFC107'

  return (
    <div className="group flex items-center gap-3">
      {/* Agent dot + name */}
      <div className="flex items-center gap-2 w-24 flex-shrink-0">
        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}40` }}/>
        <span className="text-xs font-medium text-onSurfaceMuted group-hover:text-onSurface transition-colors truncate">
          {label}
        </span>
      </div>

      {/* Bar */}
      <div className="flex-1 h-1.5 bg-surface-3 rounded-full overflow-hidden relative">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${dirColor}80, ${dirColor})`,
            boxShadow: `0 0 8px ${dirColor}30`,
          }}
        />
      </div>

      {/* Value */}
      <div className="flex items-center gap-2 w-20 flex-shrink-0 justify-end">
        <span className="font-mono text-xs tabular-nums" style={{ color: dirColor }}>
          {pct.toFixed(0)}%
        </span>
        <span
          className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded"
          style={{
            color: dirColor,
            backgroundColor: `${dirColor}15`,
            border: `1px solid ${dirColor}25`,
          }}
        >
          {dirLabel}
        </span>
      </div>
    </div>
  )
}
