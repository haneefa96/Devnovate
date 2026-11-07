import type { ButtonHTMLAttributes, ReactNode } from 'react'

export function PageHeader({ title, description, action }: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="text-[25px] font-semibold tracking-tight text-slate-900">{title}</h2>
        <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">{description}</p>
      </div>
      {action}
    </div>
  )
}

export function Panel({ title, subtitle, action, children, className = '' }: {
  title?: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-200/30 ${className}`}>
      {(title || subtitle || action) && (
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4 sm:px-6">
          <div>
            {title && <h3 className="text-sm font-semibold text-slate-800">{title}</h3>}
            {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function MetricCard({ label, value, note, tone = 'slate' }: {
  label: string
  value: string
  note?: string
  tone?: 'slate' | 'amber' | 'emerald' | 'blue'
}) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700',
    amber: 'bg-amber-50 text-amber-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    blue: 'bg-blue-50 text-blue-700',
  }
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/30">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-slate-500">{label}</p>
        <span className={`rounded-md px-2 py-1 text-[10px] font-semibold ${tones[tone]}`}>LIVE</span>
      </div>
      <p className="mt-4 text-[26px] font-semibold tracking-tight text-slate-900">{value}</p>
      {note && <p className="mt-1 text-xs text-slate-400">{note}</p>}
    </div>
  )
}

export function RiskBadge({ level }: { level: string }) {
  const tone = level === 'HIGH'
    ? 'bg-rose-50 text-rose-700 ring-rose-100'
    : level === 'WATCH'
      ? 'bg-amber-50 text-amber-700 ring-amber-100'
      : 'bg-emerald-50 text-emerald-700 ring-emerald-100'
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wide ring-1 ring-inset ${tone}`}>{level}</span>
}

export function StateBadge({ value }: { value: string }) {
  const tones: Record<string, string> = {
    READY: 'bg-emerald-50 text-emerald-700',
    NORMAL: 'bg-emerald-50 text-emerald-700',
    BLOCKER: 'bg-rose-50 text-rose-700',
    HIGH: 'bg-rose-50 text-rose-700',
    CONFLICT: 'bg-orange-50 text-orange-700',
    UNCERTAIN: 'bg-amber-50 text-amber-700',
    WATCH: 'bg-amber-50 text-amber-700',
    DRAFTED: 'bg-blue-50 text-blue-700',
    OPEN: 'bg-amber-50 text-amber-700',
    ACKNOWLEDGED: 'bg-slate-100 text-slate-600',
    DISMISSED: 'bg-slate-100 text-slate-600',
  }
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wide ${tones[value] ?? 'bg-slate-100 text-slate-600'}`}>{value.replace(/_/g, ' ')}</span>
}

export function ErrorNotice({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-800 sm:flex-row sm:items-center sm:justify-between">
      <p>{message}</p>
      {retry && <button className="self-start font-semibold underline underline-offset-2 sm:self-auto" onClick={retry}>Try again</button>}
    </div>
  )
}

export function LoadingState({ label = 'Loading data…' }: { label?: string }) {
  return (
    <div role="status" className="rounded-xl border border-slate-200 bg-white px-5 py-10 text-center text-sm text-slate-400">
      <span className="mx-auto mb-3 block h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-emerald-600" />
      {label}
    </div>
  )
}

export function EmptyState({ title, detail, action }: {
  title: string
  detail: string
  action?: ReactNode
}) {
  return (
    <div className="px-5 py-12 text-center">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-lg text-slate-400">—</div>
      <h3 className="mt-4 text-sm font-semibold text-slate-700">{title}</h3>
      <p className="mx-auto mt-1.5 max-w-md text-xs leading-5 text-slate-400">{detail}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function Button({ children, variant = 'primary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'quiet'
}) {
  const variants = {
    primary: 'bg-emerald-700 text-white hover:bg-emerald-800 disabled:bg-emerald-300',
    secondary: 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:text-slate-300',
    danger: 'bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300',
    quiet: 'text-slate-600 hover:bg-slate-100 disabled:text-slate-300',
  }
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2.5 text-xs font-semibold transition disabled:cursor-not-allowed ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  )
}
