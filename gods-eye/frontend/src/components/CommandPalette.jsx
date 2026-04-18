import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

const COMMANDS = [
  // Navigation
  { id: 'nav-dashboard',   label: 'Go to Dashboard',       category: 'Navigation', action: 'navigate', path: '/dashboard' },
  { id: 'nav-agents',      label: 'Go to Agents',          category: 'Navigation', action: 'navigate', path: '/agents' },
  { id: 'nav-signal',      label: 'Go to Signal',          category: 'Navigation', action: 'navigate', path: '/signal' },
  { id: 'nav-history',     label: 'Go to History',         category: 'Navigation', action: 'navigate', path: '/history' },
  { id: 'nav-backtest',    label: 'Go to Backtest',        category: 'Navigation', action: 'navigate', path: '/backtest' },
  { id: 'nav-performance', label: 'Go to Performance',     category: 'Navigation', action: 'navigate', path: '/performance' },
  { id: 'nav-trading',     label: 'Go to Paper Trading',   category: 'Navigation', action: 'navigate', path: '/paper-trading' },
  { id: 'nav-skills',      label: 'Go to Skills',          category: 'Navigation', action: 'navigate', path: '/skills' },
  { id: 'nav-settings',    label: 'Go to Settings',        category: 'Navigation', action: 'navigate', path: '/settings' },
  // Scenarios
  { id: 'sc-normal',       label: 'Scenario: Normal Day',        category: 'Scenarios', action: 'scenario', scenario: 'normal_day' },
  { id: 'sc-expiry',       label: 'Scenario: Expiry Day',        category: 'Scenarios', action: 'scenario', scenario: 'expiry_day' },
  { id: 'sc-budget',       label: 'Scenario: Budget Session',    category: 'Scenarios', action: 'scenario', scenario: 'budget_session' },
  { id: 'sc-rbi',          label: 'Scenario: RBI Policy',        category: 'Scenarios', action: 'scenario', scenario: 'rbi_policy' },
  { id: 'sc-crash',        label: 'Scenario: Flash Crash',       category: 'Scenarios', action: 'scenario', scenario: 'flash_crash' },
  { id: 'sc-global',       label: 'Scenario: Global Selloff',    category: 'Scenarios', action: 'scenario', scenario: 'global_selloff' },
]

export default function CommandPalette({ open, onClose }) {
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const navigate = useNavigate()

  const filtered = query.trim()
    ? COMMANDS.filter(cmd =>
        cmd.label.toLowerCase().includes(query.toLowerCase()) ||
        cmd.category.toLowerCase().includes(query.toLowerCase())
      )
    : COMMANDS

  const grouped = filtered.reduce((acc, cmd) => {
    if (!acc[cmd.category]) acc[cmd.category] = []
    acc[cmd.category].push(cmd)
    return acc
  }, {})

  const flatList = Object.values(grouped).flat()

  useEffect(() => {
    if (open) {
      setQuery('')
      setActiveIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  useEffect(() => {
    if (listRef.current && flatList.length > 0) {
      const activeEl = listRef.current.querySelector(`[data-index="${activeIndex}"]`)
      activeEl?.scrollIntoView({ block: 'nearest' })
    }
  }, [activeIndex, flatList.length])

  const executeCommand = useCallback((cmd) => {
    if (!cmd) return
    if (cmd.action === 'navigate') navigate(cmd.path)
    if (cmd.action === 'scenario') navigate('/dashboard')
    onClose()
  }, [navigate, onClose])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex(i => Math.min(i + 1, flatList.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      executeCommand(flatList[activeIndex])
    } else if (e.key === 'Escape') {
      onClose()
    }
  }, [flatList, activeIndex, executeCommand, onClose])

  useEffect(() => { setActiveIndex(0) }, [query])

  if (!open) return null

  let flatIndex = -1

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" />

      {/* Palette */}
      <div
        className="relative w-full max-w-lg bg-white rounded-2xl border border-gray-200 shadow-elevated overflow-hidden animate-slide-up"
        onClick={e => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 h-12 border-b border-gray-100">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4 text-onSurfaceDim flex-shrink-0">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search pages, scenarios..."
            className="flex-1 bg-transparent text-sm text-onSurface placeholder-onSurfaceDim outline-none"
            spellCheck={false}
          />
          <kbd className="text-[10px] font-mono text-onSurfaceDim bg-surface-2 px-1.5 py-0.5 rounded">ESC</kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[320px] overflow-y-auto py-2">
          {flatList.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-onSurfaceDim">
              No results for "{query}"
            </div>
          ) : (
            Object.entries(grouped).map(([category, commands]) => (
              <div key={category}>
                <div className="px-4 pt-2 pb-1 text-[10px] font-mono uppercase tracking-widest text-onSurfaceDim">
                  {category}
                </div>
                {commands.map((cmd) => {
                  flatIndex++
                  const idx = flatIndex
                  const isActive = idx === activeIndex
                  return (
                    <button
                      key={cmd.id}
                      data-index={idx}
                      className={`w-full px-4 py-2 flex items-center gap-3 text-left text-sm transition-colors duration-75 ${
                        isActive
                          ? 'bg-primary/5 text-primary'
                          : 'text-onSurface hover:bg-surface-2'
                      }`}
                      onClick={() => executeCommand(cmd)}
                      onMouseEnter={() => setActiveIndex(idx)}
                    >
                      {cmd.action === 'navigate' ? (
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5 text-onSurfaceDim flex-shrink-0">
                          <path d="M5 12h14M12 5l7 7-7 7"/>
                        </svg>
                      ) : (
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5 text-onSurfaceDim flex-shrink-0">
                          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10"/>
                        </svg>
                      )}
                      <span>{cmd.label}</span>
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-gray-100 flex items-center gap-4 text-[10px] font-mono text-onSurfaceDim">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>ESC Close</span>
        </div>
      </div>
    </div>
  )
}
