import { useState, useEffect, useCallback } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import CommandPalette from './CommandPalette'

export default function Layout({ children }) {
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false)

  const openPalette = useCallback(() => setCmdPaletteOpen(true), [])
  const closePalette = useCallback(() => setCmdPaletteOpen(false), [])

  // Global ⌘K / Ctrl+K listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCmdPaletteOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <div className="flex h-screen bg-white">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <TopBar onCommandPalette={openPalette} />
        <div className="flex-1 overflow-auto bg-surface-1">
          {children}
        </div>
      </div>
      <CommandPalette open={cmdPaletteOpen} onClose={closePalette} />
    </div>
  )
}
