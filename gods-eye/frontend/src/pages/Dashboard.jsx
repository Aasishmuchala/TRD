import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import ScenarioPanel from '../components/ScenarioPanel'
import PressurePanel from '../components/PressurePanel'
import InsightsPanel from '../components/InsightsPanel'
import AccuracyPanel from '../components/AccuracyPanel'
import FeedbackPanel from '../components/FeedbackPanel'
import ScenarioModal from '../components/ScenarioModal'
import SimulationStream from '../components/SimulationStream'
import TradeAlert from '../components/TradeAlert'
import { useStreamingSimulation } from '../hooks/useStreamingSimulation'

export default function Dashboard() {
  const {
    simulate, result, isLoading, error,
    events, currentRound, completedAgents, aggregation, streamStatus,
  } = useStreamingSimulation()
  const [showModal, setShowModal] = useState(false)
  const [selectedScenario, setSelectedScenario] = useState(null)
  const [toast, setToast] = useState(null)
  const [dismissedFallback, setDismissedFallback] = useState(false)

  // Reset fallback banner dismissal when a new result arrives
  useEffect(() => {
    if (result) setDismissedFallback(false)
  }, [result])

  const handleSimulateClick = (data) => {
    setSelectedScenario(data)
    setShowModal(true)
  }

  const handleConfirm = async (flowData) => {
    setShowModal(false)
    try {
      // Merge flowData (from ScenarioModal) into the scenario payload when present
      const payload = flowData ? { ...selectedScenario, flow_data: flowData } : selectedScenario
      await simulate(payload)
      setToast({ message: 'Simulation complete', type: 'success' })
      setTimeout(() => setToast(null), 3000)
    } catch (err) {
      setToast({ message: `Simulation failed: ${err.message}`, type: 'error' })
      setTimeout(() => setToast(null), 5000)
    }
  }

  const showStream = streamStatus === 'streaming' || streamStatus === 'connecting'

  return (
    <Layout>
      <div className="p-4 space-y-4 max-h-[calc(100vh-2.5rem)] overflow-auto relative">
        {/* NSE Fallback Banner — shown when market data is not live */}
        {result?.data_source === 'fallback' && !dismissedFallback && (
          <div
            role="alert"
            className="flex items-center justify-between px-4 py-2 rounded-lg text-xs font-mono border bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
          >
            <span>
              <span className="font-bold uppercase tracking-wide mr-2">DATA: FALLBACK</span>
              NSE live data unavailable — simulation used mock market values. Results may not reflect current conditions.
            </span>
            <button
              onClick={() => setDismissedFallback(true)}
              className="ml-4 text-yellow-400/60 hover:text-yellow-400 transition-colors"
              aria-label="Dismiss fallback warning"
            >
              ✕
            </button>
          </div>
        )}

        {/* Toast notification */}
        {toast && (
          <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg text-xs font-mono shadow-lg border transition-all ${
            toast.type === 'success' ? 'bg-bull/10 text-bull border-bull/20' :
            toast.type === 'error' ? 'bg-bear/10 text-bear border-bear/20' :
            'bg-primary/10 text-primary border-primary/20'
          }`}>
            {toast.message}
          </div>
        )}

        {/* Streaming Overlay — replaces the old static loading spinner */}
        {showStream && (
          <div className="fixed inset-0 z-40 flex items-center justify-center bg-surface-0/80 backdrop-blur-sm overflow-auto py-8">
            <div className="w-full max-w-3xl mx-4">
              <SimulationStream
                events={events}
                currentRound={currentRound}
                completedAgents={completedAgents}
                aggregation={aggregation}
                streamStatus={streamStatus}
              />
            </div>
          </div>
        )}

        {/* Top Row: Scenario | Pressure Map | Signal Intel */}
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-3">
            <ScenarioPanel onSimulate={handleSimulateClick} isLoading={isLoading} />
          </div>
          <div className="col-span-5">
            <PressurePanel result={result} isLoading={isLoading} />
          </div>
          <div className="col-span-4">
            <InsightsPanel result={result} isLoading={isLoading} />
          </div>
        </div>

        {/* Streaming results panel (visible after simulation completes) */}
        {streamStatus === 'done' && events.length > 0 && (
          <SimulationStream
            events={events}
            currentRound={currentRound}
            completedAgents={completedAgents}
            aggregation={aggregation}
            streamStatus={streamStatus}
          />
        )}

        {/* Trade Alert — surfaces when conviction filter passes */}
        {result && (
          <TradeAlert simulationResult={result} capital={10000} />
        )}

        {/* Bottom Row: Accuracy | Feedback Engine */}
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-7">
            <AccuracyPanel />
          </div>
          <div className="col-span-5">
            <FeedbackPanel />
          </div>
        </div>

        {/* Error bar (fallback if toast missed) */}
        {error && !toast && (
          <div className="terminal-card p-3 border-l-2 border-bear">
            <p className="text-xs font-mono text-bear">{error}</p>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {showModal && (
        <ScenarioModal
          scenario={selectedScenario}
          onConfirm={handleConfirm}
          onCancel={() => setShowModal(false)}
        />
      )}
    </Layout>
  )
}
