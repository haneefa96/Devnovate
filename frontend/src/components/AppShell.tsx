import { Suspense, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

const navigation = [
  { label: 'Dashboard', to: '/dashboard', icon: 'grid' },
  { label: 'Customers', to: '/customers', icon: 'users' },
  { label: 'New invoice', to: '/invoices/new', icon: 'file' },
  { label: 'Approvals', to: '/approvals', icon: 'check' },
  { label: 'Risk alerts', to: '/risk', icon: 'alert' },
  { label: 'Simulation', to: '/simulation', icon: 'play' },
  { label: 'Evaluation', to: '/evaluation', icon: 'chart' },
] as const

const titles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/customers': 'Customers',
  '/invoices/new': 'New invoice',
  '/approvals': 'Approvals inbox',
  '/risk': 'Risk alerts',
  '/simulation': 'Simulation console',
  '/evaluation': 'Evaluation',
}

function NavigationIcon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z',
    users: 'M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M10 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M20 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75',
    file: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h8',
    check: 'M9 12l2 2 4-4 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
    alert: 'M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.5L13.7 3.9a2 2 0 0 0-3.4 0z M12 9v4 M12 17h.01',
    play: 'M8 5v14l11-7z M3 5v14',
    chart: 'M3 3v18h18 M18 17V9 M13 17V5 M8 17v-3',
  }
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="none">
      <path d={paths[name]} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const title = location.pathname.startsWith('/customers/')
    ? 'Customer profile'
    : titles[location.pathname] ?? 'Munshi'

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-slate-900">
      {menuOpen && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-slate-950/30 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[248px] flex-col border-r border-slate-200 bg-white transition-transform lg:translate-x-0 ${menuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex h-[76px] items-center gap-3 border-b border-slate-100 px-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-700 text-sm font-bold text-white">M</div>
          <div>
            <div className="text-[17px] font-semibold tracking-tight text-slate-900">munshi</div>
            <div className="text-[11px] font-medium text-slate-400">RECEIVABLES DESK</div>
          </div>
        </div>
        <div className="px-4 pt-7">
          <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Workspace</p>
          <nav aria-label="Main navigation" className="space-y-1">
            {navigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition ${isActive ? 'bg-emerald-50 text-emerald-800' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}
              >
                <NavigationIcon name={item.icon} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="mt-auto border-t border-slate-100 p-5">
          <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-600">OW</div>
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-slate-800">Business owner</p>
              <p className="text-[11px] text-slate-400">Demo workspace</p>
            </div>
          </div>
        </div>
      </aside>

      <div className="min-h-screen lg:pl-[248px]">
        <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between border-b border-slate-200 bg-white/95 px-5 backdrop-blur sm:px-8">
          <div className="flex items-center gap-3">
            <button
              aria-label="Open navigation"
              className="rounded-md p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
              onClick={() => setMenuOpen(true)}
            >
              <span className="block h-0.5 w-5 bg-current" />
              <span className="mt-1 block h-0.5 w-5 bg-current" />
              <span className="mt-1 block h-0.5 w-5 bg-current" />
            </button>
            <h1 className="text-sm font-semibold text-slate-800">{title}</h1>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-[11px] font-medium text-emerald-800">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Owner review required
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1440px] px-5 py-7 sm:px-8 sm:py-9">
          <Suspense fallback={<div role="status" className="rounded-xl border border-slate-200 bg-white px-5 py-10 text-center text-sm text-slate-400">Loading screen…</div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
