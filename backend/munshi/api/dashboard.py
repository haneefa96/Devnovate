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
    receivable = session.exec(
        select(func.coalesce(func.sum(Invoice.amount_paise), 0))
        .where(Invoice.status.in_(open_statuses))
    ).one()
    total_receivable_paise: int = receivable or 0

    # Overdue: open invoices past their due date
    overdue = session.exec(
        select(func.coalesce(func.sum(Invoice.amount_paise), 0))
        .where(Invoice.status.in_(open_statuses))
        .where(Invoice.due_date < today)
    ).one()
    overdue_paise: int = overdue or 0

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
