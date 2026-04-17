import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

export default function ScenarioModal({ scenario, onConfirm, onCancel }) {
  // Defaults when market is closed or API unavailable
  const DEFAULTS = {
    fii_net_today: -3200,
    fii_5day_avg: -8400,
    fii_futures_oi_change: -12,
    dii_net_today: 2100,
    dii_5day_avg: 6200,
    sip_inflow: 21000,
  }

  const [flowData, setFlowData] = useState(DEFAULTS)
  const [dataSource, setDataSource] = useState('defaults')

  // Auto-fetch latest market data to pre-fill flow fields
  useEffect(() => {
    apiClient.getMarketLive()
      .then((data) => {
        if (data && (data.fii_net_today || data.fii_flow_5d)) {
          setFlowData({
            fii_net_today: data.fii_net_today || DEFAULTS.fii_net_today,
            fii_5day_avg: data.fii_flow_5d || DEFAULTS.fii_5day_avg,
            fii_futures_oi_change: DEFAULTS.fii_futures_oi_change,
            dii_net_today: data.dii_net_today || DEFAULTS.dii_net_today,
            dii_5day_avg: data.dii_flow_5d || DEFAULTS.dii_5day_avg,
            sip_inflow: DEFAULTS.sip_inflow,
          })
          setDataSource('live')
        }
      })
      .catch(() => null) // TODO (FE-M9): Swallowed error — consider logging or showing fallback indicator
  }, [])

  const handleConfirm = () => {
    // Pass flowData back to parent along with confirmation
    onConfirm(flowData)
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onCancel}>
      <div className="terminal-card-lg p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
        <div className="section-header mb-3">Confirm Simulation</div>
        <p className="text-xs text-onSurfaceMuted mb-4">
          Running 6-agent, 3-round analysis with knowledge graph + memory layer.
        </p>

        {scenario && (
          <div className="bg-surface-2 rounded-lg p-3 mb-4 border border-[rgba(255,255,255,0.04)]">
            <p className="text-sm font-semibold text-onSurface">{scenario.name}</p>
            <p className="text-[11px] text-onSurfaceMuted mt-0.5">{scenario.description}</p>
          </div>
        )}

        {/* Flow Data */}
        <div className="mb-5">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] font-mono text-onSurfaceDim uppercase">Flow Data</div>
            <span className={`text-[8px] font-mono ${dataSource === 'live' ? 'text-bull' : 'text-neutral-bright'}`}>
              {dataSource === 'live' ? 'LIVE DATA' : 'RECENT ESTIMATES'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { key: 'fii_net_today',         label: 'FII Net (Today)',  placeholder: '₹ crore' },
              { key: 'fii_5day_avg',          label: 'FII 5-Day Avg',   placeholder: '₹ crore' },
              { key: 'fii_futures_oi_change', label: 'FII Futures OI Δ', placeholder: '% change' },
              { key: 'dii_net_today',         label: 'DII Net (Today)',  placeholder: '₹ crore' },
              { key: 'dii_5day_avg',          label: 'DII 5-Day Avg',   placeholder: '₹ crore' },
              { key: 'sip_inflow',            label: 'SIP Inflow',       placeholder: '₹ crore' },
            ].map(({ key, label, placeholder }) => (
              <div key={key}>
                <label className="block text-[9px] font-mono text-onSurfaceDim mb-0.5">{label}</label>
                <input
                  type="number"
                  value={flowData[key]}
                  onChange={(e) => setFlowData(prev => ({ ...prev, [key]: Number(e.target.value) || 0 }))}
                  placeholder={placeholder}
                  className="w-full px-2 py-1 text-[11px] font-mono bg-surface-2 border border-[rgba(255,255,255,0.08)] rounded text-onSurface placeholder-onSurfaceDim focus:outline-none focus:border-primary/40"
                />
              </div>
            ))}
          </div>
        </div>

        <div className="flex gap-3">
          <button onClick={onCancel} className="flex-1 btn-secondary text-xs font-mono">
            CANCEL
          </button>
          <button onClick={handleConfirm} className="flex-1 btn-primary text-xs font-mono">
            EXECUTE
          </button>
        </div>
      </div>
    </div>
  )
}
