import { useState } from 'react'
import { X, CheckCircle, XCircle, Mail, Users, Clock, Eye, AlertTriangle } from 'lucide-react'

export default function ApprovalModal({
  isOpen,
  onClose,
  onApprove,
  onReject,
  emailSubject,
  emailBody,
  recipientEmails = [],
  plan,
  complianceApproved,
  contentVariants = [],
}) {
  const [isApproving, setIsApproving] = useState(false)
  const [isRejecting, setIsRejecting] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  if (!isOpen) return null

  const handleApprove = async () => {
    setIsApproving(true)
    try {
      await onApprove()
    } finally {
      setIsApproving(false)
    }
  }

  const handleReject = async () => {
    setIsRejecting(true)
    try {
      await onReject()
    } finally {
      setIsRejecting(false)
    }
  }

  const sendTime = new Date().toLocaleString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className="fixed inset-0 z-50 modal-backdrop flex items-center justify-center p-4 animate-fade-in">
      <div className="glass-card rounded-3xl w-full max-w-3xl max-h-[90vh] overflow-hidden animate-scale-in shadow-2xl shadow-brand-500/10">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-brand-500/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/15 flex items-center justify-center border border-amber-500/30">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Campaign Approval Required</h2>
              <p className="text-xs text-slate-400 mt-0.5">Review the generated content before execution</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)] space-y-5">
          {/* Summary Cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Users className="w-4 h-4 text-brand-400" />
                <span className="text-xs font-medium text-slate-400">Recipients</span>
              </div>
              <p className="text-2xl font-bold text-white">{recipientEmails.length}</p>
              <p className="text-[10px] text-slate-500 mt-1">{plan?.segment || 'all'} segment</p>
            </div>
            <div className="glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-brand-400" />
                <span className="text-xs font-medium text-slate-400">Scheduled</span>
              </div>
              <p className="text-sm font-semibold text-white leading-tight">{sendTime}</p>
              <p className="text-[10px] text-slate-500 mt-1">Immediate send</p>
            </div>
            <div className="glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-medium text-slate-400">Compliance</span>
              </div>
              <p className={`text-sm font-semibold ${complianceApproved ? 'text-emerald-400' : 'text-red-400'}`}>
                {complianceApproved ? 'Passed ✅' : 'Failed ❌'}
              </p>
              <p className="text-[10px] text-slate-500 mt-1">BFSI brand safety</p>
            </div>
          </div>

          {/* Email Subject */}
          <div className="glass rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Mail className="w-4 h-4 text-brand-400" />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Email Subject</span>
            </div>
            <p className="text-white font-medium">{emailSubject || 'No subject generated'}</p>
          </div>

          {/* Email Body Preview */}
          <div className="glass rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4 text-brand-400" />
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Email Body Preview</span>
              </div>
              <button
                onClick={() => setShowPreview(!showPreview)}
                className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
              >
                {showPreview ? 'Show HTML Source' : 'Show Rendered Preview'}
              </button>
            </div>
            {showPreview ? (
              <div
                className="bg-white rounded-lg p-6 text-gray-800 text-sm max-h-64 overflow-y-auto"
                dangerouslySetInnerHTML={{ __html: emailBody || '<p>No content generated</p>' }}
              />
            ) : (
              <pre className="bg-surface-800/80 rounded-lg p-4 text-xs text-slate-300 overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap font-mono">
                {emailBody || 'No content generated'}
              </pre>
            )}
          </div>

          {/* Target Customer List */}
          <div className="glass rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Users className="w-4 h-4 text-brand-400" />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Target Customer List ({recipientEmails.length} recipients)
              </span>
            </div>
            <div className="bg-surface-800/80 rounded-lg p-3 max-h-32 overflow-y-auto">
              <div className="flex flex-wrap gap-1.5">
                {recipientEmails.slice(0, 20).map((email, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded-md bg-brand-500/10 text-brand-300 text-[10px] font-mono border border-brand-500/10"
                  >
                    {email}
                  </span>
                ))}
                {recipientEmails.length > 20 && (
                  <span className="px-2 py-0.5 rounded-md bg-slate-700/50 text-slate-400 text-[10px] font-medium">
                    +{recipientEmails.length - 20} more
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-brand-500/10">
          <button
            onClick={handleReject}
            disabled={isRejecting || isApproving}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 hover:border-red-500/40 transition-all duration-200 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <XCircle className="w-4 h-4" />
            {isRejecting ? 'Rejecting...' : 'Reject Campaign'}
          </button>
          <button
            onClick={handleApprove}
            disabled={isApproving || isRejecting}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 hover:border-emerald-500/50 hover:shadow-lg hover:shadow-emerald-500/10 transition-all duration-200 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <CheckCircle className="w-4 h-4" />
            {isApproving ? 'Approving...' : 'Approve & Send'}
          </button>
        </div>
      </div>
    </div>
  )
}
