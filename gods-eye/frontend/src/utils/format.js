/**
 * Shared direction formatting helpers used across simulation views.
 */

export const dirColor = (dir) => {
  if (!dir) return '#FFC107'
  if (dir.includes('BUY')) return '#00E676'
  if (dir.includes('SELL')) return '#FF1744'
  return '#FFC107'
}

export const dirLabel = (dir) => {
  if (!dir) return 'NEUTRAL'
  if (dir.includes('STRONG_BUY')) return 'STRONG BUY'
  if (dir.includes('BUY')) return 'BULLISH'
  if (dir.includes('STRONG_SELL')) return 'STRONG SELL'
  if (dir.includes('SELL')) return 'BEARISH'
  return 'NEUTRAL'
}
