import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'

export default function AuthGate({ children }) {
  const navigate = useNavigate()
  const [checked, setChecked] = useState(false)
  const [authed, setAuthed] = useState(false)

  useEffect(() => {
    const key = localStorage.getItem('godsEyeApiKey')
    if (!key) {
      navigate('/welcome', { replace: true })
      setChecked(true)
      return
    }

    // Have a PIN stored — verify it against a protected endpoint.
    // Any 401 means the PIN is wrong (either rotated server-side or user
    // tampered with localStorage). Bounce to /welcome so they re-enter it.
    apiClient.getPresets()
      .then(() => {
        setAuthed(true)
        setChecked(true)
      })
      .catch((err) => {
        // Only clear on auth-style errors, not transient network issues —
        // otherwise a flaky connection logs the user out.
        const msg = (err?.message || '').toLowerCase()
        if (msg.includes('invalid') || msg.includes('pin') || msg.includes('unauthorized') || msg.includes('401')) {
          localStorage.removeItem('godsEyeApiKey')
          navigate('/welcome', { replace: true })
        } else {
          // Network error — let the user in; individual pages will surface
          // the error on their own API calls.
          setAuthed(true)
        }
        setChecked(true)
      })
  }, [navigate])

  if (!checked) {
    return null
  }

  if (!authed) {
    return null
  }

  return children
}
