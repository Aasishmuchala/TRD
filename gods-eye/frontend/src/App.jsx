import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import AuthGate from './components/AuthGate'
import Dashboard from './pages/Dashboard'
import AgentDetail from './pages/AgentDetail'
import SimulationHistory from './pages/SimulationHistory'
import PaperTrading from './pages/PaperTrading'
import Settings from './pages/Settings'

export default function App() {
  return (
    <ErrorBoundary>
      <AuthGate>
        <Router>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/agents" element={<AgentDetail />} />
            <Route path="/history" element={<SimulationHistory />} />
            <Route path="/paper-trading" element={<PaperTrading />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Router>
      </AuthGate>
    </ErrorBoundary>
  )
}
