"""Collector: create evidence-backed reminder drafts for owner approval."""

import json
import logging
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlmodel import Session, select

from munshi.agents.policy import (
    BasePolicy,
    ReminderPlan,
    ReminderWording,
    clamp_contact_time,
    contains_coercive_language,
)
from munshi.band.bridge import band_bridge
from munshi.config import clock
from munshi.db.models import (
    Action,
    ActionKind,
    ActionStatus,
    Business,
    Customer,
    Invoice,
    InvoiceStatus,
    Payment,
    Promise,
)
from munshi.llm.groq_client import groq_client
from munshi.memory import queries as memory_queries

logger = logging.getLogger(__name__)
_PROMPT_PATH = Path(__file__).parent / "prompts" / "collector.md"
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_UNVERIFIED_CLAIMS = (
    "already paid",
    "payment received",
    "received your payment",
    "we received",
    "settled",
    "cleared",
    "invoice is valid",
    "overdue by",
    "balance due",
)


class CollectorAgent(BasePolicy):
    """Draft follow-up messages, but never deliver them or bypass owner approval."""

    def __init__(self) -> None:
        super().__init__()
        self.drafts: list[dict[str, Any]] = []
        self._prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def create_draft(
        self,
        session: Session,
        invoice_id: int,
        customer_id: int,
        timing: datetime,
    ) -> dict[str, Any]:
        """Create and persist a reminder draft; posting it never sends the message."""
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            raise LookupError(f"Invoice {invoice_id} not found")
        if invoice.customer_id != customer_id:
            raise ValueError("Invoice does not belong to the requested customer")

        customer = session.get(Customer, customer_id)
        if customer is None:
            raise LookupError(f"Customer {customer_id} not found")
        invoice.customer = customer
        business = session.get(Business, customer.business_id)
        if business is None:
            raise LookupError(f"Business {customer.business_id} not found")
        customer.business = business

        now = clock.now()
        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.WRITTEN_OFF):
            raise ValueError(f"Cannot create a reminder for invoice with status {invoice.status.value}")

        actions = session.exec(
            select(Action).where(
                Action.invoice_id == invoice_id,
                Action.kind == ActionKind.REMINDER,
                Action.created_at >= now - timedelta(days=7),
            )
        ).all()
        if len(actions) >= 2:
            raise ValueError("Reminder limit reached: at most two reminders per invoice per week")

        requested_time = clamp_contact_time(timing, now)
        payments = session.exec(
            select(Payment)
            .where(Payment.customer_id == customer_id, Payment.invoice_id == invoice_id)
            .order_by(Payment.paid_on)
        ).all()
        if sum(payment.amount_paise for payment in payments) >= invoice.amount_paise:
            raise ValueError(f"Invoice {invoice.number} is fully paid in the ledger")
        promises = session.exec(
            select(Promise)
            .where(Promise.customer_id == customer_id, Promise.invoice_id == invoice_id)
            .order_by(Promise.promised_date)
        ).all()
        latest_promise = promises[-1] if promises else None
        if (
            latest_promise
            and latest_promise.kept is not True
            and latest_promise.promised_date >= requested_time.date()
        ):
            after_promise = datetime.combine(
                latest_promise.promised_date + timedelta(days=1),
                time(9),
                tzinfo=now.tzinfo,
            )
            requested_time = clamp_contact_time(max(requested_time, after_promise), now)

        memory_available = memory_queries.memory_store.is_available
        reflect: dict[str, Any] = {}
        recalled: list[dict[str, Any]] = []
        if memory_available:
            reflect = await memory_queries.get_memory_for_collector(
                bank_name=customer.business.bank_id,
                customer_id=str(customer_id),
            )
            recalled = await memory_queries.memory_store.recall(
                bank_name=customer.business.bank_id,
                customer_id=str(customer_id),
                kind="experience",
                query=f"Payment and reminder history for invoice {invoice.number}",
                k=10,
            )
        recalled = [
            event for event in recalled if _belongs_to_customer(event, customer_id)
        ]

        evidence_ids = [f"invoice:{invoice.id}"]
        evidence_ids.extend(f"payment:{payment.id}" for payment in payments)
        evidence_ids.extend(f"promise:{promise.id}" for promise in promises)
        memory_evidence_ids = [
            str(event.get("id"))
            for event in recalled
            if event.get("id")
        ]
        evidence_ids.extend(memory_evidence_ids)
        evidence_ids = list(dict.fromkeys(evidence_ids))

        reason = _ledger_reason(invoice, payments, promises)
        memory_supported = bool(memory_available and memory_evidence_ids)
        wording = await self._draft_wording(
            customer=customer,
            invoice=invoice,
            reflect=reflect,
            recalled=recalled,
            evidence_ids=evidence_ids,
        )
        if wording is None:
            greeting = f"Hello {customer.contact_name or customer.name}"
            request = "Could you please share an update on the expected payment timing?"
            memory_supported = False
        else:
            greeting = wording.greeting.strip()
            request = wording.request.strip()
            if (
                contains_coercive_language(greeting)
                or contains_coercive_language(request)
                or _contains_unverified_claim(greeting)
                or _contains_unverified_claim(request)
            ):
                greeting = f"Hello {customer.contact_name or customer.name}"
                request = "Could you please share an update on the expected payment timing?"
                memory_supported = False

        due_date = invoice.due_date.isoformat()
        body = (
            f"{greeting}, a gentle follow-up regarding invoice {invoice.number}, "
            f"due {due_date}. {request} Thank you."
        )
        if contains_coercive_language(body):
            raise ValueError("Message policy rejected coercive wording")

        actual_documents = [document.file_path for document in invoice.documents]
        plan = ReminderPlan(
            invoice_id=invoice.id,
            customer_id=customer_id,
            send_on=requested_time,
            recipient=customer.contact_name or customer.name,
            channel="WHATSAPP",
            body=body,
            attachments=actual_documents,
            reason=reason,
            evidence_ids=evidence_ids,
            memory_supported=memory_supported,
        )
        action = Action(
            invoice_id=invoice.id,
            customer_id=customer_id,
            kind=ActionKind.REMINDER,
            channel=plan.channel,
            recipient=plan.recipient,
            body=plan.body,
            attachments=plan.attachments,
            planned_for=plan.send_on,
            status=ActionStatus.DRAFTED,
            created_at=now,
        )
        session.add(action)
        session.commit()
        session.refresh(action)

        draft = plan.model_dump()
        draft.update({
            "id": action.id,
            "status": action.status.value,
            "customer": customer.name,
            "time": plan.send_on.strftime("%H:%M"),
            "evidence": f"{plan.reason} Evidence: {', '.join(plan.evidence_ids)}",
        })
        self.drafts.append(draft)
        await band_bridge.post_draft(draft)
        return draft

    async def _draft_wording(
        self,
        customer: Customer,
        invoice: Invoice,
        reflect: dict[str, Any],
        recalled: list[dict[str, Any]],
        evidence_ids: list[str],
    ) -> ReminderWording | None:
        """Ask Groq for generic wording, retry structured parsing once, then use fallback."""
        allowed_ids = set(evidence_ids)
        prompt = {
            "customer_name": customer.name,
            "invoice_number": invoice.number,
            "ledger_due_date": invoice.due_date.isoformat(),
            "payment_and_promise_history": _ledger_memory_summary(reflect, recalled),
            "evidence_ids": evidence_ids,
        }
        messages = [
            {"role": "system", "content": self._prompt},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ]
        for attempt in range(2):
            try:
                response = await groq_client.call_agent_model(
                    messages,
                    response_format=ReminderWording,
                )
            except Exception:
                logger.exception("Structured reminder wording failed on attempt %s", attempt + 1)
                continue
            parsed = response.get("parsed")
            try:
                if isinstance(parsed, dict):
                    parsed = ReminderWording.model_validate(parsed)
            except ValidationError as error:
                logger.warning("Structured reminder output invalid: %s", error)
                continue
            if isinstance(parsed, ReminderWording):
                cited_ids = [value for value in parsed.evidence_ids if value in allowed_ids]
                if (
                    cited_ids
                    and not contains_coercive_language(parsed.greeting)
                    and not contains_coercive_language(parsed.request)
                ):
                    return parsed.model_copy(update={"evidence_ids": cited_ids})
            logger.warning("Structured reminder wording invalid on attempt %s", attempt + 1)
        return None

    async def on_invoice_due(
        self,
        session: Session,
        invoice_id: int,
    ) -> list[dict[str, Any]]:
        """Create a reminder draft for the requested invoice."""
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            raise LookupError(f"Invoice {invoice_id} not found")
        return [
            await self.create_draft(
                session,
                invoice_id,
                invoice.customer_id,
                clock.now(),
            )
        ]

    async def on_customer_reply(
        self,
        session: Session,
        message_id: int,
    ) -> list[dict[str, Any]]:
        """Hand distress-bearing replies to Risk; never auto-reply to a customer."""
        from munshi.db.models import InboundMessage

        message = session.get(InboundMessage, message_id)
        if message is None:
            raise LookupError(f"Inbound message {message_id} not found")
        if self.risk_agent is None or not _contains_distress_signal(message.body):
            return []
        assessment = await self.risk_agent.calculate_risk_level(session, message.customer_id)
        return [assessment.model_dump()]

    async def on_payment(
        self,
        session: Session,
        payment_id: int,
    ) -> dict[str, Any]:
        """Delegate payment-triggered risk assessment to the Risk agent."""
        from munshi.db.models import Payment

        payment = session.get(Payment, payment_id)
        if payment is None:
            raise LookupError(f"Payment {payment_id} not found")
        if self.risk_agent is None:
            return {}
        assessment = await self.risk_agent.calculate_risk_level(session, payment.customer_id)
        return assessment.model_dump()

    async def on_daily_check(
        self,
        session: Session,
        date: datetime,
    ) -> list[dict[str, Any]]:
        """Draft reminders for open invoices due or overdue within seven days."""
        from munshi.db.models import InvoiceStatus

        cutoff = date.date() + timedelta(days=7)
        invoices = session.exec(
            select(Invoice)
            .where(Invoice.due_date <= cutoff)
            .where(Invoice.status.not_in([InvoiceStatus.PAID, InvoiceStatus.WRITTEN_OFF]))
            .order_by(Invoice.due_date, Invoice.id)
        ).all()
        drafts = []
        for invoice in invoices:
            try:
                drafts.append(
                    await self.create_draft(
                        session,
                        invoice.id,
                        invoice.customer_id,
                        date,
                    )
                )
            except ValueError as error:
                if str(error).startswith("Reminder limit reached"):
                    logger.info("Skipping invoice %s: %s", invoice.id, error)
                    continue
                raise
        return drafts


def _belongs_to_customer(event: dict[str, Any], customer_id: int) -> bool:
    """Drop unscoped or cross-customer memories before they reach a prompt."""
    expected = str(customer_id)
    if str(event.get("customer_id", "")) == expected:
        return True
    metadata = event.get("metadata") or {}
    if str(metadata.get("customer_id", "")) == expected:
        return True
    return f"customer:{expected}" in (event.get("tags") or [])


def _ledger_reason(
    invoice: Invoice,
    payments: list[Any],
    promises: list[Any],
) -> str:
    if promises:
        promise = promises[-1]
        return (
            f"Following up after the recorded payment promise for "
            f"{promise.promised_date.isoformat()} and the invoice due date."
        )
    if payments:
        return "Following up on the ledger-recorded payment history and invoice due date."
    return f"Following up because ledger invoice {invoice.number} is due {invoice.due_date.isoformat()}."


def _ledger_memory_summary(reflect: dict[str, Any], recalled: list[dict[str, Any]]) -> dict[str, Any]:
    """Limit model context to scoped memory and non-sensitive ledger context."""
    allowed_memory_ids = {
        str(event.get("id"))
        for event in recalled
        if event.get("id")
    }
    return {
        "reflection_requirements": [
            scoped_item
            for item in reflect.get("requirements", [])
            if (scoped_item := _memory_item(item, allowed_memory_ids)) is not None
        ],
        "experience_events": [
            {
                "id": event.get("id"),
                "timestamp": event.get("timestamp"),
                "content": _PHONE_PATTERN.sub("[redacted]", str(event.get("content") or "")),
            }
            for event in recalled
        ],
    }


def _memory_item(item: Any, allowed_ids: set[str]) -> dict[str, Any] | None:
    if isinstance(item, dict):
        code = item.get("code", "")
        description = item.get("description", "")
        evidence_ids = item.get("evidence_ids", [])
    else:
        code = getattr(item, "code", "")
        description = getattr(item, "description", "")
        evidence_ids = getattr(item, "evidence_ids", [])
    scoped_ids = [
        str(value)
        for value in evidence_ids or []
        if str(value) in allowed_ids
    ]
    if not scoped_ids:
        return None
    return {
        "code": str(code),
        "description": str(description),
        "evidence_ids": scoped_ids,
    }


def _contains_distress_signal(text: str) -> bool:
    normalized = text.casefold()
    return any(
        phrase in normalized
        for phrase in (
            "cash flow",
            "cashflow",
            "cannot pay",
            "can't pay",
            "unable to pay",
            "funds are tight",
            "financial difficulty",
            "financial distress",
            "insolvency",
            "bankruptcy",
        )
    )


def _contains_unverified_claim(text: str) -> bool:
    normalized = text.casefold()
    return bool(
        re.search(r"\d|₹|\b(?:rs\.?|inr)\b", normalized)
        or any(phrase in normalized for phrase in _UNVERIFIED_CLAIMS)
    )
