import { useState, type FormEvent, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  checkReadiness,
  createInvoice,
  fetchCustomers,
  uploadInvoiceDocument,
} from '../api/client'
import { Button, EmptyState, ErrorNotice, LoadingState, PageHeader, Panel, StateBadge } from '../components/ui'
import type { Finding, InvoiceCreateResult, ReadinessResult } from '../types'

const DOCUMENT_TYPES = ['INVOICE_PDF', 'PO_COPY', 'SIGNED_CHALLAN', 'GRN', 'EWAY_BILL', 'OTHER']

export default function NewInvoice() {
  const queryClient = useQueryClient()
  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
    refetchInterval: 3000,
  })
  const [created, setCreated] = useState<InvoiceCreateResult | null>(null)
  const [result, setResult] = useState<ReadinessResult | null>(null)
  const [number, setNumber] = useState('')
  const [customerId, setCustomerId] = useState('')
  const [issueDate, setIssueDate] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [amountRupees, setAmountRupees] = useState('')
  const [poNumber, setPoNumber] = useState('')
  const [docType, setDocType] = useState(DOCUMENT_TYPES[0])
  const [file, setFile] = useState<File | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: createInvoice,
    onSuccess: (invoice) => {
      setCreated(invoice)
      setResult(invoice.readiness === null ? null : {
        readiness: invoice.readiness,
        findings: invoice.findings,
        memory_pending: false,
      })
      setFile(null)
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!created || !file) throw new Error('Choose a document to upload.')
      return uploadInvoiceDocument(created.id, docType, file)
    },
    onSuccess: () => {
      setFile(null)
      void readinessMutation.mutateAsync()
    },
  })

  const readinessMutation = useMutation({
    mutationFn: () => {
      if (!created) throw new Error('Create an invoice before checking readiness.')
      return checkReadiness(created.id)
    },
    onSuccess: setResult,
  })

  function submitInvoice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const rupees = Number(amountRupees)
    const paise = Math.round(rupees * 100)
    if (!Number.isFinite(rupees) || !Number.isSafeInteger(paise) || paise <= 0) {
      setFormError('Enter an amount greater than zero with no more than two decimal places.')
      return
    }
    setFormError(null)
    createMutation.mutate({
      customer_id: Number(customerId),
      number: number.trim(),
      issue_date: issueDate,
      due_date: dueDate,
      amount_paise: paise,
      ...(poNumber.trim() ? { po_number: poNumber.trim() } : {}),
    })
  }

  function submitDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    uploadMutation.mutate()
  }

  const findings = result?.findings ?? []

  return (
    <>
      <PageHeader
        title="New invoice"
        description="Create an invoice and review its readiness before it moves forward."
      />
      {customers.isPending ? (
        <LoadingState label="Loading customer records…" />
      ) : customers.isError ? (
        <ErrorNotice message={customers.error.message} retry={() => void customers.refetch()} />
      ) : customers.data.length === 0 ? (
        <Panel><EmptyState title="No customers available" detail="Create or import a customer record before adding an invoice." /></Panel>
      ) : (
        <div className="grid items-start gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <Panel title="Invoice details" subtitle="Amounts are entered in rupees and sent to the ledger as paise.">
            <form onSubmit={submitInvoice} className="space-y-5 p-5 sm:p-6">
              <Field label="Customer" required>
                <select required value={customerId} onChange={(event) => setCustomerId(event.target.value)} className="field-control">
                  <option value="">Select a customer</option>
                  {customers.data.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}
                </select>
              </Field>
              <Field label="Invoice number" required>
                <input required maxLength={100} value={number} onChange={(event) => setNumber(event.target.value)} placeholder="e.g. INV-1042" className="field-control" />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Issue date" required>
                  <input required type="date" value={issueDate} onChange={(event) => setIssueDate(event.target.value)} className="field-control" />
                </Field>
                <Field label="Due date" required>
                  <input required type="date" min={issueDate || undefined} value={dueDate} onChange={(event) => setDueDate(event.target.value)} className="field-control" />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Invoice amount (₹)" required>
                  <input required min="0.01" step="0.01" type="number" value={amountRupees} onChange={(event) => setAmountRupees(event.target.value)} placeholder="0.00" className="field-control" />
                </Field>
                <Field label="Purchase order number">
                  <input value={poNumber} onChange={(event) => setPoNumber(event.target.value)} placeholder="Optional" className="field-control" />
                </Field>
              </div>
              {createMutation.isError && <ErrorNotice message={createMutation.error.message} />}
              {formError && <ErrorNotice message={formError} />}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5">
                <p className="text-[11px] text-slate-400">Readiness is checked by the backend.</p>
                <Button type="submit" disabled={createMutation.isPending || !customerId}>
                  {createMutation.isPending ? 'Creating…' : 'Create and check readiness'}
                </Button>
              </div>
            </form>
          </Panel>

          <div className="space-y-5">
            {created ? (
              <Panel
                title="Readiness result"
                subtitle={`Invoice #${created.id} · ${created.status}`}
                action={result && <StateBadge value={result.readiness} />}
              >
                {result ? (
                  <>
                    {findings.length === 0 ? (
                      <EmptyState title="No findings returned" detail="The backend did not return readiness findings for this invoice." />
                    ) : (
                      <div className="divide-y divide-slate-100">
                        {findings.map((finding, index) => <FindingRow key={`${finding.code}-${index}`} finding={finding} />)}
                      </div>
                    )}
                    {result.memory_pending && <p className="border-t border-slate-100 px-5 py-3 text-xs text-amber-700">Customer memory is still being processed.</p>}
                    <div className="border-t border-slate-100 p-4">
                      <Button variant="secondary" disabled={readinessMutation.isPending} onClick={() => readinessMutation.mutate()}>
                        {readinessMutation.isPending ? 'Checking…' : 'Recheck readiness'}
                      </Button>
                    </div>
                  </>
                ) : created.readiness === null ? (
                  <EmptyState title="No readiness state returned" detail="The backend created this invoice without returning a readiness result." />
                ) : <LoadingState label="Checking invoice readiness…" />}
              </Panel>
            ) : (
              <Panel title="Readiness review" subtitle="Results will appear after the invoice is created.">
                <EmptyState title="Ready for a review" detail="Munshi will show rule and memory findings returned by the backend here." />
              </Panel>
            )}

            {created && (
              <Panel title="Attach invoice documents" subtitle="Upload one document, then run readiness again.">
                <form onSubmit={submitDocument} className="space-y-4 p-5">
                  <Field label="Document type" required>
                    <select value={docType} onChange={(event) => setDocType(event.target.value)} className="field-control">
                                      {DOCUMENT_TYPES.map((type) => <option key={type} value={type}>{type.replace(/_/g, ' ')}</option>)}
                    </select>
                  </Field>
                  <Field label="File" required>
                    <input type="file" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="block w-full text-xs text-slate-500 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-slate-600 hover:file:bg-slate-200" />
                  </Field>
                  {uploadMutation.isError && <ErrorNotice message={uploadMutation.error.message} />}
                  {readinessMutation.isError && <ErrorNotice message={readinessMutation.error.message} />}
                  <Button type="submit" variant="secondary" disabled={!file || uploadMutation.isPending || readinessMutation.isPending}>
                    {uploadMutation.isPending || readinessMutation.isPending ? 'Uploading and checking…' : 'Upload and recheck'}
                  </Button>
                </form>
              </Panel>
            )}
          </div>
        </div>
      )}
    </>
  )
}

function Field({ label, required, children }: { label: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="block text-xs font-medium text-slate-600">
      {label}{required && <span className="ml-1 text-rose-500">*</span>}
      <div className="mt-1.5">{children}</div>
    </label>
  )
}

function FindingRow({ finding }: { finding: Finding }) {
  return (
    <div className="px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-600">{finding.code}</span>
        <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{finding.source}</span>
      </div>
      <p className="mt-2 text-sm leading-5 text-slate-600">{finding.message}</p>
      {finding.evidence_ids.length > 0 && <p className="mt-2 text-[10px] text-slate-400">Evidence: {finding.evidence_ids.join(', ')}</p>}
    </div>
  )
}
