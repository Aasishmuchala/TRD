export default function ScenarioModal({ scenario, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onCancel}>
      <div className="terminal-card-lg p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
        <div className="section-header mb-3">Confirm Simulation</div>
        <p className="text-xs text-onSurfaceMuted mb-4">
          Running 6-agent, 3-round analysis with knowledge graph + memory layer.
        </p>

        {scenario && (
          <div className="bg-surface-2 rounded-lg p-3 mb-5 border border-[rgba(255,255,255,0.04)]">
            <p className="text-sm font-semibold text-onSurface">{scenario.name}</p>
            <p className="text-[11px] text-onSurfaceMuted mt-0.5">{scenario.description}</p>
          </div>
        )}

        <div className="flex gap-3">
          <button onClick={onCancel} className="flex-1 btn-secondary text-xs font-mono">
            CANCEL
          </button>
          <button onClick={onConfirm} className="flex-1 btn-primary text-xs font-mono">
            EXECUTE
          </button>
        </div>
      </div>
    </div>
  )
}
