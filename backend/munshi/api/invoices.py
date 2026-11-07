"""
Munshi - Invoices API
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from munshi.api.schemas import (
    DocumentUploadOut,
    Finding,
    InvoiceCheckOut,
    InvoiceConfirmIn,
    InvoiceConfirmOut,
    InvoiceCreate,
    InvoiceCreateOut,
    InvoiceSendIn,
    InvoiceSendOut,
    TallyImportOut,
    TallyRowSkipped,
)
from munshi.checks.readiness import check_readiness
from munshi.config import clock
from munshi.db.models import (
    Business,
    Customer,
    DocType,
    Invoice,
    InvoiceDocument,
    InvoiceReadiness,
    InvoiceStatus,
    MemoryEvent,
    ReadinessCheck,
)
from munshi.db.session import get_session

router = APIRouter(tags=["invoices"])

# Documents are stored on the local filesystem in this folder
_UPLOAD_DIR = Path(os.getenv("DOCUMENT_UPLOAD_DIR", "./uploads"))


@router.post("/invoices", response_model=InvoiceCreateOut, status_code=201)
async def create_invoice(
    body: InvoiceCreate,
    session: Session = Depends(get_session),
) -> InvoiceCreateOut:
    """
    Create a new invoice and immediately run a readiness check.
    Returns 201 with id, status, readiness, and findings.
    """
    customer = session.get(Customer, body.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {body.customer_id} not found")

    # Validate invoice number uniqueness per customer
    existing = session.exec(
        select(Invoice)
        .where(Invoice.customer_id == body.customer_id)
        .where(Invoice.number == body.number)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Invoice number '{body.number}' already exists for this customer",
        )

    invoice = Invoice(
        customer_id=body.customer_id,
        number=body.number,
        issue_date=body.issue_date,
        due_date=body.due_date,
        amount_paise=body.amount_paise,
        po_number=body.po_number,
        status=InvoiceStatus.DRAFT,
        created_at=clock.now(),
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    invoice.customer = customer

    # Run readiness check
    result = await check_readiness(invoice, session=session)
    readiness_enum = InvoiceReadiness(result.status)
    invoice.readiness = readiness_enum
    session.add(invoice)

    findings_list = [
        f if isinstance(f, dict) else f.to_dict()
        for f in result.findings
    ]
    rc = ReadinessCheck(
        invoice_id=invoice.id,
        run_at=clock.now(),
        result=readiness_enum,
        findings=findings_list,
    )
    session.add(rc)
    session.commit()
    session.refresh(invoice)

    findings_out = [
        Finding(
            code=f.get("code", "CHECK"),
            source=f.get("source", "RULE"),
            message=f.get("message", ""),
            evidence_ids=f.get("evidence_ids", []),
        )
        for f in findings_list
    ]

    return InvoiceCreateOut(
        id=invoice.id,
        status=invoice.status,
        readiness=invoice.readiness,
        findings=findings_out,
    )


@router.post("/invoices/{invoice_id}/check", response_model=InvoiceCheckOut)
async def check_invoice_readiness_endpoint(
    invoice_id: int,
    session: Session = Depends(get_session),
) -> InvoiceCheckOut:
    """Re-run readiness check and update invoice readiness field."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

    customer = session.get(Customer, invoice.customer_id)
    invoice.customer = customer

    result = await check_readiness(invoice, session=session)
    readiness_enum = InvoiceReadiness(result.status)
    invoice.readiness = readiness_enum
    session.add(invoice)

    findings_list = [
        f if isinstance(f, dict) else f.to_dict()
        for f in result.findings
    ]
    rc = ReadinessCheck(
        invoice_id=invoice.id,
        run_at=clock.now(),
        result=readiness_enum,
        findings=findings_list,
    )
    session.add(rc)
    session.commit()
    session.refresh(invoice)

    findings_out = [
        Finding(
            code=f.get("code", "CHECK"),
            source=f.get("source", "RULE"),
            message=f.get("message", ""),
            evidence_ids=f.get("evidence_ids", []),
        )
        for f in findings_list
    ]

    return InvoiceCheckOut(
        readiness=invoice.readiness,
        findings=findings_out,
        memory_pending=getattr(result, "memory_pending", False),
    )


@router.post("/invoices/{invoice_id}/confirm", response_model=InvoiceConfirmOut)
async def confirm_invoice_requirement(
    invoice_id: int,
    body: InvoiceConfirmIn,
    session: Session = Depends(get_session),
) -> InvoiceConfirmOut:
    """
    Resolve Conflict/Uncertain finding; updates customer rules if confirmed.
    """
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

    customer = session.get(Customer, invoice.customer_id)
    customer_updated = False

    if body.decision == "CONFIRM_NEW":
        if body.finding_code == "PO_REQUIRED":
            customer.po_required = True
            customer_updated = True
        elif body.finding_code in [e.value for e in DocType]:
            if body.finding_code not in customer.required_docs:
                customer.required_docs = list(customer.required_docs) + [body.finding_code]
                customer_updated = True
        if customer_updated:
            session.add(customer)
            session.commit()

    # Re-evaluate readiness
    invoice.customer = customer
    result = await check_readiness(invoice, session=session)
    readiness_enum = InvoiceReadiness(result.status)
    invoice.readiness = readiness_enum
    session.add(invoice)
    session.commit()

    return InvoiceConfirmOut(
        readiness=invoice.readiness,
        customer_updated=customer_updated,
    )


@router.post("/invoices/{invoice_id}/send", response_model=InvoiceSendOut)
def send_invoice(
    invoice_id: int,
    body: InvoiceSendIn = InvoiceSendIn(),
    session: Session = Depends(get_session),
) -> InvoiceSendOut:
    """
    Mark invoice sent. Allowed only if readiness is READY or overridden.
    Returns 409 if readiness is BLOCKER without override.
    """
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

    if invoice.status == InvoiceStatus.SENT:
        raise HTTPException(status_code=409, detail=f"Invoice {invoice_id} is already SENT")

    if invoice.readiness == InvoiceReadiness.BLOCKER and not body.override:
        raise HTTPException(
            status_code=409,
            detail="Invoice has BLOCKER readiness. Provide override=true to force send.",
        )

    invoice.status = InvoiceStatus.SENT
    session.add(invoice)

    evt_id = f"evt_{uuid.uuid4().hex[:12]}"
    memory_evt = MemoryEvent(
        id=evt_id,
        kind="invoice_sent",
        customer_id=invoice.customer_id,
        invoice_id=invoice.id,
        occurred_on=clock.now().date(),
        content=f"Invoice {invoice.number} sent to customer.",
    )
    session.add(memory_evt)
    session.commit()

    return InvoiceSendOut(
        status=invoice.status,
        memory_event_id=evt_id,
    )


@router.post("/invoices/{invoice_id}/documents", response_model=DocumentUploadOut, status_code=201)
async def upload_document(
    invoice_id: int,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> DocumentUploadOut:
    """
    Upload a document (PDF, challan, etc.) and attach it to an invoice.
    """
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

    try:
        dtype = DocType(doc_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid doc_type '{doc_type}'. Must be one of: {[e.value for e in DocType]}",
        )

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "doc"
    dest = _UPLOAD_DIR / f"inv_{invoice_id}_{doc_type}_{filename}"
    with open(dest, "wb") as fout:
        shutil.copyfileobj(file.file, fout)

    doc = InvoiceDocument(
        invoice_id=invoice_id,
        doc_type=dtype,
        file_path=str(dest),
        uploaded_at=clock.now(),
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    return DocumentUploadOut(
        id=doc.id,
        doc_type=doc.doc_type,
    )


@router.post("/import/tally-csv", response_model=TallyImportOut)
async def import_tally_csv(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> TallyImportOut:
    """
    Import customers and open invoices from Tally CSV.
    Expected columns: customer_name, gstin, state_code, invoice_number, issue_date, due_date, amount_rupees, po_number
    """
    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    # Get primary business
    business = session.exec(select(Business)).first()
    if not business:
        business = Business(
            name="Imported Business",
            gstin="27IMPORT1234F1Z1",
            state_code="27",
            msme_registered=True,
            bank_id="munshi-imported",
        )
        session.add(business)
        session.flush()

    customers_created = 0
    invoices_created = 0
    rows_skipped: List[TallyRowSkipped] = []

    for row_idx, row in enumerate(reader, start=2):
        c_name = row.get("customer_name", "").strip()
        gstin = row.get("gstin", "").strip()
        state_code = row.get("state_code", "").strip()
        inv_number = row.get("invoice_number", "").strip()
        issue_date_str = row.get("issue_date", "").strip()
        due_date_str = row.get("due_date", "").strip()
        amount_str = row.get("amount_rupees", "").strip()
        po_number = row.get("po_number", "").strip() or None

        if not c_name or not gstin or not inv_number:
            rows_skipped.append(TallyRowSkipped(row=row_idx, reason="Missing required fields"))
            continue

        try:
            issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            amount_paise_decimal = Decimal(amount_str) * 100
            if not amount_paise_decimal.is_finite():
                raise InvalidOperation
            if amount_paise_decimal != amount_paise_decimal.to_integral_value():
                rows_skipped.append(
                    TallyRowSkipped(row=row_idx, reason="Amount must have at most two decimal places")
                )
                continue
            amount_paise = int(amount_paise_decimal)
            if amount_paise <= 0:
                rows_skipped.append(TallyRowSkipped(row=row_idx, reason="Amount must be positive"))
                continue
        except (InvalidOperation, ValueError) as ex:
            rows_skipped.append(TallyRowSkipped(row=row_idx, reason=f"Date/amount parse error: {ex}"))
            continue

        # Find or create customer
        customer = session.exec(
            select(Customer).where(Customer.gstin == gstin)
        ).first()
        if not customer:
            customer = Customer(
                business_id=business.id,
                name=c_name,
                gstin=gstin,
                state_code=state_code or gstin[:2],
            )
            session.add(customer)
            session.flush()
            customers_created += 1

        # Check existing invoice
        existing_inv = session.exec(
            select(Invoice)
            .where(Invoice.customer_id == customer.id)
            .where(Invoice.number == inv_number)
        ).first()
        if existing_inv:
            rows_skipped.append(TallyRowSkipped(row=row_idx, reason=f"Invoice {inv_number} already exists"))
            continue

        inv = Invoice(
            customer_id=customer.id,
            number=inv_number,
            issue_date=issue_date,
            due_date=due_date,
            amount_paise=amount_paise,
            po_number=po_number,
            status=InvoiceStatus.DRAFT,
            created_at=clock.now(),
        )
        session.add(inv)
        session.flush()
        invoices_created += 1

    session.commit()
    return TallyImportOut(
        customers_created=customers_created,
        invoices_created=invoices_created,
        rows_skipped=rows_skipped,
    )
