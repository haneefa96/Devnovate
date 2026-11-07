import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './api/client'
import type { ActionDraft } from './types'

vi.mock('./api/client', () => ({
  fetchDashboard: vi.fn(),
  fetchCustomers: vi.fn(),
  fetchCustomer: vi.fn(),
  createInvoice: vi.fn(),
  uploadInvoiceDocument: vi.fn(),
  checkReadiness: vi.fn(),
  fetchActions: vi.fn(),
  approveAction: vi.fn(),
  rejectAction: vi.fn(),
  explainAction: vi.fn(),
  fetchRiskAlerts: vi.fn(),
  acknowledgeRiskAlert: vi.fn(),
  resetSimulation: vi.fn(),
  advanceSimulation: vi.fn(),
  injectSimulationEvent: vi.fn(),
  fetchEvaluationResults: vi.fn(),
}))

const customer = {
  id: 12,
  name: 'Reddy Traders',
  risk_level: 'WATCH' as const,
  open_invoices: 2,
  overdue_paise: 482000,
}

function renderApp(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(api.fetchDashboard).mockResolvedValue({
    total_receivable_paise: 482000,
    overdue_paise: 10000,
    at_risk_customers: [{ id: customer.id, name: customer.name, risk_level: customer.risk_level }],
    pending_drafts: 1,
    blockers_caught_this_month: 3,
  })
  vi.mocked(api.fetchCustomers).mockResolvedValue([customer])
  vi.mocked(api.fetchCustomer).mockResolvedValue({
    customer: {
      id: 12,
      name: 'Reddy Traders',
      gstin: '36ABCDE1234F1Z5',
      state_code: '36',
      credit_days: 30,
      po_required: true,
      required_docs: ['SIGNED_CHALLAN'],
      contact_name: 'Rahul',
      contact_role: 'Payables',
      risk_level: 'WATCH',
    },
    playbook: { text: '', updating: true },
    beliefs: [],
    timeline: [{ date: '2026-03-05', kind: 'PAYMENT', text: 'Payment received' }],
    outstanding_paise: 0,
    memory_status: 'AVAILABLE',
  })
  vi.mocked(api.fetchActions).mockResolvedValue([])
  vi.mocked(api.fetchRiskAlerts).mockResolvedValue([])
  vi.mocked(api.fetchEvaluationResults).mockResolvedValue({
    git_hash: '',
    arms: { A: {}, B: {}, C: {} },
    test_months: [4, 5, 6],
    seeds: [1, 2, 3],
  })
})

describe('application screens', () => {
  it('renders dashboard values returned by the API', async () => {
    renderApp('/dashboard')
    expect(await screen.findByText('Total receivables')).toBeInTheDocument()
    expect(screen.getByText('₹4,820.00')).toBeInTheDocument()
    expect(screen.getByText('Reddy Traders')).toBeInTheDocument()
  })

  it('renders customer facts, payment history and the memory updating state', async () => {
    renderApp('/customers/12')
    expect(await screen.findByText('Reddy Traders')).toBeInTheDocument()
    expect(screen.getByText('SIGNED_CHALLAN')).toBeInTheDocument()
    expect(screen.getByText('Payment received')).toBeInTheDocument()
    expect(screen.getByText('Memory is updating')).toBeInTheDocument()
  })

  it('renders the customer portfolio returned by the API', async () => {
    renderApp('/customers')
    expect(await screen.findByText('Customer portfolio')).toBeInTheDocument()
    expect(screen.getByText('Reddy Traders')).toBeInTheDocument()
    expect(screen.getByText('₹4,820.00')).toBeInTheDocument()
  })

  it('renders empty states for approvals, risk and evaluation without inventing results', async () => {
    renderApp('/approvals')
    expect(await screen.findByText('Inbox is clear')).toBeInTheDocument()
    cleanup()
    renderApp('/risk')
    expect(await screen.findByText('No open risk alerts')).toBeInTheDocument()
    cleanup()
    renderApp('/evaluation')
    expect(await screen.findByText('No evaluation results yet', {}, { timeout: 5000 })).toBeInTheDocument()
  })

  it('shows a loading state then a retryable API error on the dashboard', async () => {
    let rejectRequest: (reason?: unknown) => void = () => undefined
    vi.mocked(api.fetchDashboard).mockImplementation(() => new Promise((_, reject) => {
      rejectRequest = reject
    }))
    renderApp('/dashboard')
    expect(screen.getByRole('status')).toHaveTextContent('Loading your collection summary')
    rejectRequest(new Error('Dashboard service unavailable'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Dashboard service unavailable')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('creates an invoice with paise conversion and displays backend readiness', async () => {
    const user = userEvent.setup()
    vi.mocked(api.createInvoice).mockResolvedValue({
      id: 44,
      status: 'DRAFT',
      readiness: 'BLOCKER',
      findings: [{ code: 'R4_PO', source: 'RULE', message: 'Purchase order is missing', evidence_ids: [] }],
    })
    renderApp('/invoices/new')
    await user.selectOptions(await screen.findByLabelText(/Customer/), '12')
    await user.type(screen.getByLabelText(/Invoice number/), 'INV-44')
    await user.type(screen.getByLabelText(/Issue date/), '2026-04-01')
    await user.type(screen.getByLabelText(/Due date/), '2026-04-30')
    await user.type(screen.getByLabelText(/Invoice amount/), '1250.50')
    await user.click(screen.getByRole('button', { name: 'Create and check readiness' }))

    await waitFor(() => expect(vi.mocked(api.createInvoice).mock.calls[0]?.[0]).toEqual({
      customer_id: 12,
      number: 'INV-44',
      issue_date: '2026-04-01',
      due_date: '2026-04-30',
      amount_paise: 125050,
    }))
    expect(await screen.findByText('Purchase order is missing')).toBeInTheDocument()
    expect(screen.getByText('BLOCKER')).toBeInTheDocument()
  })

  it('submits the edited message through the owner approval endpoint', async () => {
    const user = userEvent.setup()
    const draft: ActionDraft = {
      id: 3,
      invoice_id: 10,
      customer: 'Reddy Traders',
      kind: 'REMINDER',
      channel: 'WHATSAPP',
      recipient: 'Rahul',
      body: 'Original reminder',
      planned_for: null,
      attachments: [],
      status: 'DRAFTED',
      why: 'Invoice is due soon.',
      evidence: [],
      handoff_url: null,
      handoff_opened_at: null,
      delivery_confirmation_source: null,
    }
    vi.mocked(api.fetchActions).mockImplementation(async (status = 'DRAFTED') =>
      status === 'DRAFTED' ? [draft] : [],
    )
    vi.mocked(api.approveAction).mockResolvedValue({
      id: 3,
      status: 'APPROVED',
      sent_at: null,
      handoff_url: '/api/actions/3/handoff',
      whatsapp_link: null,
      memory_event_id: null,
      handoff_status: 'READY_FOR_HANDOFF',
    })
    renderApp('/approvals')
    await user.click(await screen.findByRole('button', { name: 'Edit' }))
    await user.clear(screen.getByRole('textbox', { name: 'Edit draft 3' }))
    await user.type(screen.getByRole('textbox', { name: 'Edit draft 3' }), 'Updated reminder')
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(api.approveAction).toHaveBeenCalledWith(3, 'Updated reminder'))
  })

  it('renders simulation controls and customer event fields', async () => {
    renderApp('/simulation')
    expect(await screen.findByText('Simulation clock')).toBeInTheDocument()
    expect(screen.getByLabelText('Advance by hours')).toBeInTheDocument()
    expect(await screen.findByLabelText('Event type')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Advance time' })).toBeInTheDocument()
  })

  it('records an acknowledgement for a risk alert', async () => {
    const user = userEvent.setup()
    vi.mocked(api.fetchRiskAlerts).mockResolvedValue([{
      id: 8,
      customer_id: customer.id,
      from_level: 'WATCH',
      to_level: 'HIGH',
      signals: ['Two missed payment runs'],
      suggestion: 'Review recent payment history.',
      evidence: [],
      memory_status: 'AVAILABLE',
      status: 'OPEN',
      created_at: '2026-03-05T10:00:00+05:30',
    }])
    vi.mocked(api.acknowledgeRiskAlert).mockResolvedValue({
      id: 8,
      customer_id: customer.id,
      from_level: 'WATCH',
      to_level: 'HIGH',
      signals: ['Two missed payment runs'],
      suggestion: 'Review recent payment history.',
      evidence: [],
      memory_status: 'AVAILABLE',
      status: 'ACKNOWLEDGED',
      created_at: '2026-03-05T10:00:00+05:30',
    })
    renderApp('/risk')
    await user.click(await screen.findByRole('button', { name: 'Acknowledge' }))
    await waitFor(() => expect(api.acknowledgeRiskAlert).toHaveBeenCalledWith(8, 'ACKNOWLEDGED'))
  })

  it('submits the selected customer and JSON payload for a scenario event', async () => {
    const user = userEvent.setup()
    vi.mocked(api.injectSimulationEvent).mockResolvedValue({ ok: true })
    renderApp('/simulation')
    await user.selectOptions(await screen.findByLabelText('Customer'), '12')
    await user.selectOptions(screen.getByLabelText('Event type'), 'DISTRESS_START')
    fireEvent.change(screen.getByLabelText('JSON payload'), {
      target: { value: '{"signal":"cash-flow trouble"}' },
    })
    await user.click(screen.getByRole('button', { name: 'Inject event' }))
    await waitFor(() => expect(vi.mocked(api.injectSimulationEvent).mock.calls[0]?.[0]).toEqual({
      customer_id: 12,
      type: 'DISTRESS_START',
      payload: { signal: 'cash-flow trouble' },
    }))
  })
})
