import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  approveAction,
  confirmActionDelivery,
  explainAction,
  fetchActions,
  getActionHandoffUrl,
  rejectAction,
} from '../api/client'
import { Button, EmptyState, ErrorNotice, LoadingState, PageHeader, Panel } from '../components/ui'
import { formatDateTime } from '../lib/format'

export default function Approvals() {
  const queryClient = useQueryClient()
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editedBodies, setEditedBodies] = useState<Record<number, string>>({})
  const [reasons, setReasons] = useState<Record<number, string>>({})
  const [feedback, setFeedback] = useState<string | null>(null)
  const [whatsAppLink, setWhatsAppLink] = useState<string | null>(null)

  const actions = useQuery({
    queryKey: ['actions', 'review-and-handoff'],
    queryFn: async () => {
      const [drafts, approved, edited] = await Promise.all([
        fetchActions('DRAFTED'),
        fetchActions('APPROVED'),
        fetchActions('EDITED'),
      ])
      return [...drafts, ...approved, ...edited]
    },
    refetchInterval: 3000,
  })

  const explanation = useQuery({
    queryKey: ['action-explanation', expandedId],
    queryFn: () => explainAction(expandedId ?? 0),
    enabled: expandedId !== null,
  })

  const approve = useMutation({
    mutationFn: ({ id, body }: { id: number; body?: string }) => approveAction(id, body),
    onSuccess: (result) => {
      setFeedback(`Draft ${result.id} approved. It is ready for manual handoff; it has not been sent.`)
      setWhatsAppLink(result.handoff_url ?? null)
      setEditingId(null)
      void queryClient.invalidateQueries({ queryKey: ['actions', 'review-and-handoff'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const confirmDelivery = useMutation({
    mutationFn: (id: number) => confirmActionDelivery(id),
    onSuccess: (result) => {
      setFeedback(`You reported action ${result.id} as sent. WhatsApp provider delivery was not verified.`)
      void queryClient.invalidateQueries({ queryKey: ['actions', 'review-and-handoff'] })
    },
  })

  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) => rejectAction(id, reason),
    onSuccess: (result) => {
      setFeedback(`Draft ${result.id} rejected.`)
      setWhatsAppLink(null)
      void queryClient.invalidateQueries({ queryKey: ['actions', 'review-and-handoff'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  function approveDraft(id: number, originalBody: string) {
    const body = editedBodies[id]
    approve.mutate({ id, ...(body !== undefined && body !== originalBody ? { body } : {}) })
  }

  return (
    <>
      <PageHeader
        title="Approvals inbox"
        description="Review each evidence-backed draft. Messages are only acted on after your explicit approval."
      />
      {feedback && (
        <div role="status" className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span>{feedback}</span>
          {whatsAppLink && <a className="font-semibold underline underline-offset-2" href={whatsAppLink} target="_blank" rel="noreferrer">Open WhatsApp handoff</a>}
        </div>
      )}
      {approve.isError && <div className="mb-5"><ErrorNotice message={approve.error.message} /></div>}
      {reject.isError && <div className="mb-5"><ErrorNotice message={reject.error.message} /></div>}
      {confirmDelivery.isError && <div className="mb-5"><ErrorNotice message={confirmDelivery.error.message} /></div>}
      {actions.isPending ? (
        <LoadingState label="Loading drafts awaiting your review…" />
      ) : actions.isError ? (
        <ErrorNotice message={actions.error.message} retry={() => void actions.refetch()} />
      ) : actions.data.length === 0 ? (
        <Panel><EmptyState title="Inbox is clear" detail="There are no drafts awaiting approval or approved handoffs awaiting confirmation." /></Panel>
      ) : (
        <div className="space-y-4">
          {actions.data.map((action) => {
            const body = editedBodies[action.id] ?? action.body
            const isEditing = editingId === action.id
            const isExpanded = expandedId === action.id
            const isApproved = action.status === 'APPROVED' || action.status === 'EDITED'
            return (
              <Panel key={action.id} className="overflow-hidden">
                <article>
                  <div className="flex flex-col gap-4 border-b border-slate-100 p-5 sm:flex-row sm:items-start sm:justify-between sm:px-6">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-slate-800">{action.customer}</span>
                        <span className="rounded bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-500">{action.kind.replace(/_/g, ' ')}</span>
                      </div>
                      <p className="mt-1.5 text-xs text-slate-500">To {action.recipient} · {action.channel} · Invoice #{action.invoice_id}</p>
                      {action.planned_for && <p className="mt-1 text-[11px] text-slate-400">Proposed for {formatDateTime(action.planned_for)} IST</p>}
                    </div>
                    <span className="shrink-0 rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-blue-700">
                      {isApproved ? 'APPROVED · READY FOR HANDOFF' : 'AWAITING REVIEW'}
                    </span>
                  </div>

                  <div className="p-5 sm:px-6">
                    {isEditing ? (
                      <label className="block text-xs font-medium text-slate-600">
                        Edit proposed message
                        <textarea
                          aria-label={`Edit draft ${action.id}`}
                          rows={4}
                          value={body}
                          onChange={(event) => setEditedBodies((current) => ({ ...current, [action.id]: event.target.value }))}
                          className="field-control mt-2 resize-y"
                        />
                      </label>
                    ) : (
                      <p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm leading-6 text-slate-700">{body}</p>
                    )}
                    {action.attachments.length > 0 && <p className="mt-3 text-xs text-slate-500">Attachments: {action.attachments.join(', ')}</p>}
                    <div className="mt-4 rounded-lg border-l-2 border-emerald-400 bg-emerald-50/60 px-4 py-3">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-800">Why this draft</p>
                      <p className="mt-1 text-xs leading-5 text-emerald-900/80">{action.why}</p>
                    </div>
                    {action.evidence.length > 0 && (
                      <ul className="mt-3 space-y-2">
                        {action.evidence.map((item) => (
                          <li key={item.id} className="rounded-md bg-slate-50 p-3 text-xs leading-5 text-slate-600">
                            {item.date} · {item.text}
                          </li>
                        ))}
                      </ul>
                    )}

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      {!isApproved && (
                        <>
                      <Button disabled={approve.isPending || reject.isPending || !body.trim()} onClick={() => approveDraft(action.id, action.body)}>
                        {approve.isPending && approve.variables?.id === action.id ? 'Approving…' : 'Approve'}
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={approve.isPending || reject.isPending}
                        onClick={() => {
                          if (isEditing) {
                            setEditedBodies((current) => ({ ...current, [action.id]: action.body }))
                            setEditingId(null)
                          } else {
                            setEditedBodies((current) => ({ ...current, [action.id]: current[action.id] ?? action.body }))
                            setEditingId(action.id)
                          }
                        }}
                      >
                        {isEditing ? 'Cancel edit' : 'Edit'}
                      </Button>
                      <Button
                        variant="danger"
                        disabled={approve.isPending || reject.isPending}
                        onClick={() => reject.mutate({ id: action.id, reason: reasons[action.id] })}
                      >
                        {reject.isPending && reject.variables?.id === action.id ? 'Rejecting…' : 'Reject'}
                      </Button>
                        </>
                      )}
                      {isApproved && action.handoff_url && (
                        <a
                          className="inline-flex items-center justify-center rounded-lg bg-emerald-700 px-4 py-2.5 text-xs font-semibold text-white hover:bg-emerald-800"
                          href={getActionHandoffUrl(action.id)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open WhatsApp handoff
                        </a>
                      )}
                      {isApproved && action.handoff_opened_at && (
                        <>
                          <span className="text-xs text-amber-700">Handoff link opened · awaiting your confirmation</span>
                          <Button
                            disabled={confirmDelivery.isPending}
                            onClick={() => confirmDelivery.mutate(action.id)}
                          >
                            {confirmDelivery.isPending && confirmDelivery.variables === action.id ? 'Saving…' : 'I sent this message'}
                          </Button>
                        </>
                      )}
                      <Button
                        variant="quiet"
                        aria-expanded={isExpanded}
                        onClick={() => setExpandedId(isExpanded ? null : action.id)}
                      >
                        {isExpanded ? 'Hide explanation' : 'View explanation'}
                      </Button>
                    </div>
                    {!isApproved && <label className="mt-4 block text-[11px] text-slate-400">
                      Rejection reason (optional)
                      <input
                        value={reasons[action.id] ?? ''}
                        onChange={(event) => setReasons((current) => ({ ...current, [action.id]: event.target.value }))}
                        placeholder="Add a note for the record"
                        className="field-control mt-1.5"
                      />
                    </label>}
                  </div>

                  {isExpanded && (
                    <div className="border-t border-slate-100 bg-slate-50/70 px-5 py-4 sm:px-6">
                      {explanation.isPending ? <p className="text-xs text-slate-400">Loading explanation…</p>
                        : explanation.isError ? <ErrorNotice message={explanation.error.message} retry={() => void explanation.refetch()} />
                          : explanation.data && (
                            <>
                              <p className="text-xs font-semibold text-slate-700">{explanation.data.summary}</p>
                              {explanation.data.evidence.length === 0 ? (
                                <p className="mt-2 text-xs text-slate-500">No supporting evidence was returned by the backend.</p>
                              ) : (
                                <ul className="mt-3 space-y-2">
                                  {explanation.data.evidence.map((item) => <li key={item.id} className="rounded-md bg-white p-3 text-xs leading-5 text-slate-600">{item.date} · {item.text}</li>)}
                                </ul>
                              )}
                            </>
                          )}
                    </div>
                  )}
                </article>
              </Panel>
            )
          })}
        </div>
      )}
    </>
  )
}
