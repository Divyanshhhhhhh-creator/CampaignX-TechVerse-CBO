import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  fetchCampaignStatus,
  fetchCampaignLogs,
  fetchPipelineState,
  runPipeline,
  approvePipeline,
  rejectPipeline,
  runSimulation,
  fetchSimulationReport,
  startOptimization,
} from '../api'
import PipelineVisualizer from '../components/PipelineVisualizer'
import ApprovalModal from '../components/ApprovalModal'
import ReasoningDrawer from '../components/ReasoningDrawer'
import StatusBadge from '../components/StatusBadge'
import OptimizationPanel from '../components/OptimizationPanel'
import {
  ArrowLeft, Play, FileJson, BarChart3, RefreshCw,
  Rocket, AlertTriangle, CheckCircle, XCircle,
  Mail, Users, Target
} from 'lucide-react'

export default function CampaignDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [campaign, setCampaign] = useState(null)
  const [pipelineState, setPipelineState] = useState(null)
  const [logs, setLogs] = useState([])
  const [simReport, setSimReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [showApprovalModal, setShowApprovalModal] = useState(false)
  const [showReasoningDrawer, setShowReasoningDrawer] = useState(false)
  const [pipelineRunning, setPipelineRunning] = useState(false)

  const pollingRef = useRef(null)

  // Load campaign data
  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const [status, logsData, report] = await Promise.all([
          fetchCampaignStatus(id),
          fetchCampaignLogs(id).catch(() => ({ logs: [] })),
          fetchSimulationReport(id),
        ])
        setCampaign(status)
        setLogs(logsData.logs || [])
        setSimReport(report)
        setError(null)

        // Also try to load pipeline state
        try {
          const ps = await fetchPipelineState(id)
          setPipelineState(ps)
        } catch {}
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  // Poll pipeline state when running or optimizing
  useEffect(() => {
    const shouldPoll = pipelineRunning
      || pipelineState?.status === 'running'
      || pipelineState?.status === 'optimizing'
      || pipelineState?.status === 'executing'

    if (!shouldPoll) return

    pollingRef.current = setInterval(async () => {
      try {
        const ps = await fetchPipelineState(id)
        setPipelineState(ps)

        if (ps.status === 'awaiting_approval') {
          setPipelineRunning(false)
          setShowApprovalModal(true)
          clearInterval(pollingRef.current)
        } else if (ps.status === 'optimization_complete' || ps.status === 'rejected' || ps.status === 'cancelled') {
          setPipelineRunning(false)
          clearInterval(pollingRef.current)
          // Refresh campaign status
          const status = await fetchCampaignStatus(id)
          setCampaign(status)
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 1000)

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [pipelineRunning, pipelineState?.status, id])

  const handleRunPipeline = async () => {
    try {
      setPipelineRunning(true)
      setError(null)
      await runPipeline(id)
    } catch (err) {
      setError(err.message)
      setPipelineRunning(false)
    }
  }

  const handleApprove = async () => {
    try {
      await approvePipeline(id)
      setShowApprovalModal(false)
      const ps = await fetchPipelineState(id)
      setPipelineState(ps)
      const status = await fetchCampaignStatus(id)
      setCampaign(status)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleReject = async () => {
    try {
      await rejectPipeline(id)
      setShowApprovalModal(false)
      const ps = await fetchPipelineState(id)
      setPipelineState(ps)
      const status = await fetchCampaignStatus(id)
      setCampaign(status)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleRunSim = async () => {
    try {
      setError(null)
      const result = await runSimulation(id)
      setSimReport(result)
      const status = await fetchCampaignStatus(id)
      setCampaign(status)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleStartOptimization = async () => {
    try {
      setError(null)
      await startOptimization(id)
      setPipelineRunning(true)
      // Refresh pipeline state to start polling
      const ps = await fetchPipelineState(id)
      setPipelineState(ps)
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-brand-400 animate-spin mr-3" />
        <span className="text-slate-400">Loading campaign...</span>
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <XCircle className="w-10 h-10 text-red-400 mb-3" />
        <p className="text-slate-400">Campaign not found</p>
        <button onClick={() => navigate('/')} className="text-brand-400 text-sm mt-2 hover:underline">
          Back to Dashboard
        </button>
      </div>
    )
  }

  const allLogs = pipelineState?.logs || logs

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-brand-400 mb-3 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Dashboard
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">Campaign</h1>
            <span className="text-sm font-mono text-brand-400 bg-brand-500/10 px-2.5 py-1 rounded-lg border border-brand-500/10">
              {id}
            </span>
            <StatusBadge status={campaign.status} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowReasoningDrawer(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl glass hover:bg-white/5 text-sm text-slate-300 transition-all border border-brand-500/10 hover:border-brand-500/20"
          >
            <FileJson className="w-4 h-4 text-brand-400" />
            Reasoning Trace
          </button>
          {campaign.status === 'submitted' && (
            <button
              onClick={handleRunPipeline}
              disabled={pipelineRunning}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-all shadow-lg shadow-brand-500/20 disabled:opacity-50"
            >
              {pipelineRunning ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Run Pipeline
                </>
              )}
            </button>
          )}
          {pipelineState?.status === 'awaiting_approval' && (
            <button
              onClick={() => setShowApprovalModal(true)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500/15 text-amber-400 border border-amber-500/30 hover:bg-amber-500/25 text-sm font-medium transition-all animate-pulse"
            >
              <AlertTriangle className="w-4 h-4" />
              Review & Approve
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Pipeline Visualizer */}
      {(pipelineState || pipelineRunning) && (
        <PipelineVisualizer
          activeNode={pipelineState?.active_node}
          pipelineStatus={pipelineState?.status || (pipelineRunning ? 'running' : 'idle')}
          logs={allLogs}
          iteration={pipelineState?.iteration || 1}
        />
      )}

      {/* Campaign Info */}
      <div className="grid grid-cols-3 gap-4">
        <div className="glass-card rounded-2xl p-5 col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <Mail className="w-4 h-4 text-brand-400" />
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Campaign Brief</h3>
          </div>
          <p className="text-sm text-slate-200 leading-relaxed">{campaign.brief}</p>
        </div>
        <div className="glass-card rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-4 h-4 text-brand-400" />
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Details</h3>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Created</p>
              <p className="text-sm text-slate-300">
                {new Date(campaign.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </p>
            </div>
            {campaign.latest_score !== null && campaign.latest_score !== undefined && (
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider">Latest Score</p>
                <p className="text-lg font-bold text-emerald-400">{(campaign.latest_score * 100).toFixed(1)}%</p>
              </div>
            )}
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Iterations</p>
              <p className="text-sm text-slate-300">{campaign.iterations_run} run{campaign.iterations_run !== 1 ? 's' : ''}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline Results (if completed or optimization complete) */}
      {(pipelineState?.status === 'completed' || pipelineState?.status === 'optimization_complete') && (
        <div className="glass-card rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Rocket className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
              {pipelineState?.status === 'optimization_complete' ? 'Campaign Optimized & Complete' : 'Campaign Executed Successfully'}
            </h3>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="glass rounded-xl p-4">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Recipients</p>
              <p className="text-2xl font-bold text-white">{pipelineState.send_result?.recipients_count || 0}</p>
            </div>
            <div className="glass rounded-xl p-4">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Subject</p>
              <p className="text-sm text-slate-200 truncate">{pipelineState.email_subject}</p>
            </div>
            <div className="glass rounded-xl p-4">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Status</p>
              <p className="text-sm font-semibold text-emerald-400 flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4" />
                {pipelineState?.status === 'optimization_complete' ? 'Optimized' : 'Sent'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Rejected notice */}
      {pipelineState?.status === 'rejected' && (
        <div className="glass-card rounded-2xl p-5 border-red-500/20">
          <div className="flex items-center gap-2">
            <XCircle className="w-5 h-5 text-red-400" />
            <h3 className="text-sm font-semibold text-red-400">Campaign Rejected</h3>
          </div>
          <p className="text-xs text-slate-400 mt-2">The pipeline was aborted by human review. You can create a new campaign brief to try again.</p>
        </div>
      )}

      {/* Simulation Section */}
      <div className="glass-card rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-brand-400" />
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Gamification Engine</h3>
          </div>
          <button
            onClick={handleRunSim}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-500/10 text-brand-400 border border-brand-500/20 text-xs font-medium hover:bg-brand-500/20 transition-all"
          >
            <Play className="w-3 h-3" />
            Run Simulation
          </button>
        </div>

        {simReport ? (
          <div className="grid grid-cols-4 gap-3">
            <div className="glass rounded-xl p-3">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Sent</p>
              <p className="text-xl font-bold text-white">{simReport.summary.total_sent}</p>
            </div>
            <div className="glass rounded-xl p-3">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Open Rate</p>
              <p className="text-xl font-bold text-blue-400">{(simReport.summary.open_rate * 100).toFixed(1)}%</p>
            </div>
            <div className="glass rounded-xl p-3">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Click Rate</p>
              <p className="text-xl font-bold text-emerald-400">{(simReport.summary.click_rate * 100).toFixed(1)}%</p>
            </div>
            <div className="glass rounded-xl p-3">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Weighted Score</p>
              <p className="text-xl font-bold gradient-text">{(simReport.summary.weighted_score * 100).toFixed(1)}%</p>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500">No simulation data yet. Click "Run Simulation" to test locally.</p>
        )}
      </div>

      {/* Optimization Panel */}
      {pipelineState && (
        <OptimizationPanel
          pipelineState={pipelineState}
          onStartOptimization={handleStartOptimization}
        />
      )}

      {/* Approval Modal */}
      <ApprovalModal
        isOpen={showApprovalModal}
        onClose={() => setShowApprovalModal(false)}
        onApprove={handleApprove}
        onReject={handleReject}
        emailSubject={pipelineState?.email_subject}
        emailBody={pipelineState?.email_body}
        recipientEmails={pipelineState?.recipient_emails || []}
        plan={pipelineState?.plan}
        complianceApproved={pipelineState?.compliance_approved}
        contentVariants={pipelineState?.content_variants || []}
      />

      {/* Reasoning Drawer */}
      <ReasoningDrawer
        isOpen={showReasoningDrawer}
        onClose={() => setShowReasoningDrawer(false)}
        logs={allLogs}
      />
    </div>
  )
}
