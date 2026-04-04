import { useState, useCallback, useRef } from 'react'

/**
 * useStreamingSimulation — SSE-based simulation with real-time events.
 *
 * Uses Server-Sent Events (SSE) via fetch + ReadableStream instead of WebSocket.
 * SSE works through HTTP proxies and tunnel services where WebSocket fails.
 *
 * Streams events as agents complete:
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
  const abortRef = useRef(null)

  const simulate = useCallback(async (data) => {
    // Reset state
    setEvents([])
    setCurrentRound(0)
    setCompletedAgents({})
    setAggregation(null)
    setResult(null)
    setError(null)
    setStreamStatus('connecting')

    // Abort any previous in-flight request
    if (abortRef.current) {
      abortRef.current.abort()
    }
    const controller = new AbortController()
    abortRef.current = controller

    const apiBase = import.meta.env.VITE_API_BASE || '/api'
    const url = `${apiBase}/simulate/stream-sse`

    // Auth header
    const headers = { 'Content-Type': 'application/json' }
    const apiKey = localStorage.getItem('godsEyeApiKey')
    if (apiKey) {
      headers['Authorization'] = `Bearer ${apiKey}`
    }

    let allEvents = []
    let finalResult = null

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(data),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      setStreamStatus('streaming')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE lines: "data: {...}\n\n"
        const lines = buffer.split('\n')
        buffer = lines.pop() // Keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6) // Remove "data: " prefix
          if (!jsonStr.trim()) continue

          try {
            const event = JSON.parse(jsonStr)
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
                  [event.agent_name]: event,
                }))
                break

              case 'round_complete':
              case 'round_skipped':
                break

              case 'aggregation':
                setAggregation(event)
                break

              case 'simulation_end':
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
            // Ignore parse errors for individual lines
          }
        }
      }

      // If stream ended without simulation_end, build result from what we have
      if (!finalResult && allEvents.length > 0) {
        finalResult = buildResultFromEvents(allEvents)
        setResult(finalResult)
        setStreamStatus('done')
      }

      return finalResult
    } catch (err) {
      if (err.name === 'AbortError') return null
      setError(err.message || 'Simulation failed')
      setStreamStatus('error')
      throw err
    }
  }, [])

  const reset = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
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
