import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import CampaignDetail from './pages/CampaignDetail'
import NewCampaign from './pages/NewCampaign'

export default function App() {
  return (
    <div className="flex min-h-screen bg-surface-900">
      <Sidebar />
      <main className="flex-1 ml-64 p-8 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/campaign/:id" element={<CampaignDetail />} />
          <Route path="/new" element={<NewCampaign />} />
        </Routes>
      </main>
    </div>
  )
}
