"""
Munshi - Plain language question / Explain API
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from munshi.api.schemas import ExplainIn, ExplainOut
from munshi.db.models import Customer
from munshi.db.session import get_session

router = APIRouter(tags=["explain"])


@router.post("/explain", response_model=ExplainOut)
def explain_query(
    body: ExplainIn,
    session: Session = Depends(get_session),
) -> ExplainOut:
    """
    Plain-language question about customer risk or memory.
    Wired to knowledge/memory layer when available; provides structured fallback.
    """
    customer = session.get(Customer, body.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {body.customer_id} not found")

    return ExplainOut(
        answer="No evidence is available yet.",
        evidence=[],
    )
