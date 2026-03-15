import { useState, useEffect } from 'react'
import {
  RefreshCw, TrendingUp, TrendingDown, Target, Users,
  ChevronRight, Zap, CheckCircle, AlertTriangle, BarChart3
} from 'lucide-react'

export default function OptimizationPanel({ pipelineState, onStartOptimization }) {
  const [expanded, setExpanded] = useState(true)

  const history = pipelineState?.optimization_history || []
  const microSegments = pipelineState?.micro_segments || []
  const action = pipelineState?.optimization_action
  const iteration = pipelineState?.iteration || 1
  const directives = pipelineState?.optimization_directives || ''
  const status = pipelineState?.status

  const isOptimizing = status === 'optimizing'
  const isComplete = action === 'COMPLETE' || status === 'optimization_complete'
  const showPanel = history.length > 0 || isOptimizing || isComplete

  if (!showPanel && status !== 'completed') return null

  // Calculate improvement
  const firstScore = history.length > 0 ? history[0].weighted_score : 0
  const latestScore = history.length > 0 ? history[history.length - 1].weighted_score : 0
  const improvement = firstScore > 0 ? ((latestScore - firstScore) / firstScore * 100) : 0

  return (
    <div className="glass-card rounded-2xl overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between p-5 cursor-pointer hover:bg-white/[0.02] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl ${isOptimizing ? 'bg-amber-500/15 text-amber-400' : isComplete ? 'bg-emerald-500/15 text-emerald-400' : 'bg-brand-500/15 text-brand-400'}`}>
            <RefreshCw className={`w-4 h-4 ${isOptimizing ? 'animate-spin' : ''}`} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              Autonomous Optimization Loop
              {isOptimizing && (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/20 animate-pulse">
                  RUNNING
                </span>
              )}
              {isComplete && (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                  COMPLETE
                </span>
              )}
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              {history.length > 0
                ? `${history.length} iteration${history.length !== 1 ? 's' : ''} · Score: ${(latestScore * 100).toFixed(1)}%`
                : 'Autonomous performance optimization'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {status === 'completed' && !isOptimizing && !isComplete && (
            <button
              onClick={(e) => { e.stopPropagation(); onStartOptimization?.() }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium transition-all shadow-lg shadow-brand-500/20"
            >
              <Zap className="w-3 h-3" />
              Start Optimization
            </button>
          )}
          <ChevronRight className={`w-4 h-4 text-slate-500 transition-transform ${expanded ? 'rotate-90' : ''}`} />
        </div>
      </div>

      {/* Body */}
      {expanded && (
        <div className="px-5 pb-5 space-y-4">
          {/* Iteration Timeline */}
          {history.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <BarChart3 className="w-3 h-3" />
                Iteration History
              </h4>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                {history.map((h, i) => (
                  <div key={i} className="glass rounded-xl p-3 relative overflow-hidden">
                    <div className="absolute top-0 left-0 h-full bg-gradient-to-r from-brand-500/10 to-transparent" style={{ width: `${h.weighted_score * 100}%` }} />
                    <div className="relative">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[10px] font-medium text-slate-400">Iter {h.iteration}</span>
                        <span className={`text-[10px] font-bold ${h.recommendation === 'COMPLETE' ? 'text-emerald-400' : 'text-amber-400'}`}>
                          {h.recommendation}
                        </span>
                      </div>
                      <p className="text-lg font-bold text-white">{(h.weighted_score * 100).toFixed(1)}%</p>
                      <div className="flex gap-3 mt-1">
                        <span className="text-[9px] text-blue-400">Open {(h.open_rate * 100).toFixed(0)}%</span>
                        <span className="text-[9px] text-emerald-400">Click {(h.click_rate * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Improvement badge */}
              {history.length > 1 && (
                <div className="flex items-center gap-2 mt-3">
                  {improvement > 0 ? (
                    <div className="flex items-center gap-1 text-xs text-emerald-400">
                      <TrendingUp className="w-3.5 h-3.5" />
                      <span>+{improvement.toFixed(1)}% improvement over {history.length} iterations</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 text-xs text-red-400">
                      <TrendingDown className="w-3.5 h-3.5" />
                      <span>{improvement.toFixed(1)}% change</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Micro-Segments */}
          {microSegments.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <Users className="w-3 h-3" />
                Micro-Segment Analysis
              </h4>
              <div className="rounded-xl border border-white/[0.04] overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-white/[0.02]">
                      <th className="text-left py-2 px-3 text-slate-500 font-medium">Segment</th>
                      <th className="text-center py-2 px-3 text-slate-500 font-medium">Total</th>
                      <th className="text-center py-2 px-3 text-slate-500 font-medium">Open %</th>
                      <th className="text-center py-2 px-3 text-slate-500 font-medium">Click %</th>
                      <th className="text-center py-2 px-3 text-slate-500 font-medium">Score</th>
                      <th className="text-center py-2 px-3 text-slate-500 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {microSegments.map((seg, i) => (
                      <tr key={i} className="border-t border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                        <td className="py-2 px-3 text-slate-300 font-medium">{seg.segment}</td>
                        <td className="py-2 px-3 text-center text-slate-400">{seg.total}</td>
                        <td className="py-2 px-3 text-center text-blue-400">{(seg.open_rate * 100).toFixed(1)}%</td>
                        <td className="py-2 px-3 text-center text-emerald-400">{(seg.click_rate * 100).toFixed(1)}%</td>
                        <td className="py-2 px-3 text-center font-semibold text-white">{(seg.weighted_score * 100).toFixed(1)}%</td>
                        <td className="py-2 px-3 text-center">
                          {seg.status === 'optimized' ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-medium">
                              <CheckCircle className="w-2.5 h-2.5" />
                              Optimized
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 text-[10px] font-medium">
                              <AlertTriangle className="w-2.5 h-2.5" />
                              Underperforming
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Optimization Directives */}
          {directives && (
            <div>
              <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Target className="w-3 h-3" />
                Optimization Directives
              </h4>
              <div className="glass rounded-xl p-3 text-xs text-slate-300 leading-relaxed whitespace-pre-line">
                {directives}
              </div>
            </div>
          )}

          {/* Threshold indicator */}
          <div className="glass rounded-xl p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">Performance vs Threshold</span>
              <span className="text-[10px] text-slate-400">Target: 18%</span>
            </div>
            <div className="w-full bg-white/[0.04] rounded-full h-2.5 relative overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-1000 ${latestScore >= 0.18 ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' : 'bg-gradient-to-r from-amber-500 to-amber-400'}`}
                style={{ width: `${Math.min(latestScore * 100 / 0.30, 100)}%` }}
              />
              {/* Threshold marker */}
              <div className="absolute top-0 h-full w-0.5 bg-white/30" style={{ left: `${0.18 / 0.30 * 100}%` }} />
            </div>
            <div className="flex items-center justify-between mt-1.5">
              <span className="text-[10px] text-slate-500">0%</span>
              <span className={`text-[10px] font-bold ${latestScore >= 0.18 ? 'text-emerald-400' : 'text-amber-400'}`}>
                Current: {(latestScore * 100).toFixed(1)}%
              </span>
              <span className="text-[10px] text-slate-500">30%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
