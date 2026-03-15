const statusConfig = {
  submitted: {
    label: 'Submitted',
    classes: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
    dot: 'bg-blue-400',
  },
  pipeline_running: {
    label: 'Running',
    classes: 'bg-brand-500/15 text-brand-300 border-brand-500/20',
    dot: 'bg-brand-400 animate-pulse',
  },
  running: {
    label: 'Running',
    classes: 'bg-brand-500/15 text-brand-300 border-brand-500/20',
    dot: 'bg-brand-400 animate-pulse',
  },
  awaiting_approval: {
    label: 'Awaiting Approval',
    classes: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
    dot: 'bg-amber-400 animate-pulse',
  },
  completed: {
    label: 'Completed',
    classes: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    dot: 'bg-emerald-400',
  },
  rejected: {
    label: 'Rejected',
    classes: 'bg-red-500/15 text-red-400 border-red-500/20',
    dot: 'bg-red-400',
  },
  simulated: {
    label: 'Simulated',
    classes: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
    dot: 'bg-cyan-400',
  },
  optimizing: {
    label: 'Optimizing',
    classes: 'bg-violet-500/15 text-violet-400 border-violet-500/20',
    dot: 'bg-violet-400 animate-pulse',
  },
}

const fallback = {
  label: 'Unknown',
  classes: 'bg-slate-500/15 text-slate-400 border-slate-500/20',
  dot: 'bg-slate-400',
}

export default function StatusBadge({ status }) {
  const config = statusConfig[status] || fallback

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${config.classes}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  )
}
