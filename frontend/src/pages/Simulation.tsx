import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { advanceSimulation, fetchCustomers, injectSimulationEvent, resetSimulation } from '../api/client'
import { Button, ErrorNotice, LoadingState, PageHeader, Panel } from '../components/ui'
import type { SimulationInjectionResult, SimulationResetResult, SimulationTickResult } from '../types'

const eventTypes = ['CONTACT_CHANGE', 'REQUIREMENT_CHANGE', 'DISTRESS_START'] as const

export default function Simulation() {
  const queryClient = useQueryClient()
  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
    refetchInterval: 3000,
  })
  const [days, setDays] = useState('1')
  const [customerId, setCustomerId] = useState('')
  const [eventType, setEventType] = useState<(typeof eventTypes)[number]>('CONTACT_CHANGE')
  const [payloadText, setPayloadText] = useState('{}')
  const [clock, setClock] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [eventResult, setEventResult] = useState<SimulationInjectionResult | null>(null)

  const reset = useMutation({
    mutationFn: () => resetSimulation('demo'),
    onSuccess: (result: SimulationResetResult) => {
      setClock(result.clock)
      setMessage('Demo simulation reset. Demo data was re-seeded by the backend.')
      setEventResult(null)
      void queryClient.invalidateQueries()
    },
  })
  const tick = useMutation({
    mutationFn: () => advanceSimulation(Number(days)),
    onSuccess: (result: SimulationTickResult) => {
      setClock(result.clock)
      setMessage(`Simulation advanced. ${result.drafts_created} drafts created · ${result.alerts_raised} alerts raised.`)
      void queryClient.invalidateQueries()
    },
  })
  const inject = useMutation({
    mutationFn: injectSimulationEvent,
    onSuccess: (result) => {
      setEventResult(result)
      setMessage(result.ok ? 'The backend acknowledged this event injection.' : 'The backend did not confirm the event injection.')
      void queryClient.invalidateQueries()
    },
  })

  function submitInjection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    let payload: unknown
    try {
      payload = JSON.parse(payloadText) as unknown
    } catch {
      setMessage('Payload must be valid JSON.')
      return
    }
    if (!isPayloadRecord(payload)) {
      setMessage('Payload must be a JSON object.')
      return
    }
    if (!customerId) {
      setMessage('Choose a customer for this event.')
      return
    }
    setMessage(null)
    setEventResult(null)
    inject.mutate({
      customer_id: Number(customerId),
      type: eventType,
      payload,
    })
  }

  const isPending = reset.isPending || tick.isPending || inject.isPending
  const errors = [reset.error, tick.error, inject.error].filter((error): error is Error => error !== null)

  return (
    <>
      <PageHeader title="Simulation console" description="Control the local demo clock and send documented synthetic events to the backend." />
      {errors.map((error) => <div key={error.message} className="mb-4"><ErrorNotice message={error.message} /></div>)}
      {message && <div role="status" className={`mb-5 rounded-xl border px-4 py-3 text-sm ${eventResult?.ok === false ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>{message}</div>}

      <div className="grid items-start gap-5 xl:grid-cols-2">
        <Panel title="Simulation clock" subtitle="Simulation controls are available only when the backend enables SIM_MODE.">
          <div className="p-5 sm:p-6">
            <div className="rounded-xl bg-slate-50 p-5">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Current simulated date</p>
              <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-800">{clock ?? 'Not available yet'}</p>
              {!clock && <p className="mt-1 text-xs text-slate-400">Reset or advance the clock to receive its current value.</p>}
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto]">
              <label className="text-xs font-medium text-slate-600">
                Advance by days
                <input type="number" min={1} max={365} value={days} onChange={(event) => setDays(event.target.value)} className="field-control mt-1.5" />
              </label>
              <Button
                className="self-end"
                disabled={isPending || !Number.isInteger(Number(days)) || Number(days) < 1 || Number(days) > 365}
                onClick={() => { setMessage(null); tick.mutate() }}
              >
                {tick.isPending ? 'Advancing…' : 'Advance time'}
              </Button>
            </div>
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5">
              <p className="max-w-sm text-xs leading-5 text-slate-400">Reset replaces the current demo database with a fresh seed.</p>
              <Button variant="danger" disabled={isPending} onClick={() => {
                if (window.confirm('Reset the demo database and replace its current contents with a fresh demo seed?')) {
                  setMessage(null)
                  reset.mutate()
                }
              }}>
                {reset.isPending ? 'Resetting…' : 'Reset demo'}
              </Button>
            </div>
          </div>
        </Panel>

        <Panel title="Inject scenario event" subtitle="Event types and payloads are passed to the documented simulator endpoint.">
          {customers.isPending ? (
            <div className="p-5"><LoadingState label="Loading customer list…" /></div>
          ) : customers.isError ? (
            <div className="p-5"><ErrorNotice message={customers.error.message} retry={() => void customers.refetch()} /></div>
          ) : (
            <form onSubmit={submitInjection} className="space-y-4 p-5 sm:p-6">
              <label className="block text-xs font-medium text-slate-600">
                Customer
                <select required value={customerId} onChange={(event) => setCustomerId(event.target.value)} className="field-control mt-1.5">
                  <option value="">Select a customer</option>
                  {customers.data.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}
                </select>
              </label>
              <label className="block text-xs font-medium text-slate-600">
                Event type
                <select value={eventType} onChange={(event) => setEventType(event.target.value as (typeof eventTypes)[number])} className="field-control mt-1.5">
                  {eventTypes.map((type) => <option key={type} value={type}>{type.replace(/_/g, ' ')}</option>)}
                </select>
              </label>
              <label className="block text-xs font-medium text-slate-600">
                JSON payload
                <textarea rows={4} value={payloadText} onChange={(event) => setPayloadText(event.target.value)} className="field-control mt-1.5 font-mono text-xs" />
              </label>
              <p className="text-[11px] leading-5 text-slate-400">The backend currently acknowledges the injection request; the response does not report whether customer state changed.</p>
              <Button type="submit" disabled={isPending || !customerId}>
                {inject.isPending ? 'Sending event…' : 'Inject event'}
              </Button>
            </form>
          )}
        </Panel>
      </div>
    </>
  )
}

function isPayloadRecord(value: unknown): value is Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  return true
}
