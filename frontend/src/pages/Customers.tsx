import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCustomers } from '../api/client'
import { EmptyState, ErrorNotice, LoadingState, PageHeader, Panel, RiskBadge } from '../components/ui'
import { formatMoney } from '../lib/format'

export default function Customers() {
  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
    refetchInterval: 3000,
  })

  return (
    <>
      <PageHeader
        title="Customers"
        description="Review open exposure, overdue balances and customer risk from your business ledger."
      />
      {customers.isPending ? (
        <LoadingState label="Loading customers…" />
      ) : customers.isError ? (
        <ErrorNotice message={customers.error.message} retry={() => void customers.refetch()} />
      ) : (
        <Panel title="Customer portfolio" subtitle={`${customers.data.length} customer records`}>
          {customers.data.length === 0 ? (
            <EmptyState title="No customers found" detail="Customer records will appear here when available from the backend." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left">
                <thead className="bg-slate-50 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-6 py-3.5">Customer</th>
                    <th className="px-6 py-3.5">Risk</th>
                    <th className="px-6 py-3.5 text-right">Open invoices</th>
                    <th className="px-6 py-3.5 text-right">Overdue balance</th>
                    <th className="px-6 py-3.5"><span className="sr-only">Open</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {customers.data.map((customer) => (
                    <tr key={customer.id} className="hover:bg-slate-50/70">
                      <td className="px-6 py-4">
                        <Link to={`/customers/${customer.id}`} className="font-semibold text-slate-800 hover:text-emerald-700">{customer.name}</Link>
                        <p className="mt-1 text-[11px] text-slate-400">Customer #{customer.id}</p>
                      </td>
                      <td className="px-6 py-4"><RiskBadge level={customer.risk_level} /></td>
                      <td className="px-6 py-4 text-right text-sm text-slate-600">{customer.open_invoices}</td>
                      <td className="px-6 py-4 text-right text-sm font-medium text-slate-700">{formatMoney(customer.overdue_paise)}</td>
                      <td className="px-6 py-4 text-right">
                        <Link to={`/customers/${customer.id}`} className="text-xs font-semibold text-emerald-700">View →</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </>
  )
}
