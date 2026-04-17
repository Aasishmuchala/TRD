import { useState, useEffect } from 'react'

// FE-M7: Isolated clock component so the 1-second interval only re-renders this subtree,
// not the entire TopNav and its children.
function ISTClock() {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const istTime = time.toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })

  const isMarketHours = (() => {
    const ist = new Date(time.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
    const h = ist.getHours()
    const m = ist.getMinutes()
    const mins = h * 60 + m
    const day = ist.getDay()
    return day >= 1 && day <= 5 && mins >= 555 && mins <= 930
  })()

  return (
    <>
      <div className="flex items-center gap-2 text-onSurfaceMuted" aria-label={`Current time: ${istTime} IST`}>
        <span className="font-mono text-onSurface">{istTime}</span>
        <span>IST</span>
      </div>
      <div className="flex items-center gap-2" aria-live="polite" aria-label={isMarketHours ? 'Market is open' : 'Market is closed'}>
        <span className={`w-1.5 h-1.5 rounded-full ${isMarketHours ? 'bg-bull animate-pulse' : 'bg-onSurfaceDim'}`} aria-hidden="true"></span>
        <span className={`font-mono uppercase tracking-wide ${isMarketHours ? 'text-bull' : 'text-onSurfaceDim'}`}>
          {isMarketHours ? 'MARKET OPEN' : 'MARKET CLOSED'}
        </span>
      </div>
    </>
  )
}

export default function TopNav() {
  return (
    <div className="h-10 bg-surface-1 border-b border-[rgba(255,255,255,0.06)] px-6 flex items-center justify-between text-xs">
      <div className="flex items-center gap-6">
        <ISTClock />
      </div>

      <div className="flex items-center gap-4 text-onSurfaceMuted">
        <span className="font-mono">NSE</span>
        <span className="text-[rgba(255,255,255,0.06)]">|</span>
        <span className="font-mono">8 AGENTS</span>
        <span className="text-[rgba(255,255,255,0.06)]">|</span>
        <span className="font-mono">3 ROUNDS</span>
      </div>
    </div>
  )
}
