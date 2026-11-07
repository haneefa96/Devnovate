"""
Munshi - Actions (draft approval) API

Every outbound message must be approved by the owner before it is sent.
The first valid decision wins — duplicate POSTs return 409.
"""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from munshi.api.schemas import (
    ActionExplainOut,
    ActionOut,
    ApproveActionIn,
    ApproveActionOut,
    RejectActionIn,
    RejectActionOut,
)
from munshi.config import clock, settings
from munshi.db.models import Action, ActionStatus, Customer, MemoryEvent
from munshi.db.session import get_session
from munshi.services.whatsapp_link import generate_whatsapp_link

router = APIRouter(tags=["actions"])


def _get_action_or_404(action_id: int, session: Session) -> Action:
    action = session.get(Action, action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
    return action


def _guard_not_decided(action: Action) -> None:
    """Prevent duplicate decisions — first valid decision wins."""
    decided = {ActionStatus.APPROVED, ActionStatus.EDITED, ActionStatus.REJECTED, ActionStatus.SENT}
    if action.status in decided:
        raise HTTPException(
            status_code=409,
            detail=f"Action {action.id} has already been decided (status={action.status})",
        )


@router.get("/actions", response_model=List[ActionOut])
def list_actions(
    status: str = "DRAFTED",
    session: Session = Depends(get_session),
) -> List[ActionOut]:
    """List actions filtered by status (default: DRAFTED = awaiting approval)."""
    try:
        status_enum = ActionStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Must be one of: {[s.value for s in ActionStatus]}",
        )
    rows = session.exec(select(Action).where(Action.status == status_enum)).all()
    results: List[ActionOut] = []
    for a in rows:
        customer = session.get(Customer, a.customer_id)
        customer_name = customer.name if customer else ""
        results.append(
            ActionOut(
                id=a.id,
                invoice_id=a.invoice_id,
                customer=customer_name,
                kind=a.kind,
                channel=a.channel,
                recipient=a.recipient,
                body=a.body,
                planned_for=a.planned_for,
                attachments=a.attachments,
                status=a.status,
                why="No supporting evidence is available yet.",
            )
        )
    return results


@router.post("/actions/{action_id}/approve", response_model=ApproveActionOut)
def approve_action(
    action_id: int,
    body: ApproveActionIn = ApproveActionIn(),
    session: Session = Depends(get_session),
) -> ApproveActionOut:
    """
    Approve a draft — marks as SENT, records memory event, generates whatsapp link.
    409 CONFLICT if already decided (first decision wins).
    """
    action = _get_action_or_404(action_id, session)
    _guard_not_decided(action)

    if body.edited_body is not None:
        action.body = body.edited_body
        action.status = ActionStatus.EDITED
    else:
        action.status = ActionStatus.APPROVED

    action.status = ActionStatus.SENT
    action.decided_by = body.decided_by
    action.decided_at = clock.now()
    action.sent_at = clock.now()

    # Retain memory event
    evt_id = f"evt_{uuid.uuid4().hex[:12]}"
    action.memory_event_id = evt_id
    session.add(action)

    mem_event = MemoryEvent(
        id=evt_id,
        kind="reminder_sent",
        customer_id=action.customer_id,
        invoice_id=action.invoice_id,
        occurred_on=clock.now().date(),
        content=f"Reminder sent to {action.recipient} via {action.channel}: {action.body}",
    )
    session.add(mem_event)
    session.commit()
    session.refresh(action)

    # In simulator mode, whatsapp_link is null
    customer = session.get(Customer, action.customer_id)
    phone = customer.contact_phone if customer else None
    wa_link = None
    if not settings.SIM_MODE and phone:
        wa_link = generate_whatsapp_link(phone, action.body)

    return ApproveActionOut(
        id=action.id,
        status=ActionStatus.SENT,
        sent_at=action.sent_at,
        whatsapp_link=wa_link,
        memory_event_id=evt_id,
    )


@router.post("/actions/{action_id}/reject", response_model=RejectActionOut)
def reject_action(
    action_id: int,
    body: RejectActionIn = RejectActionIn(),
    session: Session = Depends(get_session),
) -> RejectActionOut:
    """Reject a draft — it will not be sent."""
    action = _get_action_or_404(action_id, session)
    _guard_not_decided(action)

    action.status = ActionStatus.REJECTED
    action.decided_by = body.decided_by
    action.decided_at = clock.now()
    session.add(action)

    if body.reason:
        evt = MemoryEvent(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            kind="owner_note",
            customer_id=action.customer_id,
            invoice_id=action.invoice_id,
            occurred_on=clock.now().date(),
            content=f"Draft {action.id} rejected by owner. Reason: {body.reason}",
        )
        session.add(evt)

    session.commit()
    session.refresh(action)

    return RejectActionOut(
        id=action.id,
        status=ActionStatus.REJECTED,
    )


@router.get("/actions/{action_id}/explain", response_model=ActionExplainOut)
def explain_action(
    action_id: int,
    session: Session = Depends(get_session),
) -> ActionExplainOut:
    """
    Return the evidence behind a draft action.
    """
    action = _get_action_or_404(action_id, session)
    return ActionExplainOut(
        summary=f"Drafted {action.kind.value} follow-up for invoice {action.invoice_id}.",
        evidence=[],
    )
