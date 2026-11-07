from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from munshi.checks.gstin import calculate_gstin_checksum
from munshi.checks.rules import (
    R1_GSTIN_FORMAT,
    R2_GSTIN_CHECKSUM,
    R3_GSTIN_MATCH,
    R4_STATE_CODE,
    R5_PO_REQUIRED,
    R6_PO_AMOUNT,
    R7_DUPLICATE,
    R8_DUE_DATE,
    R9_REQUIRED_DOCS,
    RULES,
    run_all_rules,
)
from munshi.db.models import Business, Customer, DocType, Invoice, InvoiceDocument


def _gstin(state_code: str) -> str:
    body = f"{state_code}AAACA1234A1Z"
    return body + calculate_gstin_checksum(body)


def _invoice() -> Invoice:
    business = Business(
        id=1,
        name="Supplier",
        gstin=_gstin("27"),
        state_code="27",
        bank_id="munshi-test",
    )
    customer = Customer(
        id=1,
        business_id=1,
        name="Buyer",
        gstin=_gstin("27"),
        state_code="27",
        po_required=False,
        business=business,
        required_docs=[],
        invoices=[],
    )
    invoice = Invoice(
        id=1,
        customer_id=1,
        number="INV-1",
        issue_date=date(2026, 1, 1),
        due_date=date(2027, 1, 1),
        amount_paise=10_000,
        customer=customer,
        documents=[],
    )
    customer.invoices = [invoice]
    return invoice


def test_rules_registry_and_complete_execution():
    assert len(RULES) == 9
    results = run_all_rules(_invoice())
    assert len(results) == 9
    assert all(result.code in RULES for result in results)


def test_r1_checks_buyer_and_supplier_gstin_format():
    invoice = _invoice()
    assert R1_GSTIN_FORMAT(invoice).is_pass
    invoice.customer.gstin = "INVALID"
    assert not R1_GSTIN_FORMAT(invoice).is_pass


def test_r2_checks_buyer_and_supplier_gstin_checksum():
    invoice = _invoice()
    assert R2_GSTIN_CHECKSUM(invoice).is_pass
    invoice.customer.gstin = invoice.customer.gstin[:-1] + "0"
    assert not R2_GSTIN_CHECKSUM(invoice).is_pass


def test_r3_compares_invoice_gstin_to_buyer_record_when_available():
    invoice = _invoice()
    assert R3_GSTIN_MATCH(invoice, invoice.customer.gstin).is_pass
    assert not R3_GSTIN_MATCH(invoice, _gstin("29")).is_pass
    assert "not present" in R3_GSTIN_MATCH(invoice).message


def test_r4_checks_state_consistency_and_reports_tax_regime():
    invoice = _invoice()
    assert "CGST+SGST" in R4_STATE_CODE(invoice).message
    invoice.customer.business.gstin = _gstin("29")
    invoice.customer.business.state_code = "29"
    assert "IGST" in R4_STATE_CODE(invoice).message
    invoice.customer.state_code = "29"
    assert not R4_STATE_CODE(invoice).is_pass


def test_r5_purchase_order_presence():
    invoice = _invoice()
    invoice.customer.po_required = True
    assert not R5_PO_REQUIRED(invoice).is_pass
    invoice.po_number = "PO-123"
    assert R5_PO_REQUIRED(invoice).is_pass
    invoice.customer.po_required = False
    invoice.po_number = None
    assert R5_PO_REQUIRED(invoice).is_pass


def test_r6_purchase_order_amount_tolerance_is_exactly_one_percent():
    invoice = _invoice()
    assert R6_PO_AMOUNT(invoice, 10_000).is_pass
    invoice.amount_paise = 10_100
    assert R6_PO_AMOUNT(invoice, 10_000).is_pass
    invoice.amount_paise = 10_101
    assert not R6_PO_AMOUNT(invoice, 10_000).is_pass
    invoice.amount_paise = 9_900
    assert R6_PO_AMOUNT(invoice, 10_000).is_pass
    invoice.amount_paise = 9_899
    assert not R6_PO_AMOUNT(invoice, 10_000).is_pass
    assert "not available" in R6_PO_AMOUNT(invoice).message


def test_r7_duplicate_invoice_number():
    invoice = _invoice()
    duplicate = Invoice(
        id=2,
        customer_id=1,
        number=invoice.number,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        amount_paise=invoice.amount_paise,
    )
    invoice.customer.invoices.append(duplicate)
    assert not R7_DUPLICATE(invoice).is_pass
    duplicate.number = "INV-2"
    assert R7_DUPLICATE(invoice).is_pass


def test_r7_checks_existing_database_records():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(
            name="Supplier",
            gstin=_gstin("27"),
            state_code="27",
            bank_id="munshi-test",
        )
        customer = Customer(
            business=business,
            name="Buyer",
            gstin=_gstin("27"),
            state_code="27",
        )
        existing = Invoice(
            customer=customer,
            number="INV-DUP",
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 2, 1),
            amount_paise=10_000,
        )
        session.add(existing)
        session.commit()
        candidate = Invoice(
            customer_id=customer.id,
            number="INV-DUP",
            issue_date=date(2026, 1, 2),
            due_date=date(2026, 2, 2),
            amount_paise=10_000,
        )
        assert not R7_DUPLICATE(candidate, session).is_pass


def test_r8_due_date_warning_uses_shared_clock(monkeypatch):
    invoice = _invoice()
    monkeypatch.setattr(
        "munshi.checks.rules.clock.now",
        lambda: datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    )
    invoice.due_date = date(2026, 1, 8)
    result = R8_DUE_DATE(invoice)
    assert result.is_pass and result.warning
    assert "7 days" in result.message
    invoice.due_date = date(2026, 1, 9)
    assert not R8_DUE_DATE(invoice).warning


def test_r9_required_documents():
    invoice = _invoice()
    invoice.customer.required_docs = ["SIGNED_CHALLAN", "GRN"]
    assert not R9_REQUIRED_DOCS(invoice).is_pass
    invoice.documents = [
        InvoiceDocument(
            invoice_id=invoice.id,
            doc_type=DocType.SIGNED_CHALLAN,
            file_path="signed.pdf",
        ),
        InvoiceDocument(invoice_id=invoice.id, doc_type=DocType.GRN, file_path="grn.pdf"),
    ]
    assert R9_REQUIRED_DOCS(invoice).is_pass
