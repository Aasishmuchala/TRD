import Sidebar from './Sidebar'
import TopNav from './TopNav'
import MarketTicker from './MarketTicker'

export default function Layout({ children }) {
  return (
    <div className="flex h-screen bg-surface-0">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <MarketTicker />
        <TopNav />
        <div className="flex-1 overflow-auto">
          {children}
        </div>
      </div>
    </div>
  )
}
