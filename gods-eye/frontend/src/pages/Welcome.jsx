import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { AGENTS } from '../constants/agents'

export default function Welcome() {
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!apiKey.trim()) {
      setError('API key is required')
      return
    }
    localStorage.setItem('godsEyeApiKey', apiKey)
    navigate('/dashboard')
  }

  const handleMockMode = async () => {
    setLoading(true)
    setError('')
    try {
      await apiClient.getHealth()
      localStorage.setItem('godsEyeApiKey', 'mock-mode')
      apiClient.simulate({ scenario_id: 'rbi_rate_cut' }).catch(() => {})
      navigate('/dashboard')
    } catch (err) {
      setError('Backend not reachable. Start the server first.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-white flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center shadow-btn">
            <svg viewBox="0 0 24 24" fill="none" className="w-9 h-9">
              <circle cx="12" cy="12" r="10" stroke="#fff" strokeWidth="2"/>
              <circle cx="12" cy="12" r="4" fill="#fff"/>
              <path d="M12 2v4M12 18v4M2 12h4M18 12h4" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
        </div>

        {/* Title */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-onSurface tracking-wide mb-1">GOD'S EYE</h1>
          <p className="text-xs font-mono text-primary uppercase tracking-widest">Multi-Agent Market Intel</p>
        </div>

        {/* Agent network mini */}
        <div className="flex justify-center gap-2 mb-8">
          {AGENTS.map((agent) => (
            <div
              key={agent.id}
              className="w-9 h-9 rounded-xl flex items-center justify-center text-[8px] font-mono font-bold border"
              style={{
                backgroundColor: `${agent.color}08`,
                borderColor: `${agent.color}20`,
                color: agent.color
              }}
            >
              {agent.shortLabel}
            </div>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3 mb-4">
          <div>
            <label className="block text-[10px] font-mono text-onSurfaceMuted uppercase tracking-wider mb-1.5">
              Anthropic API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => { setApiKey(e.target.value); setError('') }}
              placeholder="sk-ant-..."
              className="input-field font-mono text-sm"
            />
          </div>
          <button type="submit" className="w-full btn-primary font-mono text-xs tracking-wider">
            CONNECT
          </button>
        </form>

        {/* Mock mode */}
        <button
          onClick={handleMockMode}
          disabled={loading}
          className="w-full btn-secondary font-mono text-xs tracking-wider disabled:opacity-50"
        >
          {loading ? 'CONNECTING...' : 'ENTER MOCK MODE'}
        </button>

        {error && (
          <p className="text-center text-[10px] text-bear font-mono mt-3">{error}</p>
        )}

        <p className="text-center text-[10px] font-mono text-onSurfaceDim mt-6">
          Mock mode uses deterministic responses. No API key required.
        </p>
      </div>
    </div>
  )
}
