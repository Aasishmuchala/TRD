import { useState } from 'react'

const AGENT_LABELS = {
  FII: 'FII',
  DII: 'DII',
  RETAIL_FNO: 'Retail F&O',
  ALGO_QUANT: 'Algo/Quant',
  PROMOTER: 'Promoter',
  RBI: 'RBI',
}

const AGENT_COLORS = {
  FII: '#FF6B6B',
  DII: '#00E676',
  RETAIL_FNO: '#FFD740',
  ALGO_QUANT: '#00D4E0',
  PROMOTER: '#BB86FC',
  RBI: '#448AFF',
}

export default function AgentAccuracyTable({ perAgentAccuracy }) {
  const [sortAsc, setSortAsc] = useState(false)

  if (!perAgentAccuracy) return null

  const rows = Object.entries(perAgentAccuracy)
    .map(([key, accuracy]) => ({
      key,
      label: AGENT_LABELS[key] || key,
      color: AGENT_COLORS[key] || '#888888',
      accuracy,
    }))
    .sort((a, b) => sortAsc ? a.accuracy - b.accuracy : b.accuracy - a.accuracy)

  return (
    <div className="terminal-card p-4">
      <div className="mb-3">
        <h2 className="text-xs font-mono text-onSurfaceDim uppercase tracking-wider">Agent Accuracy</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[rgba(255,255,255,0.06)]">
              <th className="text-left pb-2 text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider">
                Agent
              </th>
              <th
                className="text-right pb-2 text-[10px] font-mono text-onSurfaceDim uppercase tracking-wider cursor-pointer select-none hover:text-onSurface transition-colors"
                onClick={() => setSortAsc((v) => !v)}
              >
                Accuracy {sortAsc ? '▲' : '▼'}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const pct = (row.accuracy * 100).toFixed(1)
              const isGood = row.accuracy >= 0.5
              return (
                <tr key={row.key} className="border-b border-[rgba(255,255,255,0.04)] last:border-0">
                  <td className="py-2.5 pr-4">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: row.color }}
                      />
                      <span className="text-[11px] text-onSurface">{row.label}</span>
                    </div>
                  </td>
                  <td className="py-2.5 pl-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-surface-2 rounded h-1 min-w-[60px]">
                        <div
                          className="h-1 rounded transition-all"
                          style={{
                            width: `${row.accuracy * 100}%`,
                            backgroundColor: row.color,
                          }}
                        />
                      </div>
                      <span
                        className={`text-[11px] font-mono font-bold w-12 text-right ${
                          isGood ? 'text-bull' : 'text-bear'
                        }`}
                      >
                        {pct}%
                      </span>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
