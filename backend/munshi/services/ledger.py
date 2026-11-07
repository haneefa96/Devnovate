"""Ledger-derived invoice balances shared by API summaries."""

from sqlmodel import Session, func, select

from munshi.db.models import Invoice, Payment


def outstanding_by_invoice(
    session: Session,
    invoices: list[Invoice],
) -> dict[int, int]:
    if not invoices:
        return {}
    invoice_ids = [invoice.id for invoice in invoices if invoice.id is not None]
    paid_rows = session.exec(
        select(Payment.invoice_id, func.sum(Payment.amount_paise))
        .where(Payment.invoice_id.in_(invoice_ids))
        .group_by(Payment.invoice_id)
    ).all()
    paid_by_invoice = {
        invoice_id: int(amount or 0)
        for invoice_id, amount in paid_rows
    }
    return {
        invoice.id: max(0, invoice.amount_paise - paid_by_invoice.get(invoice.id, 0))
        for invoice in invoices
        if invoice.id is not None
    }
