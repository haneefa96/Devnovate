import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { fetchCustomer } from '../api/client'
import { EmptyState, ErrorNotice, LoadingState, PageHeader, Panel, RiskBadge } from '../components/ui'
import { formatDate } from '../lib/format'

export default function CustomerDetail() {
  const { id = '' } = useParams()
  const customerId = Number(id)
  const validId = Number.isInteger(customerId) && customerId > 0
  const customer = useQuery({
    queryKey: ['customer', customerId],
    queryFn: () => fetchCustomer(customerId),
    refetchInterval: 3000,
    enabled: validId,
  })

  if (!validId) return <ErrorNotice message="This customer link is invalid." />
  if (customer.isPending) return <LoadingState label="Loading customer profile…" />
  if (customer.isError) return <ErrorNotice message={customer.error.message} retry={() => void customer.refetch()} />

  const { customer: record, playbook, beliefs, timeline, outstanding_paise, memory_status } = customer.data
  const paymentHistory = timeline.filter((item) => item.kind === 'PAYMENT')
  const otherActivity = timeline.filter((item) => item.kind !== 'PAYMENT')

  return (
    <>
      <Link to="/customers" className="mb-5 inline-flex text-xs font-semibold text-slate-500 hover:text-emerald-700">← All customers</Link>
      <PageHeader
        title={record.name}
        description={`Customer record #${record.id} · GSTIN ${record.gstin}`}
        action={<RiskBadge level={record.risk_level} />}
      />

      <div className="grid gap-5 xl:grid-cols-[1fr_1.2fr]">
        <div className="space-y-5">
          <Panel title="Customer information" subtitle="Structured customer record">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-5 p-5 sm:p-6">
              <Info label="State code" value={record.state_code} />
              <Info label="Credit terms" value={`${record.credit_days} days`} />
              <Info label="Accounts contact" value={record.contact_name || 'Not recorded'} />
              <Info label="Contact role" value={record.contact_role || 'Not recorded'} />
              <Info label="Purchase order" value={record.po_required ? 'Required' : 'Not required'} />
              <Info label="Required documents" value={record.required_docs.length ? record.required_docs.join(', ') : 'None recorded'} />
              <Info label="Outstanding receivable" value={`₹${(outstanding_paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`} />
            </dl>
          </Panel>

          <Panel title="Learned behaviour" subtitle="Supplementary customer context; the SQLite ledger remains authoritative">
            {memory_status === 'UNAVAILABLE' && (
              <p role="status" className="border-b border-amber-100 bg-amber-50 px-5 py-3 text-xs text-amber-800">
                Hindsight is unavailable. No conclusion about the absence of learned customer history can be drawn.
              </p>
            )}
            {playbook.text ? (
              <div className="p-5">
                <p className="whitespace-pre-wrap text-sm leading-6 text-slate-600">{playbook.text}</p>
                {playbook.updating && <p className="mt-4 text-xs text-amber-700">Memory is updating.</p>}
              </div>
            ) : (
              <EmptyState
                title={memory_status === 'UNAVAILABLE' ? 'Learned behaviour unavailable' : playbook.updating ? 'Memory is updating' : 'No learned behaviour returned'}
                detail={memory_status === 'UNAVAILABLE' ? 'Use ledger history below; unavailable memory is not evidence that the customer has no history.' : playbook.updating ? 'The customer playbook and beliefs will appear when memory consolidation is available.' : 'The memory service returned no customer playbook.'}
              />
            )}
            {beliefs.length > 0 && (
              <div className="border-t border-slate-100 divide-y divide-slate-100">
                {beliefs.map((belief, index) => (
                  <article key={`${belief.text}-${index}`} className="p-5">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm leading-6 text-slate-700">{belief.text}</p>
                      <span className="shrink-0 rounded-full bg-slate-100 px-2 py-1 text-[10px] font-medium capitalize text-slate-500">{belief.trend}</span>
                    </div>
                    <p className="mt-2 text-[11px] text-slate-400">{belief.evidence_count} evidence items</p>
                    {belief.evidence.map((evidence) => (
                      <p key={evidence.id} className="mt-2 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-500">
                        <span className="font-medium">{formatDate(evidence.date)} · </span>{evidence.text}
                      </p>
                    ))}
                  </article>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <div className="space-y-5">
          <Panel title="Payment history" subtitle="Payments recorded in the ledger">
            {paymentHistory.length === 0 ? (
              <EmptyState title="No payment history yet" detail="Payments will appear here after they are recorded in the business ledger." />
            ) : (
              <div className="divide-y divide-slate-100">
                {paymentHistory.map((item, index) => (
                  <div key={`${item.date}-${index}`} className="flex items-start gap-4 px-5 py-4">
                    <span className="mt-1 h-2 w-2 rounded-full bg-emerald-500" />
                    <div>
                      <p className="text-sm font-medium text-slate-700">{item.text}</p>
                      <p className="mt-1 text-xs text-slate-400">{formatDate(item.date)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Customer activity" subtitle="Recent interactions and account events">
            {otherActivity.length === 0 ? (
              <EmptyState title="No recent activity" detail="Reminders, customer replies and other timeline events will appear here when the backend provides them." />
            ) : (
              <div className="divide-y divide-slate-100">
                {otherActivity.map((item, index) => (
                  <div key={`${item.date}-${item.kind}-${index}`} className="px-5 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{item.kind.replace(/_/g, ' ')}</span>
                      <span className="text-[11px] text-slate-400">{formatDate(item.date)}</span>
                    </div>
                    <p className="mt-2 text-sm leading-5 text-slate-600">{item.text}</p>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">{label}</dt>
      <dd className="mt-1.5 break-words text-sm font-medium text-slate-700">{value}</dd>
    </div>
  )
}
