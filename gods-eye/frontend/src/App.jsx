import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/Layout'
import Welcome from './pages/Welcome'
import Dashboard from './pages/Dashboard'
import AgentDetail from './pages/AgentDetail'
import SimulationHistory from './pages/SimulationHistory'
import Backtest from './pages/Backtest'
import PaperTrading from './pages/PaperTrading'
import Settings from './pages/Settings'
import Skills from './pages/Skills'
import Signal from './pages/Signal'
import Performance from './pages/Performance'

// TODO (FE-H4): All routes are public. Add AuthGate wrapper once auth state is stable.
// TODO (FE-L2): Add React.lazy() for route-level code splitting once imports are stable.
// TODO (FE-L8): Minimal test coverage — add unit tests for critical paths (simulation, API client, agents).

export default function App() {
  return (
    <ErrorBoundary>
      <Router>
        <Routes>
          <Route path="/welcome" element={<Welcome />} />
          <Route path="/*" element={
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/agents" element={<AgentDetail />} />
                <Route path="/history" element={<SimulationHistory />} />
                <Route path="/backtest" element={<Backtest />} />
                <Route path="/paper-trading" element={<PaperTrading />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/skills" element={<Skills />} />
                <Route path="/signal" element={<Signal />} />
                <Route path="/performance" element={<Performance />} />
                <Route path="*" element={
                  <div style={{ padding: '2rem', textAlign: 'center' }}>
                    <h2>Page Not Found</h2>
                    <p>The page you're looking for doesn't exist.</p>
                  </div>
                } />
              </Routes>
            </Layout>
          } />
        </Routes>
      </Router>
    </ErrorBoundary>
  )
}
