"""
Munshi - Database seed for demo / testing.

Creates one Business, three Customers and three Invoices with supporting
actions, risk alerts, readiness checks, and payments.
Safe to call on an empty database; idempotent when data already exists.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from munshi.config import clock
from munshi.db.models import (
    Action,
    ActionKind,
    ActionStatus,
    Business,
    Customer,
    CustomerRiskLevel,
    DocType,
    InboundMessage,
    Invoice,
    InvoiceDocument,
    InvoiceReadiness,
    InvoiceStatus,
    Payment,
    Promise,
    ReadinessCheck,
    RiskAlert,
    RiskAlertStatus,
)
from munshi.db.session import engine

logger = logging.getLogger(__name__)


def seed_demo_data(session: Session | None = None) -> None:
    """
    Seed demo data. Accepts an optional external session for testing.
    If *session* is None, opens a new session against the default engine.
    """
    own_session = session is None
    if own_session:
        session = Session(engine)

    try:
        # Idempotency guard — skip if business already exists
        existing = session.exec(select(Business).where(Business.gstin == "27ABCDE1234F1Z5")).first()
        if existing:
            logger.info("Demo data already present — skipping seed")
            return

        now = clock.now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        today = now.date()

        # ── 1. Business ───────────────────────────────────────────────────────
        business = Business(
            name="Demo Manufacturer",
            gstin="27ABCDE1234F1Z5",
            state_code="27",
            msme_registered=True,
            bank_id="munshi-demo",
        )
        session.add(business)
        session.flush()

        # ── 2. Customers ──────────────────────────────────────────────────────
        c1 = Customer(
            business_id=business.id,
            name="Reddy Traders",
            gstin="36FGHIJ1234K5Z6",
            state_code="36",
            credit_days=30,
            po_required=True,
            required_docs=["SIGNED_CHALLAN"],
            contact_name="Priya",
            contact_role="Accounts",
            contact_phone="+919876543210",
            risk_level=CustomerRiskLevel.NORMAL,
        )
        c2 = Customer(
            business_id=business.id,
            name="Sharma Suppliers",
            gstin="27LMNOP1234Q5Z6",
            state_code="27",
            credit_days=45,
            po_required=False,
            required_docs=[],
            contact_name="Amit",
            contact_role="Purchase",
            contact_phone="+919876543211",
            risk_level=CustomerRiskLevel.WATCH,
        )
        c3 = Customer(
            business_id=business.id,
            name="Patel Enterprises",
            gstin="29RSTUV1234W5Z7",
            state_code="29",
            credit_days=60,
            po_required=True,
            required_docs=["SIGNED_CHALLAN", "GRN"],
            contact_name="Suresh",
            contact_role="Owner",
            contact_phone="+919876543212",
            risk_level=CustomerRiskLevel.HIGH,
        )
        session.add_all([c1, c2, c3])
        session.flush()

        # ── 3. Invoices ───────────────────────────────────────────────────────
        # Invoice 1: Reddy Traders — overdue, blocked readiness
        inv1 = Invoice(
            customer_id=c1.id,
            number="INV-1000",
            issue_date=today - timedelta(days=32),
            due_date=today - timedelta(days=2),
            amount_paise=4_820_000,  # ₹48,200
            po_number="PO-4000",
            status=InvoiceStatus.DRAFT,
            readiness=InvoiceReadiness.BLOCKER,
            created_at=now - timedelta(days=32),
        )
        # Invoice 2: Sharma Suppliers — sent, ready
        inv2 = Invoice(
            customer_id=c2.id,
            number="INV-1001",
            issue_date=today - timedelta(days=15),
            due_date=today + timedelta(days=30),
            amount_paise=7_500_000,  # ₹75,000
            po_number=None,
            status=InvoiceStatus.SENT,
            readiness=InvoiceReadiness.READY,
            created_at=now - timedelta(days=15),
        )
        # Invoice 3: Patel Enterprises — overdue, partly paid
        inv3 = Invoice(
            customer_id=c3.id,
            number="INV-1002",
            issue_date=today - timedelta(days=45),
            due_date=today - timedelta(days=15),
            amount_paise=12_000_000,  # ₹120,000
            po_number="PO-4002",
            status=InvoiceStatus.PARTLY_PAID,
            readiness=InvoiceReadiness.READY,
            created_at=now - timedelta(days=45),
        )
        session.add_all([inv1, inv2, inv3])
        session.flush()

        # ── 4. Invoice Document ───────────────────────────────────────────────
        doc1 = InvoiceDocument(
            invoice_id=inv1.id,
            doc_type=DocType.PO_COPY,
            file_path="uploads/demo_po_4000.pdf",
            uploaded_at=now - timedelta(days=32),
        )
        session.add(doc1)

        # ── 5. Readiness Check ────────────────────────────────────────────────
        rc1 = ReadinessCheck(
            invoice_id=inv1.id,
            run_at=now - timedelta(days=32),
            result=InvoiceReadiness.BLOCKER,
            findings=[
                {
                    "code": "SIGNED_CHALLAN",
                    "source": "MEMORY",
                    "message": "Reddy Traders requires a signed delivery challan before payment.",
                    "evidence_ids": ["ev_demo_01"],
                }
            ],
        )
        session.add(rc1)

        # ── 6. Action (Draft approval) ────────────────────────────────────────
        action1 = Action(
            invoice_id=inv1.id,
            customer_id=c1.id,
            kind=ActionKind.REMINDER,
            channel="WHATSAPP",
            recipient="Priya",
            body="Hi Priya, reminder for INV-1000 of ₹48,200 due on the 5th.",
            attachments=[],
            planned_for=now,
            status=ActionStatus.DRAFTED,
        )
        session.add(action1)

        # ── 7. Payment ────────────────────────────────────────────────────────
        pmt1 = Payment(
            invoice_id=inv3.id,
            customer_id=c3.id,
            amount_paise=4_000_000,  # ₹40,000 part payment
            paid_on=today - timedelta(days=5),
            reference="UTR987654321012",
        )
        session.add(pmt1)

        # ── 8. Promise ────────────────────────────────────────────────────────
        promise1 = Promise(
            invoice_id=inv3.id,
            customer_id=c3.id,
            promised_by="Suresh",
            promised_date=today - timedelta(days=3),
            kept=False,
        )
        session.add(promise1)

        # ── 9. Risk Alert ─────────────────────────────────────────────────────
        alert1 = RiskAlert(
            customer_id=c3.id,
            from_level=CustomerRiskLevel.WATCH,
            to_level=CustomerRiskLevel.HIGH,
            signals=[
                "Payment overdue by >15 days",
                "Broken promise to clear balance by Suresh",
            ],
            suggestion="Hold next dispatch or request 50% advance.",
            evidence=[
                {
                    "id": "ev_demo_02",
                    "date": str(today - timedelta(days=3)),
                    "text": "Suresh promised payment by 3rd, no credit received.",
                    "event_id": "evt_demo_pmt",
                }
            ],
            status=RiskAlertStatus.OPEN,
            created_at=now - timedelta(days=2),
        )
        session.add(alert1)

        # ── 10. Inbound Message ───────────────────────────────────────────────
        msg1 = InboundMessage(
            customer_id=c1.id,
            invoice_id=inv1.id,
            channel="WHATSAPP",
            sender_name="Priya",
            body="Please share the signed delivery challan so we can process INV-1000 in this week's payment run.",
            received_at=now - timedelta(days=1),
        )
        session.add(msg1)

        session.commit()
        logger.info(
            "Demo data seeded: 1 business, 3 customers, 3 invoices, 1 action, 1 risk alert",
        )

    except Exception:
        session.rollback()
        raise
    finally:
        if own_session:
            session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_demo_data()

