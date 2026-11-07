"""
Munshi - Risk alerts API
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from munshi.db.session import get_session
from munshi.db.models import RiskAlert, RiskAlertStatus
from munshi.api.schemas import RiskAlertOut, AckAlertIn
from munshi.config import clock

router = APIRouter(tags=["risk"])


@router.get("/risk/alerts", response_model=list[RiskAlertOut])
def list_risk_alerts(
    status: str = "OPEN",
    session: Session = Depends(get_session),
) -> list[RiskAlertOut]:
    """List risk alerts, default filter: OPEN."""
    try:
        status_enum = RiskAlertStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Must be one of: {[s.value for s in RiskAlertStatus]}",
        )
    rows = session.exec(select(RiskAlert).where(RiskAlert.status == status_enum)).all()
    return [RiskAlertOut.model_validate(r) for r in rows]


@router.post("/risk/alerts/{alert_id}/ack", response_model=RiskAlertOut)
def ack_risk_alert(
    alert_id: int,
    body: AckAlertIn,
    session: Session = Depends(get_session),
) -> RiskAlertOut:
    """Acknowledge or dismiss a risk alert."""
    alert = session.get(RiskAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Risk alert {alert_id} not found")

    if alert.status != RiskAlertStatus.OPEN:
        raise HTTPException(
            status_code=409,
            detail=f"Alert {alert_id} is already {alert.status}",
        )

    try:
        new_status = RiskAlertStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{body.status}'. Must be ACKNOWLEDGED or DISMISSED",
        )

    alert.status = new_status
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return RiskAlertOut.model_validate(alert)
