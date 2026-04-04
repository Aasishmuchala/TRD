import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import { apiClient } from '../api/client'
import { AGENTS, AGENT_COLORS, AGENT_DISPLAY_NAMES } from '../constants/agents'

export default function Skills() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [learningEnabled, setLearningEnabled] = useState(true)
  const [toggling, setToggling] = useState(false)

  const fetchSkills = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiClient.getSkills()
      setData(result)
      setLearningEnabled(result.learning_enabled ?? true)
    } catch (err) {
      setError(err.message || 'Failed to load skills')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSkills()
  }, [])

  const handleToggle = async () => {
    setToggling(true)
    try {
      await apiClient.toggleLearning(!learningEnabled)
      setLearningEnabled((prev) => !prev)
    } catch {
      // Ignore — not critical
    } finally {
      setToggling(false)
    }
  }

  const getAgentSkills = (agentId) => {
    if (!data?.skills) return []
    const entry = data.skills.find((s) => s.agent_id === agentId)
    return entry?.skills || []
  }

  const getAgentSkillCount = (agentId) => {
    if (!data?.skills) return 0
    const entry = data.skills.find((s) => s.agent_id === agentId)
    return entry?.skill_count ?? 0
  }

  return (
    <Layout>
      <div className="p-5 h-[calc(100vh-2.5rem)] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-xl font-bold text-onSurface">Learning / Skills</h1>
            <p className="text-[10px] font-mono text-onSurfaceDim mt-0.5">
              {data ? `${data.total_skills} pattern${data.total_skills !== 1 ? 's' : ''} extracted across all agents` : 'Extracting learned patterns from simulation history'}
            </p>
          </div>
          <button
            onClick={handleToggle}
            disabled={toggling || loading}
            className={`font-mono text-[10px] tracking-wider px-3 py-1.5 rounded-lg border transition-all ${
              learningEnabled
                ? 'bg-bull/10 text-bull border-bull/20 hover:bg-bull/20'
                : 'bg-surface-2 text-onSurfaceDim border-[rgba(255,255,255,0.06)] hover:bg-surface-3'
            } disabled:opacity-50`}
          >
            {toggling ? '...' : learningEnabled ? 'LEARNING ON' : 'LEARNING OFF'}
          </button>
        </div>

        {/* Error state */}
        {error && (
          <div className="terminal-card p-3 border-l-2 border-bear mb-4">
            <p className="text-xs font-mono text-bear">
              Could not load skills: {error}. Check that the backend is running.
            </p>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <span className="text-xs font-mono text-onSurfaceDim animate-pulse">LOADING SKILLS...</span>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && data?.total_skills === 0 && (
          <div className="terminal-card p-8 flex flex-col items-center gap-2">
            <span className="text-xs font-mono text-onSurfaceDim">NO PATTERNS LEARNED YET</span>
            <span className="text-[10px] font-mono text-onSurfaceDim text-center max-w-sm">
              Run simulations to build outcome history. Skills are extracted automatically after each simulation when learning is enabled.
            </span>
          </div>
        )}

        {/* Skills grid — one card per agent */}
        {!loading && !error && data?.total_skills > 0 && (
          <div className="grid grid-cols-2 gap-4">
            {AGENTS.map((agent) => {
              const color = AGENT_COLORS[agent.id]
              const skills = getAgentSkills(agent.id)
              const count = getAgentSkillCount(agent.id)

              return (
                <div key={agent.id} className="terminal-card p-4">
                  {/* Agent header */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-mono font-bold"
                        style={{ backgroundColor: `${color}15`, border: `1px solid ${color}30`, color }}
                      >
                        {agent.shortLabel}
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-onSurface">{AGENT_DISPLAY_NAMES[agent.id]}</p>
                      </div>
                    </div>
                    <span
                      className="text-[10px] font-mono font-bold px-2 py-0.5 rounded"
                      style={{ color, backgroundColor: `${color}15`, border: `1px solid ${color}25` }}
                    >
                      {count} skill{count !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {/* Skills list */}
                  {skills.length === 0 ? (
                    <p className="text-[10px] font-mono text-onSurfaceDim italic">
                      No patterns extracted yet for this agent.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {skills.slice(0, 5).map((skill, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-2 text-[10px] font-mono text-onSurfaceMuted"
                        >
                          <span className="mt-0.5 w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: color, marginTop: '5px' }} />
                          <span className="leading-relaxed">{typeof skill === 'string' ? skill : skill.text || JSON.stringify(skill)}</span>
                        </li>
                      ))}
                      {skills.length > 5 && (
                        <li className="text-[9px] font-mono text-onSurfaceDim pl-3">
                          +{skills.length - 5} more patterns
                        </li>
                      )}
                    </ul>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Layout>
  )
}
