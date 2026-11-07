"""
Munshi - Dashboard API
"""

from datetime import datetime, time

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from munshi.api.schemas import DashboardAtRiskCustomer, DashboardOut
from munshi.config import clock
from munshi.db.models import (
    Action,
    ActionStatus,
    Customer,
    CustomerRiskLevel,
    Invoice,
    InvoiceReadiness,
    InvoiceStatus,
    ReadinessCheck,
)
from munshi.db.session import get_session
from munshi.services.ledger import outstanding_by_invoice

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(session: Session = Depends(get_session)) -> DashboardOut:
    """
    Summary numbers for the owner's home screen.

    - total_receivable_paise: sum of all unpaid invoices
    - overdue_paise:          sum of unpaid invoices past due_date
    - at_risk_customers:      WATCH or HIGH risk level
    - pending_drafts:         actions with status=DRAFTED
    - blockers_caught_this_month: readiness checks that returned BLOCKER this calendar month
    """
    today = clock.now().date()
    month_start = datetime.combine(
        today.replace(day=1),
        time.min,
        tzinfo=clock.now().tzinfo,
    )

    # Total receivable: SENT, HELD, PARTLY_PAID
    open_statuses = [InvoiceStatus.SENT, InvoiceStatus.HELD, InvoiceStatus.PARTLY_PAID]
    open_invoices = session.exec(
        select(Invoice).where(Invoice.status.in_(open_statuses))
    ).all()
    balances = outstanding_by_invoice(session, open_invoices)
    total_receivable_paise = sum(balances.values())
    overdue_paise = sum(
        balances[invoice.id]
        for invoice in open_invoices
        if invoice.id is not None and invoice.due_date < today
    )

    # At-risk customers
    at_risk_rows = session.exec(
        select(Customer).where(
            Customer.risk_level.in_([CustomerRiskLevel.WATCH, CustomerRiskLevel.HIGH])
        )
    ).all()
    at_risk_customers = [
        DashboardAtRiskCustomer(id=c.id, name=c.name, risk_level=c.risk_level)
        for c in at_risk_rows
    ]

    # Pending drafts
    pending_drafts: int = session.exec(
        select(func.count(Action.id)).where(Action.status == ActionStatus.DRAFTED)
    ).one() or 0

    # Blockers caught this month
    blockers: int = session.exec(
        select(func.count(ReadinessCheck.id))
        .where(ReadinessCheck.result == InvoiceReadiness.BLOCKER)
        .where(ReadinessCheck.run_at >= month_start)
    ).one() or 0

    return DashboardOut(
        total_receivable_paise=total_receivable_paise,
        overdue_paise=overdue_paise,
        at_risk_customers=at_risk_customers,
        pending_drafts=pending_drafts,
        blockers_caught_this_month=blockers,
    )
