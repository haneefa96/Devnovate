import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { acknowledgeRiskAlert, fetchCustomers, fetchRiskAlerts } from '../api/client'
import { Button, EmptyState, ErrorNotice, LoadingState, PageHeader, Panel, RiskBadge, StateBadge } from '../components/ui'
import { formatDateTime } from '../lib/format'

export default function RiskAlerts() {
  const queryClient = useQueryClient()
  const alerts = useQuery({
    queryKey: ['risk-alerts', 'OPEN'],
    queryFn: () => fetchRiskAlerts('OPEN'),
    refetchInterval: 3000,
  })
  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
    refetchInterval: 3000,
  })
  const decision = useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'ACKNOWLEDGED' | 'DISMISSED' }) => acknowledgeRiskAlert(id, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['risk-alerts', 'OPEN'] })
      void queryClient.invalidateQueries({ queryKey: ['customers'] })
    },
  })
  const customerNames = new Map((customers.data ?? []).map((customer) => [customer.id, customer.name]))

  return (
    <>
      <PageHeader title="Risk alerts" description="Review evidence-backed changes in customer risk and record your acknowledgement." />
      {decision.isError && <div className="mb-5"><ErrorNotice message={decision.error.message} /></div>}
      {customers.isError && <div className="mb-5"><ErrorNotice message={`Customer names are unavailable: ${customers.error.message}`} retry={() => void customers.refetch()} /></div>}
      {alerts.isPending ? (
        <LoadingState label="Loading open risk alerts…" />
      ) : alerts.isError ? (
        <ErrorNotice message={alerts.error.message} retry={() => void alerts.refetch()} />
      ) : alerts.data.length === 0 ? (
        <Panel><EmptyState title="No open risk alerts" detail="New open alerts from the backend will appear here." /></Panel>
      ) : (
        <div className="space-y-4">
          {alerts.data.map((alert) => (
            <Panel key={alert.id}>
              <article>
                <div className="flex flex-col gap-3 border-b border-slate-100 p-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{customerNames.get(alert.customer_id) ?? `Customer #${alert.customer_id}`}</p>
                    <p className="mt-1 text-xs text-slate-400">Alert #{alert.id} · {formatDateTime(alert.created_at)} IST</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <RiskBadge level={alert.from_level} />
                    <span className="text-slate-300">→</span>
                    <RiskBadge level={alert.to_level} />
                  </div>
                </div>
                <div className="grid gap-5 p-5 sm:grid-cols-[1.2fr_0.8fr] sm:px-6">
                  <div>
                    <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Supporting signals</h3>
                    {alert.signals.length > 0 ? (
                      <ul className="mt-3 space-y-2">
                        {alert.signals.map((signal, index) => (
                          <li key={`${signal}-${index}`} className="flex gap-2 text-sm leading-5 text-slate-600">
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />{signal}
                          </li>
                        ))}
                      </ul>
                    ) : <p className="mt-2 text-xs text-slate-400">No signal details were returned.</p>}
                    {alert.evidence.length > 0 && (
                      <div className="mt-4 space-y-2">
                        {alert.evidence.map((evidence, index) => (
                          <div key={evidence.id || `${evidence.event_id}-${index}`} className="rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600">
                            <span className="font-medium">{evidence.date} · </span>{evidence.text}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="rounded-lg bg-slate-50 p-4">
                    <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Suggested review</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{alert.suggestion || 'No recommendation was provided by the backend.'}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button disabled={decision.isPending} onClick={() => decision.mutate({ id: alert.id, status: 'ACKNOWLEDGED' })}>
                        {decision.isPending && decision.variables?.id === alert.id ? 'Saving…' : 'Acknowledge'}
                      </Button>
                      <Button variant="secondary" disabled={decision.isPending} onClick={() => decision.mutate({ id: alert.id, status: 'DISMISSED' })}>
                        Dismiss
                      </Button>
                    </div>
                  </div>
                </div>
                <div className="border-t border-slate-100 px-5 py-3 sm:px-6">
                  <StateBadge value={alert.status} />
                </div>
              </article>
            </Panel>
          ))}
        </div>
      )}
    </>
  )
}
