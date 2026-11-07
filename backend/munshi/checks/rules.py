"""Fixed, deterministic invoice readiness rules R1-R9."""

from typing import Any

from sqlmodel import Session, select

from munshi.checks.gstin import validate_gstin_checksum, validate_gstin_format
from munshi.checks.gstin import validate_gstin_matches_buyer, validate_state_code
from munshi.config import clock
from munshi.db.models import Invoice


class RuleResult:
    """Result of one fixed invoice readiness rule."""

    def __init__(
        self,
        code: str,
        is_pass: bool,
        message: str,
        evidence_ids: list[str] | None = None,
        warning: bool = False,
    ) -> None:
        self.code = code
        self.is_pass = is_pass
        self.message = message
        self.evidence_ids = evidence_ids or []
        self.warning = warning

    @property
    def is_blocker(self) -> bool:
        return not self.is_pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "source": "RULE",
            "message": self.message,
            "evidence_ids": self.evidence_ids,
        }


def R1_GSTIN_FORMAT(invoice: Invoice) -> RuleResult:
    """R1: Require structurally valid supplier and buyer GSTINs."""
    customer = invoice.customer
    business = customer.business if customer else None
    invalid_labels = []
    if not customer or not validate_gstin_format(customer.gstin):
        invalid_labels.append("buyer")
    if not business or not validate_gstin_format(business.gstin):
        invalid_labels.append("supplier")
    if invalid_labels:
        return RuleResult(
            "R1_GSTIN_FORMAT",
            False,
            f"Invalid or missing {' and '.join(invalid_labels)} GSTIN format",
        )
    return RuleResult("R1_GSTIN_FORMAT", True, "Buyer and supplier GSTIN formats are valid")


def R2_GSTIN_CHECKSUM(invoice: Invoice) -> RuleResult:
    """R2: Validate check characters for supplier and buyer GSTINs."""
    customer = invoice.customer
    business = customer.business if customer else None
    invalid_labels = []
    if not customer or not validate_gstin_checksum(customer.gstin):
        invalid_labels.append("buyer")
    if not business or not validate_gstin_checksum(business.gstin):
        invalid_labels.append("supplier")
    if invalid_labels:
        return RuleResult(
            "R2_GSTIN_CHECKSUM",
            False,
            f"Invalid or missing {' and '.join(invalid_labels)} GSTIN checksum",
        )
    return RuleResult("R2_GSTIN_CHECKSUM", True, "Buyer and supplier GSTIN checksums are valid")


def R3_GSTIN_MATCH(invoice: Invoice, invoice_gstin: str | None = None) -> RuleResult:
    """R3: Match the invoice recipient GSTIN against the buyer record when supplied."""
    if invoice_gstin is None:
        return RuleResult(
            "R3_GSTIN_MATCH",
            True,
            (
                "Invoice GSTIN is not present in the documented invoice data; "
                "buyer match not verifiable"
            ),
        )
    customer = invoice.customer
    if not customer or not validate_gstin_matches_buyer(customer.gstin, invoice_gstin):
        return RuleResult("R3_GSTIN_MATCH", False, "Invoice GSTIN does not match the buyer record")
    return RuleResult("R3_GSTIN_MATCH", True, "Invoice GSTIN matches the buyer record")


def R4_STATE_CODE(invoice: Invoice) -> RuleResult:
    """R4: Validate recorded GSTIN state prefixes and identify the tax regime."""
    customer = invoice.customer
    business = customer.business if customer else None
    if not customer or not business:
        return RuleResult("R4_STATE_CODE", False, "Buyer or supplier state record is unavailable")

    if not validate_state_code(customer.gstin, customer.state_code):
        return RuleResult(
            "R4_STATE_CODE",
            False,
            "Buyer GSTIN state code does not match buyer record",
        )
    if not validate_state_code(business.gstin, business.state_code):
        return RuleResult(
            "R4_STATE_CODE",
            False,
            "Supplier GSTIN state code does not match supplier record",
        )

    tax_type = "IGST" if business.state_code != customer.state_code else "CGST+SGST"
    return RuleResult("R4_STATE_CODE", True, f"State codes are consistent; apply {tax_type}")


def R5_PO_REQUIRED(invoice: Invoice) -> RuleResult:
    """R5: Require a purchase-order reference when the buyer requires one."""
    customer = invoice.customer
    if not customer or not customer.po_required:
        return RuleResult("R5_PO_REQUIRED", True, "PO not required for this customer")
    if not invoice.po_number:
        return RuleResult("R5_PO_REQUIRED", False, "PO required but not present")
    return RuleResult("R5_PO_REQUIRED", True, "PO reference present")


def R6_PO_AMOUNT(invoice: Invoice, po_amount_paise: int | None = None) -> RuleResult:
    """R6: Compare invoice and PO amounts within 1% when the PO amount is available."""
    if po_amount_paise is None:
        return RuleResult(
            "R6_PO_AMOUNT",
            True,
            "PO amount is not available in the documented invoice data; comparison skipped",
        )
    difference = abs(invoice.amount_paise - po_amount_paise)
    if po_amount_paise <= 0 or difference * 100 > po_amount_paise:
        return RuleResult(
            "R6_PO_AMOUNT",
            False,
            "Invoice amount differs from PO amount by more than 1%",
        )
    return RuleResult("R6_PO_AMOUNT", True, "Invoice amount is within 1% of PO amount")


def R7_DUPLICATE(invoice: Invoice, session: Session | None = None) -> RuleResult:
    """R7: Find an earlier invoice with the same customer and invoice number."""
    if session is not None:
        statement = select(Invoice).where(
            Invoice.customer_id == invoice.customer_id,
            Invoice.number == invoice.number,
        )
        if invoice.id is not None:
            statement = statement.where(Invoice.id != invoice.id)
        duplicate = session.exec(statement).first()
    else:
        customer_invoices = invoice.customer.invoices if invoice.customer else []
        duplicate = next(
            (
                other
                for other in customer_invoices
                if other.number == invoice.number and other.id != invoice.id
            ),
            None,
        )
    if duplicate:
        return RuleResult(
            "R7_DUPLICATE",
            False,
            f"Invoice number '{invoice.number}' already exists for this customer",
            [str(duplicate.id)] if duplicate.id is not None else [],
        )
    return RuleResult("R7_DUPLICATE", True, "Invoice number is unique for this customer")


def R8_DUE_DATE(invoice: Invoice) -> RuleResult:
    """R8: Report invoices due within seven days or already overdue."""
    days_until_due = (invoice.due_date - clock.now().date()).days
    if days_until_due <= 7:
        message = (
            f"Invoice is overdue by {abs(days_until_due)} days"
            if days_until_due < 0
            else f"Invoice is due in {days_until_due} days"
        )
        return RuleResult(
            "R8_DUE_DATE",
            True,
            message,
            warning=True,
        )
    return RuleResult("R8_DUE_DATE", True, f"Invoice is due in {days_until_due} days")


def R9_REQUIRED_DOCS(invoice: Invoice) -> RuleResult:
    """R9: Check the buyer's configured required documents against attachments."""
    customer = invoice.customer
    if not customer or not customer.required_docs:
        return RuleResult("R9_REQUIRED_DOCS", True, "No additional documents required")

    attached = {
        document.doc_type.value if hasattr(document.doc_type, "value") else str(document.doc_type)
        for document in invoice.documents
    }
    required = {
        item.value if hasattr(item, "value") else str(item)
        for item in customer.required_docs
    }
    missing = sorted(required - attached)
    if missing:
        return RuleResult(
            "R9_REQUIRED_DOCS",
            False,
            f"Required documents missing: {', '.join(missing)}",
        )
    return RuleResult("R9_REQUIRED_DOCS", True, "All required documents are attached")


RULES = {
    "R1_GSTIN_FORMAT": R1_GSTIN_FORMAT,
    "R2_GSTIN_CHECKSUM": R2_GSTIN_CHECKSUM,
    "R3_GSTIN_MATCH": R3_GSTIN_MATCH,
    "R4_STATE_CODE": R4_STATE_CODE,
    "R5_PO_REQUIRED": R5_PO_REQUIRED,
    "R6_PO_AMOUNT": R6_PO_AMOUNT,
    "R7_DUPLICATE": R7_DUPLICATE,
    "R8_DUE_DATE": R8_DUE_DATE,
    "R9_REQUIRED_DOCS": R9_REQUIRED_DOCS,
}


def run_all_rules(
    invoice: Invoice,
    session: Session | None = None,
    invoice_gstin: str | None = None,
    po_amount_paise: int | None = None,
) -> list[RuleResult]:
    """Run all fixed readiness rules using only explicitly supplied facts."""
    return [
        R1_GSTIN_FORMAT(invoice),
        R2_GSTIN_CHECKSUM(invoice),
        R3_GSTIN_MATCH(invoice, invoice_gstin),
        R4_STATE_CODE(invoice),
        R5_PO_REQUIRED(invoice),
        R6_PO_AMOUNT(invoice, po_amount_paise),
        R7_DUPLICATE(invoice, session),
        R8_DUE_DATE(invoice),
        R9_REQUIRED_DOCS(invoice),
    ]
