import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine

from munshi.checks.gstin import calculate_gstin_checksum
from munshi.checks.readiness import check_readiness, combine_readiness
from munshi.checks.rules import RuleResult, run_all_rules
from munshi.db.models import (
    Business,
    Customer,
    DocType,
    Invoice,
    InvoiceDocument,
    MemoryEvent,
)
from munshi.memory import queries


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
        required_docs=[],
        contact_name="Buyer Contact",
        business=business,
        invoices=[],
    )
    invoice = Invoice(
        id=1,
        customer_id=1,
        number="INV-1",
        issue_date=date(2026, 1, 1),
        due_date=date(2027, 1, 1),
        amount_paise=10_000,
        po_number="PO-1",
        customer=customer,
        documents=[],
    )
    customer.invoices = [invoice]
    return invoice


def _clear_rule_results() -> list[RuleResult]:
    return [RuleResult("FIXED", True, "Valid")]


def test_ready_when_fixed_rules_and_memory_findings_are_clear():
    result = combine_readiness(_clear_rule_results(), {})
    assert result.status == "READY"
    assert result.findings == []
    assert not result.memory_pending


def test_code_blocker_precedes_memory_blocker_and_conflict():
    result = combine_readiness(
        [RuleResult("R1_GSTIN_FORMAT", False, "Bad GSTIN")],
        {
            "requirements": [{
                "code": "SIGNED_CHALLAN",
                "required": True,
                "evidence_ids": ["doc-1"],
            }],
            "conflicts": [{"code": "CONFLICT-1", "description": "Changed"}],
        },
        invoice=_invoice(),
    )
    assert result.status == "BLOCKER"
    assert result.findings[0]["code"] == "R1_GSTIN_FORMAT"


def test_evidenced_missing_learned_requirement_is_blocker():
    invoice = _invoice()
    result = combine_readiness(
        _clear_rule_results(),
        {
            "requirements": [{
                "code": "SIGNED_CHALLAN",
                "description": "Signed delivery challan required",
                "required": True,
                "evidence_count": 2,
                "evidence_ids": ["doc-1", "doc-2"],
            }]
        },
        invoice=invoice,
    )
    assert result.status == "BLOCKER"
    assert result.findings[0]["source"] == "MEMORY"


def test_memory_blocker_precedes_conflict():
    invoice = _invoice()
    result = combine_readiness(
        _clear_rule_results(),
        {
            "requirements": [{
                "code": "GRN_COPY",
                "required": True,
                "evidence_ids": ["doc-1"],
            }],
            "conflicts": [{"code": "CONFLICT-1", "description": "Conflicting policy"}],
        },
        invoice=invoice,
    )
    assert result.status == "BLOCKER"


def test_conflict_precedes_thin_evidence_uncertainty():
    result = combine_readiness(
        _clear_rule_results(),
        {
            "requirements": [{
                "code": "CONTACT_PERSON",
                "required": True,
                "evidence_count": 1,
                "evidence_ids": ["doc-1"],
            }],
            "conflicts": [{"code": "CONTACT_CHANGE", "description": "Two contacts reported"}],
        },
        invoice=_invoice(),
    )
    assert result.status == "CONFLICT"
    assert result.findings[0]["code"] == "CONTACT_CHANGE"


def test_single_evidence_is_uncertain():
    result = combine_readiness(
        _clear_rule_results(),
        {
            "requirements": [{
                "code": "CONTACT_PERSON",
                "required": True,
                "evidence_count": 1,
                "evidence_ids": ["doc-1"],
            }]
        },
        invoice=_invoice(),
    )
    assert result.status == "UNCERTAIN"


def test_unknown_evidence_age_is_uncertain():
    result = combine_readiness(
        _clear_rule_results(),
        {
            "requirements": [{
                "code": "CONTACT_PERSON",
                "required": True,
                "evidence_count": 2,
                "evidence_ids": ["doc-1", "doc-2"],
            }]
        },
        invoice=_invoice(),
    )
    assert result.status == "UNCERTAIN"
    assert "age cannot be verified" in result.findings[0]["message"]


def test_insufficient_evidence_is_uncertain():
    result = combine_readiness(
        _clear_rule_results(),
        {
            "requirements": [{
                "code": "PO_REF",
                "required": True,
                "evidence_count": 0,
                "evidence_ids": [],
            }]
        },
        invoice=_invoice(),
    )
    assert result.status == "UNCERTAIN"
    assert result.findings[0]["message"] == "Learned requirement has insufficient evidence"


def test_old_evidence_from_sqlite_is_uncertain(monkeypatch):
    monkeypatch.setattr(
        "munshi.checks.readiness.clock.now",
        lambda: datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    )
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(MemoryEvent(
            id="evt-old",
            hindsight_document_id="doc-old",
            occurred_on=date(2025, 6, 30),
            content_hash="old",
        ))
        session.commit()
        result = combine_readiness(
            _clear_rule_results(),
            {
                "requirements": [{
                    "code": "CONTACT_PERSON",
                    "required": True,
                    "evidence_count": 2,
                    "evidence_ids": ["doc-old", "doc-new"],
                }]
            },
            session=session,
            invoice=_invoice(),
        )
    assert result.status == "UNCERTAIN"
    assert "older than 180 days" in result.findings[0]["message"]


def test_consolidation_pending_is_uncertain_and_exposed():
    result = combine_readiness(
        _clear_rule_results(),
        {"updating": True},
    )
    assert result.status == "UNCERTAIN"
    assert result.memory_pending


def test_supported_learned_requirement_codes():
    invoice = _invoice()
    invoice.documents = [
        InvoiceDocument(invoice_id=1, doc_type=DocType.SIGNED_CHALLAN, file_path="signed.pdf"),
        InvoiceDocument(invoice_id=1, doc_type=DocType.GRN, file_path="grn.pdf"),
        InvoiceDocument(invoice_id=1, doc_type=DocType.EWAY_BILL, file_path="eway.pdf"),
        InvoiceDocument(invoice_id=1, doc_type=DocType.OTHER, file_path="other.pdf"),
    ]
    codes = [
        "PO_REF",
        "SIGNED_CHALLAN",
        "GRN_COPY",
        "EWAY_BILL",
        "CONTACT_PERSON",
        "OTHER",
    ]
    requirements = [
        {
            "code": code,
            "required": True,
            "evidence_count": 2,
            "evidence_ids": [f"{code}-1", f"{code}-2"],
            "evidence_dates": ["2025-12-30", "2025-12-31"],
        }
        for code in codes
    ]
    result = combine_readiness(
        _clear_rule_results(),
        {"requirements": requirements},
        invoice=invoice,
    )
    assert result.status == "READY"

    requirements.append({
        "code": "EINVOICE_IRN",
        "required": True,
        "evidence_count": 2,
        "evidence_ids": ["irn-1", "irn-2"],
    })
    result = combine_readiness(
        _clear_rule_results(),
        {"requirements": requirements},
        invoice=invoice,
    )
    assert result.status == "BLOCKER"
    assert result.findings[-1]["code"] == "EINVOICE_IRN"


def test_hindsight_unavailable_returns_pending_uncertain(monkeypatch):
    invoice = _invoice()
    monkeypatch.setattr(queries, "memory_store", SimpleNamespace(is_available=False))

    async def unexpected_call(**kwargs):
        raise AssertionError("Unavailable memory service must not be queried")

    monkeypatch.setattr(queries, "get_memory_for_readiness", unexpected_call)
    result = asyncio.run(check_readiness(invoice))
    assert result.status == "UNCERTAIN"
    assert result.memory_pending


def test_readiness_uses_existing_memory_service(monkeypatch):
    invoice = _invoice()
    calls = []
    monkeypatch.setattr(queries, "memory_store", SimpleNamespace(is_available=True))

    async def get_findings(bank_name: str, customer_id: str):
        calls.append((bank_name, customer_id))
        return {
            "requirements": [{
                "code": "SIGNED_CHALLAN",
                "required": True,
                "evidence_count": 2,
                "evidence_ids": ["doc-1", "doc-2"],
            }],
            "conflicts": [],
            "playbook": "Established requirement",
        }

    monkeypatch.setattr(queries, "get_memory_for_readiness", get_findings)
    result = asyncio.run(check_readiness(invoice))
    assert calls == [("munshi-test", "1")]
    assert result.status == "BLOCKER"
    assert result.findings[-1]["code"] == "SIGNED_CHALLAN"


def test_check_readiness_runs_all_rules_and_keeps_due_warning():
    invoice = _invoice()
    invoice.due_date = date(2026, 1, 1)
    result = asyncio.run(check_readiness(invoice, memory_findings={}))
    expected = run_all_rules(invoice)
    assert len(expected) == 9
    assert result.status == "READY"
    assert any(item["code"] == "R8_DUE_DATE" for item in result.findings)
