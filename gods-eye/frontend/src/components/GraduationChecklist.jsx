/**
 * GraduationChecklist — renders graduation criteria.
 * Props:
 *   criteria: Array of { metric, target, current, passed }
 *   If not provided, renders a generic "no data" state.
 */
export default function GraduationChecklist({ criteria = [] }) {
  const passedCount = criteria.filter(c => c.passed).length

  if (criteria.length === 0) {
    return (
      <div className="terminal-card p-4">
        <div className="section-header">Graduation Checklist</div>
        <p className="text-[10px] font-mono text-onSurfaceDim">No criteria data available</p>
      </div>
    )
  }

  return (
    <div className="terminal-card p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="section-header mb-0">Graduation Checklist</div>
        <span className="text-lg font-bold font-mono text-primary">{passedCount}/{criteria.length}</span>
      </div>

      <div className="space-y-2">
        {criteria.map((item) => (
          <div
            key={item.metric}
            className={`flex items-center gap-2.5 p-2.5 rounded-lg ${
              item.passed ? 'bg-bull/5 border border-bull/10' : 'bg-surface-2'
            }`}
          >
            <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 ${
              item.passed ? 'bg-bull' : 'border border-[rgba(255,255,255,0.15)]'
            }`}>
              {item.passed && <span className="text-[8px] text-black font-bold">OK</span>}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[11px] font-mono text-onSurface">{item.metric}</p>
              <p className="text-[9px] font-mono text-onSurfaceDim">{item.target}</p>
            </div>
            <span className={`text-[11px] font-mono ${item.passed ? 'text-bull' : 'text-onSurfaceMuted'}`}>
              {typeof item.current === 'number' ? item.current : item.current}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
