"""
Munshi - Database models (SQLModel / SQLite)

SQLite is the single source of truth for amounts, dates, and statuses.
Hindsight stores narrative memory; amounts never come from Hindsight.

All monetary amounts are stored as integer paise (1 INR = 100 paise).

See ARCHITECTURE.md section 7 and DATABASE_DESIGN.md for entity descriptions.
"""

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import CheckConstraint, Column, Index, JSON, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from munshi.config import clock


def _now() -> datetime:
    """Return the shared simulated/demo clock value."""
    return clock.now()


def _enum_check(column: str, enum_type: type[Enum], name: str) -> CheckConstraint:
    values = ", ".join(f"'{member.value}'" for member in enum_type)
    return CheckConstraint(f"{column} IN ({values})", name=name)


# ──────────────────────────────────────────
# Enums
# ──────────────────────────────────────────

class InvoiceStatus(str, Enum):
    DRAFT       = "DRAFT"
    READY       = "READY"
    SENT        = "SENT"
    HELD        = "HELD"
    PARTLY_PAID = "PARTLY_PAID"
    PAID        = "PAID"
    DISPUTED    = "DISPUTED"
    WRITTEN_OFF = "WRITTEN_OFF"


class InvoiceReadiness(str, Enum):
    READY     = "READY"
    BLOCKER   = "BLOCKER"
    CONFLICT  = "CONFLICT"
    UNCERTAIN = "UNCERTAIN"


class ActionKind(str, Enum):
    REMINDER           = "REMINDER"
    DOC_SEND           = "DOC_SEND"
    THANK_YOU          = "THANK_YOU"
    ESCALATION_REQUEST = "ESCALATION_REQUEST"


class ActionStatus(str, Enum):
    DRAFTED  = "DRAFTED"
    APPROVED = "APPROVED"
    EDITED   = "EDITED"
    REJECTED = "REJECTED"
    SENT     = "SENT"


class CustomerRiskLevel(str, Enum):
    NORMAL = "NORMAL"
    WATCH  = "WATCH"
    HIGH   = "HIGH"


class DocType(str, Enum):
    INVOICE_PDF    = "INVOICE_PDF"
    PO_COPY        = "PO_COPY"
    SIGNED_CHALLAN = "SIGNED_CHALLAN"
    GRN            = "GRN"
    EWAY_BILL      = "EWAY_BILL"
    OTHER          = "OTHER"


class RiskAlertStatus(str, Enum):
    OPEN         = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISMISSED    = "DISMISSED"


class MemoryStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class SimArm(str, Enum):
    A = "A"   # Fixed (no memory)
    B = "B"   # Structured (SQLite-only)
    C = "C"   # Hindsight-powered


# ──────────────────────────────────────────
# Tables (12 Entities)
# ──────────────────────────────────────────

class Business(SQLModel, table=True):
    """
    1. Supplier business — one row per demo/production business.
    Anchors the Hindsight bank and all customers.
    """
    __tablename__ = "business"

    id:              Optional[int] = Field(default=None, primary_key=True)
    name:            str           = Field(..., max_length=255)
    gstin:           str           = Field(..., max_length=15, unique=True, index=True)
    state_code:      str           = Field(..., max_length=2)
    msme_registered: bool          = Field(default=False)
    # Hindsight bank ID for this business, e.g. "munshi-demo"
    bank_id:         str           = Field(..., max_length=100)

    customers: List["Customer"] = Relationship(back_populates="business")


class Customer(SQLModel, table=True):
    """
    2. Buyer / debtor. One row per customer per business.
    Required documents are stored as a JSON array of DocType strings.
    """
    __tablename__ = "customer"
    __table_args__ = (
        CheckConstraint("credit_days >= 0", name="ck_customer_credit_days_nonnegative"),
        _enum_check("risk_level", CustomerRiskLevel, "ck_customer_risk_level"),
        Index("ix_customer_business_id", "business_id"),
        Index("ix_customer_risk_level", "risk_level"),
        Index("ix_customer_gstin", "gstin"),
    )

    id:              Optional[int]      = Field(default=None, primary_key=True)
    business_id:     int                = Field(..., foreign_key="business.id")
    name:            str                = Field(..., max_length=255)
    gstin:           str                = Field(..., max_length=15)
    state_code:      str                = Field(..., max_length=2)
    credit_days:     int                = Field(default=30, ge=0)
    po_required:     bool               = Field(default=True)
    required_docs:   List[str]          = Field(default_factory=list, sa_column=Column(JSON))
    contact_name:    Optional[str]      = Field(default=None, max_length=255)
    contact_role:    Optional[str]      = Field(default=None, max_length=255)
    contact_phone:   Optional[str]      = Field(default=None, max_length=20)
    risk_level:      CustomerRiskLevel  = Field(default=CustomerRiskLevel.NORMAL)
    risk_updated_at: Optional[datetime] = Field(default=None)

    business:         Business               = Relationship(back_populates="customers")
    invoices:         List["Invoice"]        = Relationship(back_populates="customer")
    inbound_messages: List["InboundMessage"] = Relationship(back_populates="customer")
    payments:         List["Payment"]        = Relationship(back_populates="customer")
    promises:         List["Promise"]        = Relationship(back_populates="customer")
    risk_alerts:      List["RiskAlert"]      = Relationship(back_populates="customer")
    memory_events:    List["MemoryEvent"]    = Relationship(back_populates="customer")
    actions:          List["Action"]         = Relationship(back_populates="customer")


class Invoice(SQLModel, table=True):
    """
    3. Invoice issued to a customer.
    amount_paise is stored in integer paise (1 INR = 100 paise).
    status tracks the lifecycle; readiness tracks Collector gate.
    """
    __tablename__ = "invoice"
    __table_args__ = (
        UniqueConstraint("customer_id", "number", name="uq_invoice_customer_number"),
        CheckConstraint("amount_paise > 0", name="ck_invoice_amount_paise_positive"),
        CheckConstraint(
            "po_amount_paise IS NULL OR po_amount_paise > 0",
            name="ck_invoice_po_amount_paise_positive",
        ),
        CheckConstraint("due_date >= issue_date", name="ck_invoice_due_date_after_issue_date"),
        _enum_check("status", InvoiceStatus, "ck_invoice_status"),
        _enum_check("readiness", InvoiceReadiness, "ck_invoice_readiness"),
        Index("ix_invoice_customer_id", "customer_id"),
        Index("ix_invoice_status", "status"),
        Index("ix_invoice_due_date", "due_date"),
    )

    id:           Optional[int]              = Field(default=None, primary_key=True)
    customer_id:  int                        = Field(..., foreign_key="customer.id")
    number:       str                        = Field(..., max_length=100)
    issue_date:   date                       = Field(...)
    due_date:     date                       = Field(...)
    # Amounts stored as integer paise — never as float
    amount_paise: int                        = Field(..., gt=0)
    po_number:    Optional[str]              = Field(default=None, max_length=100)
    invoice_gstin: Optional[str]             = Field(default=None, max_length=15)
    po_amount_paise: Optional[int]           = Field(default=None, gt=0)
    status:       InvoiceStatus              = Field(default=InvoiceStatus.DRAFT)
    readiness:    Optional[InvoiceReadiness] = Field(default=None)
    created_at:   datetime                   = Field(default_factory=_now)

    customer:         "Customer"              = Relationship(back_populates="invoices")
    documents:        List["InvoiceDocument"] = Relationship(back_populates="invoice")
    readiness_checks: List["ReadinessCheck"]  = Relationship(back_populates="invoice")
    actions:          List["Action"]          = Relationship(back_populates="invoice")
    payments:         List["Payment"]         = Relationship(back_populates="invoice")
    promises:         List["Promise"]         = Relationship(back_populates="invoice")
    inbound_messages: List["InboundMessage"]  = Relationship(back_populates="invoice")
    memory_events:    List["MemoryEvent"]     = Relationship(back_populates="invoice")


class InvoiceDocument(SQLModel, table=True):
    """4. Document attached to an invoice (PDF, challan, GRN, etc.)."""
    __tablename__ = "invoice_document"
    __table_args__ = (
        _enum_check("doc_type", DocType, "ck_invoice_document_doc_type"),
        Index("ix_invoice_document_invoice_id", "invoice_id"),
    )

    id:          Optional[int] = Field(default=None, primary_key=True)
    invoice_id:  int           = Field(..., foreign_key="invoice.id")
    doc_type:    DocType       = Field(...)
    file_path:   str           = Field(..., max_length=500)
    uploaded_at: datetime      = Field(default_factory=_now)

    invoice: "Invoice" = Relationship(back_populates="documents")


class ReadinessCheck(SQLModel, table=True):
    """
    5. Result of a readiness check run against an invoice.
    findings is a JSON array of Finding dicts {code, is_pass, message, evidence_ids}.
    """
    __tablename__ = "readiness_check"
    __table_args__ = (
        _enum_check("result", InvoiceReadiness, "ck_readiness_check_result"),
        Index("ix_readiness_check_invoice_id", "invoice_id"),
    )

    id:         Optional[int]    = Field(default=None, primary_key=True)
    invoice_id: int              = Field(..., foreign_key="invoice.id")
    run_at:     datetime         = Field(default_factory=_now)
    result:     InvoiceReadiness = Field(...)
    findings:   List[dict]       = Field(default_factory=list, sa_column=Column(JSON))

    invoice: "Invoice" = Relationship(back_populates="readiness_checks")


class Action(SQLModel, table=True):
    """
    6. Draft message requiring owner approval before sending.
    Connects to an invoice and a customer.
    decided_by / decided_at / sent_at track the approval lifecycle.
    memory_event_id links to the Hindsight document written after dispatch.
    """
    __tablename__ = "action"
    __table_args__ = (
        _enum_check("kind", ActionKind, "ck_action_kind"),
        _enum_check("status", ActionStatus, "ck_action_status"),
        Index("ix_action_status", "status"),
        Index("ix_action_customer_id", "customer_id"),
        Index("ix_action_invoice_id", "invoice_id"),
        Index("ix_action_dedupe_key", "dedupe_key", unique=True),
    )

    id:              Optional[int]      = Field(default=None, primary_key=True)
    invoice_id:      int                = Field(..., foreign_key="invoice.id")
    customer_id:     int                = Field(..., foreign_key="customer.id")
    kind:            ActionKind         = Field(...)
    channel:         str                = Field(..., max_length=50)  # WHATSAPP | EMAIL | PHONE
    recipient:       str                = Field(..., max_length=255)
    body:            str                = Field(..., sa_column=Column(Text))
    reason:          str                = Field(default="", sa_column=Column(Text, nullable=False))
    attachments:     List[str]          = Field(default_factory=list, sa_column=Column(JSON))
    evidence:        List[dict]         = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    dedupe_key:      Optional[str]      = Field(default=None, max_length=200)
    planned_for:     Optional[datetime] = Field(default=None)
    status:          ActionStatus       = Field(default=ActionStatus.DRAFTED)
    decided_by:      Optional[str]      = Field(default=None, max_length=255)
    decided_at:      Optional[datetime] = Field(default=None)
    sent_at:         Optional[datetime] = Field(default=None)
    handoff_opened_at: Optional[datetime] = Field(default=None)
    delivery_confirmation_source: Optional[str] = Field(default=None, max_length=30)
    delivery_confirmed_by: Optional[str] = Field(default=None, max_length=255)
    memory_event_id: Optional[str]      = Field(default=None, max_length=100)
    created_at:      datetime           = Field(default_factory=_now)

    invoice:  "Invoice"  = Relationship(back_populates="actions")
    customer: "Customer" = Relationship(back_populates="actions")


class InboundMessage(SQLModel, table=True):
    """7. Incoming message from a customer (WhatsApp, email, call note)."""
    __tablename__ = "inbound_message"
    __table_args__ = (
        Index("ix_inbound_message_customer_id", "customer_id"),
        Index("ix_inbound_message_invoice_id", "invoice_id"),
    )

    id:              Optional[int] = Field(default=None, primary_key=True)
    customer_id:     int           = Field(..., foreign_key="customer.id")
    invoice_id:      Optional[int] = Field(default=None, foreign_key="invoice.id")
    channel:         str           = Field(..., max_length=50)
    sender_name:     str           = Field(..., max_length=255)
    body:            str           = Field(..., sa_column=Column(Text))
    received_at:     datetime      = Field(default_factory=_now)
    memory_event_id: Optional[str] = Field(default=None, max_length=100)

    customer: "Customer"         = Relationship(back_populates="inbound_messages")
    invoice:  Optional["Invoice"] = Relationship(back_populates="inbound_messages")


class Payment(SQLModel, table=True):
    """
    8. Payment credited against an invoice.
    amount_paise is in integer paise.
    """
    __tablename__ = "payment"
    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_payment_amount_paise_positive"),
        Index("ix_payment_invoice_id", "invoice_id"),
        Index("ix_payment_customer_id", "customer_id"),
        Index("ix_payment_paid_on", "paid_on"),
    )

    id:              Optional[int] = Field(default=None, primary_key=True)
    invoice_id:      int           = Field(..., foreign_key="invoice.id")
    customer_id:     int           = Field(..., foreign_key="customer.id")
    amount_paise:    int           = Field(..., gt=0)
    paid_on:         date          = Field(...)
    reference:       Optional[str] = Field(default=None, max_length=100)
    memory_event_id: Optional[str] = Field(default=None, max_length=100)

    invoice:  "Invoice"  = Relationship(back_populates="payments")
    customer: "Customer" = Relationship(back_populates="payments")


class Promise(SQLModel, table=True):
    """
    9. Promise-to-pay from a customer contact.
    kept=None means not yet resolved. kept=True means paid on time.
    """
    __tablename__ = "promise"
    __table_args__ = (
        Index("ix_promise_invoice_id", "invoice_id"),
        Index("ix_promise_customer_id", "customer_id"),
        Index("ix_promise_promised_date", "promised_date"),
    )

    id:            Optional[int]  = Field(default=None, primary_key=True)
    invoice_id:    int            = Field(..., foreign_key="invoice.id")
    customer_id:   int            = Field(..., foreign_key="customer.id")
    promised_by:   str            = Field(..., max_length=255)
    promised_date: date           = Field(...)
    kept:          Optional[bool] = Field(default=None)

    invoice:  "Invoice"  = Relationship(back_populates="promises")
    customer: "Customer" = Relationship(back_populates="promises")


class RiskAlert(SQLModel, table=True):
    """
    10. Risk alert raised by the Risk agent.
    signals and evidence are JSON arrays.
    status: OPEN → ACKNOWLEDGED or DISMISSED by the owner.
    """
    __tablename__ = "risk_alert"
    __table_args__ = (
        _enum_check("from_level", CustomerRiskLevel, "ck_risk_alert_from_level"),
        _enum_check("to_level", CustomerRiskLevel, "ck_risk_alert_to_level"),
        _enum_check("status", RiskAlertStatus, "ck_risk_alert_status"),
        _enum_check("memory_status", MemoryStatus, "ck_risk_alert_memory_status"),
        Index("ix_risk_alert_customer_id", "customer_id"),
        Index("ix_risk_alert_status", "status"),
        Index("ix_risk_alert_created_at", "created_at"),
    )

    id:          Optional[int]     = Field(default=None, primary_key=True)
    customer_id: int               = Field(..., foreign_key="customer.id")
    from_level:  CustomerRiskLevel = Field(...)
    to_level:    CustomerRiskLevel = Field(...)
    signals:     List[str]         = Field(default_factory=list, sa_column=Column(JSON))
    suggestion:  Optional[str]     = Field(default=None, max_length=500)
    evidence:    List[dict]        = Field(default_factory=list, sa_column=Column(JSON))
    memory_status: MemoryStatus    = Field(default=MemoryStatus.UNAVAILABLE)
    status:      RiskAlertStatus   = Field(default=RiskAlertStatus.OPEN)
    created_at:  datetime          = Field(default_factory=_now)

    customer: "Customer" = Relationship(back_populates="risk_alerts")


class MemoryEvent(SQLModel, table=True):
    """
    11. Shadow log of events retained in (or queued for) Hindsight.
    id is the Hindsight document ID (string) or a locally-generated evt_... ID
    until Hindsight confirms retention (retained_at=NULL means pending).
    content_hash deduplicates: same hash → same event, skip re-retain.
    """
    __tablename__ = "memory_event"
    __table_args__ = (
        Index("ix_memory_customer_id", "customer_id"),
        Index("ix_memory_invoice_id", "invoice_id"),
        Index("ix_memory_retained_at", "retained_at"),
        Index("ix_memory_content_hash", "content_hash"),
    )

    id:                    str                = Field(
        default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}",
        primary_key=True,
        max_length=100,
    )
    kind:                  str                = Field(default="action", max_length=50)
    customer_id:           Optional[int]      = Field(default=None, foreign_key="customer.id")
    invoice_id:            Optional[int]      = Field(default=None, foreign_key="invoice.id")
    bank_name:             Optional[str]      = Field(default=None, max_length=100)
    content:               Optional[str]      = Field(default=None, sa_column=Column("content", Text))
    context:               Optional[str]      = Field(default=None, max_length=500)
    details:               Optional[dict]     = Field(default=None, sa_column=Column(JSON))
    metadata_:             Optional[dict]     = Field(default=None, sa_column=Column("metadata_json", type_=JSON))
    occurred_on:           date               = Field(default_factory=lambda: clock.now().date())
    timestamp:             Optional[datetime] = Field(default_factory=_now)
    content_hash:          str                = Field(default="", max_length=64)
    retained_at:           Optional[datetime] = Field(default=None)
    failed_at:             Optional[datetime] = Field(default=None)
    retry_count:           int                = Field(default=0)
    next_retry_at:         Optional[datetime] = Field(default=None)
    hindsight_document_id: Optional[str]      = Field(default=None, max_length=100)
    event_type:            Optional[str]      = Field(default=None, max_length=50)
    created_at:            datetime           = Field(default_factory=_now)

    customer: Optional["Customer"] = Relationship(back_populates="memory_events")
    invoice:  Optional["Invoice"]  = Relationship(back_populates="memory_events")

    @property
    def document_id(self) -> Optional[str]:
        return self.hindsight_document_id

    @document_id.setter
    def document_id(self, val: Optional[str]) -> None:
        self.hindsight_document_id = val


class SimRun(SQLModel, table=True):
    """
    12. Evaluation run record — one row per arm × seed combination.
    arm: A (fixed / no memory), B (structured / SQLite), C (Hindsight-powered).
    """
    __tablename__ = "sim_run"
    __table_args__ = (
        _enum_check("arm", SimArm, "ck_sim_run_arm"),
        Index("ix_sim_run_arm_seed", "arm", "seed"),
    )

    id:          Optional[int]      = Field(default=None, primary_key=True)
    arm:         SimArm             = Field(...)
    seed:        int                = Field(...)
    config:      dict               = Field(default_factory=dict, sa_column=Column(JSON))
    metrics:     dict               = Field(default_factory=dict, sa_column=Column(JSON))
    started_at:  datetime           = Field(default_factory=_now)
    finished_at: Optional[datetime] = Field(default=None)
