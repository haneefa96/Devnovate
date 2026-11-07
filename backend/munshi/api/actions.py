"""
Munshi - Actions (draft approval) API

Every outbound message must be approved by the owner before it is sent.
The first valid decision wins — duplicate POSTs return 409.
"""

from __future__ import annotations

import re
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from munshi.api.schemas import (
    ActionExplainOut,
    ActionOut,
    ApproveActionIn,
    ApproveActionOut,
    ConfirmDeliveryIn,
    ConfirmDeliveryOut,
    HandoffOpenedOut,
    RejectActionIn,
    RejectActionOut,
)
from munshi.agents.policy import contains_coercive_language, is_contact_time_allowed
from munshi.config import clock
from munshi.db.models import Action, ActionStatus, Customer, MemoryEvent
from munshi.db.session import get_session
from munshi.services.whatsapp_link import generate_whatsapp_link

router = APIRouter(tags=["actions"])


def _has_valid_phone(phone: str | None) -> bool:
    digits = re.sub(r"\D", "", phone or "")
    return 10 <= len(digits) <= 15


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


def _handoff_url(action: Action) -> str:
    return f"/api/actions/{action.id}/handoff"


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
        has_contact_number = bool(customer and _has_valid_phone(customer.contact_phone))
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
                why=a.reason or "No supporting rationale was recorded.",
                evidence=a.evidence or [],
                handoff_url=(
                    _handoff_url(a)
                    if has_contact_number and a.status in (ActionStatus.APPROVED, ActionStatus.EDITED)
                    else None
                ),
                handoff_opened_at=a.handoff_opened_at,
                delivery_confirmation_source=a.delivery_confirmation_source,
                delivery_confirmed_by=a.delivery_confirmed_by,
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
    Approve a draft and make the reviewed content eligible for a manual handoff.
    409 CONFLICT if already decided (first decision wins).
    """
    action = _get_action_or_404(action_id, session)
    _guard_not_decided(action)

    if body.edited_body is not None:
        edited_body = body.edited_body.strip()
        if not edited_body:
            raise HTTPException(status_code=422, detail="Approved message cannot be empty")
        if contains_coercive_language(edited_body):
            raise HTTPException(status_code=422, detail="Message violates the non-coercive communication policy")
        action.body = edited_body
        action.status = ActionStatus.EDITED
    else:
        action.status = ActionStatus.APPROVED

    action.decided_by = body.decided_by
    action.decided_at = clock.now()
    action.sent_at = None
    action.handoff_opened_at = None
    action.delivery_confirmation_source = None
    action.delivery_confirmed_by = None
    session.add(action)
    session.commit()
    session.refresh(action)

    customer = session.get(Customer, action.customer_id)
    phone = customer.contact_phone if customer else None
    try:
        wa_link = generate_whatsapp_link(phone, action.body) if phone else None
    except ValueError:
        wa_link = None

    return ApproveActionOut(
        id=action.id,
        status=action.status,
        sent_at=None,
        whatsapp_link=None,
        handoff_url=_handoff_url(action) if wa_link else None,
        memory_event_id=None,
        handoff_status=(
            "READY_FOR_HANDOFF"
            if wa_link
            else "NO_VALID_CONTACT_NUMBER"
        ),
    )


@router.get(
    "/actions/{action_id}/handoff",
    response_class=RedirectResponse,
    responses={302: {"description": "Redirect to the approved WhatsApp message"}},
)
def open_action_handoff(
    action_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record a handoff-link visit and redirect; this is not delivery confirmation."""
    action = _get_action_or_404(action_id, session)
    if action.status not in (ActionStatus.APPROVED, ActionStatus.EDITED):
        raise HTTPException(status_code=409, detail="Only approved actions can be handed off")
    now = clock.now()
    if not is_contact_time_allowed(now, now):
        raise HTTPException(
            status_code=409,
            detail="Customer contact is permitted only between 09:00 and 19:00 IST",
        )
    if action.planned_for is not None:
        planned_for = action.planned_for
        if planned_for.tzinfo is None:
            planned_for = planned_for.replace(tzinfo=now.tzinfo)
        else:
            planned_for = planned_for.astimezone(now.tzinfo)
        if now < planned_for:
            raise HTTPException(status_code=409, detail="This handoff is scheduled for a later time")
    customer = session.get(Customer, action.customer_id)
    if not customer or not customer.contact_phone:
        raise HTTPException(status_code=409, detail="Customer contact number is not recorded")
    try:
        whatsapp_link = generate_whatsapp_link(customer.contact_phone, action.body)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    action.handoff_opened_at = now
    session.add(action)
    session.commit()
    return RedirectResponse(
        whatsapp_link,
        status_code=302,
    )


@router.post(
    "/actions/{action_id}/confirm-delivery",
    response_model=ConfirmDeliveryOut,
)
def confirm_action_delivery(
    action_id: int,
    body: ConfirmDeliveryIn,
    session: Session = Depends(get_session),
) -> ConfirmDeliveryOut:
    """Record owner-reported sending; this does not verify provider delivery."""
    action = _get_action_or_404(action_id, session)
    if action.status not in (ActionStatus.APPROVED, ActionStatus.EDITED):
        raise HTTPException(status_code=409, detail="Only an approved action can be confirmed")
    if action.handoff_opened_at is None:
        raise HTTPException(status_code=409, detail="Open the WhatsApp handoff before confirming")
    action.status = ActionStatus.SENT
    action.sent_at = clock.now()
    action.delivery_confirmation_source = "OWNER_REPORTED"
    action.delivery_confirmed_by = body.confirmed_by.strip()
    action.decided_by = action.decided_by or body.confirmed_by
    action.memory_event_id = f"evt_{uuid.uuid4().hex[:12]}"
    session.add(action)
    session.add(MemoryEvent(
        id=action.memory_event_id,
        kind="owner_reported_message_sent",
        customer_id=action.customer_id,
        invoice_id=action.invoice_id,
        occurred_on=clock.now().date(),
        content=(
            f"Owner-reported: {body.confirmed_by} confirmed action {action.id} "
            f"for invoice {action.invoice_id} was sent via {action.channel}. "
            "WhatsApp provider delivery was not verified."
        ),
    ))
    session.commit()
    session.refresh(action)
    return ConfirmDeliveryOut(
        id=action.id,
        status=action.status,
        sent_at=action.sent_at,
        delivery_confirmation_source="OWNER_REPORTED",
        provider_confirmed=False,
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
        summary=action.reason or f"Drafted {action.kind.value} follow-up for invoice {action.invoice_id}.",
        evidence=action.evidence or [],
    )
