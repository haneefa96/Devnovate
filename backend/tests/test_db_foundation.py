"""
Munshi - Database Foundation Tests

Tests for SQLModel / SQLite architecture:
- Database initialization
- All 12 entity models
- Amounts stored as integer paise
- Primary and foreign keys
- Model relationships
- Constraints (Unique, Check, Foreign Keys)
- Database transactions & rollbacks
- Seed data verification
"""

from datetime import date, datetime, timedelta, timezone
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, create_engine, select

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
    MemoryEvent,
    Payment,
    Promise,
    ReadinessCheck,
    RiskAlert,
    RiskAlertStatus,
    SimArm,
    SimRun,
    _now,
)
from munshi.db.seed import seed_demo_data
from munshi.db.session import init_db, reset_db, session_scope


@pytest.fixture(name="test_engine")
def fixture_test_engine():
    """In-memory SQLite engine with foreign keys enabled."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    test_eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_eng, "connect")
    def _fk_pragma(dbapi_con, con_record):
        cursor = dbapi_con.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    init_db(test_eng)
    yield test_eng
    reset_db(test_eng)


@pytest.fixture(name="db_session")
def fixture_db_session(test_engine):
    """Database session connected to the test engine."""
    with Session(test_engine) as session:
        yield session


# ─── 1. Database Initialization ───────────────────────────────────────────────

def test_database_initialization(test_engine):
    """Verify that all 12 tables are created during initialization."""
    from sqlalchemy import inspect
    inspector = inspect(test_engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "business",
        "customer",
        "invoice",
        "invoice_document",
        "readiness_check",
        "action",
        "inbound_message",
        "payment",
        "promise",
        "risk_alert",
        "memory_event",
        "sim_run",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"


def test_simulated_clock_is_timezone_aware_ist():
    assert clock.now().utcoffset() == timedelta(hours=5, minutes=30)


# ─── 2. All 12 Entities and Relationships ──────────────────────────────────────

def test_all_12_entities_crud_and_relationships(db_session):
    """Test CRUD operations and navigation of relationships across all 12 entities."""
    # 1. Business
    business = Business(
        name="Apex Industrial Tools",
        gstin="27AAACA1234A1Z1",
        state_code="27",
        msme_registered=True,
        bank_id="munshi-apex",
    )
    db_session.add(business)
    db_session.commit()
    db_session.refresh(business)
    assert business.id is not None

    # 2. Customer
    customer = Customer(
        business_id=business.id,
        name="Bharat Motors",
        gstin="27BBBCB2345B1Z2",
        state_code="27",
        credit_days=45,
        po_required=True,
        required_docs=["SIGNED_CHALLAN", "GRN"],
        contact_name="Ramesh",
        contact_role="Finance Head",
        contact_phone="+919811122233",
        risk_level=CustomerRiskLevel.NORMAL,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    assert customer.id is not None
    assert customer.business.name == "Apex Industrial Tools"
    assert len(business.customers) == 1

    # 3. Invoice (Integer paise storage: ₹50,000 = 5,000,000 paise)
    today = date(2026, 3, 1)
    invoice = Invoice(
        customer_id=customer.id,
        number="INV-2001",
        issue_date=today,
        due_date=today + timedelta(days=45),
        amount_paise=5_000_000,
        po_number="PO-999",
        status=InvoiceStatus.DRAFT,
        readiness=InvoiceReadiness.BLOCKER,
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    assert invoice.id is not None
    assert invoice.amount_paise == 5_000_000
    assert invoice.customer.name == "Bharat Motors"
    assert len(customer.invoices) == 1

    # 4. InvoiceDocument
    doc = InvoiceDocument(
        invoice_id=invoice.id,
        doc_type=DocType.INVOICE_PDF,
        file_path="/uploads/inv_2001.pdf",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    assert doc.id is not None
    assert doc.invoice.number == "INV-2001"
    assert len(invoice.documents) == 1

    # 5. ReadinessCheck
    rc = ReadinessCheck(
        invoice_id=invoice.id,
        run_at=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
        result=InvoiceReadiness.BLOCKER,
        findings=[{"code": "SIGNED_CHALLAN", "message": "Missing delivery challan"}],
    )
    db_session.add(rc)
    db_session.commit()
    db_session.refresh(rc)
    assert rc.id is not None
    assert rc.invoice.number == "INV-2001"
    assert len(invoice.readiness_checks) == 1

    # 6. Action
    action = Action(
        invoice_id=invoice.id,
        customer_id=customer.id,
        kind=ActionKind.REMINDER,
        channel="WHATSAPP",
        recipient="Ramesh",
        body="Kindly confirm payment schedule for INV-2001.",
        attachments=[],
        planned_for=datetime(2026, 3, 2, 10, 30, 0, tzinfo=timezone.utc),
        status=ActionStatus.DRAFTED,
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(action)
    assert action.id is not None
    assert action.invoice.number == "INV-2001"
    assert action.customer.name == "Bharat Motors"

    # 7. InboundMessage
    inbound = InboundMessage(
        customer_id=customer.id,
        invoice_id=invoice.id,
        channel="WHATSAPP",
        sender_name="Ramesh",
        body="Challan received. Processing in Monday run.",
    )
    db_session.add(inbound)
    db_session.commit()
    db_session.refresh(inbound)
    assert inbound.id is not None
    assert inbound.customer.name == "Bharat Motors"

    # 8. Payment (Part payment: ₹20,000 = 2,000,000 paise)
    payment = Payment(
        invoice_id=invoice.id,
        customer_id=customer.id,
        amount_paise=2_000_000,
        paid_on=today + timedelta(days=20),
        reference="UTR12345678",
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)
    assert payment.id is not None
    assert payment.amount_paise == 2_000_000
    assert payment.invoice.number == "INV-2001"

    # 9. Promise
    promise = Promise(
        invoice_id=invoice.id,
        customer_id=customer.id,
        promised_by="Ramesh",
        promised_date=today + timedelta(days=30),
        kept=None,
    )
    db_session.add(promise)
    db_session.commit()
    db_session.refresh(promise)
    assert promise.id is not None
    assert promise.customer.name == "Bharat Motors"

    # 10. RiskAlert
    alert = RiskAlert(
        customer_id=customer.id,
        from_level=CustomerRiskLevel.NORMAL,
        to_level=CustomerRiskLevel.WATCH,
        signals=["Promise date pending"],
        suggestion="Monitor Friday clearing",
        evidence=[{"fact": "Promised on 1st"}],
        status=RiskAlertStatus.OPEN,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    assert alert.id is not None
    assert alert.customer.name == "Bharat Motors"

    # 11. MemoryEvent
    mem_evt = MemoryEvent(
        id="evt_test_01",
        kind="invoice_sent",
        customer_id=customer.id,
        invoice_id=invoice.id,
        bank_name="munshi-apex",
        content="Invoice INV-2001 dispatched to Ramesh",
        occurred_on=today,
    )
    db_session.add(mem_evt)
    db_session.commit()
    db_session.refresh(mem_evt)
    assert mem_evt.id == "evt_test_01"
    assert mem_evt.customer.name == "Bharat Motors"

    # 12. SimRun
    sim = SimRun(
        arm=SimArm.C,
        seed=42,
        config={"months": 6},
        metrics={"avg_days_late": 4.2},
    )
    db_session.add(sim)
    db_session.commit()
    db_session.refresh(sim)
    assert sim.id is not None
    assert sim.arm == SimArm.C


# ─── 3. Constraints Verification ──────────────────────────────────────────────

def test_unique_constraint_invoice_number_per_customer(db_session):
    """Verify UNIQUE (customer_id, number) on invoice table."""
    business = Business(name="B1", gstin="27AAACA0000A1Z0", state_code="27", bank_id="b1")
    db_session.add(business)
    db_session.commit()

    c1 = Customer(business_id=business.id, name="C1", gstin="27AAACA1111A1Z1", state_code="27")
    c2 = Customer(business_id=business.id, name="C2", gstin="27AAACA2222A1Z2", state_code="27")
    db_session.add_all([c1, c2])
    db_session.commit()

    inv1 = Invoice(
        customer_id=c1.id,
        number="INV-101",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        amount_paise=100_000,
    )
    db_session.add(inv1)
    db_session.commit()

    # Same number for DIFFERENT customer is allowed
    inv_diff_customer = Invoice(
        customer_id=c2.id,
        number="INV-101",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        amount_paise=200_000,
    )
    db_session.add(inv_diff_customer)
    db_session.commit()

    # Same number for SAME customer must fail integrity constraint
    inv_duplicate = Invoice(
        customer_id=c1.id,
        number="INV-101",
        issue_date=date(2026, 1, 5),
        due_date=date(2026, 2, 5),
        amount_paise=300_000,
    )
    db_session.add(inv_duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_positive_amount_check_constraint(db_session):
    """Verify CHECK (amount_paise > 0) on Invoice and Payment."""
    business = Business(name="B2", gstin="27AAACA9999A1Z9", state_code="27", bank_id="b2")
    db_session.add(business)
    db_session.commit()

    customer = Customer(business_id=business.id, name="C_Test", gstin="27AAACB9999B1Z8", state_code="27")
    db_session.add(customer)
    db_session.commit()

    # Non-positive invoice amount must fail check constraint
    inv_invalid = Invoice(
        customer_id=customer.id,
        number="INV-ZERO",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        amount_paise=0,
    )
    db_session.add(inv_invalid)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Valid invoice
    inv_valid = Invoice(
        customer_id=customer.id,
        number="INV-VALID",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        amount_paise=500_000,
    )
    db_session.add(inv_valid)
    db_session.commit()

    # Negative payment amount must fail check constraint
    pmt_invalid = Payment(
        invoice_id=inv_valid.id,
        customer_id=customer.id,
        amount_paise=-1000,
        paid_on=date(2026, 1, 15),
    )
    db_session.add(pmt_invalid)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_customer_credit_days_and_invoice_date_constraints(db_session):
    business = Business(name="Constraints", gstin="27CSTRS1234A1Z1", state_code="27", bank_id="constraints")
    db_session.add(business)
    db_session.commit()
    customer = Customer(
        business_id=business.id,
        name="Constraint Customer",
        gstin="27CSTRS1234B1Z2",
        state_code="27",
        credit_days=-1,
    )
    db_session.add(customer)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    customer.credit_days = 30
    db_session.add(customer)
    db_session.commit()
    invoice = Invoice(
        customer_id=customer.id,
        number="INV-BAD-DATES",
        issue_date=date(2026, 2, 1),
        due_date=date(2026, 1, 1),
        amount_paise=100_000,
    )
    db_session.add(invoice)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_enum_values_are_enforced_by_sqlite(db_session):
    business = Business(name="Enums", gstin="27ENUMS1234A1Z1", state_code="27", bank_id="enums")
    db_session.add(business)
    db_session.commit()
    customer = Customer(
        business_id=business.id,
        name="Enum Customer",
        gstin="27ENUMS1234B1Z2",
        state_code="27",
    )
    db_session.add(customer)
    db_session.commit()
    invoice = Invoice(
        customer_id=customer.id,
        number="INV-ENUM",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        amount_paise=100_000,
    )
    db_session.add(invoice)
    db_session.commit()

    db_session.add_all([
        InvoiceDocument(invoice_id=invoice.id, doc_type=DocType.INVOICE_PDF, file_path="invoice.pdf"),
        ReadinessCheck(invoice_id=invoice.id, result=InvoiceReadiness.READY),
        Action(
            invoice_id=invoice.id,
            customer_id=customer.id,
            kind=ActionKind.REMINDER,
            channel="WHATSAPP",
            recipient="Contact",
            body="Reminder",
        ),
        RiskAlert(
            customer_id=customer.id,
            from_level=CustomerRiskLevel.NORMAL,
            to_level=CustomerRiskLevel.WATCH,
        ),
        SimRun(arm=SimArm.A, seed=1),
    ])
    db_session.commit()

    invalid_enum_updates = (
        "UPDATE customer SET risk_level = 'INVALID'",
        "UPDATE invoice SET status = 'INVALID'",
        "UPDATE invoice SET readiness = 'INVALID'",
        "UPDATE invoice_document SET doc_type = 'INVALID'",
        "UPDATE readiness_check SET result = 'INVALID'",
        "UPDATE action SET kind = 'INVALID'",
        "UPDATE action SET status = 'INVALID'",
        "UPDATE risk_alert SET from_level = 'INVALID'",
        "UPDATE risk_alert SET to_level = 'INVALID'",
        "UPDATE risk_alert SET status = 'INVALID'",
        "UPDATE sim_run SET arm = 'INVALID'",
    )
    for statement in invalid_enum_updates:
        with pytest.raises(IntegrityError):
            db_session.execute(text(statement))
            db_session.commit()
        db_session.rollback()


def test_foreign_key_enforcement(db_session):
    """Verify foreign key constraint rejects non-existent parent records."""
    invoice_bad_fk = Invoice(
        customer_id=99999,  # Non-existent customer
        number="INV-NO-CUST",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        amount_paise=100_000,
    )
    db_session.add(invoice_bad_fk)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ─── 4. Database Transactions & Rollback ──────────────────────────────────────

def test_database_transaction_rollback(test_engine):
    """Verify atomic transactions and rollback using session_scope."""
    with Session(test_engine) as session:
        b = Business(name="Tx Business", gstin="27TXBUS1234A1Z1", state_code="27", bank_id="tx")
        session.add(b)
        session.commit()
        b_id = b.id

    # Transaction that fails halfway through should cleanly roll back
    try:
        with session_scope(test_engine) as session:
            c = Customer(business_id=b_id, name="Tx Customer", gstin="27TXCUS1234B1Z2", state_code="27")
            session.add(c)
            session.flush()
            # Deliberate failure: invalid invoice
            bad_inv = Invoice(
                customer_id=c.id,
                number="FAIL-INV",
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                amount_paise=-500,  # Fails CHECK constraint
            )
            session.add(bad_inv)
    except IntegrityError:
        pass

    # Verify that the customer was not committed due to rollback
    with Session(test_engine) as session:
        c_found = session.exec(select(Customer).where(Customer.name == "Tx Customer")).first()
        assert c_found is None, "Customer should have rolled back"


# ─── 5. Seed Data Verification ────────────────────────────────────────────────

def test_demo_seed_data(test_engine):
    """Verify demo seed data populates expected entities with exact relationships."""
    with Session(test_engine) as session:
        seed_demo_data(session)

        # Verify Business
        business = session.exec(select(Business)).first()
        assert business is not None
        assert business.name == "Demo Manufacturer"
        assert business.gstin == "27ABCDE1234F1Z5"

        # Verify Customers
        customers = session.exec(select(Customer)).all()
        assert len(customers) == 3
        c_names = {c.name for c in customers}
        assert c_names == {"Reddy Traders", "Sharma Suppliers", "Patel Enterprises"}

        # Verify Invoices
        invoices = session.exec(select(Invoice)).all()
        assert len(invoices) == 3
        inv_numbers = {i.number for i in invoices}
        assert inv_numbers == {"INV-1000", "INV-1001", "INV-1002"}

        # Verify specific demo data relations
        reddy = session.exec(select(Customer).where(Customer.name == "Reddy Traders")).one()
        assert len(reddy.invoices) == 1
        assert reddy.invoices[0].amount_paise == 4_820_000  # ₹48,200

        # Verify Action
        actions = session.exec(select(Action)).all()
        assert len(actions) >= 1
        assert actions[0].status == ActionStatus.DRAFTED

        # Verify Risk Alert
        alerts = session.exec(select(RiskAlert)).all()
        assert len(alerts) >= 1
        assert alerts[0].status == RiskAlertStatus.OPEN

        # Test idempotency (calling seed again does not duplicate)
        seed_demo_data(session)
        assert len(session.exec(select(Customer)).all()) == 3
