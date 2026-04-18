import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

const menuItems = [
  {
    path: '/dashboard', label: 'Dashboard',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-[18px] h-[18px]">
        <rect x="3" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="14" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/>
      </svg>
    ),
  },
  {
    path: '/agents', label: 'Agents',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-[18px] h-[18px]">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </svg>
    ),
  },
  {
    path: '/signal', label: 'Signal',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-[18px] h-[18px]">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
      </svg>
    ),
  },
  {
    path: '/history', label: 'History',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-[18px] h-[18px]">
        <circle cx="12" cy="12" r="9"/>
        <polyline points="12 6 12 12 16 14"/>
      </svg>
    ),
  },
  {
    path: '/backtest', label: 'Backtest',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-[18px] h-[18px]">
        <polyline points="23 6 13.5 15.5 8 10 1 17"/>
        <polyline points="17 6 23 6 23 12"/>
      </svg>
    ),
  },
  {
    path: '/performance', label: 'Performance',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-[18px] h-[18px]">
        <path d="M18 20V10M12 20V4M6 20v-6"/>
      </svg>
    ),
  },
  {
    path: '/paper-trading', label: 'Trading',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-[18px] h-[18px]">
        <line x1="12" y1="1" x2="12" y2="23"/>
        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
      </svg>
    ),
  },
  {
    path: '/skills', label: 'Skills',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-[18px] h-[18px]">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2zM22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
      </svg>
    ),
  },
  {
    path: '/settings', label: 'Settings',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-[18px] h-[18px]">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    ),
  },
]

export default function Sidebar() {
  const location = useLocation()
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={`${expanded ? 'w-48' : 'w-14'} bg-white border-r border-gray-100 flex flex-col h-screen transition-all duration-200 ease-out flex-shrink-0`}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      {/* Logo */}
      <div className="h-12 flex items-center justify-center border-b border-gray-100 flex-shrink-0">
        <Link to="/dashboard" className="flex items-center gap-2.5 px-3 overflow-hidden">
          <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
            <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4">
              <circle cx="12" cy="12" r="10" stroke="#fff" strokeWidth="1.5"/>
              <circle cx="12" cy="12" r="5" stroke="#fff" strokeWidth="1.5"/>
              <circle cx="12" cy="12" r="2" fill="#fff"/>
              <path d="M12 2v3M12 19v3M2 12h3M19 12h3" stroke="#fff" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <div className={`min-w-0 transition-opacity duration-200 ${expanded ? 'opacity-100' : 'opacity-0 w-0'}`}>
            <h1 className="text-xs font-bold text-onSurface tracking-wider whitespace-nowrap">GOD'S EYE</h1>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-1.5 py-3 space-y-0.5 overflow-y-auto overflow-x-hidden">
        {menuItems.map((item) => {
          const isActive = location.pathname === item.path ||
            (item.path === '/dashboard' && location.pathname === '/')
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`group relative flex items-center gap-3 h-9 rounded-xl transition-all duration-200 ${
                isActive
                  ? 'bg-primary/5 text-primary'
                  : 'text-onSurfaceMuted hover:text-onSurface hover:bg-surface-2'
              }`}
              style={isActive ? { boxShadow: 'inset 3px 0 0 #CC152B' } : undefined}
              aria-current={isActive ? 'page' : undefined}
            >
              {/* Icon — always centered in the 56px rail */}
              <span className={`flex-shrink-0 w-11 flex items-center justify-center ${
                isActive ? 'text-primary' : 'text-onSurfaceDim group-hover:text-onSurfaceMuted'
              }`}>
                {item.icon}
              </span>

              {/* Label — slides in on expand */}
              <span className={`text-[13px] font-medium whitespace-nowrap transition-opacity duration-200 ${
                expanded ? 'opacity-100' : 'opacity-0'
              }`}>
                {item.label}
              </span>

              {/* Tooltip — shows when collapsed */}
              {!expanded && (
                <span className="absolute left-full ml-2 px-2.5 py-1 rounded-lg bg-secondary text-xs text-white font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none z-50 shadow-lg">
                  {item.label}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-2 py-3 border-t border-gray-100 flex-shrink-0">
        <div className="flex items-center justify-center gap-2">
          <span className="w-1.5 h-1.5 bg-bull rounded-full animate-pulse flex-shrink-0" aria-label="System status"></span>
          <span className={`text-[10px] font-mono text-onSurfaceDim whitespace-nowrap transition-opacity duration-200 ${expanded ? 'opacity-100' : 'opacity-0 w-0'}`}>
            v1.0 · NSE
          </span>
        </div>
      </div>
    </div>
  )
}
