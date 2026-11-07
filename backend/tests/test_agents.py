from datetime import date, datetime, timedelta
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine, select

from munshi.agents.collector import CollectorAgent
from munshi.agents.policy import ReminderWording, clamp_contact_time, is_contact_time_allowed
from munshi.agents.risk import RiskAgent
from munshi.config import clock
from munshi.db.models import (
    Action,
    ActionKind,
    ActionStatus,
    Business,
    Customer,
    CustomerRiskLevel,
    InboundMessage,
    Invoice,
    InvoiceStatus,
    Payment,
    Promise,
    RiskAlert,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def ledger(db_session):
    business = Business(
        name="Supplier Ltd",
        gstin="27ABCDE1234F1Z5",
        state_code="27",
        bank_id="munshi-supplier",
    )
    db_session.add(business)
    db_session.flush()
    customer = Customer(
        business_id=business.id,
        name="Buyer Ltd",
        gstin="36FGHIJ1234K5Z6",
        state_code="36",
        contact_name="Priya",
        contact_phone="+919876543210",
        po_required=False,
    )
    other_customer = Customer(
        business_id=business.id,
        name="Other Buyer",
        gstin="29RSTUV1234W5Z7",
        state_code="29",
        contact_name="Rahul",
        contact_phone="+919812345678",
        po_required=False,
    )
    db_session.add_all([customer, other_customer])
    db_session.flush()
    invoice = Invoice(
        customer_id=customer.id,
        number="INV-100",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 5),
        amount_paise=100_000,
        status=InvoiceStatus.SENT,
    )
    other_invoice = Invoice(
        customer_id=other_customer.id,
        number="INV-OTHER",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 5),
        amount_paise=100_000,
        status=InvoiceStatus.SENT,
    )
    db_session.add_all([invoice, other_invoice])
    db_session.commit()
    return SimpleNamespace(
        business=business,
        customer=customer,
        other_customer=other_customer,
        invoice=invoice,
        other_invoice=other_invoice,
    )


@pytest.fixture
def no_memory(monkeypatch):
    from munshi.agents import collector, risk

    unavailable = SimpleNamespace(is_available=False)
    monkeypatch.setattr(collector.memory_queries, "memory_store", unavailable)
    monkeypatch.setattr(risk.memory_queries, "memory_store", unavailable)


def _good_wording(*args, **kwargs):
    prompt = json.loads(args[0][1]["content"])
    return {
        "parsed": ReminderWording(
            greeting="Hello Priya",
            request="Could you please share an update on the expected payment timing?",
            reason="Ledger invoice is due",
            evidence_ids=[
                value for value in prompt["evidence_ids"] if value.startswith("invoice:")
            ][:1],
        ),
        "fallback": False,
    }


def test_collector_persists_structured_draft_and_never_sends(
    db_session,
    ledger,
    no_memory,
    monkeypatch,
):
    from munshi.agents import collector

    monkeypatch.setattr(
        collector.groq_client,
        "call_agent_model",
        AsyncMock(side_effect=_good_wording),
    )
    post_draft = AsyncMock(return_value=False)
    monkeypatch.setattr(collector.band_bridge, "post_draft", post_draft)
    invoice = db_session.get(Invoice, ledger.invoice.id)
    invoice.due_date = date(2026, 1, 8)
    db_session.add(invoice)
    db_session.commit()

    agent = CollectorAgent()
    draft = asyncio_run(
        agent.create_draft(
            db_session,
            ledger.invoice.id,
            ledger.customer.id,
            datetime(2026, 1, 1, 10, 0, tzinfo=clock.now().tzinfo),
        )
    )
    saved = db_session.exec(select(Action).where(Action.id == draft["id"])).one()
    assert saved.status == ActionStatus.DRAFTED
    assert saved.kind == ActionKind.REMINDER
    assert draft["owner_approval_required"] is True
    assert draft["evidence_ids"] == [f"invoice:{ledger.invoice.id}"]
    assert "INV-100" in draft["body"]
    assert "2026-01-08" in draft["body"]
    assert draft["memory_supported"] is False
    post_draft.assert_awaited_once()


def asyncio_run(awaitable):
    import asyncio

    return asyncio.run(awaitable)


def test_collector_clamps_contact_hours_and_promise_timing(
    db_session,
    ledger,
    no_memory,
    monkeypatch,
):
    from munshi.agents import collector

    monkeypatch.setattr(
        collector.groq_client,
        "call_agent_model",
        AsyncMock(side_effect=_good_wording),
    )
    promise = Promise(
        invoice_id=ledger.invoice.id,
        customer_id=ledger.customer.id,
        promised_by="Priya",
        promised_date=date(2026, 1, 3),
    )
    db_session.add(promise)
    db_session.commit()
    agent = CollectorAgent()

    draft = asyncio_run(agent.create_draft(
        db_session,
        ledger.invoice.id,
        ledger.customer.id,
        datetime(2026, 1, 1, 6, 30, tzinfo=clock.now().tzinfo),
    ))
    assert draft["send_on"] == datetime(2026, 1, 4, 9, 0, tzinfo=clock.now().tzinfo)
    assert is_contact_time_allowed(draft["send_on"], clock.now())
    assert "payment promise" in draft["reason"]

    after_hours = clamp_contact_time(
        datetime(2026, 1, 1, 19, 0, tzinfo=clock.now().tzinfo),
        clock.now(),
    )
    assert after_hours == datetime(2026, 1, 2, 9, 0, tzinfo=clock.now().tzinfo)


def test_collector_enforces_reminder_cap_and_customer_isolation(
    db_session,
    ledger,
    no_memory,
    monkeypatch,
):
    from munshi.agents import collector

    monkeypatch.setattr(
        collector.groq_client,
        "call_agent_model",
        AsyncMock(side_effect=_good_wording),
    )
    agent = CollectorAgent()
    timing = clock.now().replace(hour=10)
    for _ in range(2):
        asyncio_run(agent.create_draft(
            db_session,
            ledger.invoice.id,
            ledger.customer.id,
            timing,
        ))
    with pytest.raises(ValueError, match="two reminders"):
        asyncio_run(agent.create_draft(
            db_session,
            ledger.invoice.id,
            ledger.customer.id,
            timing,
        ))
    with pytest.raises(ValueError, match="does not belong"):
        asyncio_run(agent.create_draft(
            db_session,
            ledger.invoice.id,
            ledger.other_customer.id,
            timing,
        ))


def test_collector_rejects_unsafe_llm_wording_with_safe_fallback(
    db_session,
    ledger,
    no_memory,
    monkeypatch,
):
    from munshi.agents import collector

    async def unsafe(**kwargs):
        return {
            "parsed": ReminderWording(
                greeting="Hello Priya",
                request="Pay immediately or we will take legal action",
                reason="No evidence",
                evidence_ids=["invoice:1"],
            )
        }

    monkeypatch.setattr(collector.groq_client, "call_agent_model", AsyncMock(side_effect=unsafe))
    draft = asyncio_run(CollectorAgent().create_draft(
        db_session,
        ledger.invoice.id,
        ledger.customer.id,
        clock.now().replace(hour=10),
    ))
    assert "legal action" not in draft["body"].lower()
    assert draft["memory_supported"] is False
    assert draft["owner_approval_required"] is True


def test_collector_retries_structured_output_twice_then_safe_fallback(
    db_session,
    ledger,
    no_memory,
    monkeypatch,
):
    from munshi.agents import collector

    request = AsyncMock(return_value={"parsed": None, "fallback": True})
    monkeypatch.setattr(collector.groq_client, "call_agent_model", request)
    draft = asyncio_run(CollectorAgent().create_draft(
        db_session,
        ledger.invoice.id,
        ledger.customer.id,
        clock.now().replace(hour=10),
    ))
    assert request.await_count == 2
    assert draft["memory_supported"] is False
    assert draft["evidence_ids"] == [f"invoice:{ledger.invoice.id}"]


def test_collector_filters_cross_customer_memory(
    db_session,
    ledger,
    monkeypatch,
):
    from munshi.agents import collector

    recall = AsyncMock(return_value=[
        {
            "id": "mem-own",
            "customer_id": str(ledger.customer.id),
            "content": "Pays on the 5th",
        },
        {
            "id": "mem-other",
            "customer_id": str(ledger.other_customer.id),
            "content": "Other customer's private payment history",
        },
    ])
    monkeypatch.setattr(
        collector.memory_queries,
        "memory_store",
        SimpleNamespace(is_available=True, recall=recall),
    )
    monkeypatch.setattr(
        collector.memory_queries,
        "get_memory_for_collector",
        AsyncMock(return_value={
            "playbook": "Other customer's private payment cycle",
            "requirements": [
                {
                    "code": "OTHER_CUSTOMER",
                    "description": "Never pass this unscoped requirement",
                    "evidence_ids": ["mem-other"],
                },
                {
                    "code": "PAYMENT_DAY",
                    "description": "Customer usually pays on the 5th",
                    "evidence_ids": ["mem-own"],
                },
            ],
        }),
    )
    monkeypatch.setattr(
        collector.groq_client,
        "call_agent_model",
        AsyncMock(return_value={
            "parsed": ReminderWording(
                greeting="Hello Priya",
                request="Could you please share an update?",
                reason="Pays on the 5th",
                evidence_ids=["mem-own"],
            )
        }),
    )
    draft = asyncio_run(CollectorAgent().create_draft(
        db_session,
        ledger.invoice.id,
        ledger.customer.id,
        clock.now().replace(hour=10),
    ))
    prompt_content = collector.groq_client.call_agent_model.await_args.args[0][1]["content"]
    assert "mem-own" in prompt_content
    assert "mem-other" not in prompt_content
    assert "Other customer's private" not in prompt_content
    assert "Never pass this unscoped requirement" not in prompt_content
    assert "Other customer's private payment cycle" not in prompt_content
    assert "Customer usually pays on the 5th" in prompt_content
    assert ledger.customer.contact_phone not in prompt_content
    assert f"mem-own" in draft["evidence_ids"]


def _persist_risk_data(db_session, ledger, add_distress: bool):
    today = clock.now().date()
    old_invoice_1 = Invoice(
        customer_id=ledger.customer.id,
        number="INV-LATE-1",
        issue_date=today - timedelta(days=60),
        due_date=today - timedelta(days=40),
        amount_paise=50_000,
        status=InvoiceStatus.PAID,
    )
    old_invoice_2 = Invoice(
        customer_id=ledger.customer.id,
        number="INV-LATE-2",
        issue_date=today - timedelta(days=50),
        due_date=today - timedelta(days=30),
        amount_paise=60_000,
        status=InvoiceStatus.PAID,
    )
    db_session.add_all([old_invoice_1, old_invoice_2])
    db_session.flush()
    late_payments = [
        Payment(
            customer_id=ledger.customer.id,
            invoice_id=invoice.id,
            amount_paise=invoice.amount_paise,
            paid_on=invoice.due_date + timedelta(days=5),
        )
        for invoice in (old_invoice_1, old_invoice_2)
    ]
    promise_invoice = Invoice(
        customer_id=ledger.customer.id,
        number="INV-PROMISE",
        issue_date=today - timedelta(days=15),
        due_date=today - timedelta(days=5),
        amount_paise=70_000,
        status=InvoiceStatus.SENT,
    )
    db_session.add(promise_invoice)
    db_session.flush()
    promise = Promise(
        customer_id=ledger.customer.id,
        invoice_id=promise_invoice.id,
        promised_by="Priya",
        promised_date=today - timedelta(days=2),
        kept=False,
    )
    db_session.add_all(late_payments + [promise])
    if add_distress:
        db_session.add(InboundMessage(
            customer_id=ledger.customer.id,
            invoice_id=promise_invoice.id,
            channel="WHATSAPP",
            sender_name="Priya",
            body="Cash flow is tight and we cannot pay this week.",
        ))
    db_session.commit()
    return promise_invoice


def test_risk_classification_and_high_requires_two_distinct_signals(
    db_session,
    ledger,
    no_memory,
    monkeypatch,
):
    from munshi.agents import risk

    monkeypatch.setattr(risk.band_bridge, "post_risk_alert", AsyncMock(return_value=False))
    _persist_risk_data(db_session, ledger, add_distress=False)
    agent = RiskAgent()
    assessment = asyncio_run(agent.calculate_risk_level(db_session, ledger.customer.id))
    assert assessment.level == "HIGH"
    assert len({signal.code for signal in assessment.signals}) == 2
    assert "MISSED_PAYMENT_PROMISE" in {signal.code for signal in assessment.signals}
    assert "REPEATED_PAYMENT_DELAY" in {signal.code for signal in assessment.signals}
    assert assessment.evidence_ids
    assert all(signal.evidence_ids for signal in assessment.signals)

    other = asyncio_run(agent.calculate_risk_level(db_session, ledger.other_customer.id))
    assert other.level == "NORMAL"


def test_shared_risk_policy_rejects_high_without_two_signals():
    from munshi.agents.policy import RiskAssessment, RiskSignal

    with pytest.raises(ValidationError, match="Risk level must be WATCH"):
        RiskAssessment(
            customer_id=1,
            level="HIGH",
            signals=[RiskSignal(
                code="ONE",
                description="One warning",
                evidence_ids=["ledger:1"],
            )],
            evidence_ids=["ledger:1"],
        )


def test_risk_single_signal_is_watch_and_alert_is_persisted(
    db_session,
    ledger,
    no_memory,
    monkeypatch,
):
    from munshi.agents import risk

    monkeypatch.setattr(risk.band_bridge, "post_risk_alert", AsyncMock(return_value=False))
    today = clock.now().date()
    invoice = Invoice(
        customer_id=ledger.customer.id,
        number="INV-PROMISE-ONLY",
        issue_date=today - timedelta(days=10),
        due_date=today - timedelta(days=4),
        amount_paise=20_000,
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(Promise(
        customer_id=ledger.customer.id,
        invoice_id=invoice.id,
        promised_by="Priya",
        promised_date=today - timedelta(days=2),
        kept=False,
    ))
    db_session.commit()
    agent = RiskAgent()
    assessment = asyncio_run(agent.calculate_risk_level(db_session, ledger.customer.id))
    assert assessment.level == "WATCH"
    assert len(assessment.signals) == 1
    assert db_session.get(Customer, ledger.customer.id).risk_level == CustomerRiskLevel.WATCH
    assert db_session.exec(
        select(RiskAlert).where(RiskAlert.customer_id == ledger.customer.id)
    ).first() is not None


def test_risk_detects_distress_and_requires_two_signals_for_high(
    db_session,
    ledger,
    no_memory,
    monkeypatch,
):
    from munshi.agents import risk

    monkeypatch.setattr(risk.band_bridge, "post_risk_alert", AsyncMock(return_value=False))
    db_session.add(InboundMessage(
        customer_id=ledger.customer.id,
        channel="EMAIL",
        sender_name="Priya",
        body="Our cash-flow is tight this month.",
    ))
    db_session.commit()
    result = asyncio_run(RiskAgent().calculate_risk_level(db_session, ledger.customer.id))
    assert result.level == "WATCH"
    assert result.signals[0].code == "CUSTOMER_DISTRESS"
    assert result.signals[0].evidence_ids[0].startswith("inbound_message:")


def test_risk_memory_is_customer_isolated_and_behavior_changes_need_evidence(
    db_session,
    ledger,
    monkeypatch,
):
    from munshi.agents import risk

    memory = SimpleNamespace(
        is_available=True,
        recall=AsyncMock(return_value=[
            {
                "id": "obs-own",
                "customer_id": str(ledger.customer.id),
                "content": "Payment pattern weakening",
                "timestamp": clock.now().isoformat(),
            },
            {
                "id": "obs-other",
                "customer_id": str(ledger.other_customer.id),
                "content": "Other customer's payment is weakening",
                "timestamp": clock.now().isoformat(),
            },
        ]),
    )
    monkeypatch.setattr(risk.memory_queries, "memory_store", memory)
    monkeypatch.setattr(
        risk.memory_queries,
        "get_memory_for_risk",
        AsyncMock(return_value={
            "conflicts": [
                SimpleNamespace(code="CHANGE", description="Pattern changed", evidence_ids=["obs-own"]),
                SimpleNamespace(code="OTHER", description="Other change", evidence_ids=["obs-other"]),
            ]
        }),
    )
    monkeypatch.setattr(risk.band_bridge, "post_risk_alert", AsyncMock(return_value=False))
    result = asyncio_run(RiskAgent().calculate_risk_level(db_session, ledger.customer.id))
    codes = {signal.code for signal in result.signals}
    assert codes == {"LEARNED_BEHAVIOUR_CHANGED", "PAYMENT_PATTERN_WEAKENING"}
    assert "obs-other" not in result.evidence_ids
    assert "obs-own" in result.evidence_ids


def test_risk_flags_stale_memory_with_its_source_evidence(
    db_session,
    ledger,
    monkeypatch,
):
    from munshi.agents import risk

    memory = SimpleNamespace(
        is_available=True,
        recall=AsyncMock(return_value=[{
            "id": "stale-observation",
            "customer_id": str(ledger.customer.id),
            "content": "Usually pays on time",
            "timestamp": "2025-01-01T10:00:00+05:30",
        }]),
    )
    monkeypatch.setattr(risk.memory_queries, "memory_store", memory)
    monkeypatch.setattr(
        risk.memory_queries,
        "get_memory_for_risk",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(risk.band_bridge, "post_risk_alert", AsyncMock(return_value=False))
    result = asyncio_run(RiskAgent().calculate_risk_level(db_session, ledger.customer.id))
    assert result.level == "WATCH"
    assert result.signals[0].code == "STALE_PAYMENT_BELIEF"
    assert result.evidence_ids == ["stale-observation"]


def test_band_unavailable_keeps_collector_draft_and_risk_alert_in_sqlite(
    db_session,
    ledger,
    no_memory,
    monkeypatch,
):
    from munshi.agents import collector, risk

    monkeypatch.setattr(
        collector.groq_client,
        "call_agent_model",
        AsyncMock(side_effect=_good_wording),
    )
    monkeypatch.setattr(collector.band_bridge, "post_draft", AsyncMock(return_value=False))
    monkeypatch.setattr(risk.band_bridge, "post_risk_alert", AsyncMock(return_value=False))
    draft = asyncio_run(CollectorAgent().create_draft(
        db_session,
        ledger.invoice.id,
        ledger.customer.id,
        clock.now().replace(hour=10),
    ))
    db_session.add(InboundMessage(
        customer_id=ledger.customer.id,
        channel="EMAIL",
        sender_name="Priya",
        body="We are unable to pay this week.",
    ))
    db_session.commit()
    result = asyncio_run(RiskAgent().calculate_risk_level(db_session, ledger.customer.id))
    assert db_session.get(Action, draft["id"]) is not None
    assert result.level == "WATCH"
    assert db_session.exec(
        select(RiskAlert).where(RiskAlert.customer_id == ledger.customer.id)
    ).first() is not None
