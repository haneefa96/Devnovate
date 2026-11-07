import type {
  ActionDraft,
  ActionExplanation,
  ApprovalResult,
  CustomerDetail,
  CustomerSummary,
  DashboardSummary,
  EvaluationResults,
  InvoiceCreateRequest,
  InvoiceCreateResult,
  ReadinessResult,
  RejectionResult,
  RiskAlert,
  SimulationInjection,
  SimulationInjectionResult,
  SimulationResetResult,
  SimulationTickResult,
} from '../types'

const configuredApiUrl = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '')
const API_BASE_URL = configuredApiUrl.endsWith('/api')
  ? configuredApiUrl
  : `${configuredApiUrl}/api`

export class ApiError extends Error {
  status: number
  code: string
  details: unknown

  constructor(status: number, message: string, code = 'HTTP_ERROR', details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch {
    throw new ApiError(0, 'Unable to reach Munshi. Check your connection and try again.', 'NETWORK_ERROR')
  }

  const rawBody = await response.text()
  let body: unknown
  try {
    body = rawBody ? JSON.parse(rawBody) as unknown : undefined
  } catch {
    if (!response.ok) {
      throw new ApiError(response.status, `Request failed (${response.status}).`)
    }
    throw new ApiError(response.status, 'The server returned an invalid response.', 'INVALID_RESPONSE')
  }

  if (!response.ok) {
    const payload = isRecord(body) ? body : {}
    const error = isRecord(payload.error) ? payload.error : {}
    const detail = payload.detail
    const message = stringValue(error.message)
      ?? stringValue(detail)
      ?? validationMessage(detail)
      ?? `Request failed (${response.status}).`
    throw new ApiError(
      response.status,
      message,
      stringValue(error.code) ?? (response.status === 422 ? 'VALIDATION_ERROR' : 'HTTP_ERROR'),
      error.details,
    )
  }

  return body as T
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined
}

function validationMessage(value: unknown): string | undefined {
  if (!Array.isArray(value)) return undefined
  const messages = value.flatMap((item) => {
    if (!isRecord(item) || typeof item.msg !== 'string') return []
    const location = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : ''
    return [location ? `${location}: ${item.msg}` : item.msg]
  })
  return messages.length > 0 ? messages.join('; ') : undefined
}

function jsonBody(value: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  }
}

export function fetchDashboard(): Promise<DashboardSummary> {
  return request('/dashboard')
}

export function fetchCustomers(): Promise<CustomerSummary[]> {
  return request('/customers')
}

export function fetchCustomer(id: number): Promise<CustomerDetail> {
  return request(`/customers/${id}`)
}

export function createInvoice(data: InvoiceCreateRequest): Promise<InvoiceCreateResult> {
  return request('/invoices', jsonBody(data))
}

export function uploadInvoiceDocument(
  invoiceId: number,
  docType: string,
  file: File,
): Promise<{ id: number; doc_type: string }> {
  const form = new FormData()
  form.append('doc_type', docType)
  form.append('file', file)
  return request(`/invoices/${invoiceId}/documents`, { method: 'POST', body: form })
}

export function checkReadiness(invoiceId: number): Promise<ReadinessResult> {
  return request(`/invoices/${invoiceId}/check`, { method: 'POST' })
}

export function fetchActions(status = 'DRAFTED'): Promise<ActionDraft[]> {
  return request(`/actions?status=${encodeURIComponent(status)}`)
}

export function approveAction(actionId: number, editedBody?: string): Promise<ApprovalResult> {
  return request(`/actions/${actionId}/approve`, jsonBody({
    edited_body: editedBody ?? null,
    decided_by: 'owner',
  }))
}

export function rejectAction(actionId: number, reason?: string): Promise<RejectionResult> {
  return request(`/actions/${actionId}/reject`, jsonBody({
    reason: reason || null,
    decided_by: 'owner',
  }))
}

export function explainAction(actionId: number): Promise<ActionExplanation> {
  return request(`/actions/${actionId}/explain`)
}

export function fetchRiskAlerts(status = 'OPEN'): Promise<RiskAlert[]> {
  return request(`/risk/alerts?status=${encodeURIComponent(status)}`)
}

export function acknowledgeRiskAlert(
  alertId: number,
  status: 'ACKNOWLEDGED' | 'DISMISSED',
): Promise<RiskAlert> {
  return request(`/risk/alerts/${alertId}/ack`, jsonBody({ status }))
}

export function resetSimulation(scenario = 'demo'): Promise<SimulationResetResult> {
  return request('/sim/reset', jsonBody({ scenario }))
}

export function advanceSimulation(days: number): Promise<SimulationTickResult> {
  return request(`/sim/tick?days=${encodeURIComponent(days)}`, { method: 'POST' })
}

export function injectSimulationEvent(
  injection: SimulationInjection,
): Promise<SimulationInjectionResult> {
  return request('/sim/inject', jsonBody(injection))
}

export function fetchEvaluationResults(): Promise<EvaluationResults> {
  return request('/eval/results')
}
