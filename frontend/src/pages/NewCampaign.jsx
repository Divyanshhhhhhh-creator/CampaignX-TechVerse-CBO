import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { submitCampaign } from '../api'
import { Send, ArrowLeft, Sparkles, Target, Package } from 'lucide-react'

const SEGMENTS = [
  { value: '', label: 'All Customers' },
  { value: 'female_seniors', label: 'Female Seniors' },
  { value: 'young_professionals', label: 'Young Professionals' },
  { value: 'high_net_worth', label: 'High Net Worth' },
  { value: 'students', label: 'Students' },
  { value: 'retirees', label: 'Retirees' },
]

export default function NewCampaign() {
  const [brief, setBrief] = useState('')
  const [targetSegment, setTargetSegment] = useState('')
  const [productName, setProductName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!brief.trim()) return

    try {
      setSubmitting(true)
      setError(null)
      const result = await submitCampaign({
        brief: brief.trim(),
        target_segment: targetSegment || null,
        product_name: productName.trim() || null,
      })
      navigate(`/campaign/${result.campaign_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-brand-400 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>
        <h1 className="text-3xl font-bold text-white tracking-tight">
          Create <span className="gradient-text">New Campaign</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1.5">
          Submit a campaign brief and let the AI agents handle the rest
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Brief */}
        <div className="glass-card rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-4 h-4 text-brand-400" />
            <label htmlFor="campaign-brief" className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
              Campaign Brief
            </label>
          </div>
          <textarea
            id="campaign-brief"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder="Describe your campaign goal in natural language...&#10;&#10;Example: Launch XDeposit for female seniors with +1.25% interest rate bonus on fixed deposits. Emphasize security and high returns."
            className="w-full h-36 bg-surface-800/60 rounded-xl p-4 text-sm text-slate-200 placeholder-slate-600 border border-brand-500/10 focus:border-brand-500/30 focus:ring-1 focus:ring-brand-500/20 outline-none transition-all resize-none font-[inherit]"
            required
            minLength={5}
          />
          <p className="text-[10px] text-slate-500 mt-2">
            Minimum 5 characters. Be specific about product, audience, and value proposition.
          </p>
        </div>

        {/* Segment & Product */}
        <div className="grid grid-cols-2 gap-4">
          <div className="glass-card rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Target className="w-4 h-4 text-brand-400" />
              <label htmlFor="target-segment" className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                Target Segment
              </label>
            </div>
            <select
              id="target-segment"
              value={targetSegment}
              onChange={(e) => setTargetSegment(e.target.value)}
              className="w-full bg-surface-800/60 rounded-xl px-4 py-3 text-sm text-slate-200 border border-brand-500/10 focus:border-brand-500/30 focus:ring-1 focus:ring-brand-500/20 outline-none transition-all appearance-none cursor-pointer"
            >
              {SEGMENTS.map(seg => (
                <option key={seg.value} value={seg.value}>{seg.label}</option>
              ))}
            </select>
          </div>

          <div className="glass-card rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Package className="w-4 h-4 text-brand-400" />
              <label htmlFor="product-name" className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                Product Name
              </label>
            </div>
            <input
              id="product-name"
              type="text"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              placeholder="e.g., XDeposit"
              className="w-full bg-surface-800/60 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 border border-brand-500/10 focus:border-brand-500/30 focus:ring-1 focus:ring-brand-500/20 outline-none transition-all"
            />
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting || brief.trim().length < 5}
          className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl bg-gradient-to-r from-brand-600 to-brand-500 hover:from-brand-500 hover:to-brand-400 text-white font-semibold text-sm transition-all duration-200 shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-brand-500/20"
        >
          {submitting ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              Submit Campaign Brief
            </>
          )}
        </button>
      </form>
    </div>
  )
}
