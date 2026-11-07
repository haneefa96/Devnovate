"""Risk agent: detect evidence-backed customer warnings for owner review."""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from munshi.agents.policy import BasePolicy, RiskAssessment, RiskSignal
from munshi.band.bridge import band_bridge
from munshi.config import clock
from munshi.db.models import (
    Customer,
    CustomerRiskLevel,
    InboundMessage,
    Invoice,
    Payment,
    Promise,
    RiskAlert,
    RiskAlertStatus,
)
from munshi.memory import queries as memory_queries

logger = logging.getLogger(__name__)
_DISTRESS_TERMS = (
    "cash flow",
    "cash-flow",
    "cashflow",
    "cannot pay",
    "can't pay",
    "unable to pay",
    "funds are tight",
    "financial difficulty",
    "financial distress",
    "insolvency",
    "bankruptcy",
    "liquidity problem",
)
_WEAKENING_TERMS = (
    "weakening",
    "weaker",
    "less consistent",
    "deteriorating",
    "payment delays increasing",
    "payment pattern changed",
    "behaviour changed",
    "behavior changed",
)
_STALE_DAYS = 180
_PROMISE_LOOKBACK_DAYS = 30


class RiskAgent(BasePolicy):
    """Assess risks from ledger and customer-scoped memory; never decides policy."""

    def __init__(self) -> None:
        super().__init__()
        self.current_levels: dict[int, str] = {}

    async def calculate_risk_level(
        self,
        session: Session,
        customer_id: int,
        as_of: datetime | None = None,
    ) -> RiskAssessment:
        """Calculate distinct warning signals and persist the owner-review alert."""
        customer = session.get(Customer, customer_id)
        if customer is None:
            raise LookupError(f"Customer {customer_id} not found")

        now = as_of or clock.now()
        today = now.date()
        invoices = session.exec(
            select(Invoice).where(Invoice.customer_id == customer_id)
        ).all()
        invoice_by_id = {invoice.id: invoice for invoice in invoices}
        payments = session.exec(
            select(Payment)
            .where(Payment.customer_id == customer_id)
            .order_by(Payment.paid_on)
        ).all()
        promises = session.exec(
            select(Promise)
            .where(Promise.customer_id == customer_id)
            .order_by(Promise.promised_date)
        ).all()
        messages = session.exec(
            select(InboundMessage)
            .where(InboundMessage.customer_id == customer_id)
            .order_by(InboundMessage.received_at)
        ).all()

        signals: list[RiskSignal] = []
        promise_signal = _missed_promise_signal(promises, payments, invoice_by_id, today)
        if promise_signal:
            signals.append(promise_signal)

        delay_signal = _repeated_delay_signal(invoices, payments)
        if delay_signal:
            signals.append(delay_signal)

        distress_signal = _distress_signal(messages)
        if distress_signal:
            signals.append(distress_signal)

        memory_findings, observations = await self._customer_memory(customer)
        allowed_memory_ids = {
            str(observation.get("id"))
            for observation in observations
            if observation.get("id")
        }
        memory_signals = _memory_signals(
            memory_findings,
            observations,
            today,
            allowed_memory_ids,
        )
        signals.extend(memory_signals)

        distinct_codes = {signal.code for signal in signals}
        level = "HIGH" if len(distinct_codes) >= 2 else "WATCH" if signals else "NORMAL"
        assessment = RiskAssessment(
            customer_id=customer_id,
            level=level,
            signals=signals,
            suggestion=(
                "Review the supporting evidence and decide whether follow-up is appropriate."
                if signals
                else None
            ),
            evidence_ids=list(dict.fromkeys(
                evidence_id
                for signal in signals
                for evidence_id in signal.evidence_ids
            )),
        )
        return await self._persist_assessment(session, customer, assessment, now)

    async def _customer_memory(
        self,
        customer: Customer,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Fetch Risk memory through the existing customer-scoped MemoryStore."""
        if customer.business is None:
            return {}, []
        store = memory_queries.memory_store
        if not store.is_available:
            logger.warning("Risk memory unavailable for customer %s", customer.id)
            return {}, []
        findings = await memory_queries.get_memory_for_risk(
            bank_name=customer.business.bank_id,
            customer_id=str(customer.id),
        )
        observations = await store.recall(
            bank_name=customer.business.bank_id,
            customer_id=str(customer.id),
            kind="observation",
            query="Payment timing, promises, customer distress, and changes in behaviour",
            k=20,
        )
        return findings, [
            item for item in observations if _belongs_to_customer(item, customer.id)
        ]

    async def _persist_assessment(
        self,
        session: Session,
        customer: Customer,
        assessment: RiskAssessment,
        now: datetime,
    ) -> RiskAssessment:
        previous_level = customer.risk_level.value
        customer.risk_level = CustomerRiskLevel(assessment.level)
        customer.risk_updated_at = now
        self.current_levels[customer.id] = assessment.level
        session.add(customer)

        alert: RiskAlert | None = None
        signal_descriptions = [signal.description for signal in assessment.signals]
        if assessment.signals and (
            previous_level != assessment.level
            or not _has_equivalent_open_alert(
                session,
                customer.id,
                assessment.level,
                signal_descriptions,
            )
        ):
            alert = RiskAlert(
                customer_id=customer.id,
                from_level=CustomerRiskLevel(previous_level),
                to_level=CustomerRiskLevel(assessment.level),
                signals=signal_descriptions,
                evidence=[
                    {"code": signal.code, "evidence_ids": signal.evidence_ids}
                    for signal in assessment.signals
                ],
                suggestion=assessment.suggestion,
                status=RiskAlertStatus.OPEN,
                created_at=now,
            )
            session.add(alert)

        session.commit()
        if alert:
            session.refresh(alert)
            await band_bridge.post_risk_alert({
                "customer": customer.name,
                "from_level": previous_level,
                "to_level": assessment.level,
                "signals": [
                    (
                        f"{signal.description} "
                        f"(evidence: {', '.join(signal.evidence_ids)})"
                    )
                    for signal in assessment.signals
                ],
                "suggestion": assessment.suggestion or "",
            })
            assessment_data = assessment.model_dump()
            return RiskAssessmentWithAlert(**assessment_data, alert_id=alert.id)
        return assessment

    async def on_payment(
        self,
        session: Session,
        payment_id: int,
    ) -> dict[str, Any]:
        """Reassess the payment's customer after the ledger payment is recorded."""
        payment = session.get(Payment, payment_id)
        if payment is None:
            raise LookupError(f"Payment {payment_id} not found")
        return (await self.calculate_risk_level(session, payment.customer_id)).model_dump()

    async def on_invoice_due(
        self,
        session: Session,
        invoice_id: int,
    ) -> list[dict[str, Any]]:
        """Return a customer risk assessment when Collector requests risk context."""
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            raise LookupError(f"Invoice {invoice_id} not found")
        result = await self.calculate_risk_level(session, invoice.customer_id)
        return [result.model_dump()]

    async def on_customer_reply(
        self,
        session: Session,
        message_id: int,
    ) -> list[dict[str, Any]]:
        """Reassess risk after a customer reply."""
        message = session.get(InboundMessage, message_id)
        if message is None:
            raise LookupError(f"Inbound message {message_id} not found")
        result = await self.calculate_risk_level(session, message.customer_id)
        return [result.model_dump()]

    async def on_daily_check(
        self,
        session: Session,
        date: datetime,
    ) -> list[dict[str, Any]]:
        """Reassess each customer using the supplied simulated date."""
        customers = session.exec(select(Customer).order_by(Customer.id)).all()
        results = []
        for customer in customers:
            result = await self.calculate_risk_level(session, customer.id, as_of=date)
            if result.level != "NORMAL" or result.model_dump().get("alert_id"):
                results.append(result.model_dump())
        return results


def _missed_promise_signal(
    promises: list[Promise],
    payments: list[Payment],
    invoices: dict[int | None, Invoice],
    today: date,
) -> RiskSignal | None:
    cutoff = today - timedelta(days=_PROMISE_LOOKBACK_DAYS)
    missed = []
    payments_by_invoice: dict[int, list[Payment]] = {}
    for payment in payments:
        payments_by_invoice.setdefault(payment.invoice_id, []).append(payment)
    for promise in promises:
        if not cutoff <= promise.promised_date < today:
            continue
        invoice = invoices.get(promise.invoice_id)
        if promise.kept is False or (
            promise.kept is None
            and invoice is not None
            and _unpaid_by(payments_by_invoice.get(promise.invoice_id, []), invoice, promise.promised_date)
        ):
            missed.append(promise)
    if not missed:
        return None
    evidence_ids = list(dict.fromkeys(
        value
        for promise in missed
        for value in (f"promise:{promise.id}", f"invoice:{promise.invoice_id}")
        if value
    ))
    return RiskSignal(
        code="MISSED_PAYMENT_PROMISE",
        description=f"{len(missed)} payment promise(s) were missed in the last 30 days",
        evidence_ids=evidence_ids,
    )


def _unpaid_by(
    invoice_payments: list[Payment],
    invoice: Invoice,
    promised_date: date,
) -> bool:
    paid_paise = sum(
        payment.amount_paise
        for payment in invoice_payments
        if payment.paid_on <= promised_date
    )
    return paid_paise < invoice.amount_paise


def _repeated_delay_signal(
    invoices: list[Invoice],
    payments: list[Payment],
) -> RiskSignal | None:
    invoice_by_id = {invoice.id: invoice for invoice in invoices}
    delayed: dict[int, list[Payment]] = {}
    for payment in payments:
        invoice = invoice_by_id.get(payment.invoice_id)
        if invoice and payment.paid_on > invoice.due_date:
            delayed.setdefault(invoice.id, []).append(payment)
    if len(delayed) < 2:
        return None
    evidence_ids = list(dict.fromkeys(
        value
        for invoice_id, late_payments in delayed.items()
        for value in [f"invoice:{invoice_id}"] + [
            f"payment:{payment.id}" for payment in late_payments
        ]
    ))
    return RiskSignal(
        code="REPEATED_PAYMENT_DELAY",
        description=f"Payments on {len(delayed)} invoices were recorded after their due dates",
        evidence_ids=evidence_ids,
    )


def _distress_signal(messages: list[InboundMessage]) -> RiskSignal | None:
    relevant = [
        message
        for message in messages
        if any(term in message.body.casefold() for term in _DISTRESS_TERMS)
    ]
    if not relevant:
        return None
    return RiskSignal(
        code="CUSTOMER_DISTRESS",
        description="A customer message contains a financial-distress signal",
        evidence_ids=[f"inbound_message:{message.id}" for message in relevant],
    )


def _memory_signals(
    findings: dict[str, Any],
    observations: list[dict[str, Any]],
    today: date,
    allowed_evidence_ids: set[str],
) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    changes = [
        item
        for item in findings.get("conflicts", []) or []
        if set(_evidence_ids(item)) & allowed_evidence_ids
    ]
    if changes:
        evidence_ids = list(dict.fromkeys(
            evidence_id
            for item in changes
            for evidence_id in _evidence_ids(item)
            if evidence_id in allowed_evidence_ids
        ))
        signals.append(RiskSignal(
            code="LEARNED_BEHAVIOUR_CHANGED",
            description="Customer behaviour or requirements have conflicting learned evidence",
            evidence_ids=evidence_ids,
        ))

    weakening = []
    stale = []
    for observation in observations:
        evidence_id = observation.get("id")
        if not evidence_id:
            continue
        content = str(observation.get("content") or "").casefold()
        metadata = observation.get("metadata") or {}
        trend = str(metadata.get("trend") or metadata.get("status") or "").casefold()
        if any(term in content for term in _WEAKENING_TERMS) or trend in {"weakening", "declining"}:
            weakening.append(str(evidence_id))
        observed_at = _date_value(observation.get("timestamp"))
        if observed_at and (today - observed_at).days > _STALE_DAYS:
            stale.append(str(evidence_id))
    if weakening:
        signals.append(RiskSignal(
            code="PAYMENT_PATTERN_WEAKENING",
            description="Learned observations indicate a weakening payment pattern",
            evidence_ids=list(dict.fromkeys(weakening)),
        ))
    if stale:
        signals.append(RiskSignal(
            code="STALE_PAYMENT_BELIEF",
            description="Learned payment observations are older than 180 days",
            evidence_ids=list(dict.fromkeys(stale)),
        ))
    return signals


def _date_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
    return None


def _evidence_ids(item: Any) -> list[str]:
    values = item.get("evidence_ids", []) if isinstance(item, dict) else getattr(
        item, "evidence_ids", []
    )
    return [str(value) for value in values or [] if value]


def _belongs_to_customer(event: dict[str, Any], customer_id: int) -> bool:
    expected = str(customer_id)
    if str(event.get("customer_id", "")) == expected:
        return True
    metadata = event.get("metadata") or {}
    if str(metadata.get("customer_id", "")) == expected:
        return True
    return f"customer:{expected}" in (event.get("tags") or [])


def _has_equivalent_open_alert(
    session: Session,
    customer_id: int,
    level: str,
    signals: list[str],
) -> bool:
    alerts = session.exec(
        select(RiskAlert).where(
            RiskAlert.customer_id == customer_id,
            RiskAlert.to_level == CustomerRiskLevel(level),
            RiskAlert.status == RiskAlertStatus.OPEN,
        )
    ).all()
    expected = set(signals)
    return any(set(alert.signals or []) == expected for alert in alerts)


class RiskAssessmentWithAlert(RiskAssessment):
    """Risk result including the persisted alert identifier for integrations."""

    alert_id: int
