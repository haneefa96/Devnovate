"""
Munshi - Payments API
"""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from munshi.agents.risk import RiskAgent
from munshi.api.schemas import PaymentCreate, PaymentOut
from munshi.config import clock
from munshi.db.models import Customer, Invoice, InvoiceStatus, MemoryEvent, Payment
from munshi.db.session import get_session

router = APIRouter(tags=["payments"])
logger = logging.getLogger(__name__)


@router.post("/payments", response_model=PaymentOut, status_code=201)
async def record_payment(
    body: PaymentCreate,
    session: Session = Depends(get_session),
) -> PaymentOut:
    """
    Record a payment against an invoice.

    Business rules:
    - Amount cannot exceed the outstanding balance.
    - If payment fully clears the invoice, status → PAID.
    - If partial, status → PARTLY_PAID.
    - Payments on already-PAID or WRITTEN_OFF invoices are rejected.
    """
    invoice = session.get(Invoice, body.invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {body.invoice_id} not found")

    blocked_statuses = {InvoiceStatus.PAID, InvoiceStatus.WRITTEN_OFF}
    if invoice.status in blocked_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Invoice {body.invoice_id} is already {invoice.status.value} — cannot record payment",
        )

    # Calculate total already paid
    already_paid: int = session.exec(
        select(func.coalesce(func.sum(Payment.amount_paise), 0))
        .where(Payment.invoice_id == body.invoice_id)
    ).one() or 0

    outstanding = invoice.amount_paise - already_paid
    if body.amount_paise > outstanding:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Payment {body.amount_paise} paise exceeds outstanding balance "
                f"{outstanding} paise"
            ),
        )

    evt_id = f"evt_{uuid.uuid4().hex[:12]}"
    payment = Payment(
        invoice_id=body.invoice_id,
        customer_id=invoice.customer_id,
        amount_paise=body.amount_paise,
        paid_on=body.paid_on,
        reference=body.reference,
        memory_event_id=evt_id,
    )
    session.add(payment)

    # Update invoice status
    new_paid_total = already_paid + body.amount_paise
    if new_paid_total >= invoice.amount_paise:
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTLY_PAID
    session.add(invoice)

    # Calculate days late
    days_late = max(0, (body.paid_on - invoice.due_date).days)

    mem_event = MemoryEvent(
        id=evt_id,
        kind="payment_received",
        customer_id=invoice.customer_id,
        invoice_id=invoice.id,
        occurred_on=body.paid_on,
        content=f"Payment received for invoice {invoice.number}: ₹{body.amount_paise / 100:,.2f} on {body.paid_on} ({days_late} days late)",
    )
    session.add(mem_event)

    session.commit()
    session.refresh(payment)

    risk_level = None
    risk_status = "COMPLETED"
    risk_error = None
    try:
        assessment = await RiskAgent().on_payment(session, payment.id)
        risk_level = assessment.get("level")
    except Exception as error:
        logger.error(
            "Risk assessment failed after payment %s (%s)",
            payment.id,
            type(error).__name__,
        )
        risk_status = "FAILED"
        risk_error = "Payment was recorded, but risk assessment failed."

    return PaymentOut(
        id=payment.id,
        invoice_status=invoice.status,
        days_late=days_late,
        risk_assessment_status=risk_status,
        risk_assessment_error=risk_error,
        risk_level=risk_level,
    )
