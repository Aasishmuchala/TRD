import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../api/client'

const PROVIDERS = [
  { key: 'openai', name: 'OpenAI (Codex)', icon: 'AI' },
  { key: 'nous', name: 'Nous Research', icon: 'NR' },
]

export default function AuthGate({ children }) {
  const [authStatus, setAuthStatus] = useState(null) // null = loading, object = status
  const [loginState, setLoginState] = useState(null) // null | { userCode, verificationUri, deviceCode, provider }
  const [polling, setPolling] = useState(false)
  const [error, setError] = useState(null)
  const pollTimer = useRef(null)

  // Check auth status on mount
  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const status = await apiClient.getAuthStatus()
      setAuthStatus(status)
    } catch (e) {
      setAuthStatus({ authenticated: false, mock_mode: true })
    }
  }

  const startLogin = async (provider) => {
    setError(null)
    try {
      const result = await apiClient.startLogin(provider)
      setLoginState({
        userCode: result.user_code,
        verificationUri: result.verification_uri,
        verificationUriComplete: result.verification_uri_complete,
        deviceCode: result.device_code,
        provider: provider,
        expiresIn: result.expires_in,
      })
      startPolling(result.device_code, provider)
    } catch (e) {
      setError(e.message)
    }
  }

  const startPolling = (deviceCode, provider) => {
    setPolling(true)
    let attempts = 0
    const maxAttempts = 120 // ~2 minutes at 1s intervals

    pollTimer.current = setInterval(async () => {
      attempts++
      if (attempts > maxAttempts) {
        clearInterval(pollTimer.current)
        setPolling(false)
        setError('Login timed out. Please try again.')
        setLoginState(null)
        return
      }

      try {
        const result = await apiClient.pollAuth(deviceCode, provider)
        if (result.status === 'authorized') {
          clearInterval(pollTimer.current)
          setPolling(false)
          setLoginState(null)
          await checkAuth()
        } else if (result.status === 'expired' || result.status === 'error') {
          clearInterval(pollTimer.current)
          setPolling(false)
          setError(result.message)
          setLoginState(null)
        }
        // "waiting" → continue polling
      } catch (e) {
        // Network error, continue polling
      }
    }, 2000)
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current)
    }
  }, [])

  const handleLogout = async () => {
    await apiClient.logout()
    await checkAuth()
  }

  const handleSkip = () => {
    setAuthStatus({ authenticated: false, mock_mode: true, skipped: true })
  }

  // Still checking auth
  if (authStatus === null) {
    return (
      <div className="min-h-screen bg-surface-0 flex items-center justify-center">
        <div className="flex items-center gap-3 text-onSurfaceDim" role="status" aria-live="polite" aria-label="Checking authentication status">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          <span className="text-xs font-mono">CHECKING AUTH...</span>
        </div>
      </div>
    )
  }

  // Authenticated or skipped → show app
  if (authStatus.authenticated || authStatus.skipped) {
    return children
  }

  // Login flow
  return (
    <div className="min-h-screen bg-surface-0 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
              <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6 text-primary">
                <circle cx="12" cy="12" r="3" fill="currentColor" />
                <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="text-xl font-bold text-onSurface tracking-tight">GOD'S EYE</span>
          </div>
          <p className="text-xs font-mono text-onSurfaceDim">Multi-Agent Indian Market Simulation</p>
        </div>

        {/* Login Card */}
        <div className="terminal-card-lg p-6">
          {loginState ? (
            // Device code display
            <div className="text-center">
              <div className="text-[10px] font-mono text-onSurfaceDim uppercase mb-4">
                Enter this code at the link below
              </div>

              {/* User Code */}
              <div className="bg-surface-2 rounded-lg p-4 border border-primary/20 mb-4">
                <div className="text-3xl font-mono font-bold text-primary tracking-[0.3em]">
                  {loginState.userCode}
                </div>
              </div>

              {/* Verification Link */}
              <a
                href={loginState.verificationUriComplete || loginState.verificationUri}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 transition-colors text-xs font-mono"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
                OPEN VERIFICATION PAGE
              </a>

              {/* Polling indicator */}
              {polling && (
                <div className="flex items-center justify-center gap-2 mt-4 text-onSurfaceDim" role="status" aria-live="polite" aria-label="Waiting for authorization">
                  <div className="flex gap-1">
                    <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} aria-hidden="true" />
                    <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} aria-hidden="true" />
                    <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} aria-hidden="true" />
                  </div>
                  <span className="text-[10px] font-mono">Waiting for authorization...</span>
                </div>
              )}

              <button
                onClick={() => { setLoginState(null); setPolling(false); if (pollTimer.current) clearInterval(pollTimer.current) }}
                className="mt-4 text-[10px] font-mono text-onSurfaceDim hover:text-onSurface transition-colors"
              >
                Cancel
              </button>
            </div>
          ) : (
            // Provider selection
            <>
              <div className="text-[10px] font-mono text-onSurfaceDim uppercase mb-4 text-center">
                Connect LLM Provider
              </div>

              <div className="space-y-2 mb-4">
                {PROVIDERS.map((p) => (
                  <button
                    key={p.key}
                    onClick={() => startLogin(p.key)}
                    aria-label={`Login with ${p.name}`}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-lg bg-surface-2 border border-[rgba(255,255,255,0.06)] hover:border-primary/20 hover:bg-surface-2/80 transition-all text-left"
                  >
                    <div className="w-8 h-8 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center text-[10px] font-mono font-bold text-primary">
                      {p.icon}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-onSurface">{p.name}</p>
                      <p className="text-[10px] text-onSurfaceDim">Device code login</p>
                    </div>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4 text-onSurfaceDim ml-auto">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </button>
                ))}
              </div>

              {error && (
                <div className="mb-4 px-3 py-2 rounded-lg bg-bear/10 border border-bear/20 text-[10px] font-mono text-bear" role="alert">
                  {error}
                </div>
              )}

              {/* Divider */}
              <div className="flex items-center gap-2 my-4">
                <span className="flex-1 h-px bg-[rgba(255,255,255,0.06)]" />
                <span className="text-[9px] font-mono text-onSurfaceDim">OR</span>
                <span className="flex-1 h-px bg-[rgba(255,255,255,0.06)]" />
              </div>

              {/* Skip to mock mode */}
              <button
                onClick={handleSkip}
                aria-label="Continue in mock mode without authentication"
                className="w-full px-4 py-2.5 rounded-lg border border-[rgba(255,255,255,0.06)] text-xs font-mono text-onSurfaceDim hover:text-onSurface hover:border-[rgba(255,255,255,0.12)] transition-all text-center"
              >
                Continue in Mock Mode
              </button>
              <p className="text-[9px] font-mono text-onSurfaceDim text-center mt-2">
                Uses deterministic mock responses — no API key required
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
