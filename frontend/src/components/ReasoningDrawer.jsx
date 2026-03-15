import { useState } from 'react'
import { X, ChevronDown, ChevronRight, FileJson, ArrowRightLeft } from 'lucide-react'

function JsonViewer({ data, label }) {
  const [expanded, setExpanded] = useState(false)

  if (!data) return <span className="text-slate-500 text-xs italic">No data</span>

  let parsed = data
  if (typeof data === 'string') {
    try {
      parsed = JSON.parse(data)
    } catch {
      return <span className="text-slate-300 text-xs font-mono break-all">{data}</span>
    }
  }

  const formatted = JSON.stringify(parsed, null, 2)
  const lines = formatted.split('\n')
  const isLong = lines.length > 4

  // Simple syntax highlighting
  const highlighted = formatted
    .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
    .replace(/: "([^"]*)"/g, ': <span class="json-string">"$1"</span>')
    .replace(/: (\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
    .replace(/: (true|false)/g, ': <span class="json-boolean">$1</span>')
    .replace(/: null/g, ': <span class="json-null">null</span>')

  return (
    <div>
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-[10px] text-brand-400 hover:text-brand-300 mb-1 transition-colors"
        >
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          {expanded ? 'Collapse' : `Expand ${label}`} ({lines.length} lines)
        </button>
      )}
      <pre
        className={`bg-surface-900/80 rounded-lg p-3 text-[11px] font-mono overflow-x-auto transition-all duration-200 ${
          !expanded && isLong ? 'max-h-24 overflow-hidden' : 'max-h-96 overflow-y-auto'
        }`}
        dangerouslySetInnerHTML={{ __html: highlighted }}
      />
    </div>
  )
}

function LogEntry({ log, index }) {
  const [open, setOpen] = useState(false)

  const agentColors = {
    coordinator: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    strategist: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
    creative: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
    compliance: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    hil_gate: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    execution: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    system: 'text-slate-400 bg-slate-500/10 border-slate-500/20',
    simulator: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
  }

  const colorClass = agentColors[log.agent || log.agent_name] || agentColors.system

  return (
    <div className="glass rounded-xl overflow-hidden transition-all duration-200">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 p-3 hover:bg-white/[0.02] transition-colors text-left"
      >
        <span className="text-[10px] text-slate-600 font-mono w-5 text-right">{index + 1}</span>
        <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${colorClass}`}>
          {log.agent || log.agent_name}
        </span>
        <span className="text-xs text-slate-300 flex-1 truncate">
          {log.action}
        </span>
        <span className="text-[10px] text-slate-500">
          {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
        </span>
        {open ? (
          <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
        )}
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3 animate-fade-in">
          {/* Detail */}
          {log.detail && (
            <p className="text-xs text-slate-400 pl-8">{log.detail}</p>
          )}
          {log.reasoning && (
            <p className="text-xs text-slate-400 pl-8">{log.reasoning}</p>
          )}

          {/* Input/Output */}
          <div className="grid grid-cols-2 gap-3 pl-8">
            {(log.input_data || log.input_data === null) && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <ArrowRightLeft className="w-3 h-3 text-brand-400" />
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Input</span>
                </div>
                <JsonViewer data={log.input_data} label="input" />
              </div>
            )}
            {(log.output_data || log.output_data === null) && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <FileJson className="w-3 h-3 text-emerald-400" />
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Output</span>
                </div>
                <JsonViewer data={log.output_data} label="output" />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ReasoningDrawer({ isOpen, onClose, logs = [] }) {
  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-surface-900/50 backdrop-blur-sm animate-fade-in"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`fixed top-0 right-0 h-screen w-[540px] z-50 glass border-l border-brand-500/10 shadow-2xl shadow-brand-500/5 transition-transform duration-300 ease-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-brand-500/10">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-brand-500/15 flex items-center justify-center border border-brand-500/20">
              <FileJson className="w-4 h-4 text-brand-400" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">Reasoning Trace</h2>
              <p className="text-[10px] text-slate-400 mt-0.5">{logs.length} agent interaction{logs.length !== 1 ? 's' : ''}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        {/* Log entries */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2" style={{ height: 'calc(100vh - 72px)' }}>
          {logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <FileJson className="w-12 h-12 text-slate-700 mb-3" />
              <p className="text-sm text-slate-500">No agent traces yet</p>
              <p className="text-xs text-slate-600 mt-1">Run the pipeline to see reasoning data</p>
            </div>
          ) : (
            logs.map((log, i) => (
              <LogEntry key={i} log={log} index={i} />
            ))
          )}
        </div>
      </div>
    </>
  )
}
