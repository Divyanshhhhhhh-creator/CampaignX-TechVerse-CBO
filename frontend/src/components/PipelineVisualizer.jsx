import { CheckCircle2, Circle, Loader2, XCircle, AlertCircle } from 'lucide-react'

const defaultNodes = [
  { id: 'coordinator', label: '🧭 Coordinator', description: 'Parses campaign brief' },
  { id: 'strategist', label: '📊 Strategist', description: 'Identifies target cohort' },
  { id: 'creative', label: '✍️ Creative', description: 'Generates email content' },
  { id: 'compliance', label: '🛡️ Compliance', description: 'Brand-safety validation' },
  { id: 'hil_gate', label: '👤 Human Approval', description: 'Awaiting approval' },
  { id: 'execution', label: '🚀 Execution', description: 'Send campaign' },
  { id: 'optimizer', label: '🔄 Optimizer', description: 'Performance optimization' },
]

function getNodeStatus(nodeId, activeNode, pipelineStatus, completedNodes) {
  if (completedNodes.includes(nodeId)) return 'completed'
  if (nodeId === activeNode) {
    if (pipelineStatus === 'awaiting_approval') return 'waiting'
    if (pipelineStatus === 'optimizing') return 'active'
    return 'active'
  }
  if (pipelineStatus === 'rejected' && nodeId === activeNode) return 'failed'
  return 'pending'
}

function NodeIcon({ status }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="w-5 h-5 text-emerald-400" />
    case 'active':
      return <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />
    case 'waiting':
      return <AlertCircle className="w-5 h-5 text-amber-400 animate-pulse" />
    case 'failed':
      return <XCircle className="w-5 h-5 text-red-400" />
    default:
      return <Circle className="w-5 h-5 text-slate-600" />
  }
}

export default function PipelineVisualizer({ activeNode, pipelineStatus, logs = [], iteration = 1 }) {
  // Determine completed nodes from logs
  const completedNodes = logs
    .filter(l => l.action?.includes('_completed') || l.action === 'human_approved' || l.action === 'campaign_sent' || l.action === 'optimization_complete')
    .map(l => l.agent)

  // If pipeline is completed or optimization complete, mark all nodes
  if (pipelineStatus === 'completed' || pipelineStatus === 'optimization_complete') {
    defaultNodes.forEach(n => {
      if (!completedNodes.includes(n.id)) completedNodes.push(n.id)
    })
  }

  return (
    <div className="glass-card rounded-2xl p-6">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-6">
        Pipeline Progress
      </h3>

      <div className="flex items-start justify-between gap-2">
        {defaultNodes.map((node, idx) => {
          const status = getNodeStatus(node.id, activeNode, pipelineStatus, completedNodes)
          const isLast = idx === defaultNodes.length - 1

          return (
            <div key={node.id} className="flex items-start flex-1">
              {/* Node */}
              <div className="flex flex-col items-center min-w-0">
                <div
                  className={`
                    w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-500
                    ${status === 'active' ? 'bg-brand-500/20 glow-active border-2 border-brand-400' : ''}
                    ${status === 'completed' ? 'bg-emerald-500/15 glow-success border border-emerald-500/30' : ''}
                    ${status === 'waiting' ? 'bg-amber-500/15 glow-warning border-2 border-amber-400 animate-glow-pulse' : ''}
                    ${status === 'failed' ? 'bg-red-500/15 glow-error border border-red-500/30' : ''}
                    ${status === 'pending' ? 'bg-slate-800/50 border border-slate-700/50' : ''}
                  `}
                >
                  <NodeIcon status={status} />
                </div>
                <p className={`text-[10px] mt-2 text-center leading-tight font-medium max-w-[80px] ${
                  status === 'active' ? 'text-brand-300' :
                  status === 'completed' ? 'text-emerald-400' :
                  status === 'waiting' ? 'text-amber-400' :
                  status === 'failed' ? 'text-red-400' :
                  'text-slate-500'
                }`}>
                  {node.label}
                  {node.id === 'optimizer' && iteration > 1 && (
                    <span className="ml-1 text-[8px] px-1 py-0.5 rounded bg-brand-500/20 text-brand-300">
                      ×{iteration}
                    </span>
                  )}
                </p>
                <p className="text-[9px] text-slate-600 text-center max-w-[80px] mt-0.5">
                  {node.description}
                </p>
              </div>

              {/* Connector */}
              {!isLast && (
                <div className="flex-1 flex items-center pt-5 px-1">
                  <div className={`h-0.5 w-full rounded-full transition-all duration-500 ${
                    completedNodes.includes(node.id)
                      ? 'bg-gradient-to-r from-emerald-500/60 to-emerald-500/30'
                      : status === 'active'
                        ? 'bg-gradient-to-r from-brand-500/60 to-brand-500/20'
                        : 'bg-slate-700/40'
                  }`} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
