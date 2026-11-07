export type RiskLevel = 'NORMAL' | 'WATCH' | 'HIGH'
export type Readiness = 'READY' | 'BLOCKER' | 'CONFLICT' | 'UNCERTAIN'
export type Evidence = {
  id: string
  date: string
  text: string
  event_id: string
}

export interface CustomerSummary {
  id: number
  name: string
  risk_level: RiskLevel
  open_invoices: number
  overdue_paise: number
}

export interface CustomerRecord {
  id: number
  name: string
  gstin: string
  state_code: string
  credit_days: number
  po_required: boolean
  required_docs: string[]
  contact_name: string | null
  contact_role: string | null
  risk_level: RiskLevel
}

export interface Belief {
  text: string
  trend: string
  evidence_count: number
  evidence: Evidence[]
}

export interface CustomerDetail {
  customer: CustomerRecord
  playbook: { text: string; updating: boolean }
  beliefs: Belief[]
  timeline: Array<{ date: string; kind: string; text: string }>
}

export interface DashboardSummary {
  total_receivable_paise: number
  overdue_paise: number
  at_risk_customers: Array<Pick<CustomerSummary, 'id' | 'name' | 'risk_level'>>
  pending_drafts: number
  blockers_caught_this_month: number
}

export interface Finding {
  code: string
  source: 'RULE' | 'MEMORY'
  message: string
  evidence_ids: string[]
}

export interface InvoiceCreateRequest {
  customer_id: number
  number: string
  issue_date: string
  due_date: string
  amount_paise: number
  po_number?: string
}

export interface InvoiceCreateResult {
  id: number
  status: string
  readiness: Readiness | null
  findings: Finding[]
}

export interface ReadinessResult {
  readiness: Readiness
  findings: Finding[]
  memory_pending: boolean
}

export type ActionStatus = 'DRAFTED' | 'APPROVED' | 'EDITED' | 'REJECTED' | 'SENT'

export interface ActionDraft {
  id: number
  invoice_id: number
  customer: string
  kind: 'REMINDER' | 'DOC_SEND' | 'THANK_YOU' | 'ESCALATION_REQUEST'
  channel: string
  recipient: string
  body: string
  planned_for: string | null
  attachments: string[]
  status: ActionStatus
  why: string
}

export interface ActionExplanation {
  summary: string
  evidence: Evidence[]
}

export interface ApprovalResult {
  id: number
  status: ActionStatus
  sent_at?: string | null
  whatsapp_link?: string | null
  memory_event_id?: string | null
}

export interface RejectionResult {
  id: number
  status: ActionStatus
}

export interface RiskAlert {
  id: number
  customer_id: number
  from_level: RiskLevel
  to_level: RiskLevel
  signals: string[]
  suggestion: string | null
  evidence: Evidence[]
  status: 'OPEN' | 'ACKNOWLEDGED' | 'DISMISSED'
  created_at: string
}

export interface SimulationResetResult {
  clock: string
}

export interface SimulationTickResult {
  clock: string
  drafts_created: number
  alerts_raised: number
}

export interface SimulationInjection {
  customer_id?: number
  type: 'CONTACT_CHANGE' | 'REQUIREMENT_CHANGE' | 'DISTRESS_START'
  payload: Record<string, unknown>
}

export interface SimulationInjectionResult {
  ok: boolean
}

export interface LearningPoint {
  month: number
  known_facts: number
  total_facts: number
  coverage: number | null
  seed_count?: number
}

export interface ArmMetrics {
  average_days_late?: number | null
  average_days_late_sample_count?: number
  avg_days_late_by_month?: Record<string, number | null>
  early_warning_lead_time?: number | null
  early_warning_sample_count?: number
  blocker_catch_rate?: number | null
  blocker_cases?: number
  learning_curve?: LearningPoint[]
  [key: string]: unknown
}

export type EvaluationArm = 'A' | 'B' | 'C'

export interface EvaluationResults {
  git_hash: string
  arms: Record<EvaluationArm, Record<string, ArmMetrics>>
  test_months: number[]
  seeds: number[]
}

export interface ApiErrorPayload {
  error?: {
    code?: string
    message?: string
    details?: unknown
  }
  detail?: string | Array<{ msg?: string; loc?: Array<string | number> }>
}
