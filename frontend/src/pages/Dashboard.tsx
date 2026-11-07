import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchDashboard } from '../api/client'
import { EmptyState, ErrorNotice, LoadingState, MetricCard, PageHeader, Panel, RiskBadge } from '../components/ui'
import { formatMoney } from '../lib/format'

export default function Dashboard() {
  const dashboard = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    refetchInterval: 3000,
  })

  if (dashboard.isPending) return <LoadingState label="Loading your collection summary…" />
  if (dashboard.isError) {
    return <ErrorNotice message={dashboard.error.message} retry={() => void dashboard.refetch()} />
  }

  const data = dashboard.data
  const metrics = [
    { label: 'Total receivables', value: formatMoney(data.total_receivable_paise), note: 'Open invoice balance', tone: 'emerald' as const },
    { label: 'Overdue receivables', value: formatMoney(data.overdue_paise), note: 'Past the invoice due date', tone: 'amber' as const },
    { label: 'Customers to watch', value: String(data.at_risk_customers.length), note: 'WATCH or HIGH risk level', tone: 'blue' as const },
    { label: 'Awaiting approval', value: String(data.pending_drafts), note: 'Drafts need your review', tone: 'slate' as const },
  ]

  return (
    <>
      <PageHeader
        title="Good collections start with clarity."
        description="A live view of receivables, customer risk and actions waiting for your decision."
        action={<Link to="/invoices/new" className="inline-flex items-center justify-center rounded-lg bg-emerald-700 px-4 py-2.5 text-xs font-semibold text-white hover:bg-emerald-800">Create invoice <span className="ml-2 text-base leading-none">+</span></Link>}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => <MetricCard key={metric.label} {...metric} />)}
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <Panel title="Customers needing attention" subtitle="Customers currently marked WATCH or HIGH">
          {data.at_risk_customers.length === 0 ? (
            <EmptyState title="No open risk flags" detail="There are no customers marked WATCH or HIGH right now." />
          ) : (
            <div className="divide-y divide-slate-100">
              {data.at_risk_customers.map((customer) => (
                <Link
                  key={customer.id}
                  to={`/customers/${customer.id}`}
                  className="flex items-center justify-between gap-4 px-5 py-4 transition hover:bg-slate-50 sm:px-6"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-800">{customer.name}</p>
                    <p className="mt-1 text-xs text-slate-400">Open customer profile</p>
                  </div>
                  <RiskBadge level={customer.risk_level} />
                </Link>
              ))}
            </div>
          )}
        </Panel>

        <div className="space-y-5">
          <Panel title="Readiness checks" subtitle="This calendar month">
            <div className="flex items-center justify-between px-6 py-6">
              <div>
                <p className="text-3xl font-semibold tracking-tight text-slate-900">{data.blockers_caught_this_month}</p>
                <p className="mt-1 text-xs text-slate-400">Invoices flagged with blockers</p>
              </div>
              <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 text-lg text-amber-700">!</span>
            </div>
          </Panel>
          <Panel title="Your next step" subtitle="Keep every outgoing message owner-approved">
            <div className="p-5">
              <p className="text-sm leading-6 text-slate-600">Review drafts before anything is sent to a customer. Munshi keeps the final decision with you.</p>
              <Link to="/approvals" className="mt-4 inline-flex text-xs font-semibold text-emerald-700 hover:text-emerald-800">Open approvals inbox <span aria-hidden="true" className="ml-1">→</span></Link>
            </div>
          </Panel>
        </div>
      </div>
    </>
  )
}
