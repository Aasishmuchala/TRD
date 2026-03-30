import { useState, useCallback } from 'react'
import { apiClient } from '../api/client'

export function useSimulation() {
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const simulate = useCallback(async (data) => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await apiClient.simulate(data)
      setResult(response)
      return response
    } catch (err) {
      const message = err.message || 'Simulation failed'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setResult(null)
    setError(null)
  }, [])

  return { simulate, result, isLoading, error, reset }
}
