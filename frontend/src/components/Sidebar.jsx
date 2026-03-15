import { NavLink } from 'react-router-dom'
import { LayoutDashboard, PlusCircle, Zap, Shield } from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/new', icon: PlusCircle, label: 'New Campaign' },
]

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-64 glass flex flex-col z-40">
      {/* Brand */}
      <div className="p-6 border-b border-brand-500/10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-lg shadow-brand-500/20">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold gradient-text">CampaignX</h1>
            <p className="text-[10px] text-slate-400 font-medium tracking-wider uppercase">AI Campaign Engine</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-brand-500/15 text-brand-300 shadow-sm shadow-brand-500/10'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`
            }
          >
            <Icon className="w-[18px] h-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-brand-500/10">
        <div className="flex items-center gap-2 px-4 py-2">
          <Shield className="w-4 h-4 text-brand-400" />
          <span className="text-xs text-slate-500">SuperBFSI Compliance</span>
        </div>
        <p className="px-4 text-[10px] text-slate-600 mt-1">Multi-Agent Pipeline v1.0</p>
      </div>
    </aside>
  )
}
