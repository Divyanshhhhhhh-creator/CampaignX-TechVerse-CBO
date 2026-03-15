import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchCampaigns } from '../api'
import StatusBadge from '../components/StatusBadge'
import { Zap, TrendingUp, CheckCircle, Clock, Plus, ArrowRight, RefreshCw } from 'lucide-react'

export default function Dashboard() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const loadCampaigns = async () => {
    try {
      setLoading(true)
      const data = await fetchCampaigns()
      setCampaigns(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCampaigns()
  }, [])

  const stats = {
    total: campaigns.length,
    active: campaigns.filter(c => ['pipeline_running', 'running', 'awaiting_approval', 'optimizing'].includes(c.status)).length,
    completed: campaigns.filter(c => c.status === 'completed').length,
    pending: campaigns.filter(c => c.status === 'submitted').length,
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Campaign <span className="gradient-text">Dashboard</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1.5">
            AI-powered multi-agent email campaign management
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadCampaigns}
            className="p-2.5 rounded-xl glass hover:bg-white/5 transition-all duration-200 group"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 text-slate-400 group-hover:text-brand-400 transition-colors ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => navigate('/new')}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-all duration-200 shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30"
          >
            <Plus className="w-4 h-4" />
            New Campaign
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Campaigns', value: stats.total, icon: Zap, color: 'brand' },
          { label: 'Active', value: stats.active, icon: TrendingUp, color: 'blue' },
          { label: 'Completed', value: stats.completed, icon: CheckCircle, color: 'emerald' },
          { label: 'Pending', value: stats.pending, icon: Clock, color: 'amber' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="glass-card rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className={`w-10 h-10 rounded-xl bg-${color}-500/10 flex items-center justify-center border border-${color}-500/20`}>
                <Icon className={`w-5 h-5 text-${color}-400`} />
              </div>
            </div>
            <p className="text-3xl font-bold text-white">{value}</p>
            <p className="text-xs text-slate-400 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Campaign List */}
      <div className="glass-card rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-brand-500/10">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            All Campaigns
          </h2>
        </div>

        {error && (
          <div className="p-4 m-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        {loading && !campaigns.length ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="w-6 h-6 text-brand-400 animate-spin mr-3" />
            <span className="text-slate-400 text-sm">Loading campaigns...</span>
          </div>
        ) : campaigns.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="w-16 h-16 rounded-2xl bg-brand-500/10 flex items-center justify-center mb-4 border border-brand-500/20">
              <Zap className="w-8 h-8 text-brand-400" />
            </div>
            <p className="text-slate-400 text-sm mb-1">No campaigns yet</p>
            <p className="text-slate-500 text-xs mb-4">Create your first AI-powered campaign</p>
            <button
              onClick={() => navigate('/new')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Campaign
            </button>
          </div>
        ) : (
          <div className="divide-y divide-brand-500/5">
            {campaigns.map((campaign) => (
              <button
                key={campaign.campaign_id}
                onClick={() => navigate(`/campaign/${campaign.campaign_id}`)}
                className="w-full flex items-center justify-between p-5 hover:bg-white/[0.02] transition-colors text-left group"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1.5">
                    <span className="text-xs font-mono text-brand-400/80 bg-brand-500/10 px-2 py-0.5 rounded">
                      {campaign.campaign_id}
                    </span>
                    <StatusBadge status={campaign.status} />
                  </div>
                  <p className="text-sm text-slate-200 truncate pr-4">{campaign.brief}</p>
                  {campaign.created_at && (
                    <p className="text-[10px] text-slate-500 mt-1">
                      Created {new Date(campaign.created_at).toLocaleDateString('en-US', {
                        month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
                      })}
                    </p>
                  )}
                </div>
                <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-brand-400 transition-colors shrink-0" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
