import { useState, useCallback, useRef } from 'react'

/**
 * useStreamingSimulation — WebSocket-based simulation with real-time events.
 *
 * Instead of one big POST response, streams events as agents complete:
 *   simulation_start → round_start → agent_result* → round_complete → ... → aggregation → simulation_end
 *
 * Returns the same final `result` shape as useSimulation, plus:
 *   - events: array of all streamed events (for the live feed)
 *   - currentRound: which round is running (1/2/3)
 *   - completedAgents: map of agent_name → latest response per round
 *   - streamStatus: 'idle' | 'connecting' | 'streaming' | 'done' | 'error'
 */
export function useStreamingSimulation() {
  const [result, setResult] = useState(null)
  const [events, setEvents] = useState([])
  const [currentRound, setCurrentRound] = useState(0)
  const [completedAgents, setCompletedAgents] = useState({})
  const [aggregation, setAggregation] = useState(null)
  const [streamStatus, setStreamStatus] = useState('idle')
  const [error, setError] = useState(null)
  const wsRef = useRef(null)

  const simulate = useCallback((data) => {
    return new Promise((resolve, reject) => {
      // Reset state
      setEvents([])
      setCurrentRound(0)
      setCompletedAgents({})
      setAggregation(null)
      setResult(null)
      setError(null)
      setStreamStatus('connecting')

      // Determine WS URL.
      // In production: VITE_WS_BASE = "wss://your-railway-backend.railway.app"
      // In local dev: falls back to same-host (Vite proxy handles /api/simulate/stream)
      const wsBase = import.meta.env.VITE_WS_BASE
      const wsUrl = wsBase
        ? `${wsBase}/api/simulate/stream`
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/simulate/stream`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      let allEvents = []
      let finalResult = null

      ws.onopen = () => {
        setStreamStatus('streaming')
        // Send the simulation request
        ws.send(JSON.stringify(data))
      }

      ws.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data)
          allEvents = [...allEvents, event]
          setEvents([...allEvents])

          switch (event.type) {
            case 'simulation_start':
              break

            case 'round_start':
              setCurrentRound(event.round)
              break

            case 'agent_result':
              setCompletedAgents((prev) => ({
                ...prev,
                [`${event.agent_name}_r${event.round}`]: event,
                [event.agent_name]: event, // Latest for this agent
              }))
              break

            case 'round_complete':
            case 'round_skipped':
              break

            case 'aggregation':
              setAggregation(event)
              break

            case 'simulation_end':
              // Build a result object compatible with the existing UI
              finalResult = buildResultFromEvents(allEvents)
              setResult(finalResult)
              setStreamStatus('done')
              break

            case 'error':
              setError(event.message)
              setStreamStatus('error')
              break

            default:
              break
          }
        } catch {
          // Ignore parse errors
        }
      }

      ws.onerror = () => {
        setError('WebSocket connection failed')
        setStreamStatus('error')
        reject(new Error('WebSocket connection failed'))
      }

      ws.onclose = () => {
        wsRef.current = null
        if (finalResult) {
          resolve(finalResult)
        } else if (streamStatus !== 'error') {
          // Closed without a result — might be an error
          setStreamStatus('done')
          resolve(null)
        }
      }
    })
  }, [])

  const reset = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setResult(null)
    setEvents([])
    setCurrentRound(0)
    setCompletedAgents({})
    setAggregation(null)
    setStreamStatus('idle')
    setError(null)
  }, [])

  return {
    simulate,
    result,
    events,
    currentRound,
    completedAgents,
    aggregation,
    streamStatus,
    isLoading: streamStatus === 'connecting' || streamStatus === 'streaming',
    error,
    reset,
  }
}


/**
 * Build a result object from streamed events that matches
 * the shape returned by POST /api/simulate (for compatibility
 * with existing Dashboard components).
 */
function buildResultFromEvents(events) {
  const simStart = events.find((e) => e.type === 'simulation_start')
  const simEnd = events.find((e) => e.type === 'simulation_end')
  const agg = events.find((e) => e.type === 'aggregation')

  // Build agents_output from the latest agent_result per agent
  const agentsOutput = {}
  const agentResults = events.filter((e) => e.type === 'agent_result')
  for (const ar of agentResults) {
    // Keep the latest round's result for each agent
    agentsOutput[ar.agent_name] = {
      agent_name: ar.agent_name,
      agent_type: ar.agent_type,
      direction: ar.direction,
      conviction: ar.conviction,
      reasoning: ar.reasoning,
      key_triggers: ar.key_triggers,
      time_horizon: ar.time_horizon,
    }
  }

  // Build round_history
  const roundHistory = []
  const roundStarts = events.filter((e) => e.type === 'round_start')
  for (const rs of roundStarts) {
    const roundAgents = agentResults.filter((a) => a.round === rs.round)
    roundHistory.push({
      round: rs.round,
      agents: Object.fromEntries(
        roundAgents.map((a) => [a.agent_name, {
          direction: a.direction,
          conviction: a.conviction,
          type: a.agent_type,
        }])
      ),
    })
  }

  return {
    simulation_id: simEnd?.simulation_id || simStart?.simulation_id || '',
    execution_time_ms: simEnd?.execution_time_ms || 0,
    model_used: simEnd?.model_used || '',
    feedback_active: simEnd?.feedback_active || false,
    data_source: simEnd?.data_source || 'fallback',
    agents_output: agentsOutput,
    round_history: roundHistory,
    aggregator_result: agg ? {
      final_direction: agg.final_direction,
      final_conviction: agg.final_conviction,
      consensus_score: agg.consensus_score,
      conflict_level: agg.conflict_level,
      quant_llm_agreement: agg.quant_llm_agreement,
      agent_breakdown: agg.agent_breakdown,
    } : null,
  }
}
