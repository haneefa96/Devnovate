"""
Munshi - API request / response schemas (Pydantic)

All monetary amounts exposed on the API are in integer paise
(same unit used in the database). Callers divide by 100 for INR display.

Contracts align directly with API_DOCUMENTATION.md.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from munshi.db.models import (
    ActionKind,
    ActionStatus,
    CustomerRiskLevel,
    DocType,
    InvoiceReadiness,
    InvoiceStatus,
    RiskAlertStatus,
    SimArm,
)


# ──────────────────────────────────────────────────────────────────
# Standard Error Envelope (as per API_DOCUMENTATION.md)
# ──────────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code:    str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class OKResponse(BaseModel):
    ok: bool = True


# ──────────────────────────────────────────────────────────────────
# Shared shapes
# ──────────────────────────────────────────────────────────────────

class Finding(BaseModel):
    code:         str
    source:       Literal["RULE", "MEMORY"] = "RULE"
    message:      str
    evidence_ids: List[str] = Field(default_factory=list)


class Evidence(BaseModel):
    id:       str
    date:     str
    text:     str
    event_id: str


# ──────────────────────────────────────────────────────────────────
# Business
# ──────────────────────────────────────────────────────────────────

class BusinessOut(BaseModel):
    id:              int
    name:            str
    gstin:           str
    state_code:      str
    msme_registered: bool
    bank_id:         str

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────────────────────────
# Customer
# ──────────────────────────────────────────────────────────────────

class CustomerListItem(BaseModel):
    id:            int
    name:          str
    risk_level:    CustomerRiskLevel
    open_invoices: int               = 0
    overdue_paise: int               = 0


class CustomerRecordOut(BaseModel):
    id:            int
    name:          str
    gstin:         str
    state_code:    str
    credit_days:   int
    po_required:   bool
    required_docs: List[str]
    contact_name:  Optional[str] = None
    contact_role:  Optional[str] = None
    risk_level:    CustomerRiskLevel

    model_config = {"from_attributes": True}


class CustomerPlaybookOut(BaseModel):
    text:     str  = ""
    updating: bool = False


class CustomerBeliefOut(BaseModel):
    text:           str
    trend:          str            = "stable"
    evidence_count: int            = 0
    evidence:       List[Evidence] = Field(default_factory=list)


class CustomerTimelineItem(BaseModel):
    date: str
    kind: str
    text: str


class CustomerDetailOut(BaseModel):
    customer: CustomerRecordOut
    playbook: CustomerPlaybookOut        = Field(default_factory=CustomerPlaybookOut)
    beliefs:  List[CustomerBeliefOut]    = Field(default_factory=list)
    timeline: List[CustomerTimelineItem] = Field(default_factory=list)


class CustomerOut(BaseModel):
    id:              int
    business_id:     int
    name:            str
    gstin:           str
    state_code:      str
    credit_days:     int
    po_required:     bool
    required_docs:   List[str]
    contact_name:    Optional[str] = None
    contact_role:    Optional[str] = None
    contact_phone:   Optional[str] = None
    risk_level:      CustomerRiskLevel
    risk_updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    business_id:   int
    name:          str           = Field(..., max_length=255)
    gstin:         str           = Field(..., max_length=15)
    state_code:    str           = Field(..., max_length=2)
    credit_days:   int           = Field(default=30, ge=0)
    po_required:   bool          = True
    required_docs: List[str]     = Field(default_factory=list)
    contact_name:  Optional[str] = None
    contact_role:  Optional[str] = None
    contact_phone: Optional[str] = None


class CustomerPatch(BaseModel):
    contact_name:  Optional[str]       = None
    contact_role:  Optional[str]       = None
    contact_phone: Optional[str]       = None
    po_required:   Optional[bool]      = None
    required_docs: Optional[List[DocType]] = None
    credit_days:   Optional[int]       = Field(default=None, ge=0)


# ──────────────────────────────────────────────────────────────────
# Invoice
# ──────────────────────────────────────────────────────────────────

class InvoiceCreate(BaseModel):
    customer_id:  int
    number:       str           = Field(..., max_length=100)
    issue_date:   date
    due_date:     date
    amount_paise: int           = Field(..., gt=0, description="Amount in integer paise")
    po_number:    Optional[str] = None

    @field_validator("due_date")
    @classmethod
    def due_after_issue(cls, v: date, info: Any) -> date:
        issue = info.data.get("issue_date")
        if issue and v < issue:
            raise ValueError("due_date must be on or after issue_date")
        return v


class InvoiceCreateOut(BaseModel):
    id:        int
    status:    InvoiceStatus
    readiness: Optional[InvoiceReadiness] = None
    findings:  List[Finding]              = Field(default_factory=list)


class InvoiceCheckOut(BaseModel):
    readiness:      InvoiceReadiness
    findings:       List[Finding] = Field(default_factory=list)
    memory_pending: bool          = False


class InvoiceConfirmIn(BaseModel):
    finding_code: str
    decision:     str = Field(..., pattern="^(CONFIRM_NEW|KEEP_OLD)$")
    note:         str = ""


class InvoiceConfirmOut(BaseModel):
    readiness:        InvoiceReadiness
    customer_updated: bool = False


class InvoiceSendIn(BaseModel):
    override: bool = False


class InvoiceSendOut(BaseModel):
    status:          InvoiceStatus = InvoiceStatus.SENT
    memory_event_id: Optional[str] = None


class DocumentUploadOut(BaseModel):
    id:       int
    doc_type: DocType


class ReadinessCheckOut(BaseModel):
    id:         int
    invoice_id: int
    run_at:     datetime
    result:     InvoiceReadiness
    findings:   List[dict]

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────────────────────────
# Action (approvals inbox & decisions)
# ──────────────────────────────────────────────────────────────────

class ActionOut(BaseModel):
    id:          int
    invoice_id:  int
    customer:    str
    kind:        ActionKind
    channel:     str
    recipient:   str
    body:        str
    planned_for: Optional[datetime] = None
    attachments: List[str] = Field(default_factory=list)
    status:      ActionStatus
    why:         str


class ApproveActionIn(BaseModel):
    edited_body: Optional[str] = None
    decided_by:  str           = Field(default="owner", max_length=255)


class ApproveActionOut(BaseModel):
    id:              int
    status:          ActionStatus = ActionStatus.SENT
    sent_at:         Optional[datetime] = None
    whatsapp_link:   Optional[str] = None
    memory_event_id: Optional[str] = None


class RejectActionIn(BaseModel):
    reason:     Optional[str] = None
    decided_by: str           = Field(default="owner", max_length=255)


class RejectActionOut(BaseModel):
    id:     int
    status: ActionStatus = ActionStatus.REJECTED


class ActionExplainOut(BaseModel):
    summary:  str
    evidence: List[Evidence] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────
# Inbound message
# ──────────────────────────────────────────────────────────────────

class InboundMessageCreate(BaseModel):
    customer_id: int
    invoice_id:  Optional[int] = None
    channel:     str           = Field(..., max_length=50)
    sender_name: str           = Field(..., max_length=255)
    body:        str


class InboundMessageOut(BaseModel):
    id:                int
    memory_event_id:   Optional[str] = None
    risk_check_queued: bool = True


# ──────────────────────────────────────────────────────────────────
# Payment
# ──────────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    invoice_id:   int
    amount_paise: int           = Field(..., gt=0, description="Amount in integer paise")
    paid_on:      date
    reference:    Optional[str] = None


class PaymentOut(BaseModel):
    id:             int
    invoice_status: InvoiceStatus
    days_late:      int = 0


# ──────────────────────────────────────────────────────────────────
# Risk alert
# ──────────────────────────────────────────────────────────────────

class RiskAlertOut(BaseModel):
    id:          int
    customer_id: int
    from_level:  CustomerRiskLevel
    to_level:    CustomerRiskLevel
    signals:     List[str]         = Field(default_factory=list)
    suggestion:  Optional[str]     = None
    evidence:    List[dict]        = Field(default_factory=list)
    status:      RiskAlertStatus   = RiskAlertStatus.OPEN
    created_at:  datetime

    model_config = {"from_attributes": True}


class AckAlertIn(BaseModel):
    status: Literal["ACKNOWLEDGED", "DISMISSED"]


# ──────────────────────────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────────────────────────

class DashboardAtRiskCustomer(BaseModel):
    id:         int
    name:       str
    risk_level: CustomerRiskLevel


class DashboardOut(BaseModel):
    total_receivable_paise:     int
    overdue_paise:              int
    at_risk_customers:          List[DashboardAtRiskCustomer] = Field(default_factory=list)
    pending_drafts:             int
    blockers_caught_this_month: int


# ──────────────────────────────────────────────────────────────────
# Explain API
# ──────────────────────────────────────────────────────────────────

class ExplainIn(BaseModel):
    customer_id: int
    question:    str = Field(..., max_length=500)


class ExplainOut(BaseModel):
    answer:   str
    evidence: List[Evidence] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────
# Simulation / evaluation
# ──────────────────────────────────────────────────────────────────

class SimResetIn(BaseModel):
    scenario: Optional[str] = "demo"


class SimResetOut(BaseModel):
    clock: str


class SimTickOut(BaseModel):
    clock:          str
    drafts_created: int = 0
    alerts_raised:  int = 0


class SimInjectIn(BaseModel):
    customer_id: Optional[int] = None
    type:        Optional[Literal["CONTACT_CHANGE", "REQUIREMENT_CHANGE", "DISTRESS_START"]] = None
    payload:     dict          = Field(default_factory=dict)


class SimInjectOut(BaseModel):
    ok: bool = True


class SimRunOut(BaseModel):
    id:          int
    arm:         SimArm
    seed:        int
    started_at:  datetime
    finished_at: Optional[datetime] = None
    metrics:     dict               = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class EvalResultsOut(BaseModel):
    git_hash:    str            = ""
    arms:        dict           = Field(default_factory=dict)
    test_months: List[int]      = Field(default_factory=lambda: [4, 5, 6])
    seeds:       List[int]      = Field(default_factory=lambda: [1, 2, 3])


# ──────────────────────────────────────────────────────────────────
# Tally CSV Import
# ──────────────────────────────────────────────────────────────────

class TallyRowSkipped(BaseModel):
    row:    int
    reason: str


class TallyImportOut(BaseModel):
    customers_created: int
    invoices_created:  int
    rows_skipped:      List[TallyRowSkipped] = Field(default_factory=list)
