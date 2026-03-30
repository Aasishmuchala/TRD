import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export default function AuthGate({ children }) {
  const navigate = useNavigate()

  useEffect(() => {
    const key = localStorage.getItem('godsEyeApiKey')
    if (!key) {
      navigate('/welcome', { replace: true })
    }
  }, [navigate])

  const key = localStorage.getItem('godsEyeApiKey')
  if (!key) {
    // Render nothing while redirecting — avoid flash of protected content
    return null
  }

  return children
}
