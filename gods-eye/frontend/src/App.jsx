import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import AuthGate from './components/AuthGate'
import Welcome from './pages/Welcome'
import Dashboard from './pages/Dashboard'
import AgentDetail from './pages/AgentDetail'
import SimulationHistory from './pages/SimulationHistory'
import Backtest from './pages/Backtest'
import PaperTrading from './pages/PaperTrading'
import Settings from './pages/Settings'
import Skills from './pages/Skills'

export default function App() {
  return (
    <ErrorBoundary>
      <Router>
        <Routes>
          {/* Public route — no auth required */}
          <Route path="/welcome" element={<Welcome />} />

          {/* Protected routes — AuthGate redirects to /welcome if unauthenticated */}
          <Route path="/*" element={
            <AuthGate>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/agents" element={<AgentDetail />} />
                <Route path="/history" element={<SimulationHistory />} />
                <Route path="/backtest" element={<Backtest />} />
                <Route path="/paper-trading" element={<PaperTrading />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/skills" element={<Skills />} />
              </Routes>
            </AuthGate>
          } />
        </Routes>
      </Router>
    </ErrorBoundary>
  )
}
