import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'

export default function AuthGate({ children }) {
  const navigate = useNavigate()
  const [checked, setChecked] = useState(false)
  const [authed, setAuthed] = useState(false)

  useEffect(() => {
    const key = localStorage.getItem('godsEyeApiKey')
    if (key) {
      // Already have a key stored — proceed
      setAuthed(true)
      setChecked(true)
      return
    }

    // No key in localStorage — probe the backend.
    // If the backend has LLM_API_KEY configured it will respond 200
    // without any Bearer token (api_key_mode). In that case, auto-auth.
    apiClient.getHealth()
      .then(() => {
        localStorage.setItem('godsEyeApiKey', 'server-managed')
        setAuthed(true)
        setChecked(true)
      })
      .catch(() => {
        // Backend unreachable or requires a key — send to welcome
        setChecked(true)
        navigate('/welcome', { replace: true })
      })
  }, [navigate])

  if (!checked) {
    // Still probing backend — show nothing to avoid flash
    return null
  }

  if (!authed) {
    return null
  }

  return children
}
