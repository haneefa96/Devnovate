"""
Munshi - Inbound messages API
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from munshi.api.schemas import InboundMessageCreate, InboundMessageOut
from munshi.config import clock
from munshi.db.models import Customer, InboundMessage, Invoice, MemoryEvent
from munshi.db.session import get_session

router = APIRouter(tags=["messages"])


@router.post("/messages/inbound", response_model=InboundMessageOut, status_code=201)
def record_inbound_message(
    body: InboundMessageCreate,
    session: Session = Depends(get_session),
) -> InboundMessageOut:
    """
    Record an inbound customer message (WhatsApp, email, call note).
    The message is stored immediately; an audit/outbox memory event is queued.
    """
    customer = session.get(Customer, body.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {body.customer_id} not found")

    if body.invoice_id is not None:
        invoice = session.get(Invoice, body.invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {body.invoice_id} not found")
        if invoice.customer_id != body.customer_id:
            raise HTTPException(status_code=422, detail="Invoice does not belong to this customer")

    evt_id = f"evt_{uuid.uuid4().hex[:12]}"
    msg = InboundMessage(
        customer_id=body.customer_id,
        invoice_id=body.invoice_id,
        channel=body.channel,
        sender_name=body.sender_name,
        body=body.body,
        received_at=clock.now(),
        memory_event_id=evt_id,
    )
    session.add(msg)

    mem_event = MemoryEvent(
        id=evt_id,
        kind="customer_reply",
        customer_id=body.customer_id,
        invoice_id=body.invoice_id,
        occurred_on=clock.now().date(),
        content=f"Inbound reply from {body.sender_name} via {body.channel}: {body.body}",
    )
    session.add(mem_event)

    session.commit()
    session.refresh(msg)

    return InboundMessageOut(
        id=msg.id,
        memory_event_id=evt_id,
        risk_check_queued=True,
    )

