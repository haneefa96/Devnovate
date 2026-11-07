"""Evidence-backed customer explanation API."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from munshi.api.schemas import Evidence, ExplainIn, ExplainOut
from munshi.config import clock
from munshi.db.models import (
    Customer,
    Invoice,
    InvoiceStatus,
    MemoryStatus,
    Payment,
    Promise,
    RiskAlert,
)
from munshi.db.session import get_session
from munshi.memory import queries as memory_queries
from munshi.memory.client import HindsightUnavailable
from munshi.services.evidence import resolve_evidence
from munshi.services.ledger import outstanding_by_invoice

logger = logging.getLogger(__name__)
router = APIRouter(tags=["explain"])


@router.post("/explain", response_model=ExplainOut)
async def explain_query(
    body: ExplainIn,
    session: Session = Depends(get_session),
) -> ExplainOut:
    """Summarize persisted ledger facts and, when available, scoped memory."""
    customer = session.get(Customer, body.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {body.customer_id} not found")

    invoices = session.exec(
        select(Invoice).where(Invoice.customer_id == customer.id)
    ).all()
    payments = session.exec(
        select(Payment).where(Payment.customer_id == customer.id)
    ).all()
    promises = session.exec(
        select(Promise).where(Promise.customer_id == customer.id)
    ).all()
    alerts = session.exec(
        select(RiskAlert)
        .where(RiskAlert.customer_id == customer.id)
        .order_by(RiskAlert.created_at.desc())
        .limit(1)
    ).all()

    open_invoices = [
        invoice for invoice in invoices
        if invoice.status in (
            InvoiceStatus.SENT,
            InvoiceStatus.HELD,
            InvoiceStatus.PARTLY_PAID,
        )
    ]
    balances = outstanding_by_invoice(session, open_invoices)
    overdue = [
        invoice for invoice in open_invoices
        if invoice.due_date < clock.now().date()
    ]
    evidence_ids = [
        *(f"invoice:{invoice.id}" for invoice in open_invoices),
        *(f"payment:{payment.id}" for payment in payments),
        *(f"promise:{promise.id}" for promise in promises),
    ]
    if alerts:
        evidence_ids.extend(
            evidence_id
            for item in (alerts[0].evidence or [])
            for evidence_id in (
                [item.get("id")] if isinstance(item, dict) and item.get("id") else []
            )
        )
    evidence = resolve_evidence(session, evidence_ids)
    total_outstanding = sum(balances.values())
    answer = (
        f"SQLite ledger: {len(open_invoices)} open invoice(s), "
        f"{total_outstanding} paise outstanding; "
        f"{len(overdue)} overdue invoice(s). "
        f"Recorded payments: {len(payments)}; recorded promises: {len(promises)}."
    )
    if alerts:
        answer += (
            f" Latest persisted risk alert changed from "
            f"{alerts[0].from_level.value} to {alerts[0].to_level.value}."
        )

    memory_status = MemoryStatus.UNAVAILABLE
    memory_evidence_added = False
    business = customer.business
    if business is not None and memory_queries.memory_store.is_available:
        try:
            memories = await memory_queries.memory_store.recall(
                bank_name=business.bank_id,
                customer_id=str(customer.id),
                query=body.question,
                k=5,
            )
            scoped = [
                item for item in memories
                if (
                    str(item.get("customer_id") or (item.get("metadata") or {}).get("customer_id") or "")
                    == str(customer.id)
                    or f"customer:{customer.id}" in (item.get("tags") or [])
                )
            ]
            memory_status = MemoryStatus.AVAILABLE
            for item in scoped:
                memory_id = str(item.get("id") or item.get("document_id") or "")
                content = str(item.get("content") or "")
                if not memory_id or not content:
                    continue
                answer += f" Customer-scoped learned context: {content}"
                memory_evidence_added = True
                timestamp = item.get("timestamp")
                evidence_date = (
                    timestamp.date().isoformat()
                    if isinstance(timestamp, datetime)
                    else timestamp[:10]
                    if isinstance(timestamp, str) and timestamp
                    else "Unknown date"
                )
                evidence.append(Evidence(
                    id=memory_id,
                    date=evidence_date,
                    text=content,
                    event_id=str(item.get("document_id") or memory_id),
                ))
        except HindsightUnavailable:
            logger.warning("Explain memory unavailable for customer %s", customer.id)

    if memory_status == MemoryStatus.UNAVAILABLE:
        answer += " Hindsight was unavailable; this answer uses SQLite ledger evidence only."
    elif not memory_evidence_added:
        answer += " No customer-scoped learned records were returned."

    return ExplainOut(answer=answer, evidence=evidence, memory_status=memory_status)
