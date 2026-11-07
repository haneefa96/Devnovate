"""
Munshi - Customers API
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from munshi.api.schemas import (
    CustomerBeliefOut,
    CustomerDetailOut,
    CustomerListItem,
    CustomerOut,
    CustomerPatch,
    CustomerPlaybookOut,
    CustomerRecordOut,
    CustomerTimelineItem,
)
from munshi.config import clock
from munshi.db.models import (
    Action,
    Customer,
    InboundMessage,
    Invoice,
    InvoiceStatus,
    MemoryEvent,
    Payment,
    Promise,
    RiskAlert,
)
from munshi.db.session import get_session
from munshi.memory import queries as memory_queries
from munshi.memory.client import HindsightUnavailable
from munshi.services.ledger import outstanding_by_invoice

router = APIRouter(tags=["customers"])
logger = logging.getLogger(__name__)


@router.get("/customers", response_model=List[CustomerListItem])
def list_customers(session: Session = Depends(get_session)) -> List[CustomerListItem]:
    """
    List all customers with risk level, count of open invoices, and overdue paise.
    """
    customers = session.exec(select(Customer)).all()
    today = clock.now().date()
    open_statuses = [InvoiceStatus.SENT, InvoiceStatus.HELD, InvoiceStatus.PARTLY_PAID]

    result: List[CustomerListItem] = []
    for c in customers:
        open_invoices = session.exec(
            select(Invoice)
            .where(Invoice.customer_id == c.id)
            .where(Invoice.status.in_(open_statuses))
        ).all()
        balances = outstanding_by_invoice(session, open_invoices)
        overdue_paise = sum(
            balances[invoice.id]
            for invoice in open_invoices
            if invoice.id is not None and invoice.due_date < today
        )

        result.append(
            CustomerListItem(
                id=c.id,
                name=c.name,
                risk_level=c.risk_level,
                open_invoices=len(open_invoices),
                overdue_paise=overdue_paise,
            )
        )
    return result


@router.get("/customers/{customer_id}", response_model=CustomerDetailOut)
async def get_customer(
    customer_id: int,
    session: Session = Depends(get_session),
) -> CustomerDetailOut:
    """
    Get customer detail with record (no phone), playbook, beliefs, and timeline.
    """
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    record = CustomerRecordOut(
        id=customer.id,
        name=customer.name,
        gstin=customer.gstin,
        state_code=customer.state_code,
        credit_days=customer.credit_days,
        po_required=customer.po_required,
        required_docs=customer.required_docs,
        contact_name=customer.contact_name,
        contact_role=customer.contact_role,
        risk_level=customer.risk_level,
    )

    # Build timeline from events, actions, inbound messages, and payments
    timeline: List[CustomerTimelineItem] = []

    actions = session.exec(
        select(Action).where(Action.customer_id == customer_id).order_by(Action.created_at.desc())
    ).all()
    for a in actions:
        timeline.append(
            CustomerTimelineItem(
                date=str(a.planned_for.date() if a.planned_for else a.created_at.date()),
                kind="REMINDER",
                text=f"{a.kind.value} to {a.recipient} via {a.channel}",
            )
        )

    messages = session.exec(
        select(InboundMessage).where(InboundMessage.customer_id == customer_id).order_by(InboundMessage.received_at.desc())
    ).all()
    for m in messages:
        timeline.append(
            CustomerTimelineItem(
                date=str(m.received_at.date()),
                kind="REPLY",
                text=f"Reply from {m.sender_name} via {m.channel}: {m.body[:60]}",
            )
        )

    payments = session.exec(
        select(Payment).where(Payment.customer_id == customer_id).order_by(Payment.paid_on.desc())
    ).all()
    for p in payments:
        timeline.append(
            CustomerTimelineItem(
                date=str(p.paid_on),
                kind="PAYMENT",
                text=f"Payment received: ₹{p.amount_paise / 100:,.2f}",
            )
        )

    promises = session.exec(
        select(Promise).where(Promise.customer_id == customer_id).order_by(Promise.promised_date.desc())
    ).all()
    for promise in promises:
        state = "kept" if promise.kept is True else "missed" if promise.kept is False else "unresolved"
        timeline.append(
            CustomerTimelineItem(
                date=str(promise.promised_date),
                kind="PROMISE",
                text=f"Payment promise for invoice #{promise.invoice_id} was {state}.",
            )
        )

    alerts = session.exec(
        select(RiskAlert).where(RiskAlert.customer_id == customer_id).order_by(RiskAlert.created_at.desc())
    ).all()
    for alert in alerts:
        timeline.append(
            CustomerTimelineItem(
                date=str(alert.created_at.date()),
                kind="RISK_ASSESSMENT",
                text=f"Risk assessment changed from {alert.from_level.value} to {alert.to_level.value}.",
            )
        )

    open_invoices = session.exec(
        select(Invoice)
        .where(Invoice.customer_id == customer_id)
        .where(Invoice.status.in_([
            InvoiceStatus.SENT,
            InvoiceStatus.HELD,
            InvoiceStatus.PARTLY_PAID,
        ]))
    ).all()
    outstanding = sum(outstanding_by_invoice(session, open_invoices).values())

    memory_status = "UNAVAILABLE"
    playbook_text = ""
    beliefs: list[CustomerBeliefOut] = []
    business = customer.business
    if business is not None and memory_queries.memory_store.is_available:
        try:
            findings = await memory_queries.get_memory_for_collector(
                bank_name=business.bank_id,
                customer_id=str(customer.id),
            )
            playbook_text = str(findings.get("playbook") or "")
            memories = await memory_queries.memory_store.recall(
                bank_name=business.bank_id,
                customer_id=str(customer.id),
                kind="observation",
                query="Learned customer payment behaviour and requirements",
                k=10,
            )
            for memory in memories:
                metadata = memory.get("metadata") or {}
                tags = memory.get("tags") or []
                if (
                    str(memory.get("customer_id") or metadata.get("customer_id") or "")
                    != str(customer.id)
                    and f"customer:{customer.id}" not in tags
                ):
                    continue
                memory_id = str(memory.get("id") or memory.get("document_id") or "")
                if not memory_id:
                    continue
                timestamp = memory.get("timestamp")
                if isinstance(timestamp, datetime):
                    evidence_date = timestamp.date().isoformat()
                elif isinstance(timestamp, str) and timestamp:
                    evidence_date = timestamp[:10]
                else:
                    evidence_date = "Unknown date"
                beliefs.append(CustomerBeliefOut(
                    text=str(memory.get("content") or ""),
                    trend=str(metadata.get("trend") or "stable"),
                    evidence_count=1,
                    evidence=[{
                        "id": memory_id,
                        "date": evidence_date,
                        "text": str(memory.get("content") or ""),
                        "event_id": str(memory.get("document_id") or memory_id),
                    }],
                ))
            memory_status = "AVAILABLE"
        except HindsightUnavailable:
            playbook_text = ""
            beliefs = []
            logger.warning("Customer memory unavailable for customer %s", customer.id)

    return CustomerDetailOut(
        customer=record,
        playbook=CustomerPlaybookOut(text=playbook_text, updating=False),
        beliefs=beliefs,
        timeline=timeline,
        outstanding_paise=outstanding,
        memory_status=memory_status,
    )


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
def patch_customer(
    customer_id: int,
    patch_data: CustomerPatch,
    session: Session = Depends(get_session),
) -> CustomerOut:
    """
    Owner edits contact, po_required, required_docs, credit_days.
    Retains an owner-confirmation event when contact/requirements change.
    """
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    changed_fields = []
    if patch_data.contact_name is not None and patch_data.contact_name != customer.contact_name:
        customer.contact_name = patch_data.contact_name
        changed_fields.append("contact_name")
    if patch_data.contact_role is not None and patch_data.contact_role != customer.contact_role:
        customer.contact_role = patch_data.contact_role
        changed_fields.append("contact_role")
    if "contact_phone" in patch_data.model_fields_set and patch_data.contact_phone != customer.contact_phone:
        customer.contact_phone = patch_data.contact_phone
        changed_fields.append("contact_phone")
    if patch_data.po_required is not None and patch_data.po_required != customer.po_required:
        customer.po_required = patch_data.po_required
        changed_fields.append("po_required")
    if patch_data.required_docs is not None and patch_data.required_docs != customer.required_docs:
        customer.required_docs = patch_data.required_docs
        changed_fields.append("required_docs")
    if patch_data.credit_days is not None and patch_data.credit_days != customer.credit_days:
        customer.credit_days = patch_data.credit_days
        changed_fields.append("credit_days")

    session.add(customer)

    # Retain an owner-confirmation event when contact/requirements change
    if changed_fields:
        evt = MemoryEvent(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            kind="owner_confirmation",
            customer_id=customer.id,
            occurred_on=clock.now().date(),
            content=f"Owner updated {', '.join(changed_fields)} for {customer.name}",
        )
        session.add(evt)

    session.commit()
    session.refresh(customer)
    return CustomerOut.model_validate(customer)
